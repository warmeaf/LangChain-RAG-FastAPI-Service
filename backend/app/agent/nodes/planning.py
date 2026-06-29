"""Planning 节点

分析用户问题，制定检索计划，调用 create_plan 元工具。
"""

import json
from typing import List, Callable

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from app.agent.state import AgentState, Step
from app.prompt.tool_xml import tools_to_xml, tools_to_json_schemas
from app.prompt.tool_xml import tool_to_json_schema
from app.utils.prompt_loader import build_stage_prompt
from app.utils.factory import create_anthropic_model
from app.agent.meta_tools.create_plan import create_plan
from app.core.logger_handler import logger

# Planning 最大重试次数
MAX_PLANNING_RETRIES = 3


async def planning_node(state: AgentState, tools: List[Callable]) -> AgentState:
    """Planning 节点：LLM 分析问题 → 调用 create_plan 制定检索计划

    如果 planning 失败（JSON 解析错误等），重试最多 3 次。

    Args:
        state: 当前 Agent 状态
        tools: 可用工具列表（不含元工具）

    Returns:
        更新后的 AgentState（plan 字段已填充）
    """
    # 构建系统提示词（planning 层 + 工具描述）
    meta_tool_xml = tools_to_xml([create_plan])
    all_xml = tools_to_xml(tools) + "\n\n" + meta_tool_xml
    system_prompt = build_stage_prompt("planning", all_xml)

    # 构建 Anthropic-format tools（JSON Schema）
    tool_schemas = tools_to_json_schemas(tools)
    tool_schemas.append(tool_to_json_schema(create_plan))

    llm = create_anthropic_model(temperature=0.2)
    llm_with_tools = llm.bind_tools(tool_schemas, tool_choice="any")

    # 构建对话消息
    messages = [SystemMessage(content=system_prompt)]
    messages.extend(state.get("messages", []))

    # 如果还没有用户消息，添加一个当前查询提示
    user_query = state.get("messages", [])[-1].content if state.get("messages") else "请制定检索计划"

    for attempt in range(MAX_PLANNING_RETRIES):
        try:
            logger.info(f"[Planning] 第 {attempt + 1} 次尝试...")
            response = await llm_with_tools.ainvoke(messages)

            # 提取 tool_use
            tool_calls = _extract_tool_calls(response)
            if not tool_calls:
                logger.warning("[Planning] LLM 未调用任何工具")
                if attempt < MAX_PLANNING_RETRIES - 1:
                    messages.append(response)
                    messages.append(HumanMessage(content="请调用 create_plan 工具提交检索计划"))
                    continue
                else:
                    # 最终降级：空计划
                    state["plan"] = []
                    state["current_step"] = 0
                    return state

            # 查找 create_plan 调用
            for tc in tool_calls:
                if tc.get("name") == "create_plan":
                    steps_data = tc.get("args", {}).get("steps", [])
                    if isinstance(steps_data, str):
                        steps_data = json.loads(steps_data)

                    plan = _parse_steps(steps_data)
                    if plan:
                        # 更新消息历史
                        messages.append(response)
                        tool_result = ToolMessage(
                            content=f"计划已创建，共 {len(plan)} 步",
                            tool_call_id=tc.get("id", ""),
                        )
                        messages.append(tool_result)

                        state["plan"] = plan
                        state["current_step"] = 0
                        state["messages"] = messages
                        logger.info(f"[Planning] 计划创建成功: {len(plan)} 步")
                        return state

            logger.warning("[Planning] create_plan 未找到或参数无效")
            if attempt < MAX_PLANNING_RETRIES - 1:
                messages.append(response)
                messages.append(HumanMessage(content="create_plan 调用格式错误，请检查 steps 参数"))

        except Exception as e:
            logger.error(f"[Planning] 错误: {e}", exc_info=True)
            if attempt < MAX_PLANNING_RETRIES - 1:
                messages.append(HumanMessage(content=f"出错了: {e}，请重试"))

    # 全部重试失败
    state["plan"] = []
    state["current_step"] = 0
    return state


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


def _parse_steps(steps_data: list) -> list:
    """解析 steps 数据为 Step 列表"""
    if not isinstance(steps_data, list):
        return []

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
    return plan
