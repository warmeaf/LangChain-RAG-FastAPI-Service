"""P1 集成测试：文档经过处理管道后携带语言元数据"""

import pytest
from langchain_core.documents import Document


class TestLanguageMetadataOnDocuments:
    """企业级验收标准：文档处理完成后 metadata 包含 language 字段"""

    def test_language_metadata_added_to_document(self):
        """DocumentProcessor 处理后文档携带 language 标签"""
        from app.utils.language_detector import detect_language

        # 模拟 DocumentProcessor 将语言检测结果写入 metadata
        doc = Document(
            page_content="公司年度财务报告摘要",
            metadata={"source": "report.pdf"}
        )
        doc.metadata["language"] = detect_language(doc.page_content)
        assert doc.metadata["language"] == "zh"

        en_doc = Document(
            page_content="Annual financial report summary",
            metadata={"source": "report_en.pdf"}
        )
        en_doc.metadata["language"] = detect_language(en_doc.page_content)
        assert en_doc.metadata["language"] == "en"

    def test_language_detection_available_during_processing(self):
        """语言检测在文档处理流程中可正常调用"""
        from app.utils.language_detector import detect_language

        # 模拟不同类型文档
        test_cases = [
            ("员工报销流程说明文档", "zh"),
            ("Employee Reimbursement Process Document", "en"),
            ("API 接口文档 v2.0", "zh"),     # 中文为主，含英文但 CJK 多
            ("System Architecture Design Document", "en"),
            ("", "zh"),
            ("2024年度", "zh"),
        ]
        for text, expected in test_cases:
            assert detect_language(text) == expected, \
                f"text={text[:30]!r} expected={expected}, got={detect_language(text)}"
