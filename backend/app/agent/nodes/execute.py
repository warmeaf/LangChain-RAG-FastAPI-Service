"""Execute 节点 — 统一工具循环

LLM 可访问全部工具（7 业务 + update_plan）。
Plan 是 LLM 的备忘录，LLM 自己决定何时更新计划、何时执行业务工具。
"""

import json
import asyncio
from typing import List, Callable, Dict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer

from app.agent.state import AgentState, Step
from app.prompt.tool_xml import tools_to_xml, tools_to_json_schemas
from app.utils.prompt_loader import build_stage_prompt
from app.utils.factory import create_anthropic_model
from app.agent.meta_tools.update_plan import update_plan
from app.core.logger_handler import logger

# 最大工具循环轮数
MAX_CYCLES = 20
# 提醒间隔（连续 N 轮未更新计划后注入提醒）
PLAN_REMINDER_INTERVAL = 3


async def execute_node(state: AgentState, tools: List[Callable]) -> AgentState:
    """Execute 节点：统一工具循环

    LLM 可同时使用 update_plan 和业务工具。
    循环直到 LLM 返回 end_turn 或达到安全上限。
    """
    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        pass

    all_tools = list(tools) + [update_plan]
    tools_by_name: Dict[str, Callable] = {t.name: t for t in all_tools}

    tools_xml = tools_to_xml(all_tools)
    system_prompt = build_stage_prompt("execute", tools_xml)
    tool_schemas = tools_to_json_schemas(all_tools)

    llm = create_anthropic_model(temperature=0.2)
    llm_with_tools = llm.bind_tools(tool_schemas)

    messages = [SystemMessage(content=system_prompt)]
    messages.extend(state.get("messages", []))

    state["cycle_count"] = state.get("cycle_count", 0)
    state["rounds_since_plan_update"] = state.get("rounds_since_plan_update", 0)

    # ── 工具循环 ──
    while state["cycle_count"] < MAX_CYCLES:
        state["cycle_count"] += 1
        logger.info(f"[Execute] 第 {state['cycle_count']} 轮...")

        # 注入提醒（如果连续多轮未更新计划）
        if state["rounds_since_plan_update"] >= PLAN_REMINDER_INTERVAL:
            reminder = f"<reminder>你已经 {state['rounds_since_plan_update']} 轮没有更新计划了。如果当前任务仍有未完成的步骤，请调用 update_plan 更新计划状态。</reminder>"
            messages.append(HumanMessage(content=reminder))
            state["rounds_since_plan_update"] = 0  # 重置，避免重复提醒
            logger.info("[Execute] 注入计划更新提醒")

        try:
            response = await llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error(f"[Execute] LLM 调用失败: {e}", exc_info=True)
            break

        stop_reason = _get_stop_reason(response)
        tool_calls = _extract_tool_calls(response)
        logger.info(f"[Execute] stop_reason={stop_reason}, tools={[t.get('name') for t in tool_calls]}")

        if stop_reason == "end_turn" or not tool_calls:
            messages.append(response)
            break

        messages.append(response)

        # ── 逐个执行 tool_use ──
        used_update_plan = False
        tool_results = []

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})
            tool_id = tc.get("id", "")

            if tool_name == "update_plan":
                result = _handle_update_plan(tool_args, state, writer)
                used_update_plan = True
            else:
                result = await _handle_business_tool(tool_name, tool_args, tools_by_name, state, writer)

            tool_results.append(ToolMessage(content=str(result), tool_call_id=tool_id))

        messages.extend(tool_results)

        # 提醒计数器
        if used_update_plan:
            state["rounds_since_plan_update"] = 0
        else:
            state["rounds_since_plan_update"] += 1

    state["messages"] = messages
    return state


# ── update_plan 处理器 ──

def _handle_update_plan(args: dict, state: AgentState, writer) -> str:
    """处理 update_plan：全量替换计划"""
    steps_data = args.get("steps", [])

    if not isinstance(steps_data, list) or len(steps_data) == 0:
        return "错误: steps 必须是非空列表"

    plan = []
    for raw in steps_data:
        if not isinstance(raw, dict):
            continue
        plan.append(Step(
            id=str(raw.get("id", "")).strip(),
            content=str(raw.get("content", "")).strip(),
            status=str(raw.get("status", "pending")).strip().lower(),
        ))

    state["plan"] = plan
    state["replan_count"] = state.get("replan_count", 0) + 1

    # SSE 事件
    if writer:
        writer({
            "type": "plan_updated",
            "steps": [{"id": s["id"], "content": s["content"], "status": s["status"]} for s in plan],
            "total_steps": len(plan),
        })

    # 渲染摘要
    markers = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
    lines = [f"  {markers.get(s['status'], '[?]')} {s['id']}: {s['content']}" for s in plan]
    completed = sum(1 for s in plan if s["status"] == "completed")
    lines.append(f"\n({completed}/{len(plan)} 已完成)")

    logger.info(f"[Execute] 计划更新: {len(plan)} 步, {completed} 已完成")
    return "\n".join(lines)


# ── 业务工具处理器 ──

async def _handle_business_tool(
    tool_name: str, tool_args: dict, tools_by_name: Dict, state: AgentState, writer
) -> str:
    """执行业务工具"""
    tool_func = tools_by_name.get(tool_name)
    if tool_func is None:
        return f"错误: 未知工具 '{tool_name}'"

    # step_start SSE 事件
    if writer:
        writer({
            "type": "step_start",
            "step_id": tool_name,
            "tool_name": tool_name,
            "reason": tool_args.get("query", tool_args.get("city", tool_args.get("condition", ""))),
        })

    # 执行工具
    try:
        if asyncio.iscoroutinefunction(tool_func.ainvoke):
            result = await tool_func.ainvoke(tool_args)
        elif asyncio.iscoroutinefunction(getattr(tool_func, 'arun', None)):
            result = await tool_func.arun(tool_args)
        else:
            result = tool_func.invoke(tool_args)
        result_str = str(result)
        status = "done"
    except Exception as e:
        result_str = f"工具执行错误: {str(e)}"
        status = "failed"

    # 更新 plan 中当前 in_progress 步骤的状态
    plan = state.get("plan", [])
    for s in plan:
        if s["status"] == "in_progress":
            s["status"] = "completed" if status == "done" else status
            break

    # step_done SSE 事件
    if writer:
        writer({
            "type": "step_done",
            "step_id": tool_name,
            "status": status,
        })

    logger.info(f"[Execute] 工具 {tool_name}: {status}")
    return result_str


# ── 辅助函数 ──

def _get_stop_reason(msg) -> str:
    if hasattr(msg, 'response_metadata') and isinstance(msg.response_metadata, dict):
        return msg.response_metadata.get("stop_reason", "")
    if hasattr(msg, 'additional_kwargs') and isinstance(msg.additional_kwargs, dict):
        return msg.additional_kwargs.get("stop_reason", "")
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        return "tool_use"
    return "end_turn"


def _extract_tool_calls(msg) -> list:
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
