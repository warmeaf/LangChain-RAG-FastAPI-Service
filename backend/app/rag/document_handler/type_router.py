from typing import List
from langchain_core.documents import Document


class DocumentTypeRouter:
    """文档类型路由器：根据扩展名选择处理器"""

    ROUTES = {
        ".xlsx": "excel",
        ".xls": "excel",
        ".py": "code",
        ".js": "code",
        ".ts": "code",
        ".java": "code",
        ".go": "code",
    }

    @classmethod
    def get_strategy(cls, file_path: str) -> str:
        import os
        ext = os.path.splitext(file_path)[1].lower()
        return cls.ROUTES.get(ext, "default")
