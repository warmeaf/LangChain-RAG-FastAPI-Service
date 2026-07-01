"""Agent 图构建

基于 LangGraph StateGraph 的统一工具循环 Agent。

图结构（2 节点）：
    START → Execute → Summarization → END
               ↑          │
               └──────────┘ (while 循环在 Execute 节点内部)
"""

import asyncio
from typing import List, Callable, Optional, AsyncGenerator

from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.nodes.execute import execute_node
from app.agent.nodes.summarization import summarization_node
from app.agent.tools.vector_search import vector_search, set_current_user_id
from app.agent.tools.keyword_search import keyword_search
from app.agent.tools.sql_query import sql_query
from app.agent.tools.metadata_filter_milvus import metadata_filter_milvus
from app.agent.tools.weather import get_weather
from app.agent.tools.time import get_current_time
from app.agent.tools.ocr import ocr_recognize
from app.core.logger_handler import logger

# 默认业务工具集（7 个，元工具 create_plan / evaluate_step_result 在 execute_node 内部追加）
DEFAULT_TOOLS = [
    vector_search,
    keyword_search,
    sql_query,
    metadata_filter_milvus,
    get_weather,
    get_current_time,
    ocr_recognize,
]

# Agent loop 全局超时（秒）
AGENT_LOOP_TIMEOUT = 120


def _build_agent_graph(tools: List[Callable]):
    """构建 LangGraph StateGraph Agent（2 节点）

    Args:
        tools: 业务工具列表

    Returns:
        编译后的 StateGraph
    """

    async def execute(state: AgentState) -> AgentState:
        """Execute 节点：统一工具循环"""
        logger.info("[AgentGraph] 进入 Execute 节点")
        return await execute_node(state, tools)

    async def summarization(state: AgentState) -> AgentState:
        """Summarization 节点：生成最终回答"""
        logger.info("[AgentGraph] 进入 Summarization 节点")
        return await summarization_node(state)

    def should_continue(state: AgentState) -> str:
        """Execute 后决定：继续执行还是进入 Summarization"""
        # Execute 节点内部已处理循环，这里始终进入 Summarization
        return "summarization"

    # ── 构建图 ──
    builder = StateGraph(AgentState)
    builder.add_node("execute", execute)
    builder.add_node("summarization", summarization)
    builder.add_edge(START, "execute")
    builder.add_conditional_edges("execute", should_continue, {
        "summarization": "summarization",
    })
    builder.add_edge("summarization", END)

    return builder.compile()


# ── 顶层 API ──

async def run_agent_stream(
    query: str,
    user_id: str,
    session_id: str,
    history_messages: Optional[list] = None,
    custom_tools: Optional[List[Callable]] = None,
) -> AsyncGenerator[dict, None]:
    """运行 Agent 并流式返回 SSE 事件

    Args:
        query: 用户问题
        user_id: 用户 ID
        session_id: 会话 ID
        history_messages: 历史消息列表
        custom_tools: 自定义工具列表（默认使用 DEFAULT_TOOLS）

    Yields:
        SSE 事件 dict
    """
    from langchain_core.messages import HumanMessage

    set_current_user_id(user_id)
    tools = custom_tools or DEFAULT_TOOLS

    messages = list(history_messages) if history_messages else []
    messages.append(HumanMessage(content=query))

    initial_state: AgentState = {
        "messages": messages,
        "plan": [],
        "replan_count": 0,
        "cycle_count": 0,
        "rounds_since_plan_update": 0,
        "final_answer": "",
        "session_id": session_id,
        "user_id": user_id,
    }

    graph = _build_agent_graph(tools)

    try:
        async for chunk in graph.astream(
            initial_state,
            stream_mode=["custom"],
            version="v2",
        ):
            if chunk["type"] == "custom":
                yield chunk["data"]

    except asyncio.TimeoutError:
        logger.error(f"[AgentStream] 全局超时 ({AGENT_LOOP_TIMEOUT}s)")
        yield {"type": "error", "content": "处理超时，请稍后重试"}

    except Exception as e:
        logger.error(f"[AgentStream] 运行错误: {e}", exc_info=True)
        yield {"type": "error", "content": f"处理错误: {str(e)}"}

    finally:
        yield {"type": "done"}


async def run_agent_non_stream(
    query: str,
    user_id: str,
    session_id: str = "",
    history_messages: Optional[list] = None,
    custom_tools: Optional[List[Callable]] = None,
) -> dict:
    """运行 Agent 并返回最终状态（非流式）

    Returns:
        {"final_answer": str, "plan": list, "tool_results": dict}
    """
    from langchain_core.messages import HumanMessage

    set_current_user_id(user_id)
    tools = custom_tools or DEFAULT_TOOLS

    messages = list(history_messages) if history_messages else []
    messages.append(HumanMessage(content=query))

    initial_state: AgentState = {
        "messages": messages,
        "plan": [],
        "replan_count": 0,
        "cycle_count": 0,
        "rounds_since_plan_update": 0,
        "final_answer": "",
        "session_id": session_id,
        "user_id": user_id,
    }

    graph = _build_agent_graph(tools)

    try:
        final_state = await asyncio.wait_for(
            graph.ainvoke(initial_state),
            timeout=AGENT_LOOP_TIMEOUT,
        )

        return {
            "final_answer": final_state.get("final_answer", "抱歉，无法回答这个问题。"),
            "plan": final_state.get("plan", []),
        }

    except asyncio.TimeoutError:
        logger.error(f"[AgentNonStream] 全局超时 ({AGENT_LOOP_TIMEOUT}s)")
        return {"final_answer": "处理超时，请稍后重试。", "plan": [], "tool_results": {}}
    except Exception as e:
        logger.error(f"[AgentNonStream] 运行错误: {e}", exc_info=True)
        return {"final_answer": f"处理错误: {str(e)}", "plan": [], "tool_results": {}}
