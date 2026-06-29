"""evaluate_step_result 元工具

Execution 节点使用：每步执行完后，LLM 调用此工具审视结果并决策。
"""

from typing import Optional

from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from app.core.logger_handler import logger


@tool
async def evaluate_step_result(
    decision: str,
    reason: str,
    replanned_steps: Optional[list] = None,
) -> str:
    """审视当前步骤的执行结果，做出下一步决策。

    每步执行完成后必须调用此工具。根据结果质量和信息充分性，
    选择继续执行、修正计划或跳过剩余步骤。

    Args:
        decision: 决策类型
            - "continue": 当前步骤结果满足需求，继续执行下一步
            - "replan": 当前结果不满足需求，需要修正计划（需提供 replanned_steps）
            - "skip": 当前步骤不需要执行，跳过（或信息已足够，跳过剩余步骤直接总结）
        reason: 决策理由（说明为什么做这个决定）
        replanned_steps: 当 decision="replan" 时，新的步骤列表（仅保留未完成的步骤）。
            每个步骤格式同 create_plan。
    """
    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        pass  # 不在 LangGraph 运行时上下文中

    if decision not in ("continue", "replan", "skip"):
        return f"错误: 不支持的决策类型 '{decision}'，可选: continue / replan / skip"

    if decision == "replan":
        if not replanned_steps:
            return "错误: decision='replan' 时必须提供 replanned_steps"

        plan_summary = "\n".join(
            f"  {s.get('id', '?')}: {s.get('tool_name', '?')} — {s.get('reason', '?')}"
            for s in replanned_steps
        )

        # 推送 replan 事件
        if writer:
            writer({
                "type": "step_replan",
                "reason": reason,
                "new_steps": replanned_steps,
                "new_total_steps": len(replanned_steps),
            })

        return (
            f"计划已修正 ({reason})\n"
            f"新计划共 {len(replanned_steps)} 步:\n{plan_summary}"
        )

    elif decision == "skip":
        return f"跳过当前步骤 ({reason})"

    else:  # continue
        return f"继续执行下一步 ({reason})"
