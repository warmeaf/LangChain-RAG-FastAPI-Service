"""Summarization 节点

不走工具，LLM 直接输出纯文本作为最终回答。
综合所有工具结果，给出完整回答，引用来源，不确定时坦诚表述。
"""

from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
from langgraph.config import get_stream_writer

from app.agent.state import AgentState
from app.utils.prompt_loader import build_stage_prompt
from app.utils.factory import create_anthropic_streaming_model
from app.core.logger_handler import logger


async def summarization_node(state: AgentState) -> AgentState:
    """Summarization 节点：综合所有工具结果，生成最终回答

    使用 tool_choice="none" 禁止调用工具，强制纯文本输出。
    流式模式：逐 token 推送 delta SSE 事件。

    Args:
        state: 当前 Agent 状态（含所有工具执行结果）

    Returns:
        更新后的 AgentState（final_answer 已填充）
    """
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    # 构建系统提示词（summarization 层，无工具）
    system_prompt = build_stage_prompt("summarization", "(无可用的工具 — 请直接基于已有信息回答)")

    llm = create_anthropic_streaming_model(temperature=0.5, max_tokens=2048)
    # Summarization 不走工具：直接使用裸 LLM，不传 tools 参数
    # 注意：不能用 llm.bind_tools([], tool_choice="none")，DeepSeek 端点对该组合
    # 支持不佳，会导致返回空响应。

    # 构建回答上下文
    context = _build_summarization_context(state)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ]

    # 流式生成最终回答
    if writer:
        writer({"type": "answer_start"})

    full_answer = ""
    try:
        async for chunk in llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                content = chunk.content
                if isinstance(content, str) and content:
                    full_answer += content
                    if writer:
                        writer({"type": "delta", "content": content})
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            full_answer += text
                            if writer:
                                writer({"type": "delta", "content": text})
    except Exception as e:
        logger.error(f"[Summarization] 流式生成失败: {e}", exc_info=True)
        # 降级：非流式生成
        try:
            result = await llm.ainvoke(messages)
            full_answer = result.content if hasattr(result, 'content') else str(result)
            if isinstance(full_answer, list):
                full_answer = "".join(
                    b.get("text", "") for b in full_answer
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            if writer:
                writer({"type": "delta", "content": full_answer})
        except Exception as e2:
            logger.error(f"[Summarization] 非流式降级也失败: {e2}", exc_info=True)
            full_answer = f"抱歉，生成回答时出现错误: {e2}"

    state["final_answer"] = full_answer or "抱歉，我无法回答这个问题。"
    logger.info(f"[Summarization] 最终回答: {len(state['final_answer'])} 字符")

    return state


def _build_summarization_context(state: AgentState) -> str:
    """构建 Summarization 的输入上下文"""
    messages = state.get("messages", [])
    user_query = _get_user_query(messages)

    plan = state.get("plan", [])
    tool_results = state.get("tool_results", {})

    parts = [f"## 用户问题\n{user_query}\n"]

    if plan:
        parts.append("## 检索执行记录\n")
        for step in plan:
            status_icon = {"done": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⏳"}.get(step["status"], "❓")
            parts.append(f"### {status_icon} {step['id']}: {step['tool_name']}")
            parts.append(f"原因: {step['reason']}")
            parts.append(f"状态: {step['status']}")
            if step.get("result"):
                # 截断过长的结果
                result = step["result"]
                if len(result) > 3000:
                    result = result[:3000] + "\n... (内容过长已截断)"
                parts.append(f"结果:\n{result}")
            parts.append("")

    parts.append("## 请基于上述信息，生成完整、准确的回答\n")
    parts.append("要求：")
    parts.append("- 综合所有步骤的结果，不遗漏重要信息")
    parts.append("- 明确标注信息来源（文档名等）")
    parts.append("- 涉及数值和时间时仔细核对")
    parts.append("- 如果信息不足或矛盾，如实说明")
    parts.append("- 使用 Markdown 格式组织回答")

    return "\n".join(parts)


def _get_user_query(messages: list) -> str:
    """从 messages 中提取用户原始问题"""
    for msg in reversed(messages):
        role = getattr(msg, 'type', None) or getattr(msg, 'role', '')
        if role in ('human', 'user'):
            content = msg.content if hasattr(msg, 'content') else str(msg)
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
            elif isinstance(content, str):
                return content
    return "未知问题"
