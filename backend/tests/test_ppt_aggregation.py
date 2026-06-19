"""P4: PPT 幻灯片逻辑聚合 — TDD 测试"""

import pytest


class TestPPTSlideAggregation:
    """企业级验收标准：同幻灯片元素聚合为一个完整观点，保留 slide 编号"""

    def test_aggregates_elements_by_slide(self):
        """多个幻灯片元素按 slide 聚合"""
        from app.rag.document_handler.format_preserver import aggregate_by_slide

        # 模拟 unstructured 提取的同幻灯片元素
        elements = _make_elements([
            (0, "Title", "Q4 业绩报告"),
            (0, "NarrativeText", "本季度营收增长 20%，超出预期。"),
            (0, "ListItem", "新产品线贡献 30%"),
            (1, "Title", "下一步计划"),
            (1, "NarrativeText", "继续拓展海外市场，加强研发投入。"),
        ])

        agg = aggregate_by_slide(elements, source_path="report.pptx")

        assert len(agg) == 2, f"应聚合为2个文档，实际: {len(agg)}"
        # Slide 1
        assert agg[0].metadata["page"] == 1
        assert "Q4 业绩报告" in agg[0].page_content
        assert "营收增长 20%" in agg[0].page_content
        assert "新产品线" in agg[0].page_content
        # Slide 2
        assert agg[1].metadata["page"] == 2
        assert "下一步计划" in agg[1].page_content
        assert "海外市场" in agg[1].page_content

    def test_slide_number_in_metadata(self):
        """每页 Document 的 metadata 包含正确的 slide 编号"""
        from app.rag.document_handler.format_preserver import aggregate_by_slide

        elements = _make_elements([
            (0, "Title", "封面"),
            (1, "NarrativeText", "内容"),
            (2, "NarrativeText", "结尾"),
        ])

        agg = aggregate_by_slide(elements, source_path="test.pptx")
        assert agg[0].metadata["page"] == 1
        assert agg[1].metadata["page"] == 2
        assert agg[2].metadata["page"] == 3  # slide_number+1

    def test_preserves_formatting_in_aggregation(self):
        """聚合后保留元素格式（Title→#, ListItem→-）"""
        from app.rag.document_handler.format_preserver import aggregate_by_slide

        elements = _make_elements([
            (0, "Title", "系统架构"),
            (0, "ListItem", "微服务架构"),
            (0, "ListItem", "容器化部署"),
        ])

        agg = aggregate_by_slide(elements, source_path="arch.pptx")
        content = agg[0].page_content
        assert "# 系统架构" in content
        assert "- 微服务架构" in content
        assert "- 容器化部署" in content

    def test_empty_elements_returns_empty(self):
        """空元素列表返回空"""
        from app.rag.document_handler.format_preserver import aggregate_by_slide

        agg = aggregate_by_slide([], source_path="empty.pptx")
        assert agg == []

    def test_single_slide_multi_element(self):
        """单幻灯片多元素不作切割（保持完整观点）"""
        from app.rag.document_handler.format_preserver import aggregate_by_slide

        elements = _make_elements([
            (0, "Title", "核心观点"),
            (0, "NarrativeText", "RAG 的优势有三点："),
            (0, "ListItem", "第一，可以实时更新知识"),
            (0, "ListItem", "第二，可以引用来源"),
            (0, "ListItem", "第三，可以降低幻觉"),
        ])

        agg = aggregate_by_slide(elements, source_path="view.pptx")
        assert len(agg) == 1, "单页应保持完整观点不切碎"
        assert "核心观点" in agg[0].page_content
        assert "降低幻觉" in agg[0].page_content


def _make_elements(items):
    """构造模拟 unstructured element 对象列表"""
    class _FakeElement:
        def __init__(self, slide_idx, category, text):
            self.category = category
            self._text = text
            self.metadata = _FakeMeta(slide_idx)

        def __str__(self):
            return self._text

    class _FakeMeta:
        def __init__(self, slide_idx):
            self.page_number = slide_idx + 1  # unstructured 从 1 开始编号

    return [_FakeElement(s, c, t) for s, c, t in items]
