"""P2: PDF 章节结构识别 — TDD 测试"""

import pytest


# 模拟 fitz 文本块： (x0,y0,x1,y1, text, block_no, block_type)
# block_type: 0=text, 1=image


class TestPDFHeadingDetector:
    """企业级验收标准：从PDF文本块中检测标题层级并构建章节路径"""

    def test_detects_large_font_as_heading(self):
        """大字体文本块检测为标题"""
        from app.utils.pdf_heading_detector import PDFHeadingDetector

        blocks = [
            {"text": "第一章 概述", "font_size": 18.0, "bbox": (72, 100, 500, 118)},
            {"text": "这是正文内容。", "font_size": 10.0, "bbox": (72, 130, 500, 145)},
            {"text": "1.1 背景介绍", "font_size": 14.0, "bbox": (72, 160, 500, 174)},
            {"text": "更多正文。", "font_size": 10.0, "bbox": (72, 185, 500, 200)},
        ]

        detector = PDFHeadingDetector()
        headings = detector.extract_headings(blocks)

        assert len(headings) >= 2, f"应检测到至少2个标题，实际: {len(headings)}"
        assert headings[0]["text"] == "第一章 概述"
        assert headings[0]["level"] == 1
        assert headings[1]["text"] == "1.1 背景介绍"
        assert headings[1]["level"] == 2

    def test_heading_number_pattern_detection(self):
        """通过编号模式（1. / 1.1 / 第X章）检测标题"""
        from app.utils.pdf_heading_detector import PDFHeadingDetector

        blocks = [
            {"text": "第一章 系统架构", "font_size": 10.0, "bbox": (72, 100, 500, 110)},
            {"text": "2. 技术选型", "font_size": 10.0, "bbox": (72, 120, 500, 130)},
            {"text": "2.1 数据库方案", "font_size": 10.0, "bbox": (72, 140, 500, 150)},
            {"text": "正文内容。", "font_size": 10.0, "bbox": (72, 160, 500, 170)},
        ]

        detector = PDFHeadingDetector()
        headings = detector.extract_headings(blocks)

        assert len(headings) >= 3, f"编号模式应检测到标题，实际: {len(headings)}"
        assert headings[0]["level"] == 1  # 第一章
        assert headings[1]["level"] == 1  # 2.
        assert headings[2]["level"] == 2  # 2.1

    def test_builds_heading_path_context(self):
        """构建标题路径上下文（面包屑）"""
        from app.utils.pdf_heading_detector import PDFHeadingDetector

        blocks = [
            {"text": "第一章 概述", "font_size": 18.0, "bbox": (72, 100, 500, 118)},
            {"text": "1.1 系统目标", "font_size": 14.0, "bbox": (72, 130, 500, 144)},
            {"text": "正文内容A。", "font_size": 10.0, "bbox": (72, 155, 500, 165)},
            {"text": "1.2 适用范围", "font_size": 14.0, "bbox": (72, 175, 500, 189)},
            {"text": "正文内容B。", "font_size": 10.0, "bbox": (72, 200, 500, 210)},
            {"text": "第二章 详细设计", "font_size": 18.0, "bbox": (72, 225, 500, 243)},
            {"text": "正文内容C。", "font_size": 10.0, "bbox": (72, 255, 500, 265)},
        ]

        detector = PDFHeadingDetector()
        path_map = detector.build_heading_path(blocks)

        assert "正文内容A。" in path_map
        assert path_map["正文内容A。"] == ["第一章 概述", "1.1 系统目标"]
        assert path_map["正文内容B。"] == ["第一章 概述", "1.2 适用范围"]
        assert path_map["正文内容C。"] == ["第二章 详细设计"]

    def test_no_headings_returns_empty(self):
        """无标题文档返回空路径"""
        from app.utils.pdf_heading_detector import PDFHeadingDetector

        blocks = [
            {"text": "这是一段纯文本，没有标题结构。", "font_size": 10.0, "bbox": (72, 100, 500, 110)},
            {"text": "另一段正文。", "font_size": 10.0, "bbox": (72, 120, 500, 130)},
        ]

        detector = PDFHeadingDetector()
        headings = detector.extract_headings(blocks)
        assert headings == []

    def test_font_size_threshold_configurable(self):
        """字号阈值可配置"""
        from app.utils.pdf_heading_detector import PDFHeadingDetector

        blocks = [
            {"text": "标题A", "font_size": 12.0, "bbox": (72, 100, 500, 112)},
            {"text": "正文。", "font_size": 10.0, "bbox": (72, 120, 500, 130)},
        ]

        # 默认阈值 13.0，12px 不算标题
        detector_default = PDFHeadingDetector(font_size_threshold=13.0)
        assert detector_default.extract_headings(blocks) == []

        # 降低阈值到 11.0，12px 算标题
        detector_low = PDFHeadingDetector(font_size_threshold=11.0)
        headings = detector_low.extract_headings(blocks)
        assert len(headings) == 1
        assert headings[0]["text"] == "标题A"
