"""单元测试 - 元工具和 Agent State"""

import pytest
from app.agent.state import Step, AgentState
from app.agent.meta_tools.create_plan import create_plan
from app.agent.meta_tools.evaluate_step_result import evaluate_step_result


def test_step_typed_dict():
    """测试 Step TypedDict 结构"""
    step = Step(
        id="step1",
        tool_name="vector_search",
        tool_args={"query": "test"},
        reason="测试原因",
        depends_on=[],
        status="pending",
        result=None,
    )
    assert step["id"] == "step1"
    assert step["tool_name"] == "vector_search"
    assert step["status"] == "pending"


def test_agent_state_typed_dict():
    """测试 AgentState TypedDict 结构"""
    state = AgentState(
        messages=[],
        plan=[],
        current_step=0,
        replan_count=0,
        tool_results={},
        final_answer="",
        session_id="test_session",
        user_id="test_user",
    )
    assert state["current_step"] == 0
    assert state["replan_count"] == 0
    assert state["session_id"] == "test_session"
    assert state["user_id"] == "test_user"


@pytest.mark.asyncio
async def test_create_plan_valid():
    """测试 create_plan 正常流程"""
    steps = [
        {
            "id": "step1",
            "tool_name": "vector_search",
            "tool_args": {"query": "测试"},
            "reason": "测试原因",
            "depends_on": [],
        }
    ]
    result = await create_plan.ainvoke({"steps": steps})
    assert isinstance(result, str)
    assert "计划已创建" in result


@pytest.mark.asyncio
async def test_create_plan_invalid():
    """测试 create_plan 无效输入"""
    result = await create_plan.ainvoke({"steps": []})
    assert isinstance(result, str)
    assert "错误" in result or "非空" in result


@pytest.mark.asyncio
async def test_evaluate_step_continue():
    """测试 evaluate_step_result: continue"""
    result = await evaluate_step_result.ainvoke({
        "decision": "continue",
        "reason": "结果满意",
    })
    assert isinstance(result, str)
    assert "继续" in result


@pytest.mark.asyncio
async def test_evaluate_step_skip():
    """测试 evaluate_step_result: skip"""
    result = await evaluate_step_result.ainvoke({
        "decision": "skip",
        "reason": "不需要执行",
    })
    assert isinstance(result, str)
    assert "跳过" in result


@pytest.mark.asyncio
async def test_evaluate_step_replan():
    """测试 evaluate_step_result: replan"""
    new_steps = [
        {"id": "step2", "tool_name": "keyword_search", "tool_args": {"query": "测试"}, "reason": "修正", "depends_on": []}
    ]
    result = await evaluate_step_result.ainvoke({
        "decision": "replan",
        "reason": "需要调整策略",
        "replanned_steps": new_steps,
    })
    assert isinstance(result, str)
    assert "修正" in result or "计划" in result


@pytest.mark.asyncio
async def test_evaluate_step_invalid():
    """测试 evaluate_step_result: 无效决策"""
    result = await evaluate_step_result.ainvoke({
        "decision": "invalid",
        "reason": "测试",
    })
    assert isinstance(result, str)
    assert "错误" in result
