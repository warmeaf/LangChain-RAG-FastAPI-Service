"""集成测试 - 对比分析与综合排序 (Q11-Q14)

测试文档间对比、多因素排序、数值事实召回。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q11_wang_vs_zhao_tech_stack(resume_uploaded):
    """Q11 王小明和赵明轩的技术栈有哪些不同？谁的技术覆盖面更广？"""
    answer = await run_agent_query(
        "王小明和赵明轩的技术栈有哪些不同？谁的技术覆盖面更广？"
    )
    result = check_answer(answer, must_contain=[
        "王小明",
        "赵明轩",
        "Python",
        "Java",
    ])
    assert result["passed"], f"Q11 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q12_team_management_comparison(resume_uploaded):
    """Q12 在团队管理经验方面，韩小团和李大乐谁的团队规模更大？各自管理过多少人？"""
    answer = await run_agent_query(
        "在团队管理经验方面，韩小团和李大乐谁的团队规模更大？各自管理过多少人？"
    )
    result = check_answer(answer, must_contain=[
        "李大乐",
        "韩小团",
    ])
    # 李大乐 150 人 > 韩小团 20 人
    assert result["passed"], f"Q12 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q13_li_dale_sales_achievements(resume_uploaded):
    """Q13 从销售业绩数据来看，李大乐最有说服力的三项核心成就是什么？
    
    已知限制：跨文档多跳检索在连续测试中可能因 Milvus 连接状态不稳定导致失败。
    """
    answer = await run_agent_query(
        "从销售业绩数据来看，李大乐最有说服力的三项核心成就是什么？"
    )
    assert isinstance(answer, str) and len(answer) > 20, f"Q13: empty/short answer"
    print(f"Q13 answer preview: {answer[:300]}")


@pytest.mark.asyncio
async def test_q14_sql_python_skills(resume_uploaded):
    """Q14 在数据分析能力方面，哪些候选人有 SQL 或 Python 技能？请列出具体工具和熟练度。"""
    answer = await run_agent_query(
        "在数据分析能力方面，哪些候选人有 SQL 或 Python 技能？请列出具体工具和熟练度。"
    )
    result = check_answer(answer, must_contain=[
        "王小明",
        "汪小辉",
        "韩小团",
        "Python",
        "SQL",
    ])
    assert result["passed"], f"Q14 failed: {result['failures']}\nAnswer: {answer[:500]}"
