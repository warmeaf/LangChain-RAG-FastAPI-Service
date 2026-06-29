"""工具单元测试 - metadata_filter_milvus 工具

测试 Milvus 标量过滤工具的自然语言转换和表达式生成。
"""

import pytest
from app.agent.tools.metadata_filter_milvus import (
    metadata_filter_milvus,
    _simple_rule_based_expr,
)


def test_simple_rule_entity_match():
    """测试简单规则：实体匹配"""
    result = _simple_rule_based_expr("doc_entity 是王小明")
    assert result is not None
    assert "王小明" in result
    assert "doc_entity" in result


def test_simple_rule_weight_compare():
    """测试简单规则：权重比较"""
    result = _simple_rule_based_expr("权重高于0.8的文档")
    assert result is not None
    assert "doc_weight" in result
    assert "0.8" in result


def test_simple_rule_no_match():
    """测试无匹配时返回 None"""
    result = _simple_rule_based_expr("这是一个无法解析的条件")
    assert result is None


@pytest.mark.asyncio
async def test_metadata_filter_no_milvus():
    """测试在 Milvus 未连接时的错误处理"""
    result = await metadata_filter_milvus.ainvoke({
        "condition": "doc_entity 是王小明",
        "user_id": "test_user",
    })
    # 可能返回错误（Milvus 未连接），但不是崩溃
    assert isinstance(result, str)
