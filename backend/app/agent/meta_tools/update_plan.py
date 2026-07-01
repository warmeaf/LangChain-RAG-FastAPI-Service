"""update_plan 元工具 — 全量更新当前计划

LLM 每次调用此工具时必须提交完整的步骤列表（含状态）。
Plan 是 LLM 的备忘录，只记录"做什么 + 做到哪了"。
"""

from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from app.core.logger_handler import logger

# 最大步骤数
MAX_STEPS = 12
# 合法状态
VALID_STATUSES = {"pending", "in_progress", "completed"}


@tool
async def update_plan(steps: list) -> str:
    """全量更新当前检索计划。每次调用必须提交完整的步骤列表及其状态。

    这是一个备忘录工具——帮助你自己追踪正在做什么、做到哪了。
    计划中的步骤是自然语言描述，你根据描述自行决定调用哪个业务工具。

    Args:
        steps: 完整步骤列表，每项包含：
            - id: 步骤唯一标识（如 step1, step2）
            - content: 自然语言描述要做什么
            - status: 状态，必须为 pending / in_progress / completed 之一
              （有且仅有一个 in_progress）
    """
    # ── 约束校验 ──
    if not isinstance(steps, list) or len(steps) == 0:
        return _err("steps 必须是非空列表")
    if len(steps) > MAX_STEPS:
        return _err(f"计划最多 {MAX_STEPS} 步，当前 {len(steps)} 步")

    normalized = []
    in_progress_count = 0

    for i, raw in enumerate(steps):
        if not isinstance(raw, dict):
            return _err(f"第 {i} 项必须是 dict 类型")

        step_id = str(raw.get("id", "")).strip()
        content = str(raw.get("content", "")).strip()
        status = str(raw.get("status", "pending")).strip().lower()

        if not step_id:
            return _err(f"第 {i} 项缺少 id")
        if not content:
            return _err(f"第 {i} 项（{step_id}）缺少 content")
        if status not in VALID_STATUSES:
            return _err(f"第 {i} 项（{step_id}）status 无效: '{status}'，可选: {VALID_STATUSES}")

        if status == "in_progress":
            in_progress_count += 1

        normalized.append({"id": step_id, "content": content, "status": status})

    if in_progress_count > 1:
        return _err(f"有且仅能有一个 in_progress 步骤，当前 {in_progress_count} 个")
    if in_progress_count == 0 and any(s["status"] == "pending" for s in normalized):
        return _err("尚有 pending 步骤但未设置 in_progress，请标记当前正在执行的步骤")

    # ── 推送 plan_updated SSE 事件 ──
    try:
        writer = get_stream_writer()
        writer({
            "type": "plan_updated",
            "steps": normalized,
            "total_steps": len(normalized),
        })
    except Exception:
        pass

    # ── 渲染计划摘要返回给 LLM ──
    markers = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
    lines = []
    for s in normalized:
        lines.append(f"  {markers[s['status']]} {s['id']}: {s['content']}")
    completed = sum(1 for s in normalized if s["status"] == "completed")
    lines.append(f"\n({completed}/{len(normalized)} 已完成)")

    result = "\n".join(lines)
    logger.info(f"[update_plan] 计划更新: {len(normalized)} 步, {completed} 已完成")
    return result


def _err(msg: str) -> str:
    return f"计划更新失败: {msg}\n请修正后重新调用 update_plan。"
