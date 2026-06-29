"""天气查询工具

接和风天气（QWeather）真实 API。
环境变量：QWEATHER_API_KEY（从 .env 加载）
"""

import os
from typing import Optional

from langchain_core.tools import tool
import httpx

from app.core.logger_handler import logger


@tool
async def get_weather(city: str) -> str:
    """查询指定城市的天气信息。

    通过和风天气 API 获取实时天气数据，包括温度、天气状况、风力等信息。

    Args:
        city: 城市名称（如"北京"、"上海"、"深圳"）
    """
    if not city:
        return "请提供城市名称"

    api_key = os.getenv("QWEATHER_API_KEY", "")
    if not api_key:
        logger.warning("QWEATHER_API_KEY 未配置，返回模拟数据")
        return _mock_weather(city)

    try:
        # ① 城市搜索（获取 location_id）
        async with httpx.AsyncClient(timeout=10) as client:
            geo_resp = await client.get(
                "https://geoapi.qweather.com/v2/city/lookup",
                params={"location": city, "key": api_key}
            )
            geo_data = geo_resp.json()

            if geo_data.get("code") != "200" or not geo_data.get("location"):
                return _mock_weather(city)

            location_id = geo_data["location"][0]["id"]
            city_name = geo_data["location"][0]["name"]

            # ② 实时天气
            weather_resp = await client.get(
                "https://devapi.qweather.com/v7/weather/now",
                params={"location": location_id, "key": api_key}
            )
            weather_data = weather_resp.json()

            if weather_data.get("code") != "200":
                return _mock_weather(city)

            now = weather_data["now"]
            lines = [
                f"【{city_name}】天气信息：",
                f"- 天气状况: {now.get('text', '未知')}",
                f"- 当前温度: {now.get('temp', 'N/A')}°C",
                f"- 体感温度: {now.get('feelsLike', 'N/A')}°C",
                f"- 相对湿度: {now.get('humidity', 'N/A')}%",
                f"- 风力等级: {now.get('windScale', 'N/A')} 级",
                f"- 风向: {now.get('windDir', 'N/A')}",
                f"- 能见度: {now.get('vis', 'N/A')} km",
            ]
            return "\n".join(lines)

    except Exception as e:
        logger.error(f"天气查询失败: {e}", exc_info=True)
        return f"天气查询出错: {str(e)}"


def _mock_weather(city: str) -> str:
    """未配置 API Key 时的模拟天气数据"""
    return (
        f"【{city}】天气信息（模拟数据）：\n"
        f"- 天气状况: 晴朗\n"
        f"- 当前温度: 22°C\n"
        f"- 相对湿度: 45%\n"
        f"- 风力等级: 2 级\n"
        f"注意：天气API Key未配置，以上为模拟数据。"
    )
