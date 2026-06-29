"""集成测试 - 实体匹配与混合检索 (Q18-Q20)

测试 doc_entity 精确过滤、中文子串匹配、长全称召回。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q18_lidale_linkedin_identity(resume_uploaded):
    """Q18 LinkedIn 用户名是 'lidale' 的人是谁？他的全名和职位是什么？"""
    answer = await run_agent_query(
        "LinkedIn 用户名是 lidale 的人是谁？他的全名和职位是什么？"
    )
    result = check_answer(answer, must_contain=[
        "李大乐",
        "销售",
    ])
    assert result["passed"], f"Q18 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q19_company_name_contains_intelligence(resume_uploaded):
    """Q19 公司名称中包含"智能"二字的有哪些候选人？请列出公司名和职位。"""
    answer = await run_agent_query(
        "公司名称中包含智能二字的有哪些候选人？请列出公司名和职位。"
    )
    result = check_answer(answer, must_contain=[
        "王小明",
        "智能",
    ])
    assert result["passed"], f"Q19 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q20_wang_xiaoming_aws_certification(resume_uploaded):
    """Q20 王小明的 AWS 认证全称是什么？他还有哪些云平台认证？"""
    answer = await run_agent_query(
        "王小明的 AWS 认证全称是什么？他还有哪些云平台认证？"
    )
    result = check_answer(answer, must_contain=[
        "AWS",
        "Google Cloud",
    ])
    assert result["passed"], f"Q20 failed: {result['failures']}\nAnswer: {answer[:500]}"
