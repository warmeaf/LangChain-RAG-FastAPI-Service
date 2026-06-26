import datetime
from typing import List, Optional
from contextvars import ContextVar

from langchain_core.tools import tool

from app.core.logger_handler import logger
from app.rag.rag_service import RagService
from app.rag.reorder_service import reorder_service
from app.utils.auth_utils import decode_django_jwt

current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)


def set_current_user_id(user_id: str):
    """设置当前用户ID到上下文"""
    current_user_id_var.set(user_id)


def get_current_user_id_from_context() -> str:
    """从上下文获取当前用户ID"""
    return current_user_id_var.get()


@tool(description="用于从向量数据库里检索文档并生成摘要，返回包含文档列表和摘要的结果。返回格式为：'摘要: [摘要内容]\n\n检索到的文档列表:\n1. [文档1内容]\n2. [文档2内容]\n...'。注意：文档已经过自动重排序，无需再调用重排序工具")
async def rag_summary_tools(query: str, user_id: str = None) -> str:
    """RAG 摘要工具"""
    effective_user_id = user_id or get_current_user_id_from_context()
    if not effective_user_id:
        return "错误: 无法确定用户身份，请提供有效的user_id"

    # 使用 langgraph 的 get_stream_writer 推送 thinking 事件
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        async def _thinking_callback(data: dict):
            writer(data)
    except Exception:
        _thinking_callback = None

    result = await RagService(effective_user_id, thinking_callback=_thinking_callback).get_documents_and_summary(query)
    documents = result.get("documents", [])
    documents_meta = result.get("documents_meta", [])
    summary = result.get("summary", "")

    formatted_result = f"摘要: {summary}\n\n"
    formatted_result += "检索到的文档列表（已重排序）:\n"
    for i, doc in enumerate(documents, 1):
        # 若有元信息可用，标注页码（PPT 幻灯片编号），帮助 LLM 回答结构类问题
        meta_label = ""
        if i - 1 < len(documents_meta):
            md = documents_meta[i - 1].get("metadata", {})
            page = md.get("page")
            total = md.get("total_slides")
            if page and total:
                meta_label = f" [第{page}页/共{total}页]"
            elif page:
                meta_label = f" [第{page}页]"
        formatted_result += f"{i}.{meta_label} {doc}\n"

    return formatted_result


@tool(description="用于对文档列表进行重排序，传入查询语句query和文档列表documents，返回重排序后的文档列表，包含文档内容和相似度。注意：rag_summary_tools已内置重排序功能，通常不需要单独调用此工具")
async def reorder_documents_tools(query: str, documents: List[str]) -> str:
    """重排序文档工具"""
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        async def _thinking_callback(data: dict):
            writer(data)
    except Exception:
        _thinking_callback = None

    result = await reorder_service.reorder_documents(query, documents, thinking_callback=_thinking_callback)
    if result["success"]:
        formatted_result = await reorder_service.format_reorder_result(result["documents"])
        logger.info(formatted_result)
        return formatted_result
    else:
        return f"重排序失败: {result['error']}"


@tool(description="当用户明确问自己的ID和用户名时，从JWT中获取当前用户ID和用户名，参数为完整的JWT token字符串")
async def get_user_info_tools(token: str) -> str:
    """获取用户信息工具"""
    payload = decode_django_jwt(token)
    if payload:
        user_id = payload.get("user_id", "未知")
        user_name = payload.get("user_name", "未知")
        return f"用户信息：\n- 用户ID: {user_id}\n- 用户名: {user_name}"
    else:
        return "无法解析JWT token，无法获取用户信息"


@tool(description="用于获取天气信息，需要提供城市名称作为参数，你需要从用户输入中提取城市名称，是str类型")
async def get_weather_tools(city: str = None) -> str:
    """获取天气工具"""
    if not city:
        return "请提供城市名称"
    return f"【{city}】的天气是晴朗的"


@tool(description="用于获取当前年月日时分的工具")
async def what_time_is_now() -> str:
    """获取当前年月日时的工具"""
    return f"当前时间是：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"


@tool(description="执行只读 SQL 查询，查询知识库中文档的结构化元数据信息。\n"
       "注意：工具会自动限制为当前用户的数据，无需在 SQL 中写 user_id 条件。\n\n"
       "可查询的表：doc_weights\n"
       "字段：user_id, doc_md5, doc_filename, category, weight, quality_score, updated_at\n\n"
       "示例：\n"
       "  SELECT COUNT(*) FROM doc_weights\n"
       "  SELECT doc_filename, category FROM doc_weights\n"
       "  SELECT * FROM doc_weights WHERE doc_filename LIKE '%算法%'\n"
       "  SELECT * FROM doc_weights ORDER BY updated_at DESC LIMIT 5\n\n"
       "限制：\n"
       "1. 仅 SELECT\n"
       "2. 自动按用户隔离\n"
       "3. 不适合语义理解问题，请用 rag_summary_tools")
async def execute_readonly_sql(sql_query: str, user_id: str = None) -> str:
    """执行只读 SQL 查询"""
    effective_user_id = user_id or get_current_user_id_from_context()
    if not effective_user_id:
        return "错误: 无法确定用户身份，请提供有效的user_id"

    # 安全检查
    sql_upper = sql_query.strip().upper()

    # 1) 必须是以 SELECT 开头
    if not sql_upper.startswith('SELECT'):
        return (
            "此工具仅允许 SELECT 查询。你提交的 SQL 不是 SELECT 类型，已被拒绝。\n"
            "请改写为 SELECT 语句后重试。\n"
            "正确示例：\n"
            "  SELECT COUNT(*) FROM doc_weights\n"
            "  SELECT doc_filename, category FROM doc_weights\n"
            "  SELECT * FROM doc_weights WHERE doc_filename LIKE '%关键词%'"
        )

    # 2) 黑名单禁止写操作关键词
    FORBIDDEN = ['INSERT ', 'UPDATE ', 'DELETE ', 'DROP ', 'ALTER ',
                 'CREATE ', 'TRUNCATE ', 'REPLACE ', 'EXEC ', 'CALL ']
    for kw in FORBIDDEN:
        if kw in f" {sql_upper} ":
            return (
                f"检测到不允许的关键词 [{kw.strip()}]。此工具仅执行 SELECT 查询。\n"
                f"请仅使用 SELECT 语句。"
            )

    # 3) 自动注入 user_id 过滤（强制用户数据隔离）
    sql_query = _inject_user_filter(sql_query, effective_user_id)

    # 4) 自动追加 LIMIT
    sql_upper = sql_query.upper()
    if 'LIMIT' not in sql_upper:
        sql_query = sql_query.rstrip('; \t') + ' LIMIT 100'

    # 执行查询
    try:
        from sqlalchemy import text
        from app.db.db_config import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(text(sql_query))
            rows = result.fetchall()

            if not rows:
                return "查询结果为空，没有找到匹配的记录。"

            columns = list(result.keys())
            header = " | ".join(columns)
            separator = "-" * min(80, max(len(header), 20))
            lines = [f"查询结果（共 {len(rows)} 条）:", "", header, separator]

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
            f"doc_weights 表字段：user_id, doc_md5, doc_filename, category, "
            f"weight, quality_score, updated_at\n\n"
            f"示例：\n"
            f"  SELECT COUNT(*) FROM doc_weights\n"
            f"  SELECT * FROM doc_weights WHERE doc_filename LIKE '%关键词%' LIMIT 10"
        )


def _inject_user_filter(sql: str, user_id: str) -> str:
    """在 SQL 中强制注入 user_id 过滤条件，确保只能查当前用户的数据。"""
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
