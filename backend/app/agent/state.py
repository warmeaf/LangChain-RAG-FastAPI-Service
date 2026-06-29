"""Agent State 数据模型定义

基于 Anthropic Messages API 的 content blocks 格式管理对话历史。
"""

from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage


class Step(TypedDict):
    """检索计划中的单个步骤"""
    id: str                # 步骤唯一标识
    tool_name: str         # 工具名
    tool_args: dict        # 工具参数
    reason: str            # 为什么需要这个步骤
    depends_on: list[str]  # 依赖的 step id 列表
    status: str            # pending | running | done | failed | skipped
    result: Optional[str]  # 工具返回结果（执行后填充）


class AgentState(TypedDict):
    """Agent 全局状态

    messages 使用手动 append 模式，不使用 LangGraph 的 MessagesState 自动合并。
    消息格式遵循 Anthropic Messages API content blocks 规范。
    """
    messages: list          # 对话历史（Anthropic content blocks 兼容格式）
    plan: list[Step]        # 当前检索计划
    current_step: int       # 当前执行到第几步（索引）
    replan_count: int       # 已重规划次数
    tool_results: dict      # 工具执行结果汇总 {step_id: result}
    final_answer: str       # 最终回答（Summarization 节点产出）
    session_id: str         # 会话 ID（持久化使用）
    user_id: str            # 用户 ID（系统注入，LLM 不可见）
