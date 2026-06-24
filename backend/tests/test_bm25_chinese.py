"""Milvus 2.5 原生 sparse BM25 中文检索集成测试。

标记 @pytest.mark.e2e，需连接 Milvus 服务。
用独立临时 collection，测试后自动清理，不污染正式数据。
"""

import os
import pytest
from pymilvus import MilvusClient, DataType, Function, FunctionType


pytestmark = [pytest.mark.e2e]


def _get_client():
    host = os.getenv("MILVUS_HOST", "localhost")
    port = int(os.getenv("MILVUS_PORT", 19530))
    return MilvusClient(uri=f"http://{host}:{port}")


def _create_test_collection(client, collection_name):
    """创建带 sparse BM25 的临时 collection"""
    schema = client.create_schema()
    schema.add_field("id", DataType.VARCHAR, max_length=128, is_primary=True)
    schema.add_field(
        "text", DataType.VARCHAR, max_length=65535,
        enable_analyzer=True,
        analyzer_params={"type": "chinese"},
    )
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)

    bm25_function = Function(
        name="text_bm25_emb",
        input_field_names=["text"],
        output_field_names=["sparse"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="sparse",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        params={"inverted_index_algo": "DAAT_MAXSCORE"},
    )

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )


def _insert_docs(client, collection_name, texts):
    """插入测试文档"""
    data = [{"id": str(i), "text": text} for i, text in enumerate(texts)]
    client.insert(collection_name=collection_name, data=data)
    client.flush(collection_name=collection_name)


def _search_sparse(client, collection_name, query, limit=3):
    """sparse BM25 检索"""
    results = client.search(
        collection_name=collection_name,
        data=[query],
        anns_field="sparse",
        param={"metric_type": "BM25"},
        limit=limit,
        output_fields=["text"],
    )
    return results


class TestSparseBM25Chinese:
    """Milvus 原生 sparse BM25 中文检索验收测试"""

    def test_sparse_bm25_chinese_search(self):
        """相关中文文档排名高于不相关文档"""
        client = _get_client()
        coll = "test_sparse_bm25_chinese"

        try:
            if client.has_collection(coll):
                client.drop_collection(coll)

            _create_test_collection(client, coll)
            _insert_docs(client, coll, [
                "公司年假政策规定每年十天",
                "报销流程：先填写报销单然后提交给财务部",
                "会议室预定系统使用指南登录后选择时间",
            ])

            results = _search_sparse(client, coll, "如何申请报销")
            assert len(results) > 0, "应有检索结果"
            assert len(results[0]) > 0, "应返回文档"

            top_text = results[0][0].get("entity", {}).get("text", "")
            assert "报销" in top_text, f"报销文档应排第一，实际: {top_text[:50]}"
        finally:
            if client.has_collection(coll):
                client.drop_collection(coll)

    def test_sparse_bm25_chinese_english_mixed(self):
        """中英混合文本正常检索"""
        client = _get_client()
        coll = "test_sparse_bm25_mixed"

        try:
            if client.has_collection(coll):
                client.drop_collection(coll)

            _create_test_collection(client, coll)
            _insert_docs(client, coll, [
                "API 接口文档 v2.0 版本说明",
                "用户登录 authentication 流程",
            ])

            results = _search_sparse(client, coll, "API 接口")
            assert len(results) > 0, "中英混合检索应返回结果"
            assert len(results[0]) > 0, "应返回文档"

            top_text = results[0][0].get("entity", {}).get("text", "")
            assert "API" in top_text, f"API 文档应排第一，实际: {top_text[:50]}"
        finally:
            if client.has_collection(coll):
                client.drop_collection(coll)

    def test_sparse_bm25_empty_collection(self):
        """空 collection 检索返回空列表"""
        client = _get_client()
        coll = "test_sparse_bm25_empty"

        try:
            if client.has_collection(coll):
                client.drop_collection(coll)

            _create_test_collection(client, coll)

            results = _search_sparse(client, coll, "测试查询")
            assert len(results) > 0, "应返回结果列表"
            assert len(results[0]) == 0, "空 collection 应返回零文档"
        finally:
            if client.has_collection(coll):
                client.drop_collection(coll)
