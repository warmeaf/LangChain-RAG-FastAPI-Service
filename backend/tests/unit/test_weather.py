"""工具单元测试 - weather 工具

测试 get_weather 工具的基本功能。
"""

import pytest
from app.agent.tools.weather import get_weather, _mock_weather


@pytest.mark.asyncio
async def test_get_weather_without_api_key():
    """测试未配置 API Key 时返回模拟数据"""
    result = await get_weather.ainvoke({"city": "北京"})
    assert isinstance(result, str)
    assert "北京" in result
    assert "天气" in result or "模拟" in result


@pytest.mark.asyncio
async def test_get_weather_empty_city():
    """测试空城市名"""
    result = await get_weather.ainvoke({"city": ""})
    assert "城市名称" in result


def test_mock_weather_format():
    """测试模拟天气格式"""
    result = _mock_weather("上海")
    assert "上海" in result
    assert "温度" in result
