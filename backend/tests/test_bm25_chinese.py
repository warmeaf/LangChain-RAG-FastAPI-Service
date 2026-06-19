"""P0: BM25 中文分词修复 — TDD 测试"""

import pytest
from langchain_core.documents import Document


class TestBM25ChineseSegmentation:
    """企业级验收标准：BM25 对中文文本按词切分（非按字或无效空白切分）"""

    def test_chinese_corpus_is_word_tokenized(self):
        """验证中文语料库被正确分词（非 .split() 的空操作）"""
        from app.rag.retrievers.hybrid_retriever import BM25Retriever

        docs = [
            Document(page_content="员工申请报销流程说明", metadata={"id": "1"}),
            Document(page_content="公司年假政策规定每年十天", metadata={"id": "2"}),
            Document(page_content="会议室预定系统使用指南", metadata={"id": "3"}),
        ]

        retriever = BM25Retriever(documents=docs, k=3)

        # 分词后应有多个 token（不是整个字符串或单字）
        assert len(retriever._tokenized_corpus[0]) > 1, \
            f"中文应被分词为多 token，实际: {retriever._tokenized_corpus[0]}"
        # 不应是单个完整字符串（未分词）
        assert len(retriever._tokenized_corpus[0]) < len(docs[0].page_content), \
            f"分词后 token 数应小于原文字数"

    def test_chinese_query_is_word_tokenized(self):
        """验证中文查询被正确分词"""
        from app.rag.retrievers.hybrid_retriever import BM25Retriever

        docs = [
            Document(page_content="员工申请报销流程说明", metadata={"id": "1"}),
            Document(page_content="公司年假政策规定每年十天", metadata={"id": "2"}),
        ]
        retriever = BM25Retriever(documents=docs, k=2)

        query = "如何申请报销"
        query_tokens = retriever._tokenize(query)
        assert len(query_tokens) > 1, \
            f"查询分词后应有多个 token，实际: {query_tokens}"
        assert "申请" in query_tokens or "报销" in query_tokens, \
            f"关键词应出现在分词结果中，实际: {query_tokens}"

    def test_bm25_ranks_relevant_chinese_higher(self):
        """相关中文文档排名高于不相关文档"""
        from app.rag.retrievers.hybrid_retriever import BM25Retriever

        docs = [
            Document(page_content="公司年假政策规定每年十天", metadata={"id": "1"}),
            Document(page_content="报销流程：先填写报销单然后提交给财务部", metadata={"id": "2"}),
            Document(page_content="会议室预定系统使用指南登录后选择时间", metadata={"id": "3"}),
        ]
        retriever = BM25Retriever(documents=docs, k=3)

        results = retriever._get_relevant_documents("如何申请报销")
        assert len(results) > 0, "应有检索结果"
        # 报销文档应排第一
        assert "报销" in results[0].page_content, \
            f"报销文档应排第一，实际: {results[0].page_content[:50]}"

    def test_chinese_tokenizer_handles_english_mixed(self):
        """中英混合文本正常分词"""
        from app.rag.retrievers.hybrid_retriever import BM25Retriever

        docs = [
            Document(page_content="API 接口文档 v2.0 版本说明", metadata={"id": "1"}),
            Document(page_content="用户登录 authentication 流程", metadata={"id": "2"}),
        ]
        retriever = BM25Retriever(documents=docs, k=2)

        # 中英混合应正常分词，不报错
        tokens = retriever._tokenized_corpus[0]
        assert len(tokens) > 0, "中英混合文本应正常分词"
        # "API" 和 "接口" 应该各自成为独立 token
        has_api = any("API" in t for t in tokens)
        assert has_api, f"英文 'API' 应被保留为独立 token，实际: {tokens}"
