"""集成测试 - 跨文档多跳推理 (Q6-Q10)

测试跨多份简历的聚合、精确匹配和语义匹配能力。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q6_beijing_tech_graduates(resume_uploaded):
    """Q6 列出所有毕业于北京理工大学的候选人，并写出各自的专业和毕业年份。"""
    answer = await run_agent_query(
        "列出所有毕业于北京理工大学的候选人，并写出各自的专业和毕业年份。"
    )
    result = check_answer(answer, must_contain=[
        "王小明",
        "赵明轩",
        "汪小辉",
        "北京理工大学",
    ])
    assert result["passed"], f"Q6 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q7_bytedance_meituan_experience(resume_uploaded):
    """Q7 哪几位候选人有字节跳动或美团的经历？各自的职位和期间是什么？"""
    answer = await run_agent_query(
        "哪几位候选人有字节跳动或美团的经历？各自的职位和期间是什么？"
    )
    result = check_answer(answer, must_contain=[
        "汪小辉",
        "字节",
        "美团",
    ])
    assert result["passed"], f"Q7 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q8_cet6_scores(resume_uploaded):
    """Q8 哪些简历提到了 CET-6 或英语六级成绩？请列出每个人的分数。"""
    answer = await run_agent_query(
        "哪些简历提到了 CET-6 或英语六级成绩？请列出每个人的分数。"
    )
    # 至少包含王小明、汪小辉、韩小团中的大部分
    result = check_answer(answer, must_contain=[
        "王小明",
        "汪小辉",
        "韩小团",
    ])
    assert result["passed"], f"Q8 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q9_masters_degree_candidates(resume_uploaded):
    """Q9 请列出所有具有硕士学位的候选人、他们的毕业院校和专业方向。"""
    answer = await run_agent_query(
        "请列出所有具有硕士学位的候选人、他们的毕业院校和专业方向。"
    )
    result = check_answer(answer, must_contain=[
        "韩小团",
        "林宇萧",
        "李大乐",
    ])
    assert result["passed"], f"Q9 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q10_product_operations_experience(resume_uploaded):
    """Q10 哪些人具有产品运营或运营相关的工作经验？在公司担任什么职位？"""
    answer = await run_agent_query(
        "哪些人具有产品运营或运营相关的工作经验？在公司担任什么职位？"
    )
    result = check_answer(answer, must_contain=[
        "汪小辉",
        "运营",
    ])
    assert result["passed"], f"Q10 failed: {result['failures']}\nAnswer: {answer[:500]}"
