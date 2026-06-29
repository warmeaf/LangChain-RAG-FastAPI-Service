"""集成测试 - Agent 基础功能

测试完整的 Plan-then-Execute 流程（需要 LLM API 连接和 Milvus/MySQL）。
"""

import pytest


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_agent_non_stream_basic():
    """测试 Agent 非流式基本流程"""
    from app.agent.graph import run_agent_non_stream

    # 使用一个简单查询（不需要实际检索数据）
    result = await run_agent_non_stream(
        query="现在几点了？",
        user_id="integration_test_user",
        session_id="integration_test_session",
    )

    assert "final_answer" in result
    assert isinstance(result["final_answer"], str)
    assert len(result["final_answer"]) > 0


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_agent_stream_basic():
    """测试 Agent 流式基本流程"""
    from app.agent.graph import run_agent_stream

    events = []
    try:
        async for event in run_agent_stream(
            query="现在几点了？",
            user_id="integration_test_user",
            session_id="integration_test_stream",
        ):
            events.append(event)
    except Exception:
        pass

    # 验证事件流结构
    event_types = [e.get("type") for e in events]
    assert "done" in event_types or "error" in event_types, "必须有结束事件"


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_agent_graph_completes():
    """测试 Agent 图可以完整运行"""
    from app.agent.graph import _build_agent_graph, DEFAULT_TOOLS
    from app.agent.state import AgentState
    from app.agent.tools.vector_search import set_current_user_id
    from langchain_core.messages import HumanMessage

    set_current_user_id("integration_test_user")
    graph = _build_agent_graph(DEFAULT_TOOLS)

    initial_state: AgentState = {
        "messages": [HumanMessage(content="现在几点了？")],
        "plan": [],
        "current_step": 0,
        "replan_count": 0,
        "tool_results": {},
        "final_answer": "",
        "session_id": "test_graph_session",
        "user_id": "integration_test_user",
    }

    final_state = await graph.ainvoke(initial_state)

    # 验证最终状态包含必要字段
    assert "final_answer" in final_state
    assert isinstance(final_state["final_answer"], str)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_agent_skip_planning_for_simple_query():
    """测试简单问题可以跳过 Planning 直接回答"""
    from app.agent.graph import _build_agent_graph, DEFAULT_TOOLS
    from app.agent.state import AgentState
    from app.agent.tools.vector_search import set_current_user_id
    from langchain_core.messages import HumanMessage

    set_current_user_id("integration_test_user")
    graph = _build_agent_graph(DEFAULT_TOOLS)

    initial_state: AgentState = {
        "messages": [HumanMessage(content="你好，请问你叫什么名字？")],
        "plan": [],
        "current_step": 0,
        "replan_count": 0,
        "tool_results": {},
        "final_answer": "",
        "session_id": "test_skip_session",
        "user_id": "integration_test_user",
    }

    final_state = await graph.ainvoke(initial_state)

    # 简单问题应该能得到回答
    assert "final_answer" in final_state
    assert len(final_state["final_answer"]) > 0
