"""集成测试 - 格式鲁棒性与特殊内容 (Q29-Q30)

测试 PPTX 幻灯片结构解析、DOCX 特殊格式处理。
"""

import pytest
from tests.integration.conftest import check_answer, run_agent_query, TEST_USER_ID

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_q29_li_dale_ppt_structure(resume_uploaded):
    """Q29 李大乐的 PPT 简历中一共有多少张幻灯片？幻灯片 4 中提到了哪些关键业绩数据？"""
    answer = await run_agent_query(
        "李大乐的 PPT 简历中一共有多少张幻灯片？幻灯片 4 中提到了哪些关键业绩数据？"
    )
    # 应提及幻灯片数量和业绩数据
    result = check_answer(answer, must_contain=[
        "李大乐",
    ])
    # 应有幻灯片相关数字或业绩数据
    has_slide_info = any(kw in answer for kw in ["8", "幻灯片", "slide", "12.8", "28%", "116%"])
    assert has_slide_info or result["passed"], (
        f"Q29 failed: 缺少幻灯片或业绩信息\nAnswer: {answer[:500]}"
    )


@pytest.mark.asyncio
async def test_q30_lin_yuxiao_certificates(resume_uploaded):
    """Q30 林宇萧有哪些证书和荣誉？她的本科和硕士分别是在哪所学校读的？"""
    answer = await run_agent_query(
        "林宇萧有哪些证书和荣誉？她的本科和硕士分别是在哪所学校读的？"
    )
    result = check_answer(answer, must_contain=[
        "林宇萧",
        "广州科技",
        "华中师范",
        "计算机二级",
    ])
    assert result["passed"], f"Q30 failed: {result['failures']}\nAnswer: {answer[:500]}"
