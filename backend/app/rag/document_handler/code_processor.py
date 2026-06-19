from typing import List
from langchain_core.documents import Document


class CodeProcessor:
    """代码处理器：AST 按函数/类/方法切分"""

    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".go": "go",
    }

    async def process(self, file_path: str) -> List[Document]:
        import os
        ext = os.path.splitext(file_path)[1].lower()
        lang = self.LANGUAGE_MAP.get(ext)

        if lang is None:
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        if lang == "python":
            return await self._process_python(source_code, file_path)

        return await self._process_generic(source_code, file_path, lang)

    async def _process_python(self, source: str, path: str) -> List[Document]:
        import ast
        tree = ast.parse(source)
        documents = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                try:
                    segment = ast.get_source_segment(source, node)
                    if segment:
                        ctx = self._build_context(tree, node)
                        full_text = f"{ctx}\n{segment}"
                        documents.append(Document(
                            page_content=full_text,
                            metadata={"source": path, "node_type": type(node).__name__},
                        ))
                except Exception:
                    pass

        return documents

    def _build_context(self, tree, node) -> str:
        import ast
        contexts = []
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in ast.walk(parent):
                    if child is node:
                        contexts.append(f"# class: {parent.name}")
        if isinstance(node, ast.FunctionDef):
            contexts.append(f"# def: {node.name}")
        return "\n".join(contexts)

    async def _process_generic(self, source: str, path: str, lang: str) -> List[Document]:
        blocks = source.split("\n\n")
        documents = []
        for block in blocks:
            block = block.strip()
            if block:
                documents.append(Document(
                    page_content=block,
                    metadata={"source": path, "language": lang},
                ))
        return documents
