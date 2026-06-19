from typing import List
from langchain_core.documents import Document


def preserve_format(elements, source_path: str) -> List[Document]:
    """将 unstructured elements 转为带 Markdown 格式的 Document"""
    docs = []
    for el in elements:
        text = str(el) if hasattr(el, "__str__") else getattr(el, "text", "")
        if not text or not text.strip():
            continue

        category = getattr(el, "category", None)

        if category == "Title":
            text = f"# {text}"
        elif category == "Header":
            text = f"## {text}"
        elif category == "ListItem":
            text = f"- {text}"

        page_number = None
        if el.metadata and hasattr(el.metadata, "page_number"):
            page_number = el.metadata.page_number

        metadata = {"source": source_path}
        if page_number:
            metadata["page"] = page_number

        docs.append(Document(page_content=text, metadata=metadata))

    return docs
