"""Agent State 数据模型定义"""

from typing import TypedDict


class Step(TypedDict):
    """计划中的单个步骤 — LLM 的备忘录

    Plan 只记录"做什么 + 做到哪了"，不含工具参数或执行结果。
    LLM 根据 content 描述自行决定调用哪个业务工具。
    结果永远从 messages 中的 ToolMessage 获取。
    """
    id: str          # 步骤唯一标识
    content: str     # 自然语言描述要做什么
    status: str      # pending | in_progress | completed


class AgentState(TypedDict):
    """Agent 全局状态"""
    messages: list          # 对话历史（Anthropic content blocks 兼容格式）
    plan: list[Step]        # 当前计划备忘录
    replan_count: int       # 计划更新次数
    cycle_count: int        # 工具循环已执行轮数（防无限循环）
    rounds_since_plan_update: int  # 自上次 update_plan 后经过的轮数（提醒用）
    final_answer: str       # 最终回答（Summarization 节点产出）
    session_id: str         # 会话 ID
    user_id: str            # 用户 ID（系统注入，LLM 不可见）
