"""只读 SQL 查询工具

从原 agent_tools.py 的 execute_readonly_sql 重写，增加自然语言转 SQL 能力。
合并原计划的 Metadata Filter (MySQL) 功能。
"""

from typing import Optional
from contextvars import ContextVar

from langchain_core.tools import tool

from app.core.logger_handler import logger

current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)

# 可用表和字段描述（供 LLM 生成 SQL 时参考）
TABLE_SCHEMA = """
可查询的表：doc_weights
字段说明：
  - user_id: 用户ID (VARCHAR)
  - doc_md5: 文档MD5值 (VARCHAR)
  - doc_filename: 文档文件名 (VARCHAR)
  - category: 文档分类 (VARCHAR)
  - weight: 文档权重 (FLOAT)
  - quality_score: 质量评分 (FLOAT)
  - impression_count: 展示次数 (INT)
  - click_count: 点击次数 (INT)
  - updated_at: 更新时间 (DATETIME)

支持的操作：SELECT（仅只读查询）
自动功能：按当前用户隔离数据，自动追加LIMIT 100
"""


@tool
async def sql_query(query: str, user_id: Optional[str] = None) -> str:
    """执行只读 SQL 查询，用于查询知识库中文档的结构化元数据信息。

    工具内部会将自然语言查询意图转为 SQL，并强制执行只读、用户隔离、结果限制。
    适合查询文档分类、权重、统计计数等结构化数据。

    可用数据表：doc_weights（文档权重表）
    字段：user_id, doc_md5, doc_filename, category, weight, quality_score, impression_count, click_count, updated_at

    Args:
        query: 自然语言查询意图描述（如"技术文档类别下权重高于0.8的文档有哪些"）
              或直接写 SELECT 语句
        user_id: 用户ID（系统自动注入，无需手动传入）
    """
    from app.agent.tools.vector_search import get_current_user_id
    effective_user_id = user_id or get_current_user_id()
    if not effective_user_id:
        return "错误: 无法确定用户身份"

    from sqlalchemy import text
    from app.db.db_config import AsyncSessionLocal

    # 尝试判断：如果 query 看起来像 SQL，直接使用；否则用 LLM 转换
    sql_text = query.strip()

    # 如果输入明显不是 SQL 也不是 SELECT，先检查是否为危险操作
    sql_upper_first = sql_text.upper().split()[0] if sql_text.split() else ""
    FORBIDDEN_FIRST = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
                       'CREATE', 'TRUNCATE', 'REPLACE', 'EXEC', 'CALL']
    if sql_upper_first in FORBIDDEN_FIRST:
        return (
            f"此工具仅允许 SELECT 查询。检测到禁止的关键词 [{sql_upper_first}]，已被拒绝。\n"
            f"请使用 SELECT 语句或自然语言描述查询意图。\n"
            f"{TABLE_SCHEMA}"
        )

    if not sql_text.upper().startswith("SELECT"):
        # 自然语言 → SQL 转换
        sql_text = await _nl_to_sql(query, effective_user_id)

    # 安全检查
    sql_upper = sql_text.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return (
            "此工具仅允许 SELECT 查询。你提交的 SQL 不是 SELECT 类型，已被拒绝。\n"
            "请改写为 SELECT 语句后重试。"
        )

    # 禁止写操作关键词
    FORBIDDEN = ['INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER ',
                 'CREATE ', 'TRUNCATE ', 'REPLACE ', 'EXEC ', 'CALL ']
    for kw in FORBIDDEN:
        if kw in f" {sql_upper} ":
            return f"检测到不允许的关键词 [{kw.strip()}]。此工具仅执行 SELECT 查询。"

    # 强制注入 user_id 过滤
    sql_text = _inject_user_filter(sql_text, effective_user_id)

    # 自动追加 LIMIT
    if 'LIMIT' not in sql_text.upper():
        sql_text = sql_text.rstrip('; \t') + ' LIMIT 100'

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(sql_text))
            rows = result.fetchall()

            if not rows:
                return "查询结果为空，没有找到匹配的记录。"

            columns = list(result.keys())
            header = " | ".join(columns)
            separator = "-" * min(80, max(len(header), 20))
            lines = [f"SQL查询结果（共 {len(rows)} 条）:", "", header, separator]

            for row in rows[:50]:
                formatted_row = " | ".join(
                    str(v) if v is not None else "NULL" for v in row
                )
                lines.append(formatted_row)

            if len(rows) > 50:
                lines.append(f"\n... 结果过多，仅显示前 50 条，共 {len(rows)} 条记录")

            return "\n".join(lines)

    except Exception as e:
        return (
            f"SQL 执行出错：{e}\n\n"
            f"请检查 SQL 语法或表名是否正确。\n"
            f"{TABLE_SCHEMA}"
        )


def _inject_user_filter(sql: str, user_id: str) -> str:
    """在 SQL 中强制注入 user_id 过滤条件"""
    cleaned = sql.rstrip('; \t')
    upper = cleaned.upper()
    CLAUSE_BOUNDARIES = ['GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING']

    if 'WHERE' in upper:
        where_end = len(cleaned)
        for kw in CLAUSE_BOUNDARIES:
            pos = upper.find(kw)
            if pos != -1 and pos < where_end:
                where_end = pos
        before = cleaned[:where_end].rstrip()
        after = cleaned[where_end:]
        return f"{before} AND user_id = '{user_id}' {after}"
    else:
        insert_pos = len(cleaned)
        for kw in CLAUSE_BOUNDARIES:
            pos = upper.find(kw)
            if pos != -1 and pos < insert_pos:
                insert_pos = pos
        before = cleaned[:insert_pos].rstrip()
        after = cleaned[insert_pos:]
        return f"{before} WHERE user_id = '{user_id}' {after}"


async def _nl_to_sql(natural_query: str, user_id: str) -> str:
    """将自然语言查询意图转为 SQL（使用 LLM 转换）"""
    from app.utils.factory import create_chat_model

    prompt = f"""{TABLE_SCHEMA}

请将以下自然语言查询转换为 SELECT 语句。只输出 SQL，不要任何解释。

查询意图：{natural_query}

要求：
1. 只输出一条 SELECT 语句
2. 不要包含 user_id 条件（系统会自动注入）
3. 使用标准 SQL 语法
"""
    try:
        llm = create_chat_model(streaming=False, temperature=0.1)
        result = await llm.ainvoke(prompt)
        sql = result.content.strip() if hasattr(result, 'content') else str(result).strip()
        # 清理 markdown 包裹
        if sql.startswith("```"):
            sql = sql.split("```sql", 1)[-1] if "```sql" in sql else sql.split("```", 1)[-1]
            sql = sql.rsplit("```", 1)[0]
        sql = sql.strip()
        if sql.upper().startswith("SELECT"):
            logger.info(f"NL→SQL 转换: {natural_query[:50]} → {sql[:100]}")
            return sql
    except Exception as e:
        logger.warning(f"NL→SQL 转换失败: {e}")

    # 降级：返回错误
    return f"无法理解查询意图，请直接提供 SELECT 语句。{TABLE_SCHEMA}"
