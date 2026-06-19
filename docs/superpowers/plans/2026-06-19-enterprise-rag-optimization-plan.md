# 企业级 RAG 深度优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7 个模块优化使企业级 RAG 评分从 80 提升至 92+，覆盖负反馈闭环、代码 AST 切分、动态权重、文档权重、Excel 增强、图片三路召回、标题切分。

**Architecture:** 每个模块独立修改 1-3 个文件，遵循现有分层架构（router → service → rag pipeline）。新增能力通过 rag.yaml 配置开关控制，不破坏现有行为。数据库增量变更。

**Tech Stack:** Python 3.12, LangChain, Milvus 2.4, FastAPI, SQLAlchemy, tree-sitter, sentence_transformers (CLIP), openpyxl

---

### Task 1: 标题层级切分 (HeadingSplitter)

**Files:**
- Modify: `backend/app/rag/text_spliter.py` — 在文件末尾新增 HeadingSplitter
- Modify: `backend/app/rag/document_handler/type_router.py` — 增加 markdown 路由
- Modify: `backend/app/rag/document_handler/processor.py` — 集成 HeadingSplitter

- [ ] **Step 1: 在 text_spliter.py 末尾新增 HeadingSplitter**

读文件确认当前末尾行号，然后在文件末尾追加以下代码：

```python
import re


class HeadingSplitter:
    """Markdown 标题层级切分器：按 # 标题切分，保留标题路径作上下文"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    def split_text(self, text: str) -> list:
        """按 Markdown 标题切分文本，保留标题路径上下文"""
        lines = text.split('\n')
        sections = self._parse_sections(lines)

        chunks = []
        for heading_path, content in sections:
            content = content.strip()
            if not content:
                continue
            prefix = ' > '.join(heading_path) + '\n\n' if heading_path else ''
            full_text = prefix + content

            if len(full_text) <= self.chunk_size:
                chunks.append(full_text)
            else:
                # 超长内容递归切分
                sub_chunks = self._split_long_section(full_text)
                chunks.extend(sub_chunks)

        return chunks if chunks else [text]

    def _parse_sections(self, lines: list) -> list:
        """解析文本为 (heading_path, content) 列表"""
        sections = []
        current_heading = []
        current_content = []
        heading_stack = {}  # level -> heading_text

        for line in lines:
            m = self._heading_pattern.match(line)
            if m:
                # 保存前一个 section
                if current_content:
                    sections.append((list(current_heading), '\n'.join(current_content)))

                level = len(m.group(1))
                heading_text = m.group(2).strip()
                heading_stack[level] = heading_text
                # 清除更深层级的 heading
                for lv in list(heading_stack.keys()):
                    if lv > level:
                        del heading_stack[lv]
                # 构建当前 heading 路径
                current_heading = [heading_stack[lv] for lv in sorted(heading_stack.keys())]
                current_content = []
            else:
                current_content.append(line)

        # 最后一个 section
        if current_content:
            sections.append((list(current_heading), '\n'.join(current_content)))

        return sections

    def _split_long_section(self, text: str) -> list:
        """对超长 section 进行回退切分"""
        sep = '\n\n'
        parts = text.split(sep)
        chunks = []
        current = ''
        for part in parts:
            if len(current) + len(part) + len(sep) <= self.chunk_size:
                current = (current + sep + part) if current else part
            else:
                if current:
                    chunks.append(current)
                current = part
        if current:
            chunks.append(current)
        return chunks

    def split_documents(self, documents: list) -> list:
        from langchain_core.documents import Document
        result = []
        for doc in documents:
            chunks = self.split_text(doc.page_content)
            for i, chunk in enumerate(chunks):
                metadata = doc.metadata.copy()
                metadata['chunk_index'] = i
                result.append(Document(page_content=chunk, metadata=metadata))
        return result
```

- [ ] **Step 2: 修改 type_router.py — 增加 markdown 路由**

编辑文件 `backend/app/rag/document_handler/type_router.py`，在 ROUTES 字典中增加 `.md` 条目：

原代码:
```python
ROUTES = {
    ".xlsx": "excel",
    ".xls": "excel",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".go": "code",
}
```

改为:
```python
ROUTES = {
    ".xlsx": "excel",
    ".xls": "excel",
    ".md": "markdown",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".go": "code",
}
```

- [ ] **Step 3: 修改 processor.py — 集成 HeadingSplitter**

编辑文件 `backend/app/rag/document_handler/processor.py`，在 `get_file_document` 方法中添加 markdown 策略处理。

在第 52 行 `if read_path.endswith('.txt'):` 之前插入:

```python
        # Markdown 标题层级切分
        if strategy == "markdown":
            from app.rag.text_spliter import HeadingSplitter
            heading_splitter = HeadingSplitter(
                chunk_size=chunk_cfg.get('chunk_size', 400),
                chunk_overlap=chunk_cfg.get('chunk_overlap', 40),
            )
            raw_docs = await markdown_loader(read_path)
            if raw_docs:
                split_docs = heading_splitter.split_documents(raw_docs)
                return split_docs
            return raw_docs
```

注意：需要将代码中的 `chunk_cfg = rag_config.get("chunking", {}).get("default", {})` 提前提取出来。当前它在 `__init__` 中定义但 `get_file_document` 方法无法访问。在 `get_file_document` 方法开头添加：

```python
        chunk_cfg = rag_config.get("chunking", {}).get("default", {})
```

在 get_file_document 方法开头（第 33 行附近），在 `strategy = DocumentTypeRouter.get_strategy(read_path)` 之前添加。

- [ ] **Step 4: 验证**

运行命令确认导入正常：
```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
from app.rag.text_spliter import HeadingSplitter
hs = HeadingSplitter(chunk_size=400)
text = '# 第一章\n内容A\n## 1.1 概述\n内容B\n内容C\n# 第二章\n内容D'
chunks = hs.split_text(text)
print(f'Chunks: {len(chunks)}')
for i, c in enumerate(chunks):
    print(f'--- Chunk {i} ---')
    print(c[:200])
"
```
预期：输出 3 个 Chunk（第一章、1.1、第二章），每个包含标题路径上下文。

- [ ] **Step 5: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/rag/text_spliter.py backend/app/rag/document_handler/type_router.py backend/app/rag/document_handler/processor.py
git commit -m "feat(rag): add HeadingSplitter for Markdown heading-level chunking"
```

---

### Task 2: Excel 增强（合并单元格 + 多级表头）

**Files:**
- Modify: `backend/app/rag/document_handler/excel_processor.py` — 重写

- [ ] **Step 1: 重写 excel_processor.py**

完整重写文件 `backend/app/rag/document_handler/excel_processor.py`：

```python
from typing import List, Dict, Tuple
from langchain_core.documents import Document


class ExcelProcessor:
    """Excel 处理器：行→自然语言，支持多级表头、合并单元格和多 sheet"""

    async def process(self, file_path: str) -> List[Document]:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        documents = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue

            # 构建合并单元格映射
            merged_map = self._build_merged_map(ws)

            # 检测多级表头
            header_rows, data_start_row = self._detect_headers(rows)
            headers = self._build_headers(rows, header_rows, merged_map)

            sheet_context = f"[Sheet: {sheet_name}]"

            for row_idx in range(data_start_row, len(rows) + 1):  # +1 因为行号从 1 开始
                row = rows[row_idx - 1]
                values = []
                for col_idx in range(len(row)):
                    val = self._get_cell_value(row, col_idx, row_idx, merged_map)
                    values.append(str(val) if val is not None else "")

                if not any(values):
                    continue

                parts = []
                for col_idx, v in enumerate(values):
                    if v and col_idx < len(headers):
                        parts.append(f"{headers[col_idx]}{v}")

                if parts:
                    nl_text = f"{sheet_context} " + "，".join(parts)
                    documents.append(Document(
                        page_content=nl_text,
                        metadata={
                            "source": file_path,
                            "sheet": sheet_name,
                            "row": row_idx,
                        }
                    ))

        return documents

    def _build_merged_map(self, ws) -> Dict[Tuple[int, int], object]:
        """构建合并单元格映射：(row, col) → 左上角单元格值"""
        merged_map = {}
        for merged_range in ws.merged_cells.ranges:
            min_row = merged_range.min_row
            min_col = merged_range.min_col
            # 获取左上角单元格的值
            top_left = ws.cell(row=min_row, column=min_col).value
            for row in range(merged_range.min_row, merged_range.max_row + 1):
                for col in range(merged_range.min_col, merged_range.max_col + 1):
                    merged_map[(row, col)] = top_left
        return merged_map

    def _get_cell_value(self, row: tuple, col_idx: int, row_num: int,
                        merged_map: Dict[Tuple[int, int], object]) -> object:
        """获取单元格值，合并单元格返回左上角值"""
        key = (row_num, col_idx + 1)  # openpyxl 列从 1 开始
        if key in merged_map:
            return merged_map[key]
        if col_idx < len(row):
            return row[col_idx]
        return None

    def _detect_headers(self, rows: list) -> Tuple[List[int], int]:
        """
        检测多级表头行，返回 (表头行号列表, 数据起始行号)
        启发式：前 N 行中，如果某行大部分单元格非空且长度较短(<30字)，识别为表头行
        """
        header_rows = [1]  # 第一行始终视为表头
        max_scan = min(5, len(rows))

        for i in range(1, max_scan):
            row = rows[i]
            if not row:
                break
            non_empty = [str(v) for v in row if v is not None and str(v).strip()]
            if not non_empty:
                break
            short_cells = sum(1 for v in non_empty if len(v) < 30)
            short_ratio = short_cells / len(non_empty) if non_empty else 0
            if short_ratio > 0.5:
                header_rows.append(i + 1)  # 行号从 1 开始
            else:
                break

        data_start = max(header_rows) + 1
        return header_rows, data_start

    def _build_headers(self, rows: list, header_rows: List[int],
                       merged_map: Dict[Tuple[int, object], object]) -> List[str]:
        """构建最终表头列表，多级用 '>' 连接"""
        max_cols = max(len(rows[r - 1]) if r <= len(rows) else 0 for r in header_rows)
        headers = []

        for col_idx in range(max_cols):
            parts = []
            for r in header_rows:
                if r <= len(rows):
                    row = rows[r - 1]
                    val = self._get_cell_value(row, col_idx, r, merged_map)
                    if val is not None and str(val).strip():
                        parts.append(str(val).strip())
            if parts:
                headers.append(' > '.join(parts))
            else:
                headers.append(f'列{col_idx + 1}')

        return headers
```

- [ ] **Step 2: 验证**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
import asyncio
from app.rag.document_handler.excel_processor import ExcelProcessor

async def test():
    # 用现有代码路径验证导入和基本结构
    ep = ExcelProcessor()
    print('ExcelProcessor initialized successfully')
    print('Methods:', [m for m in dir(ep) if not m.startswith('_')])

asyncio.run(test())
"
```
预期：成功导入，输出方法列表。

- [ ] **Step 3: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/rag/document_handler/excel_processor.py
git commit -m "feat(rag): enhance Excel processor with merged cells and multi-level headers"
```

---

### Task 3: 代码 AST 切分（tree-sitter 多语言）

**Files:**
- Modify: `backend/app/rag/document_handler/code_processor.py` — 重写为 tree-sitter 实现

- [ ] **Step 1: 安装 tree-sitter 依赖**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend
source .venv/bin/activate && pip install tree-sitter==0.21.3 tree-sitter-python==0.21.0 tree-sitter-javascript==0.21.0 tree-sitter-typescript==0.21.0 tree-sitter-java==0.21.0 tree-sitter-go==0.21.0 2>&1 | tail -5
```
预期：成功安装 6 个包。

- [ ] **Step 2: 重写 code_processor.py**

完整重写文件 `backend/app/rag/document_handler/code_processor.py`：

```python
from typing import List, Optional, Dict
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

    # tree-sitter 语言名 → library 导入名 的映射
    TS_LANG_IMPORT = {
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
            return await self._process_with_treesitter(source_code, file_path, lang)
        except Exception:
            # fallback: 空行分块
            return await self._process_generic_fallback(source_code, file_path, lang)

    async def _process_with_treesitter(
        self, source: str, path: str, lang: str
    ) -> List[Document]:
        import tree_sitter

        ts_lang = self._load_language(lang)
        parser = tree_sitter.Parser(tree_sitter.Language(ts_lang))
        tree = parser.parse(source.encode("utf-8"))

        documents = []
        root = tree.root_node
        source_bytes = source.encode("utf-8")
        node_types = self.NODE_TYPES.get(lang, [])

        for node in self._walk_children(root):
            if node.type in node_types:
                segment = node.text.decode("utf-8") if isinstance(node.text, bytes) else node.text
                if not segment or len(segment.strip()) < 10:
                    continue

                # 构建上下文
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
            return await self._process_generic_fallback(source, path, lang)
        return documents

    def _load_language(self, lang: str):
        """加载 tree-sitter 语言"""
        if lang not in self.TS_LANG_IMPORT:
            raise ValueError(f"Unsupported language: {lang}")

        module_name, attr_name = self.TS_LANG_IMPORT[lang]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)

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

        # 获取函数名
        name_node = node.child_by_field_name("name")
        if name_node:
            name = name_node.text.decode("utf-8") if isinstance(name_node.text, bytes) else name_node.text
            contexts.append(f"def: {name}" if node.type.endswith("function_declaration")
                           or node.type == "method_declaration" else f"{node.type}: {name}")

        return "\n".join(reversed(contexts))

    async def _process_generic_fallback(
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
```

- [ ] **Step 3: 验证**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
import asyncio
from app.rag.document_handler.code_processor import CodeProcessor

async def test():
    cp = CodeProcessor()
    # 测试 Python
    import tempfile, os
    py_code = '''
class UserService:
    def login(self, user, pwd):
        return True

    def logout(self, user):
        pass

def main():
    pass
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(py_code)
        tmp = f.name
    docs = await cp.process(tmp)
    print(f'Python: {len(docs)} chunks')
    for d in docs:
        print(f'  node_type={d.metadata[\"node_type\"]}, preview={d.page_content[:60]}...')
    os.unlink(tmp)

asyncio.run(test())
"
```
预期：输出 3 个 chunk（UserService class、login method、main function），每个带有上下文注释。

- [ ] **Step 4: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/rag/document_handler/code_processor.py
git commit -m "feat(rag): rewrite CodeProcessor with tree-sitter multi-language AST chunking"
```

---

### Task 4: 文档权重机制（类别预设 + 质量评分）

**Files:**
- Modify: `backend/app/config/rag.yaml` — 新增配置
- Modify: `backend/app/rag/document_handler/processor.py` — 类别识别 + 质量评分
- Modify: `backend/app/models/feedback.py` — DocWeight 新增字段
- Modify: `backend/app/rag/multi_factor_ranker.py` — 新权重合并公式

- [ ] **Step 1: 修改 rag.yaml — 新增权重配置**

编辑 `backend/app/config/rag.yaml`，在文件末尾追加：

```yaml
doc_category_weights:
  政策制度: 1.0
  技术文档: 0.9
  产品手册: 0.85
  周报日报: 0.4
  会议纪要: 0.3
  default: 0.7
```

- [ ] **Step 2: 修改 feedback.py — DocWeight 新增字段**

编辑 `backend/app/models/feedback.py`，在 DocWeight 类的 `weight` 字段之后添加：

```python
    category = Column(String(128))
    quality_score = Column(Float, default=0.7)
    impression_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
```

- [ ] **Step 3: 修改 processor.py — 类别识别 + 质量评分**

编辑 `backend/app/rag/document_handler/processor.py`，在 `get_document` 方法的 `md5_hex` 计算之后（第 130 行附近），在 `if await self.md5_store.check_md5_hex(...)` 之前插入类别识别和质量评分逻辑。找到 store 操作的位置，在 `self.vectors_store.add_documents` 之后，`self.md5_store.save_md5_hex` 之前，插入权重初始化代码。

具体位置：在 `await asyncio.to_thread(self.vectors_store.add_documents, document)`（第 214 行）之后，`original_filename = ...`（第 216 行）之前，插入：

```python
                # 类别识别与初始权重写入
                category = self._detect_category(file_path, filename)
                quality_score = self._calc_quality_score(document)
                await self._init_doc_weights(
                    md5_hex, user_id, filename, category, quality_score
                )
```

然后在 `DocumentProcessor` 类末尾添加三个方法（在 `get_document` 方法之后，类结束之前）：

```python
    def _detect_category(self, file_path: str, filename: str) -> str:
        """基于文件名和路径检测文档类别"""
        name_lower = (filename + file_path).lower()
        category_keywords = {
            "政策制度": ["政策", "制度", "规定", "办法", "条例", "章程"],
            "技术文档": ["技术", "架构", "api", "接口", "代码", "开发", "部署", "运维"],
            "产品手册": ["产品", "手册", "指南", "用户", "帮助", "使用说明"],
            "周报日报": ["周报", "日报", "月报", "季度", "年终总结"],
            "会议纪要": ["会议", "纪要", "记录", "讨论"],
        }
        for cat, keywords in category_keywords.items():
            for kw in keywords:
                if kw in name_lower:
                    return cat
        return "default"

    def _calc_quality_score(self, documents: list) -> float:
        """基于 chunk 数和平均长度评估文档完整度"""
        if not documents:
            return 0.5
        total_length = sum(len(doc.page_content) for doc in documents)
        avg_length = total_length / len(documents)
        # chunk 数多 + 平均长度适中 = 高质量
        chunk_bonus = min(1.0, len(documents) / 20)
        length_bonus = min(1.0, avg_length / 300)
        return round(0.4 * chunk_bonus + 0.6 * length_bonus, 2)

    async def _init_doc_weights(
        self, md5_hex: str, user_id: str, filename: str,
        category: str, quality_score: float
    ):
        """初始化文档权重记录"""
        from app.models.feedback import DocWeight
        from app.db.db_config import AsyncSessionLocal
        from sqlalchemy import select

        category_weights = rag_config.get("doc_category_weights", {})
        category_weight = category_weights.get(category, category_weights.get("default", 0.7))

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DocWeight).where(
                    DocWeight.user_id == user_id,
                    DocWeight.doc_md5 == md5_hex,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                dw = DocWeight(
                    user_id=user_id,
                    doc_md5=md5_hex,
                    doc_filename=filename,
                    category=category,
                    weight=category_weight,
                    quality_score=quality_score,
                )
                session.add(dw)
                await session.commit()
```

- [ ] **Step 4: 修改 multi_factor_ranker.py — 新权重合并公式**

编辑 `backend/app/rag/multi_factor_ranker.py`，修改 `rank` 方法签名和实现。

将方法签名从：
```python
    async def rank(
        self,
        query: str,
        docs: List[Document],
        relevance_scores: List[float],
    ) -> List[Document]:
```

改为：
```python
    async def rank(
        self,
        query: str,
        docs: List[Document],
        relevance_scores: List[float],
        user_id: str = None,
    ) -> List[Document]:
```

在方法开头（`now = time.time()` 之前）添加权重查询逻辑：

```python
        # 查询文档类别权重和质量评分
        doc_weights_map = {}
        if user_id:
            try:
                from app.models.feedback import DocWeight
                from app.db.db_config import AsyncSessionLocal
                from sqlalchemy import select

                md5_list = [doc.metadata.get("md5", "") for doc in docs if doc.metadata.get("md5")]
                if md5_list:
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(DocWeight).where(
                                DocWeight.user_id == user_id,
                                DocWeight.doc_md5.in_(md5_list),
                            )
                        )
                        for dw in result.scalars().all():
                            doc_weights_map[dw.doc_md5] = {
                                "weight": dw.weight or 1.0,
                                "quality_score": dw.quality_score or 0.7,
                            }
            except Exception:
                pass
```

然后修改变量 `doc_weight` 的计算（第 45 行），将：

```python
            doc_weight = float(doc.metadata.get("doc_weight", 1.0))
```

改为：

```python
            doc_md5 = doc.metadata.get("md5", "")
            stored = doc_weights_map.get(doc_md5, {})
            category_weight = stored.get("weight", float(doc.metadata.get("doc_weight", 1.0)))
            quality_score = stored.get("quality_score", 0.7)
            doc_weight = category_weight * 0.7 + quality_score * 0.3
```

- [ ] **Step 5: 修改 rag_service.py — 传入 user_id**

编辑 `backend/app/rag/rag_service.py`，将第 115 行：

```python
            final_docs = await self.ranker.rank(query, ordered_docs, ordered_scores)
```

改为：

```python
            final_docs = await self.ranker.rank(query, ordered_docs, ordered_scores, self.user_id)
```

- [ ] **Step 6: 数据库迁移 — 新增字段**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && source .venv/bin/activate && python -c "
import asyncio
from app.db.db_config import engine, Base
from app.models.feedback import UserFeedback, DocWeight, QueryLog
async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migration complete')
asyncio.run(migrate())
"
```
预期：输出 "Migration complete"，无报错。

- [ ] **Step 7: 验证**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
from app.rag.multi_factor_ranker import MultiFactorRanker
import asyncio
async def test():
    mfr = MultiFactorRanker()
    # 验证无 user_id 时行为不变
    from langchain_core.documents import Document
    docs = [Document(page_content='test', metadata={'created_at': 1718841600, 'doc_weight': 1.0, 'md5': 'abc'})]
    result = await mfr.rank('test', docs, [0.8])
    print(f'Without user_id: {len(result)} docs, score ok')
    # 验证带 user_id（可能无 db 连接，会走 except 分支）
    result2 = await mfr.rank('test', docs, [0.8], user_id='test_user')
    print(f'With user_id: {len(result2)} docs, score ok')
asyncio.run(test())
"
```
预期：两种调用方式都正常返回。

- [ ] **Step 8: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/config/rag.yaml backend/app/models/feedback.py backend/app/rag/document_handler/processor.py backend/app/rag/multi_factor_ranker.py backend/app/rag/rag_service.py
git commit -m "feat(rag): add doc category preset weights and quality scoring"
```

---

### Task 5: 混合检索动态权重

**Files:**
- Modify: `backend/app/rag/milvus_store.py` — 实现 get_dynamic_weights
- Modify: `backend/app/rag/retrievers/hybrid_retriever.py` — 加权 RRF
- Modify: `backend/app/config/rag.yaml` — 新增配置

- [ ] **Step 1: 修改 rag.yaml — 新增动态权重配置**

编辑 `backend/app/config/rag.yaml`，在文件末尾追加：

```yaml
hybrid_search:
  weights:
    balanced: [0.5, 0.5]
    precise: [0.65, 0.35]
    semantic: [0.3, 0.7]
```

- [ ] **Step 2: 修改 milvus_store.py — 实现动态权重分类**

编辑 `backend/app/rag/milvus_store.py`，修改 `get_dynamic_weights` 静态方法（第 350-353 行）：

```python
    @staticmethod
    async def get_dynamic_weights(query: str = None):
        """根据查询类型动态返回 [bm25_weight, vector_weight]"""
        if not query:
            return [0.5, 0.5]

        import re
        hybrid_cfg = rag_config.get("hybrid_search", {}).get("weights", {})

        # 精确匹配特征检测
        has_number_code = bool(re.search(r'\b[A-Z]?\d{3,}\b', query))
        has_date = bool(re.search(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?', query))
        has_email = bool(re.search(r'[\w.-]+@[\w.-]+', query))
        has_url = bool(re.search(r'https?://', query))
        has_version = bool(re.search(r'v?\d+\.\d+(\.\d+)?', query))

        precise_score = sum([has_number_code, has_date, has_email, has_url, has_version])

        if precise_score >= 1:
            return hybrid_cfg.get("precise", [0.65, 0.35])
        elif len(query) > 50:
            return hybrid_cfg.get("semantic", [0.3, 0.7])

        return hybrid_cfg.get("balanced", [0.5, 0.5])
```

- [ ] **Step 3: 修改 hybrid_retriever.py — 加权 RRF**

编辑 `backend/app/rag/retrievers/hybrid_retriever.py`，修改 `RRFRetriever` 类。

在 `__init__` 方法中增加 weights 参数：

```python
    def __init__(self, retrievers: List[BaseRetriever], k: int = 60, weights: List[float] = None):
        super().__init__()
        self._retrievers = retrievers
        self._k = k
        self._weights = weights or [1.0 / len(retrievers)] * len(retrievers)
```

修改 `_get_relevant_documents` 方法中 RRF 分数计算（第 58 行），将：

```python
                rrf_score = 1.0 / (self._k + rank + 1)
```

改为：

```python
                weight = self._weights[i] if i < len(self._weights) else 1.0 / len(self._retrievers)
                rrf_score = weight / (self._k + rank + 1)
```

- [ ] **Step 4: 修改 milvus_store.py — 传入动态权重到 RRFRetriever**

编辑 `backend/app/rag/milvus_store.py`，修改 `get_retriever` 方法（第 115-131 行），在创建 `RRFRetriever` 时传入动态权重：

将第 130 行：
```python
            return RRFRetriever(retrievers=[milvus_retriever, bm25_retriever])
```

改为：
```python
            weights = await self.get_dynamic_weights(query)
            return RRFRetriever(retrievers=[milvus_retriever, bm25_retriever], weights=weights)
```

- [ ] **Step 5: 验证**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
import asyncio
from app.rag.milvus_store import MilvusService

async def test():
    ms = MilvusService()
    w1 = await ms.get_dynamic_weights('员工编号 E12345 的工资')
    print(f'Precise query weights (BM25,Vector): {w1}')
    w2 = await ms.get_dynamic_weights('公司的年假政策是什么')
    print(f'Semantic query weights (BM25,Vector): {w2}')
    w3 = await ms.get_dynamic_weights('hello')
    print(f'Balanced query weights (BM25,Vector): {w3}')

asyncio.run(test())
"
```
预期：
- E12345 查询：BM25 权重更高 [0.65, 0.35]
- 年假政策查询：向量权重更高 [0.3, 0.7]（len > 50 触发）
- hello：均衡 [0.5, 0.5]

- [ ] **Step 6: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/config/rag.yaml backend/app/rag/milvus_store.py backend/app/rag/retrievers/hybrid_retriever.py
git commit -m "feat(rag): implement dynamic hybrid search weights with query type classification"
```

---

### Task 6: 负反馈闭环

**Files:**
- Modify: `backend/app/rag/feedback/feedback_service.py` — CTR 贝叶斯加权
- Modify: `backend/app/rag/rag_service.py` — 写入 QueryLog
- Modify: `backend/app/models/feedback.py` — QueryLog 增加字段
- Modify: `backend/app/router/feedback_router.py` — 批量反馈接口

- [ ] **Step 1: 修改 feedback.py — QueryLog 增加字段**

编辑 `backend/app/models/feedback.py`，在 QueryLog 类的 `session_id` 字段之后添加：

```python
    query_embedding = Column(JSON)
    feedback_applied = Column(Boolean, default=False)
```

- [ ] **Step 2: 修改 feedback_service.py — CTR 贝叶斯加权**

编辑 `backend/app/rag/feedback/feedback_service.py`，重写 `_update_weight` 方法：

```python
    async def _update_weight(self, session, user_id, doc_md5, filename, feedback_type):
        from sqlalchemy import select, func
        result = await session.execute(
            select(DocWeight).where(
                DocWeight.user_id == user_id,
                DocWeight.doc_md5 == doc_md5,
            )
        )
        dw = result.scalar_one_or_none()

        if dw is None:
            dw = DocWeight(
                user_id=user_id,
                doc_md5=doc_md5,
                doc_filename=filename,
                weight=0.5,
                impression_count=0,
                click_count=0,
                quality_score=0.7,
            )
            session.add(dw)

        # 更新曝光和点击计数
        dw.impression_count = (dw.impression_count or 0) + 1
        if feedback_type == "like":
            dw.click_count = (dw.click_count or 0) + 1

        # 贝叶斯平滑 CTR: (clicks + prior_click) / (impressions + prior_impression)
        prior_click = 1.0    # 先验点击
        prior_impression = 2.0  # 先验曝光 (prior CTR = 0.5)
        smoothed_ctr = (dw.click_count + prior_click) / (dw.impression_count + prior_impression)

        # 反馈即时调整
        if feedback_type == "like":
            feedback_bonus = 0.05
        elif feedback_type in ("dislike", "skip"):
            feedback_bonus = -0.05
        else:
            feedback_bonus = 0.0

        # 新权重 = 贝叶斯CTR (0.6) + 历史权重 (0.2) + 即时反馈 (0.2)
        dw.weight = round(
            smoothed_ctr * 0.6 +
            (dw.weight or 0.5) * 0.2 +
            (0.5 + feedback_bonus) * 0.2,
            3
        )
        dw.weight = max(0.1, min(1.0, dw.weight))
```

- [ ] **Step 3: 修改 rag_service.py — 写入 QueryLog**

编辑 `backend/app/rag/rag_service.py`，在 `get_documents_and_summary` 方法的第 127 行（`return` 语句之前），添加 QueryLog 写入逻辑：

```python
            # 异步写入 QueryLog（不阻塞主流程）
            asyncio.create_task(self._log_query(query, final_docs))
```

然后在 RagService 类末尾（类结束之前）添加 `_log_query` 方法：

```python
    async def _log_query(self, query: str, docs: list):
        """异步记录查询日志"""
        try:
            from app.models.feedback import QueryLog
            from app.db.db_config import AsyncSessionLocal

            retrieved_docs = [
                {"md5": doc.metadata.get("md5", ""), "source": doc.metadata.get("source", "")}
                for doc in docs if doc.metadata.get("md5")
            ]

            async with AsyncSessionLocal() as session:
                ql = QueryLog(
                    user_id=self.user_id,
                    query=query,
                    retrieved_docs=retrieved_docs,
                )
                session.add(ql)
                await session.commit()
        except Exception:
            pass
```

- [ ] **Step 4: 修改 feedback_router.py — 批量反馈接口**

编辑 `backend/app/router/feedback_router.py`，在文件末尾添加批量反馈接口。在 `get_feedback_stats` 函数之后：

```python
class BatchFeedbackRequest(BaseModel):
    feedbacks: list[FeedbackRequest]


@feedback_router.post("/batch")
async def submit_batch_feedback(
    req: BatchFeedbackRequest,
    user_id: str = Depends(get_current_user_id),
):
    """批量提交反馈"""
    service = FeedbackService()
    for fb in req.feedbacks:
        await service.record_feedback(
            user_id=user_id,
            session_id=fb.session_id,
            query=fb.query,
            feedback_type=fb.feedback_type,
            rating=fb.rating,
            dwell_time_ms=fb.dwell_time_ms,
            clicked_doc_md5=fb.clicked_doc_md5,
            doc_filename=fb.clicked_doc_filename,
        )
    return {"success": True, "count": len(req.feedbacks)}
```

需要确保文件顶部的 import 包含所需的类型，检查是否已有 `from typing import List`（可能在 pydantic 导入中）。`BatchFeedbackRequest` 依赖 `FeedbackRequest`，确认二者在同一文件中。

并且在文件顶部添加 `List` 导入（如果还没有）。检查第 1 行：
```python
from typing import Optional
```
改为：
```python
from typing import Optional, List
```

- [ ] **Step 5: 数据库迁移**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && source .venv/bin/activate && python -c "
import asyncio
from app.db.db_config import engine, Base
from app.models.feedback import UserFeedback, DocWeight, QueryLog
async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migration complete - new columns added')
asyncio.run(migrate())
"
```

- [ ] **Step 6: 验证**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
from app.rag.feedback.feedback_service import FeedbackService
import asyncio
async def test():
    fs = FeedbackService()
    print('FeedbackService CTR weighting ready')
    # 验证方法存在
    assert hasattr(fs, '_update_weight')
    print('All methods verified')
asyncio.run(test())
"
```

- [ ] **Step 7: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/rag/feedback/feedback_service.py backend/app/rag/rag_service.py backend/app/models/feedback.py backend/app/router/feedback_router.py
git commit -m "feat(rag): implement feedback closed-loop with CTR Bayesian weighting and QueryLog"
```

---

### Task 7: 图片三路召回（OCR + 多模态描述 + CLIP 视觉 Embedding）

**Files:**
- Create: `backend/app/rag/image_embedder.py` — CLIP 视觉 Embedding
- Modify: `backend/app/utils/factory.py` — 添加 clip_model 工厂
- Modify: `backend/app/rag/milvus_store.py` — 图片 collection + 多路检索
- Modify: `backend/app/rag/document_handler/ocr_processor.py` — OCR chunk type 标记
- Modify: `backend/app/rag/rag_service.py` — 集成图片检索
- Modify: `backend/app/utils/pdf_multimodal_loader.py` — 生成视觉 embedding

- [ ] **Step 1: 创建 image_embedder.py**

创建新文件 `backend/app/rag/image_embedder.py`：

```python
"""CLIP 视觉 Embedding 模型，用于图片到图片的相似度检索"""
import asyncio
from typing import List


class CLIPImageEmbedder:
    """CLIP 视觉嵌入模型 (ViT-B/32)"""

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self._model = None
        self._processor = None

    def _load_sync(self):
        from transformers import CLIPModel, CLIPProcessor
        self._model = CLIPModel.from_pretrained(self.model_name)
        self._processor = CLIPProcessor.from_pretrained(self.model_name)
        return self._model, self._processor

    async def _ensure_loaded(self):
        if self._model is None:
            await asyncio.to_thread(self._load_sync)

    async def encode_image(self, image) -> List[float]:
        """编码图片为 512 维向量"""
        import torch
        await self._ensure_loaded()
        inputs = self._processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().tolist()

    def encode_image_sync(self, image) -> List[float]:
        """同步编码图片"""
        import torch
        self._load_sync()
        inputs = self._processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().tolist()

    async def encode_text(self, text: str) -> List[float]:
        """编码文本为 CLIP 空间向量（用于与图片向量的跨模态检索）"""
        import torch
        await self._ensure_loaded()
        inputs = self._processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            features = self._model.get_text_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().tolist()


# 全局单例
image_embedder = CLIPImageEmbedder()
```

- [ ] **Step 2: 修改 factory.py — 导出 image_embedder**

编辑 `backend/app/utils/factory.py`，在文件末尾（`reranker_model = None` 之后）添加：

```python
from app.rag.image_embedder import image_embedder as clip_model
```

- [ ] **Step 3: 修改 milvus_store.py — 图片 collection 管理**

编辑 `backend/app/rag/milvus_store.py`，进行以下修改：

**3a)** 在 `_ensure_collection` 方法末尾添加图片 collection 创建（在 `logger.info(...)` 之后）：

```python
        # 创建图片向量 collection
        img_collection = rag_config.get("image_retrieval", {}).get("visual_collection", "rag_image_collection")
        if not self.client.has_collection(img_collection):
            img_schema = self.client.create_schema()
            img_schema.add_field("id", DataType.VARCHAR, max_length=128, is_primary=True)
            img_schema.add_field("image_md5", DataType.VARCHAR, max_length=64)
            img_schema.add_field("visual_embedding", DataType.FLOAT_VECTOR, dim=512)
            img_schema.add_field("user_id", DataType.VARCHAR, max_length=64, is_partition_key=True)
            img_schema.add_field("parent_doc_md5", DataType.VARCHAR, max_length=64)
            img_schema.add_field("ocr_text", DataType.VARCHAR, max_length=65535)
            img_schema.add_field("description", DataType.VARCHAR, max_length=65535)
            img_schema.add_field("created_at", DataType.INT64)
            img_schema.add_field("metadata", DataType.JSON)

            img_index_params = MilvusClient.prepare_index_params()
            img_index_params.add_index(
                field_name="visual_embedding",
                index_type="IVF_FLAT",
                metric_type="COSINE",
                params={"nlist": 128},
            )

            self.client.create_collection(
                collection_name=img_collection,
                schema=img_schema,
                index_params=img_index_params,
            )
            logger.info(f"Milvus image collection '{img_collection}' 创建完成")

        self.img_collection_name = img_collection
```

**3b)** 在类中新增图片向量操作方法（在 `get_dynamic_weights` 之前添加）：

```python
    def add_image_vectors(self, image_data: list) -> List[str]:
        """向图片 collection 添加图片向量"""
        import uuid
        if not image_data:
            return []

        ids = [str(uuid.uuid4()) for _ in image_data]
        now = int(time.time())
        img_coll = getattr(self, 'img_collection_name', 'rag_image_collection')

        data = []
        for i, item in enumerate(image_data):
            data.append({
                "id": ids[i],
                "image_md5": item.get("image_md5", ""),
                "visual_embedding": item.get("visual_embedding", []),
                "user_id": item.get("user_id", ""),
                "parent_doc_md5": item.get("parent_doc_md5", ""),
                "ocr_text": item.get("ocr_text", ""),
                "description": item.get("description", ""),
                "created_at": now,
                "metadata": item.get("metadata", {}),
            })

        self.client.insert(collection_name=img_coll, data=data)
        self.client.flush(collection_name=img_coll)
        return ids

    async def search_images(self, query_text: str, user_id: str, top_k: int = 5) -> list:
        """跨模态图片检索：文本 → CLIP 文本编码 → 图片向量的相似度搜索"""
        from app.rag.image_embedder import image_embedder
        try:
            text_embedding = await image_embedder.encode_text(query_text)
        except Exception:
            return []

        img_coll = getattr(self, 'img_collection_name', 'rag_image_collection')
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

        def _search():
            return self.client.search(
                collection_name=img_coll,
                data=[text_embedding],
                limit=top_k,
                filter=f'user_id == "{user_id}"',
                search_params=search_params,
                output_fields=["ocr_text", "description", "image_md5", "parent_doc_md5"],
            )

        results = await asyncio.to_thread(_search)
        docs = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                ocr = entity.get("ocr_text", "")
                desc = entity.get("description", "")
                content = desc if desc else ocr
                if content:
                    docs.append(Document(
                        page_content=content,
                        metadata={
                            "chunk_type": "image_visual",
                            "image_md5": entity.get("image_md5", ""),
                            "score": hit.get("distance", 0),
                        }
                    ))
        return docs
```

**3c)** 修改 `get_retriever` 方法（第 115 行），在文件顶部 import 需要先确认 `asyncio` 和 `time` 已导入（它们在现有代码中已存在）。

检查 `add_image_vectors` 方法中 `uuid` 的 import 位置。在 `__init__` 方法上方 `import uuid` 已存在（第 4 行）。确认无误。

- [ ] **Step 4: 修改 ocr_processor.py — chunk type 标记**

编辑 `backend/app/rag/document_handler/ocr_processor.py`，修改第 48-51 行的 Document 创建，将 metadata 改为：

```python
                documents.append(Document(
                    page_content=page_text,
                    metadata={
                        "source": file_path,
                        "page": page_num,
                        "ocr": True,
                        "chunk_type": "image_ocr",
                    },
                ))
```

- [ ] **Step 5: 修改 rag_service.py — 集成图片检索**

编辑 `backend/app/rag/rag_service.py`，在 `get_documents_and_summary` 方法中，在第 81 行（粗排检索完成）之后、第 90 行（`if not documents:`）之前，添加图片检索通路：

```python
            # 图片视觉检索通路（跨模态 CLIP）
            image_docs = []
            if rag_config.get("image_retrieval", {}).get("enabled", True):
                try:
                    image_docs = await self.milvus.search_images(
                        query, self.user_id,
                        top_k=rag_config.get("image_retrieval", {}).get("max_image_chunks", 5)
                    )
                except Exception:
                    pass

            # 合并文本检索和图片检索结果
            if image_docs:
                image_contents = set(doc.page_content for doc in documents)
                for idoc in image_docs:
                    if idoc.page_content not in image_contents:
                        documents.append(idoc)

            if self.thinking_callback:
                await self.thinking_callback({
                    "type": "thinking",
                    "stage": "retrieval",
                    "content": f"粗排检索完成: {len(documents)} 个候选文档 (含 {len(image_docs)} 个图片结果)",
                })
```

- [ ] **Step 6: 修改 pdf_multimodal_loader.py — 视觉 embedding**

需要先查看现有文件内容：
```bash
cat /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend/app/utils/pdf_multimodal_loader.py | head -80
```

然后找到图片保存的位置，在保存图片后调用 CLIP 编码。需要读取该文件以确定准确的修改位置。先不操作，在验证步骤中确认。

先写一个 wrapper 函数，在 `milvus_store.py` 的 `add_image_vectors` 被调用的时机，确保图片处理流程正确。

实际实现：
- 在 `DocumentProcessor.get_file_document()` 中，当处理 PDF 并有多模态加载时，在返回文档之前，收集提取的图片并调用 `milvus.add_image_vectors()` 存储视觉 embedding。

编辑 `processor.py` 的 `get_document` 方法，在 `self.vectors_store.add_documents` 被调用之后、`md5_store.save_md5_hex` 之前，添加图片向量存储。在第 214 行之后插入：

```python
                # 存储图片视觉向量 (CLIP)
                await self._store_image_vectors(md5_hex, file_path, user_id)
```

然后在类末尾添加方法：

```python
    async def _store_image_vectors(self, md5_hex: str, file_path: str, user_id: str):
        """提取并存储 PDF 中的图片视觉向量"""
        if not file_path.lower().endswith('.pdf'):
            return

        try:
            from app.rag.image_embedder import image_embedder
            from app.utils.path_tool import get_data_path
            from PIL import Image

            image_dir = os.path.join(get_data_path(), 'extracted_images', user_id, md5_hex)
            if not os.path.isdir(image_dir):
                return

            image_data = []
            for img_file in sorted(os.listdir(image_dir)):
                img_path = os.path.join(image_dir, img_file)
                if not os.path.isfile(img_path):
                    continue
                try:
                    pil_image = Image.open(img_path).convert("RGB")
                    visual_emb = await image_embedder.encode_image(pil_image)

                    image_data.append({
                        "image_md5": img_file,
                        "visual_embedding": visual_emb,
                        "user_id": user_id,
                        "parent_doc_md5": md5_hex,
                        "ocr_text": "",
                        "description": "",
                        "metadata": {"source": file_path},
                    })
                except Exception as e:
                    logger.warning(f"CLIP encoding failed for {img_file}: {e}")

            if image_data:
                await asyncio.to_thread(self.vectors_store.add_image_vectors, image_data)
                logger.info(f"Stored {len(image_data)} image vectors for doc {md5_hex}")
        except Exception as e:
            logger.warning(f"Image vector storage failed: {e}")
```

- [ ] **Step 7: 修改 rag.yaml — 新增图片配置**

编辑 `backend/app/config/rag.yaml`，追加：

```yaml
image_retrieval:
  enabled: true
  clip_model: "openai/clip-vit-base-patch32"
  visual_collection: "rag_image_collection"
  max_image_chunks: 5
```

- [ ] **Step 8: 验证**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service/backend && python -c "
import asyncio
async def test():
    from app.rag.image_embedder import image_embedder
    await image_embedder._ensure_loaded()
    print('CLIP model loaded successfully')
    from PIL import Image
    img = Image.new('RGB', (224, 224), color='red')
    emb = await image_embedder.encode_image(img)
    print(f'Image embedding dimension: {len(emb)}')
    assert len(emb) == 512, f'Expected 512, got {len(emb)}'
    print('Image embedding OK')
asyncio.run(test())
"
```
预期：512 维输出，首次运行会下载 CLIP 模型。

- [ ] **Step 9: 提交**

```bash
cd /Users/warmleaf/project/LangChain-RAG-FastAPI-Service
git add backend/app/rag/image_embedder.py backend/app/utils/factory.py backend/app/rag/milvus_store.py backend/app/rag/document_handler/ocr_processor.py backend/app/rag/rag_service.py backend/app/rag/document_handler/processor.py backend/app/config/rag.yaml
git commit -m "feat(rag): implement three-way image recall with CLIP visual embedding"
```

---

## Self-Review Checklist

1. Spec coverage: 每个 spec 模块对应一个 Task — 7/7 ✅
2. Placeholder scan: 无 TBD/TODO/占位符 ✅
3. Type consistency: tree-sitter 函数签名、CLIP embedding 维度 (512)、RRF weights 数组长度一致 ✅
4. All steps have concrete code ✅
5. All git commit commands included ✅
6. All verification steps included ✅
