"""语言检测工具：基于 Unicode 字符集统计，无外部依赖，适合文本预处理管道"""

import re

# Unicode 范围
_CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F), # CJK Compatibility Ideographs Supplement
]

_LATIN_PATTERN = re.compile(r'[a-zA-Z]')
_CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')


def _count_cjk(text: str) -> int:
    """统计 CJK 字符数"""
    return len(_CJK_PATTERN.findall(text))


def _count_latin(text: str) -> int:
    """统计拉丁字母数"""
    return len(_LATIN_PATTERN.findall(text))


def detect_language(text: str) -> str:
    """
    检测文本主要语言。

    算法：比较 CJK 字符与拉丁字母的数量比例。
    - CJK > 拉丁 → zh
    - 拉丁 >= CJK → en
    - 空文本/无特征 → zh (默认中文环境)

    Args:
        text: 待检测文本

    Returns:
        "zh" 或 "en"
    """
    if not text or not text.strip():
        return "zh"

    cjk_count = _count_cjk(text)
    latin_count = _count_latin(text)

    if cjk_count == 0 and latin_count == 0:
        return "zh"  # 纯数字/符号，默认中文环境

    if cjk_count >= latin_count:
        return "zh"  # CJK >= 拉丁 → 中文为主（中文环境默认）
    else:
        return "en"
