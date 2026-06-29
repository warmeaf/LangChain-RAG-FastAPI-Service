"""Execution 节点

串行逐步执行检索计划，每步完成后 LLM 审视结果并决策。
"""

import json
import asyncio
from typing import List, Callable, Dict

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer

from app.agent.state import AgentState, Step
from app.prompt.tool_xml import tools_to_xml, tools_to_json_schemas
from app.prompt.tool_xml import tool_to_json_schema
from app.utils.prompt_loader import build_stage_prompt
from app.utils.factory import create_anthropic_model
from app.agent.meta_tools.evaluate_step_result import evaluate_step_result
from app.core.logger_handler import logger

# 最大 replan 次数
MAX_REPLAN = 3


async def execution_node(state: AgentState, tools: List[Callable]) -> AgentState:
    """Execution 节点：串行执行计划，每步审视

    Args:
        state: 当前 Agent 状态
        tools: 可用工具列表（不含元工具）

    Returns:
        更新后的 AgentState（tool_results 和 messages 已更新）
    """
    tools_by_name: Dict[str, Callable] = {t.name: t for t in tools}
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    while state["current_step"] < len(state["plan"]):
        # 检查 replan 上限
        if state.get("replan_count", 0) >= MAX_REPLAN:
            logger.warning(f"[Execution] 已达 replan 上限 ({MAX_REPLAN})，强制结束")
            break

        step = state["plan"][state["current_step"]]

        # 跳过已完成的步
        if step["status"] == "done":
            state["current_step"] += 1
            continue

        # 检查依赖是否满足
        if not _dependencies_met(step, state["plan"]):
            step["status"] = "skipped"
            if writer:
                writer({
                    "type": "step_done",
                    "step_id": step["id"],
                    "status": "skipped",
                })
            state["current_step"] += 1
            continue

        # ── 执行步骤 ──
        logger.info(f"[Execution] 执行步骤: {step['id']} → {step['tool_name']}")
        step["status"] = "running"

        if writer:
            writer({
                "type": "step_start",
                "step_id": step["id"],
                "tool_name": step["tool_name"],
                "reason": step["reason"],
            })

        # 执行工具
        tool_func = tools_by_name.get(step["tool_name"])
        if tool_func is None:
            result = f"错误: 未知工具 '{step['tool_name']}'"
            step["status"] = "failed"
        else:
            try:
                tool_args = dict(step.get("tool_args", {}))
                if asyncio.iscoroutinefunction(tool_func.ainvoke):
                    observation = await tool_func.ainvoke(tool_args)
                else:
                    observation = tool_func.invoke(tool_args)
                result = str(observation)
                step["status"] = "done"
            except Exception as e:
                result = f"工具执行错误: {str(e)}"
                step["status"] = "failed"

        step["result"] = result
        state["tool_results"][step["id"]] = result

        if writer:
            writer({
                "type": "step_done",
                "step_id": step["id"],
                "status": step["status"],
            })

        # ── 审视步骤结果 ──
        decision = await _evaluate_step(state, step, tools)
        logger.info(f"[Execution] 审视结果: step={step['id']}, decision={decision}")

        if decision == "replan":
            state["replan_count"] = state.get("replan_count", 0) + 1
            logger.info(f"[Execution] 重规划 (#{state['replan_count']})")
            # replan 由 evaluate_step_result 工具处理（在 _evaluate_step 中）
            # 这里重置 current_step 继续执行新计划
            state["current_step"] = 0
        elif decision == "skip":
            # 跳过当前及剩余步骤
            for i in range(state["current_step"], len(state["plan"])):
                if state["plan"][i]["status"] == "pending":
                    state["plan"][i]["status"] = "skipped"
            break
        else:  # continue
            state["current_step"] += 1

    return state


def _dependencies_met(step: Step, plan: List[Step]) -> bool:
    """检查步骤的所有依赖是否已完成"""
    depends = step.get("depends_on", [])
    if not depends:
        return True

    status_map = {s["id"]: s["status"] for s in plan}
    for dep_id in depends:
        if status_map.get(dep_id) not in ("done",):
            return False
    return True


async def _evaluate_step(state: AgentState, step: Step, tools: List[Callable]) -> str:
    """LLM 审视当前步骤结果，返回决策: continue | replan | skip"""
    # 构建审视消息
    tool_xml = tools_to_xml(tools)
    meta_xml = tools_to_xml([evaluate_step_result])
    all_xml = tool_xml + "\n\n" + meta_xml
    system_prompt = build_stage_prompt("execution", all_xml)

    tool_schemas = tools_to_json_schemas(tools)
    tool_schemas.append(tool_to_json_schema(evaluate_step_result))

    llm = create_anthropic_model(temperature=0.2)
    llm_with_tools = llm.bind_tools(tool_schemas, tool_choice="any")

    # 构建审视上下文
    context = (
        f"## 当前步骤执行结果\n\n"
        f"步骤: {step['id']} ({step['tool_name']})\n"
        f"原因: {step['reason']}\n"
        f"状态: {step['status']}\n"
        f"结果:\n{step['result']}\n\n"
        f"## 用户原始问题\n{_get_user_query(state['messages'])}\n\n"
        f"## 已完成步骤\n{_format_completed_steps(state['plan'])}\n\n"
        f"## 待执行步骤\n{_format_pending_steps(state['plan'])}\n\n"
        f"请审视上述结果，调用 evaluate_step_result 做出决策。"
    )

    try:
        response = await llm_with_tools.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=context),
        ])

        # 提取决策
        tool_calls = _extract_tool_calls(response)
        for tc in tool_calls:
            if tc.get("name") == "evaluate_step_result":
                decision = tc.get("args", {}).get("decision", "continue")
                reason = tc.get("args", {}).get("reason", "")

                if decision == "replan":
                    # 更新计划：保留已完成的步骤，替换未完成的
                    new_steps_data = tc.get("args", {}).get("replanned_steps", [])
                    if isinstance(new_steps_data, str):
                        new_steps_data = json.loads(new_steps_data)

                    if new_steps_data:
                        # 保留已完成的步骤
                        completed = [s for s in state["plan"] if s["status"] == "done"]
                        new_plan = completed + [
                            Step(
                                id=s.get("id", f"step{i + 1}"),
                                tool_name=s.get("tool_name", ""),
                                tool_args=s.get("tool_args", {}) or {},
                                reason=s.get("reason", ""),
                                depends_on=s.get("depends_on", []) or [],
                                status="pending",
                                result=None,
                            )
                            for i, s in enumerate(new_steps_data)
                        ]
                        state["plan"] = new_plan
                        logger.info(f"[Execution] 计划已更新: {len(new_plan)} 步 (已完成 {len(completed)})")

                return decision

    except Exception as e:
        logger.error(f"[Execution] 审视出错: {e}", exc_info=True)

    # 默认继续
    return "continue"


def _get_user_query(messages: list) -> str:
    """从 messages 中提取用户原始问题"""
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            content = msg.content
            if isinstance(content, list):
                # Anthropic content blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
            elif isinstance(content, str):
                return content
    return "未知问题"


def _format_completed_steps(plan: List[Step]) -> str:
    """格式化已完成的步骤"""
    completed = [s for s in plan if s["status"] in ("done", "failed")]
    if not completed:
        return "(无)"
    lines = []
    for s in completed:
        lines.append(f"- {s['id']} ({s['tool_name']}): {s['status']}")
    return "\n".join(lines)


def _format_pending_steps(plan: List[Step]) -> str:
    """格式化待执行的步骤"""
    pending = [s for s in plan if s["status"] in ("pending",)]
    if not pending:
        return "(无 — 所有步骤已执行)"
    lines = []
    for s in pending:
        lines.append(f"- {s['id']}: {s['tool_name']} (原因: {s['reason']})")
    return "\n".join(lines)


def _extract_tool_calls(msg) -> list:
    """从 AIMessage 提取 tool_calls"""
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        return msg.tool_calls
    if hasattr(msg, 'content') and isinstance(msg.content, list):
        tool_calls = []
        for block in msg.content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls.append({
                    "name": block.get("name", ""),
                    "args": block.get("input", {}),
                    "id": block.get("id", ""),
                })
        return tool_calls
    return []
