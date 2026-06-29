"""工具单元测试 - sql_query 工具

测试 SQL 查询工具的安全检查和用户隔离。
"""

import pytest
from app.agent.tools.sql_query import sql_query, _inject_user_filter, _nl_to_sql


def test_inject_user_filter_no_where():
    """测试没有 WHERE 子句时自动注入"""
    sql = "SELECT * FROM doc_weights"
    result = _inject_user_filter(sql, "user123")
    assert "WHERE user_id = 'user123'" in result


def test_inject_user_filter_with_where():
    """测试已有 WHERE 子句时追加 AND"""
    sql = "SELECT * FROM doc_weights WHERE category = '技术文档'"
    result = _inject_user_filter(sql, "user123")
    assert "user_id = 'user123'" in result
    assert "WHERE category" in result
    assert "AND user_id" in result


def test_inject_user_filter_with_order_by():
    """测试带 ORDER BY 时的注入位置"""
    sql = "SELECT * FROM doc_weights ORDER BY weight DESC"
    result = _inject_user_filter(sql, "user123")
    assert "WHERE user_id" in result
    assert "ORDER BY weight DESC" in result
    # WHERE 应在 ORDER BY 之前
    assert result.index("WHERE") < result.index("ORDER BY")


def test_inject_user_filter_with_limit():
    """测试带 LIMIT 时的注入位置"""
    sql = "SELECT * FROM doc_weights LIMIT 10"
    result = _inject_user_filter(sql, "user123")
    assert "WHERE user_id" in result
    assert "LIMIT 10" in result


@pytest.mark.asyncio
async def test_sql_query_rejects_non_select():
    """测试拒绝非 SELECT 语句"""
    from app.agent.tools.vector_search import set_current_user_id
    set_current_user_id("test_user")
    result = await sql_query.ainvoke({"query": "DELETE FROM doc_weights", "user_id": "test_user"})
    assert "仅允许 SELECT" in result


@pytest.mark.asyncio
async def test_sql_query_rejects_drop():
    """测试拒绝 DROP 语句"""
    from app.agent.tools.vector_search import set_current_user_id
    set_current_user_id("test_user")
    result = await sql_query.ainvoke({"query": "DROP TABLE doc_weights", "user_id": "test_user"})
    assert "不允许" in result or "仅允许 SELECT" in result


@pytest.mark.asyncio
async def test_sql_query_select_allowed():
    """测试 SELECT 语句被允许"""
    from app.agent.tools.vector_search import set_current_user_id
    set_current_user_id("test_user")
    result = await sql_query.ainvoke({"query": "SELECT 1 AS test", "user_id": "test_user"})
    assert "仅允许 SELECT" not in result
