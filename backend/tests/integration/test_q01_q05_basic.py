"""集成测试 - 基础语义检索 (Q1-Q5)

测试单文档精准查找，覆盖 MD/PPTX/PDF/DOCX 四种格式。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q1_wang_xiaoming_email_github(resume_uploaded):
    """Q1 王小明的邮箱和 GitHub 地址是什么？"""
    answer = await run_agent_query("王小明的邮箱和GitHub地址是什么？")
    result = check_answer(answer, must_contain=[
        "wangxiaoming@email.com",
        "github.com/wangxiaoming",
    ])
    assert result["passed"], f"Q1 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q2_li_dale_sales_director(resume_uploaded):
    """Q2 李大乐在哪家上市公司担任销售总监？他管理多少人的团队？"""
    answer = await run_agent_query("李大乐在哪家上市公司担任销售总监？他管理多少人的团队？")
    result = check_answer(answer, must_contain=[
        "销售总监",
        "150",
    ])
    assert result["passed"], f"Q2 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q3_zhao_mingxuan_salary_framework(resume_uploaded):
    """Q3 赵明轩期望的薪资范围是多少？他使用什么开发框架？"""
    answer = await run_agent_query("赵明轩期望的薪资范围是多少？他使用什么开发框架？")
    result = check_answer(answer, must_contain=[
        "Spring Boot",
        "Vue",
    ])
    assert result["passed"], f"Q3 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q4_yu_han_job_education(resume_uploaded):
    """Q4 余涵的求职意向是什么？她的最高学历和专业是什么？"""
    answer = await run_agent_query("余涵的求职意向是什么？她的最高学历和专业是什么？")
    result = check_answer(answer, must_contain=[
        "行政",
        "本科",
        "工商管理",
    ])
    assert result["passed"], f"Q4 failed: {result['failures']}\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q5_han_xiaotuan_certifications(resume_uploaded):
    """Q5 韩小团获得了哪些专业认证？他毕业于哪所大学？"""
    answer = await run_agent_query("韩小团获得了哪些专业认证？他毕业于哪所大学？")
    result = check_answer(answer, must_contain=[
        "上海交通大学",
    ], must_not_contain=[])
    # 认证可能有 CSCP、Six Sigma、PMP 中的至少一个
    has_cert = any(kw in answer for kw in ["CSCP", "Six Sigma", "PMP"])
    assert has_cert or result["passed"], f"Q5 failed: no certification found\nAnswer: {answer[:500]}"
