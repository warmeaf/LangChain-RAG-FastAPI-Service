"""P1: 英文 Embedding 模型自动切换 — 语言检测 TDD 测试"""

import pytest


class TestLanguageDetection:
    """企业级验收标准：准确检测文档主要语言，支持中/英/混合"""

    def test_detect_chinese_text(self):
        """纯中文文本识别为 zh"""
        from app.utils.language_detector import detect_language
        result = detect_language("员工申请报销流程说明，需要部门经理审批。")
        assert result == "zh", f"纯中文应为 zh，实际: {result}"

    def test_detect_english_text(self):
        """纯英文文本识别为 en"""
        from app.utils.language_detector import detect_language
        result = detect_language(
            "The employee reimbursement process requires department manager approval."
        )
        assert result == "en", f"纯英文应为 en，实际: {result}"

    def test_detect_chinese_dominant_in_mixed(self):
        """中英混合且中文为主 → zh"""
        from app.utils.language_detector import detect_language
        text = "API 接口文档说明了接口的调用方式和参数格式，开发者需要仔细阅读" * 3
        result = detect_language(text)
        assert result == "zh", f"中文为主的混合文本应为 zh，实际: {result}"

    def test_detect_english_dominant_in_mixed(self):
        """中英混合且英文为主 → en"""
        from app.utils.language_detector import detect_language
        text = (
            "The API documentation describes the interface calling methods "
            "and parameter formats. Developers need to read it carefully. "
            "This section covers authentication, rate limiting, and error handling."
        )
        result = detect_language(text)
        assert result == "en", f"英文为主的文本应为 en，实际: {result}"

    def test_detect_empty_text_returns_zh_default(self):
        """空文本默认返回 zh（中文环境）"""
        from app.utils.language_detector import detect_language
        assert detect_language("") == "zh"
        assert detect_language("123") == "zh"  # 纯数字无语言特征

    def test_detect_short_text(self):
        """短文本也能正确检测"""
        from app.utils.language_detector import detect_language
        assert detect_language("报销申请") == "zh"
        assert detect_language("Reimbursement") == "en"

    def test_detect_cjk_vs_latin_in_document_metadata(self):
        """可嵌入文档处理流程：接受 page_content 返回语言标签"""
        from app.utils.language_detector import detect_language
        from langchain_core.documents import Document

        zh_doc = Document(page_content="公司年度财务报告摘要，包含收入支出分析。", metadata={})
        en_doc = Document(page_content="Annual financial report summary with revenue analysis.", metadata={})

        assert detect_language(zh_doc.page_content) == "zh"
        assert detect_language(en_doc.page_content) == "en"
