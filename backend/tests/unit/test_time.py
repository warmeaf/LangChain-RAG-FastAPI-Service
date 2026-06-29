"""工具单元测试 - time 工具

测试 get_current_time 工具的基本功能。
"""

import pytest
from app.agent.tools.time import get_current_time


@pytest.mark.asyncio
async def test_get_current_time_returns_string():
    """测试时间工具返回非空字符串"""
    result = await get_current_time.ainvoke({})
    assert isinstance(result, str)
    assert len(result) > 0
    assert "当前时间" in result or "202" in result


@pytest.mark.asyncio
async def test_get_current_time_contains_date():
    """测试时间工具包含年月日信息"""
    result = await get_current_time.ainvoke({})
    # 应包含当前年份
    import datetime
    year = str(datetime.datetime.now().year)
    assert year in result
