"""集成测试 - 数值与时态推理 (Q15-Q17)

测试时间计算、精确数值提取、因果链检索。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q15_zhao_mingxuan_work_years(resume_uploaded):
    """Q15 赵明轩在哪一年入职现在的公司？到目前为止（2026年）他有多久工作经验？"""
    answer = await run_agent_query(
        "赵明轩在哪一年入职现在的公司？到目前为止（2026年）他有多久工作经验？"
    )
    has_zhao = "赵明轩" in answer
    assert has_zhao, f"Q15: 未提到赵明轩\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q16_li_dale_2023_sales_growth(resume_uploaded):
    """Q16 李大乐 2023 年的销售额是多少？同比增长百分之多少？"""
    answer = await run_agent_query(
        "李大乐 2023 年的销售额是多少？同比增长百分之多少？"
    )
    has_li = "李大乐" in answer
    assert has_li, f"Q16: 未提到李大乐\nAnswer: {answer[:500]}"


@pytest.mark.asyncio
async def test_q17_wang_xiaohui_meituan_product(resume_uploaded):
    """Q17 汪小辉在美团期间负责什么产品？提升了多少商家活跃度？"""
    answer = await run_agent_query(
        "汪小辉在美团期间负责什么产品？提升了多少商家活跃度？"
    )
    result = check_answer(answer, must_contain=[
        "美团",
        "活跃",
    ])
    assert result["passed"], f"Q17 failed: {result['failures']}\nAnswer: {answer[:500]}"
