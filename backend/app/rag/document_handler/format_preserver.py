from typing import List
from langchain_core.documents import Document


def _format_text(text: str, category: str = None) -> str:
    """将文本按类别添加 Markdown 格式标记

    支持的类别：
    - Title → # text
    - Header → ## text
    - ListItem → - text
    - Bold → **text**
    - Italic → *text*
    - Underline → _text_
    - 其余类别 → 原样返回
    """
    if not text or not text.strip():
        return text

    if category == "Title":
        return f"# {text}"
    elif category == "Header":
        return f"## {text}"
    elif category == "ListItem":
        return f"- {text}"
    elif category == "Bold":
        return f"**{text}**"
    elif category == "Italic":
        return f"*{text}*"
    elif category == "Underline":
        return f"_{text}_"
    else:
        return text


def preserve_format(elements, source_path: str) -> List[Document]:
    """将 unstructured elements 转为带 Markdown 格式的 Document"""
    docs = []
    for el in elements:
        text = str(el) if hasattr(el, "__str__") else getattr(el, "text", "")
        if not text or not text.strip():
            continue

        category = getattr(el, "category", None)
        text = _format_text(text, category)

        page_number = None
        if el.metadata and hasattr(el.metadata, "page_number"):
            page_number = el.metadata.page_number

        metadata = {"source": source_path}
        if page_number:
            metadata["page"] = page_number

        docs.append(Document(page_content=text, metadata=metadata))

    return docs


def aggregate_by_slide(elements, source_path: str) -> List[Document]:
    """PPT 幻灯片聚合：同一 slide 的元素合并为一个完整观点的 Document

    文章标准：PPT 按照幻灯片逻辑切分，一张幻灯片通常是一个完整观点，不要切碎。

    Args:
        elements: unstructured 提取的元素列表
        source_path: PPT 文件路径

    Returns:
        按幻灯片聚合后的 Document 列表，每个 Document 对应一个幻灯片
    """
    if not elements:
        return []

    slides: dict = {}  # slide_number → list of formatted text lines

    for el in elements:
        text = str(el) if hasattr(el, "__str__") else getattr(el, "text", "")
        if not text or not text.strip():
            continue

        category = getattr(el, "category", None)
        formatted = _format_text(text, category)

        # 获取页码（slide 编号）
        page_number = None
        if el.metadata and hasattr(el.metadata, "page_number"):
            page_number = el.metadata.page_number

        slide_key = page_number if page_number else 1
        if slide_key not in slides:
            slides[slide_key] = []
        slides[slide_key].append(formatted)

    result = []
    for slide_num in sorted(slides.keys()):
        content = "\n".join(slides[slide_num])
        result.append(Document(
            page_content=content,
            metadata={
                "source": source_path,
                "page": slide_num,
            }
        ))

    return result
