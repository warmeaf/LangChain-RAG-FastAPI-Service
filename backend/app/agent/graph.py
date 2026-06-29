"""Agent 图构建

基于 LangGraph StateGraph 的 Plan-then-Execute Agent Loop。

图结构：
    START → Planning → Execution → Summarization → END
               ↑            │
               └── replan ──┘ (最多 3 次)
"""

import asyncio
from typing import List, Callable, Optional, AsyncGenerator

from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState, Step
from app.agent.nodes.planning import planning_node
from app.agent.nodes.execution import execution_node
from app.agent.nodes.summarization import summarization_node
from app.agent.tools.vector_search import vector_search, set_current_user_id
from app.agent.tools.keyword_search import keyword_search
from app.agent.tools.sql_query import sql_query
from app.agent.tools.metadata_filter_milvus import metadata_filter_milvus
from app.agent.tools.weather import get_weather
from app.agent.tools.time import get_current_time
from app.agent.tools.ocr import ocr_recognize
from app.core.logger_handler import logger

# 默认工具集（8 个工具，7 个面向用户 + 不含 user_id 在参数中暴露）
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
    """构建 LangGraph StateGraph Agent

    Args:
        tools: 可用工具列表

    Returns:
        编译后的 StateGraph
    """

    # ── 节点实现 ──

    async def planning(state: AgentState) -> AgentState:
        """Planning 节点：LLM 制定检索计划"""
        logger.info("[AgentGraph] 进入 Planning 节点")
        return await planning_node(state, tools)

    async def execution(state: AgentState) -> AgentState:
        """Execution 节点：串行执行计划并审视"""
        logger.info(f"[AgentGraph] 进入 Execution 节点 (当前步: {state.get('current_step', 0)}, 计划: {len(state.get('plan', []))} 步)")
        return await execution_node(state, tools)

    async def summarization(state: AgentState) -> AgentState:
        """Summarization 节点：生成最终回答"""
        logger.info("[AgentGraph] 进入 Summarization 节点")
        return await summarization_node(state)

    # ── 条件路由 ──

    def should_execute(state: AgentState) -> str:
        """判断是否需要进入 Execution 节点"""
        plan = state.get("plan", [])
        if not plan:
            # 空计划 → 直接进入 Summarization（问题不需要检索）
            logger.info("[AgentGraph] 空计划，跳过 Execution")
            return "summarization"
        return "execution"

    def should_continue_execution(state: AgentState) -> str:
        """判断 Execution 后是否继续或 replan"""
        plan = state.get("plan", [])
        current = state.get("current_step", 0)

        # 还有未执行的步骤 → 继续
        pending = [s for s in plan if s["status"] == "pending"]
        if pending and current < len(plan):
            should_replan = state.get("replan_count", 0) < 3
            if should_replan and _check_if_replan_needed(state):
                return "planning"
            return "execution"

        # 所有步骤完成或已跳过 → 进入 Summarization
        return "summarization"

    # ── 构建图 ──
    builder = StateGraph(AgentState)

    builder.add_node("planning", planning)
    builder.add_node("execution", execution)
    builder.add_node("summarization", summarization)

    builder.add_edge(START, "planning")
    builder.add_conditional_edges("planning", should_execute, {
        "execution": "execution",
        "summarization": "summarization",
    })
    builder.add_conditional_edges("execution", should_continue_execution, {
        "execution": "execution",
        "planning": "planning",
        "summarization": "summarization",
    })
    builder.add_edge("summarization", END)

    return builder.compile()


def _check_if_replan_needed(state: AgentState) -> bool:
    """检查是否需要 replan（Execution 节点内部已处理，此处为额外保护）"""
    return False  # Replan 逻辑在 execution_node 内部处理


# ── 顶层 API ──

async def run_agent_stream(
    query: str,
    user_id: str,
    session_id: str,
    history_messages: Optional[list] = None,
    custom_tools: Optional[List[Callable]] = None,
) -> AsyncGenerator[dict, None]:
    """运行 Agent 并流式返回 SSE 事件

    使用 LangGraph 的 astream() + custom stream writer 推送事件。

    Args:
        query: 用户问题
        user_id: 用户 ID
        session_id: 会话 ID
        history_messages: 历史消息列表（Anthropic content blocks 兼容格式）
        custom_tools: 自定义工具列表（默认使用 DEFAULT_TOOLS）

    Yields:
        SSE 事件 dict（由各节点通过 get_stream_writer() 推送）
    """
    from langchain_core.messages import HumanMessage

    set_current_user_id(user_id)
    tools = custom_tools or DEFAULT_TOOLS

    # 构建初始消息
    messages = list(history_messages) if history_messages else []
    messages.append(HumanMessage(content=query))

    initial_state: AgentState = {
        "messages": messages,
        "plan": [],
        "current_step": 0,
        "replan_count": 0,
        "tool_results": {},
        "final_answer": "",
        "session_id": session_id,
        "user_id": user_id,
    }

    graph = _build_agent_graph(tools)

    try:
        # 运行 Agent 图（带全局超时）
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
        "current_step": 0,
        "replan_count": 0,
        "tool_results": {},
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
            "tool_results": final_state.get("tool_results", {}),
        }

    except asyncio.TimeoutError:
        logger.error(f"[AgentNonStream] 全局超时 ({AGENT_LOOP_TIMEOUT}s)")
        return {
            "final_answer": "处理超时，请稍后重试。",
            "plan": [],
            "tool_results": {},
        }
    except Exception as e:
        logger.error(f"[AgentNonStream] 运行错误: {e}", exc_info=True)
        return {
            "final_answer": f"处理错误: {str(e)}",
            "plan": [],
            "tool_results": {},
        }
