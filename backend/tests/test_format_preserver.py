"""P3: Word/PPT 格式保留增强 — TDD 测试"""

import pytest


class TestFormatPreserverEnhanced:
    """企业级验收标准：保留 Bold→**text**、Italic→*text*、Table→Markdown"""

    def test_preserves_bold_to_markdown(self):
        """加粗文本转为 **text** 格式"""
        from app.rag.document_handler.format_preserver import _format_text

        # 模拟 unstructured Bold 元素
        result = _format_text("重要提示", category="Bold")
        assert result == "**重要提示**", f"Bold 应转为 Markdown，实际: {result!r}"

    def test_preserves_italic_to_markdown(self):
        """斜体文本转为 *text* 格式"""
        from app.rag.document_handler.format_preserver import _format_text

        result = _format_text("注释说明", category="Italic")
        assert result == "*注释说明*", f"Italic 应转为 Markdown，实际: {result!r}"

    def test_preserves_underline(self):
        """下划线保留标记"""
        from app.rag.document_handler.format_preserver import _format_text

        result = _format_text("关键术语", category="Underline")
        assert result == "_关键术语_", f"Underline 应转下划线标记，实际: {result!r}"

    def test_title_header_listitem_unchanged(self):
        """已实现的 Title/Header/ListItem 行为不变"""
        from app.rag.document_handler.format_preserver import _format_text

        assert _format_text("文档标题", category="Title") == "# 文档标题"
        assert _format_text("节标题", category="Header") == "## 节标题"
        assert _format_text("列表项", category="ListItem") == "- 列表项"

    def test_narrative_text_unchanged(self):
        """正文不添加格式标记"""
        from app.rag.document_handler.format_preserver import _format_text

        result = _format_text("这是一段普通正文内容。", category="NarrativeText")
        assert result == "这是一段普通正文内容。"

    def test_unknown_category_unchanged(self):
        """未知类别不修改"""
        from app.rag.document_handler.format_preserver import _format_text

        result = _format_text("一些内容", category="UnknownCategory")
        assert result == "一些内容"

    def test_empty_text_handled(self):
        """空文本安全处理"""
        from app.rag.document_handler.format_preserver import _format_text

        assert _format_text("", category="Bold") == ""
        assert _format_text("  ", category="Italic") == "  "
