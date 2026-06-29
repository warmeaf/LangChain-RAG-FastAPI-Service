"""OCR 光学字符识别工具

包装现有 PaddleOCR 能力，提供 Agent 可调用的 OCR 工具。
安全：工具层校验路径合法性，防止路径遍历攻击。
"""

import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from app.core.logger_handler import logger
from app.utils.path_tool import get_project_root


# 允许访问的基础目录
_ALLOWED_BASE_DIRS = [
    str(get_project_root()),
    "/tmp",
]


@tool
async def ocr_recognize(file_path: str) -> str:
    """对图片或扫描版 PDF 进行 OCR 文字识别。

    使用 PaddleOCR 引擎识别图片中的文字内容。
    支持常见图片格式（PNG、JPG）和 PDF 文件。

    Args:
        file_path: 要识别的文件路径（绝对路径或相对于项目根目录的路径）
    """
    if not file_path:
        return "请提供文件路径"

    # 安全校验：路径合法性
    file_path = _validate_path(file_path)
    if file_path.startswith("Error:"):
        return file_path

    if not os.path.exists(file_path):
        return f"Error: 文件不存在: {file_path}"

    try:
        from paddleocr import PaddleOCR
        from PIL import Image
        import fitz

        ocr = PaddleOCR(lang="ch")

        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == '.pdf':
            # PDF 处理
            images = []
            fitz_doc = fitz.open(file_path)
            for page_num in range(len(fitz_doc)):
                page = fitz_doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append((page_num + 1, img))
            fitz_doc.close()
        else:
            # 图片处理
            img = Image.open(file_path)
            images = [(1, img)]

        all_text = []
        for page_num, image in images:
            import numpy as np
            img_array = np.array(image)
            result = ocr.ocr(img_array, cls=True)

            if not result or not result[0]:
                continue

            lines = []
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                if confidence > 0.7:
                    lines.append(text)

            if lines:
                page_text = "\n".join(lines)
                if len(images) > 1:
                    all_text.append(f"--- 第 {page_num} 页 ---\n{page_text}")
                else:
                    all_text.append(page_text)

        if not all_text:
            return f"OCR 未识别到文字内容（文件: {file_path}）"

        result_text = "\n\n".join(all_text)
        logger.info(f"OCR 识别完成: {file_path}, {len(result_text)} 字符")
        return f"OCR 识别结果（文件: {os.path.basename(file_path)}）:\n\n{result_text}"

    except ImportError as e:
        return f"OCR 引擎不可用: {e}"
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}", exc_info=True)
        return f"OCR 识别出错: {str(e)}"


def _validate_path(file_path: str) -> str:
    """验证路径合法性，防止路径遍历攻击"""
    # 标准化路径
    try:
        resolved = str(Path(file_path).resolve())
    except (ValueError, OSError):
        return "Error: 无效的文件路径"

    # 检查是否在允许的基础目录下
    is_allowed = any(
        resolved.startswith(str(Path(base).resolve()))
        for base in _ALLOWED_BASE_DIRS
    )
    if not is_allowed:
        return f"Error: 不允许访问该路径。允许的目录: {_ALLOWED_BASE_DIRS}"

    return resolved
