"""时间获取工具"""

import datetime
from langchain_core.tools import tool


@tool
async def get_current_time() -> str:
    """获取当前日期和时间。

    返回当前的年月日时分秒的文本描述。

    Returns:
        当前时间的格式化字符串
    """
    now = datetime.datetime.now()
    weekday_map = {
        0: "星期一", 1: "星期二", 2: "星期三",
        3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日",
    }
    weekday = weekday_map[now.weekday()]
    return (
        f"当前时间：{now.strftime('%Y年%m月%d日')} {weekday} "
        f"{now.strftime('%H:%M:%S')}"
    )
