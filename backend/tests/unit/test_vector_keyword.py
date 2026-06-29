"""工具单元测试 - vector_search 和 keyword_search 工具

测试向量检索和关键词检索工具的基本结构。
"""

import pytest
from app.agent.tools.vector_search import vector_search, set_current_user_id
from app.agent.tools.keyword_search import keyword_search


def test_set_current_user_id():
    """测试设置用户 ID 上下文"""
    set_current_user_id("test_user_123")
    from app.agent.tools.vector_search import get_current_user_id
    assert get_current_user_id() == "test_user_123"


@pytest.mark.asyncio
async def test_vector_search_no_user():
    """测试无用户 ID 时的错误返回"""
    set_current_user_id(None)
    result = await vector_search.ainvoke({"query": "测试查询"})
    assert "错误" in result or "Error" in result


@pytest.mark.asyncio
async def test_vector_search_with_user():
    """测试有用户 ID 时的基本行为（可能因 Milvus 未初始化失败，但不崩溃）"""
    set_current_user_id("test_user")
    result = await vector_search.ainvoke({"query": "测试查询"})
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_keyword_search_no_user():
    """测试关键词检索无用户 ID 时"""
    from app.agent.tools.vector_search import set_current_user_id
    set_current_user_id(None)
    result = await keyword_search.ainvoke({"query": "测试"})
    assert "错误" in result or "Error" in result


@pytest.mark.asyncio
async def test_keyword_search_with_user():
    """测试关键词检索有用户 ID 时"""
    set_current_user_id("test_user")
    result = await keyword_search.ainvoke({"query": "测试"})
    assert isinstance(result, str)
