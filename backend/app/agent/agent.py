import os
import json
import asyncio
from typing import List, Optional, AsyncGenerator

from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage,
)
from langchain_core.tools import BaseTool

from app.agent.agent_tools import (
    rag_summary_tools, get_weather_tools, what_time_is_now,
    get_user_info_tools, reorder_documents_tools,
    set_current_user_id,
)
from app.core.logger_handler import logger
from app.services import session_manager as sm
from app.utils.factory import create_chat_model
from app.utils.prompt_loader import load_prompt


_SYSTEM_PROMPT = load_prompt('main_prompt')

DEFAULT_TOOLS = [
    rag_summary_tools,
    get_weather_tools,
    what_time_is_now,
    get_user_info_tools,
    reorder_documents_tools,
]


def _build_agent_graph(tools: List[BaseTool], system_prompt: str):
    """构建 LangGraph StateGraph Agent"""

    from typing import Annotated, TypedDict
    from langgraph.graph.message import add_messages

    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]

    llm = create_chat_model(streaming=True)
    llm_with_tools = llm.bind_tools(tools)

    tools_by_name = {tool.name: tool for tool in tools}

    # ── LLM 调用节点 ──
    async def llm_call(state: AgentState):
        logger.info(f"[llm_call] 模型调用，当前消息数: {len(state['messages'])}")
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        response = await llm_with_tools.ainvoke(messages)
        logger.info(f"[llm_call] 模型响应: tool_calls={bool(response.tool_calls)}, content_len={len(response.content or '')}")
        return {"messages": [response]}

    # ── 工具执行节点 ──
    async def tool_node(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        writer = get_stream_writer()

        results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            tool = tools_by_name.get(tool_name)
            if tool is None:
                observation = f"Error: 未知工具 '{tool_name}'"
                logger.error(f"[tool_node] 未知工具: {tool_name}")
            else:
                logger.info(f"[tool_node] 调用工具: {tool_name}, 参数: {json.dumps(tool_args, ensure_ascii=False)[:200]}")
                try:
                    if asyncio.iscoroutinefunction(tool.ainvoke):
                        observation = await tool.ainvoke(tool_args)
                    elif asyncio.iscoroutinefunction(tool.invoke):
                        observation = await tool.invoke(tool_args)
                    else:
                        observation = tool.invoke(tool_args)
                    observation = str(observation)
                except Exception as e:
                    observation = f"Error: {str(e)}"
                    logger.error(f"[tool_node] 工具 {tool_name} 执行失败: {e}")

                # 推送 thinking 事件（兼容旧 SSE 格式）
                writer({
                    "type": "thinking",
                    "stage": "tool_call",
                    "content": f"调用工具: {tool_name}",
                    "details": {
                        "tool": tool_name,
                        "input": str(tool_args)[:500],
                        "output": str(observation)[:500],
                    }
                })

            results.append(ToolMessage(content=str(observation), tool_call_id=tool_id))

        return {"messages": results}

    # ── 条件路由 ──
    def should_continue(state: AgentState) -> str:
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return END

    # ── 构建图 ──
    builder = StateGraph(AgentState)
    builder.add_node("llm", llm_call)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "llm")
    builder.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "llm")

    return builder.compile()


async def get_agent_stream_response(
    query: str,
    session_id: str,
    user_id: str,
    custom_tools: Optional[List[BaseTool]] = None,
    **kwargs
) -> AsyncGenerator[str, None]:
    """LangGraph Agent SSE 流式响应（保持与旧版完全相同的 SSE 格式）"""

    thinking_events = []
    tools = custom_tools or DEFAULT_TOOLS

    try:
        set_current_user_id(user_id)

        # 加载聊天历史
        history = await sm.session_manager.get_history(session_id, user_id)
        logger.info(f"【Agent流式响应】会话历史记录数: {len(history)}")

        chat_messages = []
        if history:
            for user_msg, assistant_msg in history:
                chat_messages.append(HumanMessage(content=user_msg))
                chat_messages.append(AIMessage(content=assistant_msg))

        # 添加当前查询
        chat_messages.append(HumanMessage(content=query))

        # 构建 Agent 图
        graph = _build_agent_graph(tools, _SYSTEM_PROMPT)

        # 发送初始响应（保持与旧版相同的格式）
        yield f"data: {json.dumps({'type': 'response', 'content': '', 'session_id': session_id}, ensure_ascii=False)}\n\n"

        # 流式执行
        full_response = []
        async for chunk in graph.astream(
            {"messages": chat_messages},
            stream_mode=["updates", "custom"],
            version="v2",
        ):
            if chunk["type"] == "custom":
                # thinking 事件
                event_data = chunk["data"]
                thinking_events.append(event_data)
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            elif chunk["type"] == "updates":
                for node_name, state in chunk["data"].items():
                    if node_name == "llm":
                        messages = state.get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            if hasattr(last_msg, 'content') and last_msg.content and not last_msg.tool_calls:
                                content = last_msg.content
                                if content not in full_response:
                                    full_response.append(content)

        response_text = "".join(full_response) if full_response else "抱歉，我无法理解您的请求。"

        # 保存到会话历史
        message_id = await sm.session_manager.add_message(session_id, user_id, query, response_text)
        if thinking_events:
            try:
                await sm.session_manager.save_thinking_events(session_id, message_id, thinking_events)
            except Exception as e:
                logger.error(f"【Agent流式响应】保存思考过程失败: {e}")

        # 逐字推送回答（保持与旧版相同的行为 + 延迟）
        for char in response_text:
            yield f"data: {json.dumps({'type': 'response', 'content': char}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        logger.info(f"【Agent流式响应】处理完成，会话ID: {session_id}")

    except Exception as e:
        logger.error(f"【Agent流式响应】处理请求失败: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': f'错误: {str(e)}', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"


async def get_agent_response(
    query: str,
    history: Optional[List[tuple]] = None,
    user_id: Optional[str] = None,
    custom_tools: Optional[List[BaseTool]] = None,
    **kwargs
) -> dict:
    """
    非流式 Agent 响应（供 chat_service.py 使用）
    :return: {"response": str, "steps": list}
    """
    if user_id:
        set_current_user_id(user_id)

    tools = custom_tools or DEFAULT_TOOLS

    try:
        chat_messages = []
        if history:
            for user_msg, assistant_msg in history:
                chat_messages.append(HumanMessage(content=user_msg))
                chat_messages.append(AIMessage(content=assistant_msg))

        chat_messages.append(HumanMessage(content=query))

        graph = _build_agent_graph(tools, _SYSTEM_PROMPT)
        result = await graph.ainvoke({"messages": chat_messages})

        # 提取最终回复
        messages = result.get("messages", [])
        response_text = ""
        steps = []
        for msg in messages:
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                response_text = msg.content or ""
            elif isinstance(msg, AIMessage) and msg.tool_calls:
                steps.append({
                    "thought": f"调用工具: {[tc.get('name', '') for tc in msg.tool_calls]}",
                    "tool": [tc.get('name', '') for tc in msg.tool_calls],
                    "tool_input": [tc.get('args', {}) for tc in msg.tool_calls],
                })
            elif isinstance(msg, ToolMessage):
                if steps:
                    steps[-1]["tool_output"] = msg.content

        return {
            "response": response_text or "抱歉，我无法理解您的请求。",
            "steps": steps
        }

    except Exception as e:
        logger.error(f"Agent 执行错误: {str(e)}", exc_info=True)
        return {
            "response": f"抱歉，处理您的请求时出现了错误: {str(e)}",
            "steps": []
        }
