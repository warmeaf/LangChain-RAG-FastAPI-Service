"""测试 1.4: OCR 后处理纠错 + 2.2: 动态权重 + 2.3: Reranker + 2.4: 多因素排序"""

import pytest


# ════════════════ 1.4 OCR 后处理 ════════════════

class TestOCRPostProcess:
    """企业级验收标准：OCR 常见错字纠正确认"""

    def test_corrections(self):
        """P5: 扩展 OCR 纠错词表 — 原有 5 条 + 新增"""
        from app.rag.document_handler.ocr_processor import OCRProcessor
        op = OCRProcessor()
        # 原有
        assert op._post_process("白勺") == "的"
        assert op._post_process("己经") == "已经"
        assert op._post_process("土也") == "地"
        assert op._post_process("午") == "年"
        # P5 新增：常见形近字纠错
        assert op._post_process("人账") == "入账"
        assert op._post_process("曰期") == "日期"
        assert op._post_process("末来") == "未来"
        assert op._post_process("千扰") == "干扰"
        assert op._post_process("折口") == "折扣"
        assert op._post_process("折和") == "折扣"

    def test_correction_in_context(self):
        from app.rag.document_handler.ocr_processor import OCRProcessor
        op = OCRProcessor()
        text = "这是白勺测试，己经完成。"
        result = op._post_process(text)
        assert "的测试" in result
        assert "已经完成" in result

    def test_extended_corrections_in_context(self):
        """P5 扩展：复杂上下文中批量纠错"""
        from app.rag.document_handler.ocr_processor import OCRProcessor
        op = OCRProcessor()
        text = "请确认人账曰期，末来三天内处理千扰问题，享受折和优惠。"
        result = op._post_process(text)
        assert "入账" in result
        assert "日期" in result
        assert "未来" in result
        assert "干扰" in result
        assert "折扣" in result

    def test_no_change_on_correct_text(self):
        from app.rag.document_handler.ocr_processor import OCRProcessor
        op = OCRProcessor()
        text = "这是一段正常的文字。"
        result = op._post_process(text)
        assert result == text

    def test_partial_word_not_over_corrected(self):
        """P5: 不应对正确词语过度纠错"""
        from app.rag.document_handler.ocr_processor import OCRProcessor
        op = OCRProcessor()
        # "人口" 不应变成 "入口"
        assert op._post_process("人口普查") == "人口普查"
        # "昨日" 不应被修改
        assert op._post_process("昨日重现") == "昨日重现"
        # "周末" 不应变成 "周未"
        assert op._post_process("周末愉快") == "周末愉快"


# ════════════════ 2.2 动态权重 ════════════════

class TestDynamicWeights:
    """企业级验收标准：精确查询偏重 BM25，语义查询偏重向量"""

    @pytest.mark.asyncio
    async def test_precise_query_prefers_bm25(self):
        """精确查询（含编号 E12345）→ BM25 ≥ 0.6"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights("员工编号 E12345 的工资")
        assert w[0] >= 0.6, f"精确查询 BM25 权重应 ≥0.6，实际 {w[0]}"
        assert w[0] > w[1], f"精确查询 BM25 应 > 向量"

    @pytest.mark.asyncio
    async def test_balanced_query(self):
        """短查询 → 均衡权重"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights("hello")
        assert w[0] == 0.5 and w[1] == 0.5, f"短查询应均衡，实际 {w}"

    @pytest.mark.asyncio
    async def test_date_triggers_precise(self):
        """日期触发精确模式"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights("2024-01-15 的会议记录")
        assert w[0] >= 0.6, f"日期应触发精确模式"

    @pytest.mark.asyncio
    async def test_null_query_defaults(self):
        """空查询返回默认权重"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights(None)
        assert w == [0.5, 0.5]

    @pytest.mark.asyncio
    async def test_email_triggers_precise(self):
        """邮箱触发精确模式"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights("联系 user@example.com")
        assert w[0] >= 0.6

    @pytest.mark.asyncio
    async def test_url_triggers_precise(self):
        """URL 触发精确模式"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights("查看 https://docs.example.com")
        assert w[0] >= 0.6

    @pytest.mark.asyncio
    async def test_version_triggers_precise(self):
        """版本号触发精确模式"""
        from app.rag.milvus_store import MilvusService
        w = await MilvusService.get_dynamic_weights("升级到 v2.3.1")
        assert w[0] >= 0.6


# ════════════════ 2.3 Reranker ════════════════

class TestReranker:
    """企业级验收标准：报销文档排在年假文档前面，分数在 [0,1]"""

    @pytest.mark.asyncio
    async def test_relevance_ordering(self):
        """报销文档 > 年假文档"""
        from app.rag.reorder_service import reorder_service
        result = await reorder_service.reorder_documents(
            "怎么申请报销",
            [
                "报销流程：先填写报销单，然后提交给财务部审核。需要部门经理签字。",
                "公司年假政策：员工每年有10天年假，其中5天必须在上半年使用。",
                "报销表格可以在公司内网下载，支持电子签名。",
                "会议室预定系统使用指南：登录后选择时间即可预定。",
            ],
        )
        assert result["success"], f"Reranker 失败: {result.get('error')}"
        docs = result["documents"]
        first_text = docs[0]["document"]
        assert "报销" in first_text, f"第一个文档应是报销相关，实际: {first_text[:60]}"

    @pytest.mark.asyncio
    async def test_scores_normalized(self):
        """分数在 [0, 1] 区间"""
        from app.rag.reorder_service import reorder_service
        result = await reorder_service.reorder_documents(
            "测试查询",
            ["文档A内容", "文档B内容", "文档C内容"],
        )
        assert result["success"]
        for doc in result["documents"]:
            assert 0.0 <= doc["similarity"] <= 1.0, \
                f"分数 {doc['similarity']} 不在 [0,1]"

    @pytest.mark.asyncio
    async def test_stable_sorting(self):
        """相同输入多次调用排序一致"""
        from app.rag.reorder_service import reorder_service
        docs = ["A", "B", "C", "D"]
        r1 = await reorder_service.reorder_documents("query", docs)
        r2 = await reorder_service.reorder_documents("query", docs)
        if r1["success"] and r2["success"]:
            s1 = [d["document"] for d in r1["documents"]]
            s2 = [d["document"] for d in r2["documents"]]
            assert s1 == s2, "排序应稳定"

    @pytest.mark.asyncio
    async def test_empty_documents(self):
        """空文档列表正常返回"""
        from app.rag.reorder_service import reorder_service
        result = await reorder_service.reorder_documents("query", [])
        assert result["success"]
        assert result["documents"] == []


# ════════════════ 2.4 多因素排序 ════════════════

class TestMultiFactorRanker:
    """企业级验收标准：时间衰减 + 文档权重正确生效"""

    @pytest.mark.asyncio
    async def test_time_decay_newer_first(self):
        """相同相关性下，新文档 > 旧文档"""
        import time
        from langchain_core.documents import Document
        from app.rag.multi_factor_ranker import MultiFactorRanker

        now = int(time.time())
        one_year_ago = now - 365 * 24 * 3600
        docs = [
            Document(page_content="旧文档", metadata={
                "created_at": one_year_ago, "doc_weight": 1.0, "md5": "old"
            }),
            Document(page_content="新文档", metadata={
                "created_at": now, "doc_weight": 1.0, "md5": "new"
            }),
        ]
        result = await MultiFactorRanker().rank("查询", docs, [0.8, 0.8])
        assert result[0].page_content == "新文档", \
            f"新文档应排第一，实际: {result[0].page_content}"

    @pytest.mark.asyncio
    async def test_higher_weight_ranks_higher(self):
        """高权重文档排名靠前"""
        import time
        from langchain_core.documents import Document
        from app.rag.multi_factor_ranker import MultiFactorRanker

        now = int(time.time())
        docs = [
            Document(page_content="低权重", metadata={
                "created_at": now, "doc_weight": 0.3, "md5": "low"
            }),
            Document(page_content="高权重", metadata={
                "created_at": now, "doc_weight": 1.0, "md5": "high"
            }),
        ]
        result = await MultiFactorRanker().rank("查询", docs, [0.8, 0.8])
        assert result[0].page_content == "高权重", \
            f"高权重应排第一，实际: {result[0].page_content}"

    @pytest.mark.asyncio
    async def test_respects_max_documents(self):
        """返回文档数 ≤ max_documents"""
        import time
        from langchain_core.documents import Document
        from app.rag.multi_factor_ranker import MultiFactorRanker

        now = int(time.time())
        docs = [
            Document(page_content=f"doc{i}", metadata={
                "created_at": now, "doc_weight": 1.0, "md5": str(i)
            })
            for i in range(20)
        ]
        scores = [0.5 + i * 0.02 for i in range(20)]
        result = await MultiFactorRanker().rank("查询", docs, scores)
        from app.utils.config import rag_config
        max_docs = rag_config["retrieval"]["max_documents"]
        assert len(result) <= max_docs, f"应 ≤ {max_docs}，实际 {len(result)}"
