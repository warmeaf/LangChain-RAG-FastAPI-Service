"""Execute 节点 — 统一工具循环

LLM 在单次循环中可访问全部 9 个工具（7 业务 + 2 元工具），
自行决策何时规划、何时执行、何时结束。
Plan-then-Execute 通过系统提示词引导，而非图结构强制。
"""

import json
from typing import List, Callable, Dict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer

from app.agent.state import AgentState, Step
from app.prompt.tool_xml import tools_to_xml, tools_to_json_schemas
from app.utils.prompt_loader import build_stage_prompt
from app.utils.factory import create_anthropic_model
from app.agent.meta_tools.create_plan import create_plan
from app.agent.meta_tools.evaluate_step_result import evaluate_step_result
from app.core.logger_handler import logger

# 最大工具循环轮数（防无限循环）
MAX_CYCLES = 20
# 最大 replan 次数
MAX_REPLAN = 3


async def execute_node(state: AgentState, tools: List[Callable]) -> AgentState:
    """Execute 节点：统一工具循环

    LLM 可同时使用元工具（create_plan / evaluate_step_result）和业务工具。
    循环直到 LLM 返回 end_turn 或达到安全上限。

    Args:
        state: 当前 Agent 状态
        tools: 业务工具列表（7 个，不含元工具）

    Returns:
        更新后的 AgentState
    """
    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        pass

    # 构建全部工具列表（业务工具 + 元工具）
    all_tools = list(tools) + [create_plan, evaluate_step_result]
    tools_by_name: Dict[str, Callable] = {t.name: t for t in all_tools}

    # 构建系统提示词（execute 层 + 全部工具 XML）
    tools_xml = tools_to_xml(all_tools)
    system_prompt = build_stage_prompt("execute", tools_xml)

    # 构建 Anthropic-format tools JSON Schema
    tool_schemas = tools_to_json_schemas(all_tools)

    llm = create_anthropic_model(temperature=0.2)
    llm_with_tools = llm.bind_tools(tool_schemas)

    # 构建初始消息
    messages = [SystemMessage(content=system_prompt)]
    messages.extend(state.get("messages", []))

    state["cycle_count"] = state.get("cycle_count", 0)

    # ── 工具循环 ──
    while state["cycle_count"] < MAX_CYCLES:
        # 检查 replan 上限
        if state.get("replan_count", 0) >= MAX_REPLAN:
            logger.warning(f"[Execute] 已达 replan 上限 ({MAX_REPLAN})，强制结束")
            break

        state["cycle_count"] += 1
        logger.info(f"[Execute] 第 {state['cycle_count']} 轮...")

        try:
            response = await llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error(f"[Execute] LLM 调用失败: {e}", exc_info=True)
            break

        # 提取 stop_reason
        stop_reason = _get_stop_reason(response)
        logger.info(f"[Execute] stop_reason={stop_reason}")

        # 提取 tool_use blocks
        tool_calls = _extract_tool_calls(response)

        if stop_reason == "end_turn" or not tool_calls:
            # LLM 认为任务完成，退出循环
            messages.append(response)
            break

        # 将 assistant 消息加入历史
        messages.append(response)

        # ── 逐个执行 tool_use ──
        tool_results = []
        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = tc.get("args", {})
            tool_id = tc.get("id", "")

            logger.info(f"[Execute] 调用工具: {tool_name}")

            if tool_name == "create_plan":
                result = await _handle_create_plan(tool_args, state, writer)
            elif tool_name == "evaluate_step_result":
                result = await _handle_evaluate_step_result(tool_args, state, writer)
            else:
                result = await _handle_business_tool(tool_name, tool_args, tools_by_name, state, writer)

            tool_results.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_id,
            ))

        messages.extend(tool_results)

    # 更新 state.messages
    state["messages"] = messages
    return state


async def _handle_create_plan(args: dict, state: AgentState, writer) -> str:
    """处理 create_plan 工具调用"""
    steps_data = args.get("steps", [])
    if isinstance(steps_data, str):
        try:
            steps_data = json.loads(steps_data)
        except json.JSONDecodeError:
            return "错误: 无法解析 steps 参数"

    if not isinstance(steps_data, list) or len(steps_data) == 0:
        return "错误: steps 必须是非空列表"

    plan = []
    for i, s in enumerate(steps_data):
        if not isinstance(s, dict):
            continue
        plan.append(Step(
            id=s.get("id", f"step{i + 1}"),
            tool_name=s.get("tool_name", ""),
            tool_args=s.get("tool_args", {}) or {},
            reason=s.get("reason", ""),
            depends_on=s.get("depends_on", []) or [],
            status="pending",
            result=None,
        ))

    state["plan"] = plan
    state["current_step"] = 0

    # 推送 plan_created 事件
    if writer:
        writer({
            "type": "plan_created",
            "steps": [
                {"id": s["id"], "tool_name": s["tool_name"], "reason": s["reason"]}
                for s in plan
            ],
            "total_steps": len(plan),
        })

    plan_summary = "\n".join(f"  {s['id']}: {s['tool_name']} — {s['reason']}" for s in plan)
    logger.info(f"[Execute] 计划创建: {len(plan)} 步")
    return f"计划已创建，共 {len(plan)} 步:\n{plan_summary}"


async def _handle_evaluate_step_result(args: dict, state: AgentState, writer) -> str:
    """处理 evaluate_step_result 工具调用"""
    decision = args.get("decision", "continue")
    reason = args.get("reason", "")

    if decision == "replan":
        state["replan_count"] = state.get("replan_count", 0) + 1
        new_steps_data = args.get("replanned_steps", [])
        if isinstance(new_steps_data, str):
            try:
                new_steps_data = json.loads(new_steps_data)
            except json.JSONDecodeError:
                return "错误: 无法解析 replanned_steps"

        if new_steps_data:
            completed = [s for s in state.get("plan", []) if s["status"] == "done"]
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
            state["current_step"] = 0

        if writer:
            writer({
                "type": "step_replan",
                "reason": reason,
                "new_steps": new_steps_data,
                "new_total_steps": len(new_steps_data) if new_steps_data else 0,
            })

        logger.info(f"[Execute] 计划修正 (#{state['replan_count']}): {reason}")
        return f"计划已修正 ({reason})，新计划共 {len(state.get('plan', []))} 步"

    elif decision == "skip":
        # 标记所有 pending 步骤为 skipped
        for s in state.get("plan", []):
            if s["status"] == "pending":
                s["status"] = "skipped"
        return f"跳过剩余步骤 ({reason})"

    else:  # continue
        # 标记当前步骤为 done（如果还没标记）
        plan = state.get("plan", [])
        idx = state.get("current_step", 0)
        if idx < len(plan) and plan[idx]["status"] == "running":
            plan[idx]["status"] = "done"
        return f"继续执行下一步 ({reason})"


async def _handle_business_tool(
    tool_name: str, tool_args: dict, tools_by_name: Dict, state: AgentState, writer
) -> str:
    """执行业务工具（vector_search / keyword_search / get_current_time 等）"""
    tool_func = tools_by_name.get(tool_name)
    if tool_func is None:
        return f"错误: 未知工具 '{tool_name}'"

    # 推送 step_start 事件
    if writer:
        writer({
            "type": "step_start",
            "step_id": tool_name,
            "tool_name": tool_name,
            "reason": tool_args.get("query", tool_args.get("city", tool_args.get("condition", ""))),
        })

    # 执行工具
    import asyncio
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

    # 更新 plan 中的对应步骤
    plan = state.get("plan", [])
    for s in plan:
        if s["tool_name"] == tool_name and s["status"] in ("pending", "running"):
            s["status"] = status
            s["result"] = result_str
            state["tool_results"][s["id"]] = result_str
            break

    # 推送 step_done 事件
    if writer:
        writer({
            "type": "step_done",
            "step_id": tool_name,
            "status": status,
        })

    logger.info(f"[Execute] 工具 {tool_name}: {status}")
    return result_str


def _get_stop_reason(msg) -> str:
    """从 AIMessage 提取 stop_reason"""
    if hasattr(msg, 'response_metadata') and isinstance(msg.response_metadata, dict):
        return msg.response_metadata.get("stop_reason", "")
    # ChatAnthropic 可能将 stop_reason 放在 additional_kwargs 中
    if hasattr(msg, 'additional_kwargs') and isinstance(msg.additional_kwargs, dict):
        return msg.additional_kwargs.get("stop_reason", "")
    # 通过 tool_calls 推断
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        return "tool_use"
    return "end_turn"


def _extract_tool_calls(msg) -> list:
    """从 AIMessage 提取 tool_calls"""
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        return msg.tool_calls
    # ChatAnthropic 返回的 content blocks 格式
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
