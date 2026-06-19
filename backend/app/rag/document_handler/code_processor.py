from typing import List
from langchain_core.documents import Document


class CodeProcessor:
    """代码处理器：基于 tree-sitter 按函数/类/方法切分，支持多语言"""

    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".go": "go",
    }

    # tree-sitter 语言名 → (module_name, attr_name)
    TS_LANG_SPEC = {
        "python": ("tree_sitter_python", "language"),
        "javascript": ("tree_sitter_javascript", "language"),
        "typescript": ("tree_sitter_typescript", "language_typescript"),
        "java": ("tree_sitter_java", "language"),
        "go": ("tree_sitter_go", "language"),
    }

    # 各语言的 "可切分节点类型"
    NODE_TYPES = {
        "python": ["function_definition", "class_definition"],
        "javascript": ["function_declaration", "class_declaration", "method_definition",
                       "arrow_function"],
        "typescript": ["function_declaration", "class_declaration", "method_definition",
                       "arrow_function"],
        "java": ["method_declaration", "class_declaration", "constructor_declaration"],
        "go": ["function_declaration", "method_declaration", "type_declaration"],
    }

    async def process(self, file_path: str) -> List[Document]:
        import os
        ext = os.path.splitext(file_path)[1].lower()
        lang = self.LANGUAGE_MAP.get(ext)

        if lang is None:
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        try:
            return self._process_with_treesitter(source_code, file_path, lang)
        except Exception:
            return self._process_generic_fallback(source_code, file_path, lang)

    def _process_with_treesitter(
        self, source: str, path: str, lang: str
    ) -> List[Document]:
        from tree_sitter import Language, Parser

        ts_lang = self._load_language(lang)
        parser = Parser(Language(ts_lang))
        tree = parser.parse(source.encode("utf-8"))

        documents = []
        source_bytes = source.encode("utf-8")
        node_types = self.NODE_TYPES.get(lang, [])

        for node in self._walk_children(tree.root_node):
            if node.type in node_types:
                segment = node.text.decode("utf-8") if isinstance(node.text, bytes) else node.text
                if not segment or len(segment.strip()) < 10:
                    continue

                ctx = self._get_node_context(node, source_bytes)
                full_text = f"{ctx}\n{segment}" if ctx else segment

                documents.append(Document(
                    page_content=full_text,
                    metadata={
                        "source": path,
                        "node_type": node.type,
                        "language": lang,
                    },
                ))

        if not documents:
            return self._process_generic_fallback(source, path, lang)
        return documents

    def _load_language(self, lang: str):
        """加载 tree-sitter 语言"""
        if lang not in self.TS_LANG_SPEC:
            raise ValueError(f"Unsupported language: {lang}")

        module_name, attr_name = self.TS_LANG_SPEC[lang]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)()

    def _walk_children(self, node):
        """递归遍历子节点"""
        for child in node.children:
            yield child
            yield from self._walk_children(child)

    def _get_node_context(self, node, source_bytes: bytes) -> str:
        """获取节点的父级上下文（类名、模块名）"""
        contexts = []
        current = node.parent
        while current:
            if current.type in ("class_definition", "class_declaration", "type_declaration"):
                name_node = current.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode("utf-8") if isinstance(name_node.text, bytes) else name_node.text
                    contexts.append(f"class: {name}")
            elif current.type in ("program", "source_file", "module"):
                break
            current = current.parent

        name_node = node.child_by_field_name("name")
        if name_node:
            name = name_node.text.decode("utf-8") if isinstance(name_node.text, bytes) else name_node.text
            if node.type in ("function_definition", "function_declaration", "method_declaration"):
                contexts.append(f"def: {name}")
            else:
                contexts.append(f"{node.type}: {name}")

        return "\n".join(reversed(contexts))

    def _process_generic_fallback(
        self, source: str, path: str, lang: str
    ) -> List[Document]:
        """回退：按空行分块"""
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
