import os
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from app.utils.config import rag_config
from app.core.logger_handler import logger
from app.utils.path_tool import get_project_root
from app.utils.pdf_heading_detector import PDFHeadingDetector


# PaddleOCR 模型缓存目录
# 优先级：环境变量 PADDLE_OCR_BASE_DIR > 默认 .cache/paddleocr
# 相对路径基于 backend/ 根目录解析
_PADDLEOCR_CACHE = os.environ.get("PADDLE_OCR_BASE_DIR")
if _PADDLEOCR_CACHE:
    _PROJ_ROOT = Path(get_project_root())
    _PADDLEOCR_CACHE = str(_PROJ_ROOT / _PADDLEOCR_CACHE)
else:
    _PADDLEOCR_CACHE = str(Path(get_project_root()) / ".cache" / "paddleocr")
    os.environ["PADDLE_OCR_BASE_DIR"] = _PADDLEOCR_CACHE
Path(_PADDLEOCR_CACHE).mkdir(parents=True, exist_ok=True)
class OCRProcessor:
    """扫描版 PDF OCR 处理器 (PaddleOCR)"""

    async def process(self, file_path: str) -> List[Document]:
        """异步版 OCR 处理（内部调同步实现）"""
        return self._process_impl(file_path)

    def process_sync(self, file_path: str) -> List[Document]:
        """同步版 OCR 处理（用于多线程场景）"""
        return self._process_impl(file_path)

    def _process_impl(self, file_path: str) -> List[Document]:
        """OCR 处理同步实现"""
        ocr_cfg = rag_config.get("ocr", {})
        if not ocr_cfg.get("enabled", True):
            return []

        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(lang=ocr_cfg.get("language", "ch"))
        except ImportError:
            logger.warning("PaddleOCR 未安装，跳过 OCR 处理")
            return []

        try:
            import fitz  # PyMuPDF
            from PIL import Image
            fitz_doc = fitz.open(file_path)
            images = []
            for page_num in range(len(fitz_doc)):
                page = fitz_doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            fitz_doc.close()
        except ImportError:
            logger.warning("PyMuPDF 未安装，跳过 OCR 处理")
            return []

        documents = []
        for page_num, image in enumerate(images, start=1):
            import numpy as np
            img_array = np.array(image)
            result = ocr.ocr(img_array, cls=True)

            if not result or not result[0]:
                continue

            # 构建 OCR 文本块（保留边界框供标题检测）
            blocks = []
            lines = []
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                if confidence > 0.7:
                    bbox = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                    bbox_height = bbox[2][1] - bbox[1][1]  # 右下 y - 右上 y
                    font_size = max(5.0, bbox_height / 2.8) if bbox_height > 0 else 10.0
                    blocks.append({"text": text, "font_size": font_size, "bbox": tuple(bbox)})
                    lines.append(text)

            if lines:
                page_text = "\n".join(lines)
                page_text = self._post_process(page_text)

                metadata = {"source": file_path, "page": page_num, "ocr": True, "chunk_type": "image_ocr"}
                if blocks:
                    try:
                        detector = PDFHeadingDetector(font_size_threshold=9.0)
                        headings = detector.extract_headings(blocks)
                        if headings:
                            metadata["headings"] = [h["text"] for h in headings]
                            path_map = detector.build_heading_path(blocks)
                            if path_map:
                                last_body_key = list(path_map.keys())[-1]
                                metadata["heading_path"] = path_map[last_body_key]
                    except Exception:
                        logger.warning("OCR 标题检测异常，跳过", exc_info=True)

                documents.append(Document(
                    page_content=page_text,
                    metadata=metadata,
                ))
                logger.info(f"OCR 处理第 {page_num} 页完成（来源: {file_path}），"
                            f"检测到 {len(metadata.get('headings', []))} 个标题")

        return documents

    def _post_process(self, text: str) -> str:
        # 越长越优先替换（避免短词误伤长词），按长度降序排列
        corrections = {
            "己经": "已经", "白勺": "的",
            "土也": "地",
            "人账": "入账", "曰期": "日期", "末来": "未来",
            "千扰": "干扰", "折和": "折扣", "折口": "折扣",
            "己": "已",
            "午": "年",
        }
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        return text
