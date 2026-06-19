from typing import List
from langchain_core.documents import Document
from app.utils.config import rag_config
from app.core.logger_handler import logger


class OCRProcessor:
    """扫描版 PDF OCR 处理器 (PaddleOCR)"""

    async def process(self, file_path: str) -> List[Document]:
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
            from pdf2image import convert_from_path
            images = convert_from_path(file_path, dpi=200)
        except ImportError:
            logger.warning("pdf2image 未安装，跳过 OCR 处理")
            return []

        documents = []
        for page_num, image in enumerate(images, start=1):
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
                page_text = self._post_process(page_text)
                documents.append(Document(
                    page_content=page_text,
                    metadata={"source": file_path, "page": page_num, "ocr": True, "chunk_type": "image_ocr"},
                ))

        return documents

    def _post_process(self, text: str) -> str:
        corrections = {
            "己": "已", "己经": "已经", "白勺": "的",
            "土也": "地", "午": "年",
        }
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        return text
