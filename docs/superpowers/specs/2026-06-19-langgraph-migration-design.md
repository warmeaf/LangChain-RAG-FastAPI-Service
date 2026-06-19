# Backend LangGraph 迁移设计文档

> **日期**: 2026-06-19  
> **分支**: feature/langgraph-migration  
> **目标**: 将 backend 从 LangChain 系列技术栈迁移到 LangGraph 系列技术栈，移除除 langchain-core 外的所有 langchain-* 包。

---

## 1. 概述

### 1.1 迁移目标

将 backend 后端项目从 LangChain 生态（langchain、langchain-classic、langchain-community、langchain-ollama、langchain-deepseek、langchain-chroma、langchain-text-splitters 等）迁移到 LangGraph 技术栈，同时：

- **功能完全对等**：所有现有 API 接口行为不变
- **升级空间**：在保持功能对等的基础上，引入更优的技术方案（如 RRF 替代简单加权融合）
- **依赖精简**：移除 8 个 langchain-* 包，仅保留 `langgraph` + `langchain-core`（langgraph 强依赖）

### 1.2 迁移原则

| 原则 | 说明 |
|------|------|
| 接口不变 | FastAPI 路由、Pydantic Schema、SSE 格式、API 契约保持完全兼容 |
| 功能对等 | RAG 管线、Agent 工具调用、文档上传/Slicing、多模态 PDF 等行为不变 |
| 有升级 | RRF 融合替代简单加权、openai SDK 统一模型调用 |
| 可回滚 | 新旧实现接口隔离，通过 pyproject.toml 依赖切换即可回滚 |

### 1.3 不变模块

以下模块完全不改动：

- `app/router/` — 所有路由和 SSE 端点
- `app/schemas/` — Pydantic 请求/响应模型
- `app/services/` — 会话管理（MySQL 持久化）
- `app/db/` — MySQL/Redis 数据库连接
- `app/core/` — 异常处理、限流、日志、统一响应
- `app/models/` — ORM 模型
- `app/utils/auth_utils.py` — JWT 认证
- `app/utils/config.py` / `config_handler.py` — 配置加载
- `app/utils/path_tool.py` — 路径工具
- `app/utils/prompt_loader.py` — Prompt 文件加载
- `app/utils/image_extractor.py` — PDF 图片提取
- `app/config/` — YAML 配置文件
- `app/prompt/` — Prompt 模板文件
- `data/` — ChromaDB 持久化、图片存储、MD5 记录
- `tests/` — （暂无测试，后续补充）

---

## 2. 依赖变更

### 2.1 pyproject.toml

#### 移除的包

| 包名 | 原因 |
|------|------|
| `langchain` | Agent 编排逻辑被 langgraph 取代；AgentState/middleware 不再需要 |
| `langchain-classic` | AgentExecutor → StateGraph；EnsembleRetriever → 自研 RRF |
| `langchain-community` | BM25Retriever → 自研；ChatTongyi → openai SDK；文档 loaders → 原生库 |
| `langchain-ollama` | ChatOllama/OllamaEmbeddings → openai SDK 兼容接口 |
| `langchain-deepseek` | ChatDeepSeek → openai SDK（DeepSeek 兼容 OpenAI API） |
| `langchain-openai` | 原未直接使用，直接移除 |
| `langchain-chroma` | Chroma wrapper → 原生 chromadb 客户端 |
| `langchain-text-splitters` | RecursiveCharacterTextSplitter → 自研实现 |
| `langchain-dashscope` | 未直接使用（用 dashscope SDK 直接调用） |

#### 新增的包

| 包名 | 用途 |
|------|------|
| `openai>=1.0.0` | 统一 LLM 调用（兼容 Ollama/DeepSeek/阿里云百炼三家 OpenAI-compatible API） |

#### 保留的关键包

| 包名 | 原因 |
|------|------|
| `langgraph>=1.1.6` | 核心编排框架 |
| `langchain-core>=1.2.0` | langgraph 强依赖；提供 Message/Document/Tool/BaseRetriever/PromptTemplate 等基础抽象 |
| `chromadb>=1.5.0` | 向量数据库原生客户端 |
| `rank-bm25>=0.2.2` | BM25 算法实现（自研 Retriever 使用） |
| `langsmith` | 追踪/调试（非 langchain 系列，保留） |

---

## 3. 模块改造方案

### 3.1 Agent 层 (`app/agent/`)

#### 3.1.1 架构变化

```
旧: AgentFactory → create_tool_calling_agent() → AgentExecutor.astream()
                      ↓ 使用 langchain_classic
                      ↓ middleware hooks (langchain.agents.middleware)

新: LangGraphAgent → StateGraph(llm_call + tool_node + conditional edges)
                      ↓ 使用 langgraph
                      ↓ get_stream_writer() + 内联 logger
```

#### 3.1.2 StateGraph 结构

```python
# Agent 图
START → llm_call_node → [conditional: has_tool_calls?]
                           ├── YES → tool_node → llm_call_node (loop)
                           └── NO  → END

# State
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

**节点说明**：

| 节点 | 职责 |
|------|------|
| `llm_call` | 绑定 tools 的 LLM 调用；判断是否需要调用工具；产出 AIMessage（含 tool_calls 或 content） |
| `tool_node` | 执行 `ToolNode`（langgraph.prebuilt）；通过 `get_stream_writer()` 推送 thinking 事件 |

#### 3.1.3 Streaming SSE 方案

```python
# 使用 astream_events 或 astream(stream_mode=["updates", "custom"])
async for chunk in graph.astream(
    {"messages": [HumanMessage(content=query)]},
    stream_mode=["updates", "custom"],
):
    if chunk["type"] == "custom":
        yield format_sse_event(chunk["data"])  # thinking 事件
    elif chunk["type"] == "updates":
        # 提取 AIMessage content 逐字推送 SSE
        yield format_sse_token(...)
```

#### 3.1.4 Middleware 替代

| 旧 Hook | 新实现 |
|---------|--------|
| `@before_agent` | Agent 入口函数内 `logger.info` |
| `@after_agent` | Agent 出口函数内 `logger.info` |
| `@before_model` | `llm_call` 节点开头 `logger.info` |
| `@after_model` | `llm_call` 节点末尾 `logger.info` |
| `@wrap_model_call` | `llm_call` 节点内 `logger.info` |
| `@wrap_tool_call` | `tool_node` 内 `logger.info` + `get_stream_writer()` 推送自定义事件 |

#### 3.1.5 文件变更

| 文件 | 操作 |
|------|------|
| `app/agent/agent.py` | **重写** — AgentFactory → LangGraphAgent；适配 StateGraph 流式 |
| `app/agent/agent_middleware.py` | **删除** |
| `app/agent/agent_tools.py` | **微调** — 用 `get_stream_writer()` 替代 `thinking_callback`（从 ContextVar 获取 → 从流写入器获取） |

---

### 3.2 模型层 (`app/utils/factory.py`)

#### 3.2.1 统一 OpenAI 兼容接口

三家 LLM 提供商都支持 OpenAI-compatible API：

| 提供商 | Base URL |
|--------|----------|
| Ollama | `http://localhost:11434/v1` |
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | `https://api.deepseek.com` (兼容 `/v1`) |

#### 3.2.2 Chat Model 封装

```python
class ChatModel:
    """统一 Chat 模型，底层 openai.AsyncOpenAI"""
    
    def __init__(self, llm_type: str):
        self.client = openai.AsyncOpenAI(
            api_key=...,
            base_url=base_urls[llm_type]
        )
    
    async def ainvoke(self, messages: list[dict], **kwargs) -> AIMessage:
        """非流式调用，返回完整的 AIMessage"""
    
    async def astream(self, messages: list[dict], **kwargs) -> AsyncIterator[AIMessageChunk]:
        """流式调用"""
    
    def bind_tools(self, tools: list) -> "ChatModel":
        """绑定工具定义，返回新的 ChatModel 实例"""
```

#### 3.2.3 Embedding 模型

| 提供商 | 方案 | 接口 |
|--------|------|------|
| Ollama | `openai.AsyncOpenAI.embeddings.create()` — Ollama 0.1.24+ 支持 | 包装为 `langchain_core.embeddings.Embeddings` |
| 阿里云 | 保留 `DashScopeEmbeddingsWrapper`（已自研） | 同上 |

#### 3.2.4 文件变更

| 文件 | 操作 |
|------|------|
| `app/utils/factory.py` | **重写** — 删除 langchain_ollama/community/deepseek 导入；统一 openai SDK；保留 DashScopeEmbeddingsWrapper |

---

### 3.3 向量库 & 检索器 (`app/rag/`)

#### 3.3.1 ChromaDB (`vector_store.py`)

```
旧: langchain_chroma.Chroma(...)
    .get(include=[...], where=...)
    .delete(where=...)
    .as_retriever(search_type=...)
    .add_documents(docs)

新: chromadb.PersistentClient(...)
    .get_or_create_collection(name=..., embedding_function=wrapper)
    collection.get(...) / .delete(...) / .add(...) / .query(...)
```

需要编写 `ChromaEmbeddingWrapper`：将 `langchain_core.embeddings.Embeddings` 包装为 `chromadb.EmbeddingFunction`。

#### 3.3.2 BM25 Retriever (`hybrid_retriever.py`)

```
旧: langchain_community.retrievers.BM25Retriever.from_documents(...)
新: 直接使用 rank-bm25 库的 BM25Okapi，封装为 BaseRetriever
```

#### 3.3.3 Ensemble Retriever (`hybrid_retriever.py`)

```
旧: langchain_classic.retrievers.EnsembleRetriever(retrievers=[...], weights=[...])
新: 自研 RRF (Reciprocal Rank Fusion) 融合策略
```

**RRF 升级说明**：旧方案使用简单加权融合（weights=[0.5, 0.5] + 动态调整），新方案使用 RRF 公式：

```
RRF_score(d) = Σ 1/(k + rank_i(d))
```

其中 k=60（标准值），rank_i(d) 是文档 d 在第 i 个检索器中的排名。RRF 不需要手动调权，自适应不同检索器的得分分布，是业界更优的融合策略。

#### 3.3.4 文件变更

| 文件 | 操作 |
|------|------|
| `app/rag/vector_store.py` | **重写** — 原生 chromadb 客户端；新增 ChromaEmbeddingWrapper |
| `app/rag/retrievers/hybrid_retriever.py` | **重写** — 自研 BM25 + RRF 融合 |
| `app/rag/retrievers/empty_retriever.py` | **微调** — 保持 BaseRetriever 接口 |

---

### 3.4 文本分割器 (`app/rag/text_spliter.py`)

```
旧: langchain_text_splitters.RecursiveCharacterTextSplitter(chunk_size, chunk_overlap, separators)
新: 自研 RecursiveTextSplitter（纯 Python，~80行）
```

**核心逻辑不变**：
1. 按优先级尝试 separators（`\n\n` → `\n` → `。` → `！` → `？` → `!` → `?` → ` ` → ``）
2. 每段不超过 chunk_size
3. chunk 间保留 overlap
4. `AsyncTextSplitter` 的语义合并逻辑（embedding similarity > 0.7）完全保留

---

### 3.5 文档加载器 (`app/utils/file_handler.py`)

```
旧: langchain_community.document_loaders.{PyPDFLoader, TextLoader, UnstructuredPDFLoader, ...}
新: 直接调用 pypdf / unstructured，手动构造 langchain_core.documents.Document
```

| 文件类型 | 旧方案 | 新方案 |
|---------|--------|--------|
| PDF (结构化) | `PyPDFLoader(file)` | `pypdf.PdfReader(file).pages[i].extract_text()` |
| PDF (非结构化) | `UnstructuredPDFLoader(file)` | `unstructured.partition_pdf(file)` |
| TXT | `TextLoader(file, encoding=...)` | 原生 `open()` + encoding fallback |
| Markdown | `UnstructuredMarkdownLoader(file)` | `unstructured.partition_md(file)` |
| PPTX | `UnstructuredPowerPointLoader(file)` | `unstructured.partition_pptx(file)` |
| DOCX | `TextLoader(file)` | `unstructured.partition_docx(file)` |

---

### 3.6 RAG Service (`app/rag/rag_service.py`)

**改动极小**。LangChain Core 的 `PromptTemplate`、`StrOutputParser`、LCEL（`|` 管道操作符）全部来自 `langchain-core`，保留不变。

唯一变化：`self.chat_model` 从 `langchain_ollama.ChatOllama` 变成自研 openai 封装。只要实现了 `ainvoke()` / `astream()`，LCEL 管道完全兼容。

### 3.7 Vision Service (`app/utils/vision_service.py`)

`HumanMessage` 来自 `langchain-core`，保留。实际模型调用改为 openai SDK。

### 3.8 PDF 多模态 Loader (`app/utils/pdf_multimodal_loader.py`)

`Document` 类来自 `langchain-core`，保留。Loader 本身已用 pymupdf + imagehash + vision_service，不依赖其他 langchain 封装。**基本不变**。

---

## 4. 文件变更总览

### 4.1 重写文件（7个）

| 文件 | 变更原因 |
|------|---------|
| `app/agent/agent.py` | AgentExecutor → StateGraph |
| `app/utils/factory.py` | langchain 模型封装 → openai SDK |
| `app/rag/vector_store.py` | langchain_chroma → 原生 chromadb |
| `app/rag/retrievers/hybrid_retriever.py` | langchain BM25/Ensemble → 自研 + RRF |
| `app/rag/text_spliter.py` | langchain Splitter → 自研 |
| `app/utils/file_handler.py` | langchain loaders → 原生 pypdf/unstructured |
| `pyproject.toml` | 依赖更新 |

### 4.2 微调文件（3个）

| 文件 | 变更原因 |
|------|---------|
| `app/agent/agent_tools.py` | `get_stream_writer()` 替代 ContextVar thinking_callback |
| `app/rag/retrievers/empty_retriever.py` | 接口微调 |
| `app/rag/rag_service.py` | chat_model 引用调整 |
| `app/utils/vision_service.py` | openai SDK 调用 |

### 4.3 删除文件（1个）

| 文件 | 原因 |
|------|------|
| `app/agent/agent_middleware.py` | 逻辑内联到 Agent 节点 |

### 4.4 不变文件（所有其他文件）

`app/router/*`、`app/schemas/*`、`app/services/*`、`app/db/*`、`app/core/*`、`app/models/*`、`app/config/*`、`app/prompt/*`、`app/utils/auth_utils.py`、`app/utils/config.py`、`app/utils/config_handler.py`、`app/utils/path_tool.py`、`app/utils/prompt_loader.py`、`app/utils/image_extractor.py`、`app/utils/pdf_multimodal_loader.py`、`app/rag/reorder_service.py`、`app/rag/sse_models.py`、`app/rag/task_queue.py`、`app/rag/document_handler/processor.py`、`app/rag/md5_manager/md5_store.py`、`app/cache/redis_decorator.py`、`main.py`

---

## 5. API 兼容性保证

所有现有 API 端点保持完全兼容：

| 端点 | 兼容性 |
|------|--------|
| `POST /chat/agent/query/stream` | SSE 格式不变（type: thinking/response/error/done） |
| `POST /chat/rag/query` | 响应格式不变 |
| `GET/DELETE /chat/session/*` | 不变 |
| `POST /knowledge/add/*` | 上传流程不变（SSE 进度不变） |
| `DELETE /knowledge/*` | 不变 |
| `GET /knowledge/*` | 不变 |
| `GET /health/*` | 不变 |
| `GET /user/detail/` | 不变 |

---

## 6. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| ChromaDB 原生 API 与 langchain-chroma 行为差异 | 逐方法适配，保留 `_clear_chroma_cache()` 和自愈逻辑 |
| openai SDK 透传 DeepSeek `thinking` 参数 | 使用 `extra_body` 参数透传 |
| Ollama embeddings API 兼容性 | 确认 Ollama 版本 >=0.1.24 支持 `/v1/embeddings` |
| 自研分割器切分行为差异 | 单元测试验证与原 langchain Splitter 输出一致 |
| RRF 融合检索质量变化 | 保留动态权重逻辑作为可配置备选 |
| 流式事件推送格式变化 | SSE 序列化格式保持不变 |

---

## 7. 实施顺序

建议按以下顺序逐步迁移，每步可独立验证：

1. **依赖更新** — pyproject.toml 移除旧包、添加 openai
2. **模型层** — factory.py（最独立，无下游依赖变更）
3. **向量库 + 检索器** — vector_store.py + hybrid_retriever.py + empty_retriever.py
4. **文本分割器** — text_spliter.py
5. **文档加载器** — file_handler.py
6. **Agent 层** — agent.py + agent_tools.py（删除 agent_middleware.py）
7. **RAG/Vision 微调** — rag_service.py + vision_service.py
8. **端到端验证** — 全流程测试
