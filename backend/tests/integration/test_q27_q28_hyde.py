"""集成测试 - HyDE 与查询扩展 (Q27-Q28)

测试口语化到专业化的查询扩展、HyDE 假设文档生成。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q27_selling_expert_colloquial(resume_uploaded):
    """Q27 我想找一个"卖东西很厉害的人"，有哪些候选人符合？"""
    answer = await run_agent_query(
        "我想找一个卖东西很厉害的人，有哪些候选人符合？"
    )
    # 李大乐最匹配（销售总监）
    result = check_answer(answer, must_contain=[
        "李大乐",
    ])
    assert result["passed"], f"Q27 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q28_frontend_backend_colloquial(resume_uploaded):
    """Q28 哪些人是"搞前端"或"写后端代码"的？请列出他们的具体技术栈。"""
    answer = await run_agent_query(
        "哪些人是搞前端或写后端代码的？请列出他们的具体技术栈。"
    )
    result = check_answer(answer, must_contain=[
        "王小明",
        "赵明轩",
        "Python",
        "Java",
    ])
    assert result["passed"], f"Q28 failed: {result['failures']}\nAnswer: {answer[:500]}"
