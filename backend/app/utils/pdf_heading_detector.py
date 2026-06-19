"""PDF 章节标题检测器：基于字号 + 编号模式识别标题层级，构建章节路径上下文"""

import re
from typing import List, Dict, Optional


# 常见中文标题编号模式
_HEADING_NUMBER_PATTERNS = [
    re.compile(r'^第[一二三四五六七八九十百千\d]+[章节部篇]\s'),   # 第X章 / 第X节
    re.compile(r'^[一二三四五六七八九十]+[、，,\s]'),              # 一、/ 二、
    re.compile(r'^\d+[\.\、\s]+\d+[\.\、\s]'),                      # 2.1 / 3.2.1
    re.compile(r'^\d+[\.\、\s]'),                                    # 1. / 2、
    re.compile(r'^[\(（]\d+[\)）]'),                                 # (1)
]


def _detect_heading_level(text: str) -> Optional[int]:
    """通过编号模式推断标题层级"""
    text = text.strip()

    for i, pattern in enumerate(_HEADING_NUMBER_PATTERNS):
        m = pattern.match(text)
        if m:
            if i == 0:
                return 1  # 第X章
            elif i == 1:
                return 1  # 一、二、三
            elif i == 2:
                return 2  # 2.1
            elif i == 3:
                return 1  # 1.
            elif i == 4:
                return 3  # (1)
    return None


def _looks_like_heading(text: str) -> bool:
    """启发式判断是否为标题：短文本、以大写/数字开头、不含句号"""
    text = text.strip()
    if len(text) > 50:
        return False
    if not text:
        return False
    # 不含句尾标点
    if re.search(r'[。；，、；]', text):
        return False
    return True


class PDFHeadingDetector:
    """PDF 标题检测器：从文本块列表 (font_size, text, bbox) 中识别标题层级"""

    def __init__(self, font_size_threshold: float = 13.0):
        """
        Args:
            font_size_threshold: 字号阈值，≥此值的文本块视为候选标题
        """
        self.font_size_threshold = font_size_threshold

    def extract_headings(self, blocks: List[dict]) -> List[dict]:
        """
        从文本块列表中提取标题。

        Args:
            blocks: 每项 {'text': str, 'font_size': float, 'bbox': tuple}

        Returns:
            [{'text': str, 'level': int, 'index': int}, ...]
        """
        headings = []
        for idx, block in enumerate(blocks):
            text = block.get("text", "").strip()
            if not text:
                continue

            font_size = block.get("font_size", 10.0)
            is_heading = False
            detected_level = None

            # 策略一：编号模式检测（优先级最高）
            pattern_level = _detect_heading_level(text)
            if pattern_level and _looks_like_heading(text):
                is_heading = True
                detected_level = pattern_level

            # 策略二：字号检测
            if not is_heading and font_size >= self.font_size_threshold:
                if _looks_like_heading(text):
                    is_heading = True
                    detected_level = 1  # 大字体默认为一级标题

            if is_heading and detected_level:
                headings.append({
                    "text": text,
                    "level": detected_level,
                    "index": idx,
                    "font_size": font_size,
                })

        return headings

    def build_heading_path(self, blocks: List[dict]) -> Dict[str, List[str]]:
        """
        为每个正文文本块构建标题路径上下文。

        Args:
            blocks: 文本块列表

        Returns:
            {正文文本: [父标题1, 父标题2, ...]}
            键为每个非标题文本块的前20字，值为当前生效的标题路径
        """
        headings = self.extract_headings(blocks)
        if not headings:
            return {}

        heading_stack: List[tuple] = []  # [(level, text), ...]
        result: Dict[str, List[str]] = {}
        heading_idx = 0

        for idx, block in enumerate(blocks):
            text = block.get("text", "").strip()
            if not text:
                continue

            # 检查当前块是否为已知标题
            if heading_idx < len(headings) and headings[heading_idx]["index"] == idx:
                h = headings[heading_idx]
                # 弹出同级及更深层标题
                while heading_stack and heading_stack[-1][0] >= h["level"]:
                    heading_stack.pop()
                heading_stack.append((h["level"], h["text"]))
                heading_idx += 1
                continue

            # 正文块：记录当前标题路径
            if heading_stack:
                key = text[:20]  # 用前20字作为键
                result[key] = [t for _, t in heading_stack]

        return result
