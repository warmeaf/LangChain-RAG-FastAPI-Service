"""create_plan 元工具

Planning 节点使用：LLM 调用此工具提交结构化检索计划。
"""

import json
from typing import Optional

from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from app.agent.state import AgentState, Step
from app.core.logger_handler import logger


@tool
async def create_plan(steps: list) -> str:
    """创建或提交检索计划。

    将拆解后的检索步骤列表写入 Agent 状态，开始逐步执行。
    每个步骤需要指定工具名称、参数、理由和依赖关系。

    Args:
        steps: 检索步骤列表，每个步骤包含：
            - id: 步骤唯一标识（如 step1, step2）
            - tool_name: 要使用的工具名称
            - tool_args: 工具参数字典
            - reason: 为什么需要这个步骤
            - depends_on: 依赖的前置步骤 id 列表（无依赖则为空列表）
    """
    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        pass  # 不在 LangGraph 运行时上下文中

    # 验证和规范化 steps
    try:
        if isinstance(steps, str):
            steps = json.loads(steps)

        if not isinstance(steps, list) or len(steps) == 0:
            return "错误: steps 必须是非空列表"

        plan = []
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                return f"错误: step[{i}] 必须是 dict 类型"

            step_id = s.get("id", f"step{i + 1}")
            plan.append(Step(
                id=step_id,
                tool_name=s.get("tool_name", ""),
                tool_args=s.get("tool_args", {}) or {},
                reason=s.get("reason", ""),
                depends_on=s.get("depends_on", []) or [],
                status="pending",
                result=None,
            ))

        # 推送 plan_created 事件（如果有 stream writer）
        if writer:
            writer({
                "type": "plan_created",
                "steps": [
                    {"id": s["id"], "tool_name": s["tool_name"], "reason": s["reason"]}
                    for s in plan
                ],
                "total_steps": len(plan),
            })

        # 返回计划摘要
        plan_summary = "\n".join(
            f"  {s['id']}: {s['tool_name']} — {s['reason']}"
            for s in plan
        )
        return f"计划已创建，共 {len(plan)} 步:\n{plan_summary}"

    except json.JSONDecodeError:
        return "错误: 无法解析 steps 参数，请确保传入有效的 JSON 列表"
    except Exception as e:
        logger.error(f"create_plan 执行失败: {e}", exc_info=True)
        return f"错误: 创建计划失败 - {str(e)}"
