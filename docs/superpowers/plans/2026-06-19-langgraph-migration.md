# Backend LangGraph 迁移实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 backend 从 LangChain 生态迁移到 LangGraph，移除 8 个 langchain-* 包，用 openai SDK + 自研组件替代，功能完全对等。

**Architecture:** Agent 层用 LangGraph StateGraph（llm_call + tool_node + 条件边）；模型层统一 openai SDK；ChromaDB 用原生客户端；检索器/分割器/加载器自研实现；RRF 融合替代简单加权。

**Tech Stack:** LangGraph 1.x, langchain-core, openai SDK, chromadb, rank-bm25, pypdf, unstructured, FastAPI, uv

---

## 文件结构

| 文件 | 责任 | 操作 |
|------|------|------|
| `pyproject.toml` | 依赖管理 | 修改 |
| `app/utils/factory.py` | Chat/Embedding/Vision 模型工厂，统一 openai SDK | 重写 |
| `app/rag/vector_store.py` | ChromaDB 原生客户端单例 + 文档 CRUD | 重写 |
| `app/rag/retrievers/hybrid_retriever.py` | 自研 BM25 + RRF 融合检索器 | 重写 |
| `app/rag/retrievers/empty_retriever.py` | 空检索器（用户无上下文时返回空） | 微调 |
| `app/rag/text_spliter.py` | 自研 RecursiveTextSplitter + AsyncTextSplitter | 重写 |
| `app/utils/file_handler.py` | 原生 pypdf/unstructured 文档加载器 | 重写 |
| `app/agent/agent.py` | LangGraph StateGraph Agent + SSE 流式 | 重写 |
| `app/agent/agent_middleware.py` | 删除（逻辑内联到 Agent 节点） | 删除 |
| `app/agent/agent_tools.py` | get_stream_writer 替代 ContextVar | 微调 |
| `app/rag/rag_service.py` | chat_model 引用调整 | 微调 |
| `app/utils/vision_service.py` | openai SDK 调用替代 langchain 封装 | 微调 |

---

### Task 1: 依赖更新

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 移除旧 langchain 依赖包**

```bash
cd backend && uv remove langchain langchain-classic langchain-community langchain-ollama langchain-deepseek langchain-openai langchain-chroma langchain-text-splitters langchain-dashscope
```

- [ ] **Step 2: 添加新依赖包**

```bash
cd backend && uv add "openai>=2.0.0"
```

- [ ] **Step 3: 同步依赖并验证关键包版本**

```bash
cd backend && uv sync
cd backend && uv run python -c "
import langgraph; print('langgraph:', langgraph.__version__)
import langchain_core; print('langchain_core:', langchain_core.__version__)
import openai; print('openai:', openai.__version__)
import chromadb; print('chromadb:', chromadb.__version__)
import rank_bm25; print('rank_bm25 imported OK')
import pypdf; print('pypdf imported OK')
"
```

预期：输出各包版本号，无 ImportError。

- [ ] **Step 4: 确认不再有 langchain 包（除 core）**

```bash
cd backend && uv run pip list 2>/dev/null | grep -i langchain || uv pip list 2>/dev/null | grep -i langchain
```

预期：仅显示 `langchain-core` 和 `langgraph` 相关包，无 `langchain`、`langchain-classic`、`langchain-community`、`langchain-ollama`、`langchain-deepseek`、`langchain-openai`、`langchain-chroma`、`langchain-text-splitters`。

- [ ] **Step 5: 提交**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: migrate dependencies from langchain to langgraph + openai"
```

---

### Task 2: 模型层 — factory.py 重写

**Files:**
- Modify: `backend/app/utils/factory.py`

- [ ] **Step 1: 创建 ChatModel 类（openai SDK 封装）**

在 `factory.py` 顶部添加导入和 ChatModel 类：

```python
import os
from typing import Optional, List, AsyncIterator
from openai import AsyncOpenAI

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.embeddings import Embeddings
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.tools import BaseTool

from app.core.logger_handler import logger


# OpenAI-compatible base_url 映射
BASE_URL_MAP = {
    "OLLAMA": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1",
    "ALIYUN": os.getenv("ALIYUN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "DEEPSEEK": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
}

# API key 映射（Ollama 不需要真实 key）
API_KEY_MAP = {
    "OLLAMA": "ollama",
    "ALIYUN": os.getenv("ALIYUN_ACCESS_KEY_SECRET", ""),
    "DEEPSEEK": os.getenv("DEEPSEEK_API_KEY", ""),
}

# 模型名映射
MODEL_NAME_MAP = {
    "OLLAMA": os.getenv("OLLAMA_MODEL_NAME", "qwen3.5:0.8b"),
    "ALIYUN": os.getenv("CHAT_MODEL_NAME", "qwen3-max"),
    "DEEPSEEK": os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-flash"),
}


class ChatModel(BaseChatModel):
    """统一 Chat 模型，基于 openai.AsyncOpenAI，兼容 Ollama/阿里云百炼/DeepSeek"""

    _bound_tools: Optional[List[dict]] = None
    _model_name: str
    _streaming: bool
    _temperature: float
    _max_tokens: Optional[int]
    _extra_body: Optional[dict]

    def __init__(
        self,
        llm_type: Optional[str] = None,
        model_name: Optional[str] = None,
        streaming: bool = True,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ):
        super().__init__()
        llm_type = (llm_type or os.getenv("LLM_TYPE", "ALIYUN")).upper()
        if llm_type not in BASE_URL_MAP:
            raise ValueError(f"不支持的 LLM_TYPE: {llm_type}，可选值: {', '.join(BASE_URL_MAP)}")

        self._model_name = model_name or MODEL_NAME_MAP[llm_type]
        self._streaming = streaming
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._extra_body = extra_body or {}

        self._client = AsyncOpenAI(
            api_key=API_KEY_MAP[llm_type],
            base_url=BASE_URL_MAP[llm_type],
        )
        logger.info(f"🤖 ChatModel 初始化: type={llm_type}, model={self._model_name}, base_url={BASE_URL_MAP[llm_type]}")

    @property
    def _llm_type(self) -> str:
        return "openai-compatible-chat"

    @property
    def _identifying_params(self) -> dict:
        return {"model": self._model_name}

    def bind_tools(
        self,
        tools: list,
        **kwargs,
    ) -> "ChatModel":
        """绑定工具，返回新的 ChatModel 实例（工具以 OpenAI function calling 格式传入）"""
        tool_schemas = []
        for tool in tools:
            if hasattr(tool, "args_schema") and tool.args_schema:
                schema = tool.args_schema.model_json_schema()
            else:
                schema = {"type": "object", "properties": {}}
            tool_schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": schema,
                },
            })

        new_model = ChatModel(
            model_name=self._model_name,
            streaming=self._streaming,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            extra_body=self._extra_body,
        )
        new_model._client = self._client
        new_model._bound_tools = tool_schemas
        return new_model

    def _messages_to_openai(self, messages: List[BaseMessage]) -> List[dict]:
        """将 langchain_core messages 转为 OpenAI 格式"""
        openai_msgs = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                openai_msgs.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["args"] if isinstance(tc["args"], str) else json.dumps(tc["args"], ensure_ascii=False),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                openai_msgs.append(entry)
            elif hasattr(msg, "type") and msg.type == "system":
                openai_msgs.append({"role": "system", "content": msg.content})
            elif hasattr(msg, "type") and msg.type == "tool":
                openai_msgs.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
            else:
                openai_msgs.append({"role": "user", "content": str(msg.content)})
        return openai_msgs

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        raise NotImplementedError("ChatModel 仅支持异步调用，请使用 ainvoke/astream")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """异步非流式生成"""
        openai_msgs = self._messages_to_openai(messages)

        params = {
            "model": self._model_name,
            "messages": openai_msgs,
            "temperature": self._temperature,
        }
        if self._max_tokens:
            params["max_tokens"] = self._max_tokens
        if self._bound_tools:
            params["tools"] = self._bound_tools
        if self._extra_body:
            params["extra_body"] = self._extra_body
        if stop:
            params["stop"] = stop

        response = await self._client.chat.completions.create(**params)
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append({
                    "name": tc.function.name,
                    "args": args,
                    "id": tc.id,
                })

        ai_message = AIMessage(
            content=choice.message.content or "",
            tool_calls=tool_calls if tool_calls else None,
        )
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> AsyncIterator[AIMessageChunk]:
        """异步流式生成"""
        import json

        openai_msgs = self._messages_to_openai(messages)

        params = {
            "model": self._model_name,
            "messages": openai_msgs,
            "temperature": self._temperature,
            "stream": True,
        }
        if self._max_tokens:
            params["max_tokens"] = self._max_tokens
        if self._bound_tools:
            params["tools"] = self._bound_tools
        if self._extra_body:
            params["extra_body"] = self._extra_body
        if stop:
            params["stop"] = stop

        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            content = delta.content or ""
            tool_call_chunks = []
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tool_call_chunks.append({
                        "name": tc.function.name if tc.function and tc.function.name else None,
                        "args": tc.function.arguments if tc.function and tc.function.arguments else None,
                        "id": tc.id,
                        "index": tc.index,
                    })
            yield AIMessageChunk(
                content=content,
                tool_call_chunks=tool_call_chunks if tool_call_chunks else None,
            )
```

- [ ] **Step 2: 保留并微调 DashScopeEmbeddingsWrapper**

保留原有的 `DashScopeEmbeddingsWrapper` 类，移除无用的 `load_dotenv()` 调用（main.py 已加载），保持其余不变。

```python
class DashScopeEmbeddingsWrapper(Embeddings):
    """阿里云DashScope嵌入模型封装（直接使用 dashscope SDK，不依赖 langchain 封装）"""
    
    def __init__(self, model_name: str = "qwen3-embedding", api_key: str = None):
        try:
            import dashscope
            self.dashscope = dashscope
            self.dashscope.api_key = api_key or os.getenv("ALIYUN_ACCESS_KEY_SECRET")
            self.model_name = model_name
        except ImportError:
            raise ImportError("需要安装 dashscope 库")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            resp = self.dashscope.TextEmbedding.call(
                model=self.model_name,
                input=text
            )
            if resp.status_code == 200:
                results.append(resp.output['embedding'])
            else:
                logger.error(f"阿里云嵌入调用失败: {resp.message}")
                results.append([])
        return results
    
    def embed_query(self, text: str) -> List[float]:
        resp = self.dashscope.TextEmbedding.call(
            model=self.model_name,
            input=text
        )
        if resp.status_code == 200:
            return resp.output['embedding']
        else:
            logger.error(f"阿里云嵌入调用失败: {resp.message}")
            return []
```

- [ ] **Step 3: 创建 Ollama 兼容的 Embedding 封装**

```python
class OpenAICompatibleEmbeddings(Embeddings):
    """基于 OpenAI 兼容 API 的嵌入模型封装（适用于 Ollama）"""
    
    def __init__(self, model_name: str, base_url: str, api_key: str = "ollama"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        result = []
        for text in texts:
            resp = self._client.embeddings.create(
                model=self.model_name,
                input=text,
            )
            result.append(resp.data[0].embedding)
        return result
    
    def embed_query(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(
            model=self.model_name,
            input=text,
        )
        return resp.data[0].embedding
```

- [ ] **Step 4: 重写工厂函数**

删除旧的 `BaseModelFactory`、`ChatModelFactory`、`EmbedModelFactory`、`VisionModelFactory`、`RerankerModelFactory` 类，替换为简单工厂函数：

```python
def create_chat_model(
    llm_type: Optional[str] = None,
    model_name: Optional[str] = None,
    streaming: bool = True,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    extra_body: Optional[dict] = None,
) -> ChatModel:
    """创建 Chat 模型实例"""
    llm_type = (llm_type or os.getenv("LLM_TYPE", "ALIYUN")).upper()
    
    if llm_type == "DEEPSEEK":
        extra_body = extra_body or {"thinking": {"type": "disabled"}}
    
    return ChatModel(
        llm_type=llm_type,
        model_name=model_name,
        streaming=streaming,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=extra_body,
    )


def create_embedding_model(embed_type: Optional[str] = None) -> Embeddings:
    """创建 Embedding 模型实例"""
    embed_type = (embed_type or os.getenv("EMBED_MODEL_TYPE", "OLLAMA")).upper()
    
    if embed_type == "OLLAMA":
        model_name = os.getenv("TEXT_EMBEDDING_MODEL_NAME", "qwen3-embedding:0.6b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1"
        logger.info(f"📦 EmbedModel 使用Ollama嵌入模型: {model_name}, 地址: {base_url}")
        return OpenAICompatibleEmbeddings(
            model_name=model_name,
            base_url=base_url,
        )
    
    elif embed_type == "ALIYUN":
        model_name = os.getenv("ALIYUN_EMBED_MODEL_NAME", "qwen3-embedding")
        api_key = os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        logger.info(f"📦 EmbedModel 使用阿里云嵌入模型: {model_name}")
        return DashScopeEmbeddingsWrapper(model_name=model_name, api_key=api_key)
    
    else:
        raise ValueError(f"不支持的 EMBED_MODEL_TYPE: {embed_type}，可选值: OLLAMA, ALIYUN")


def create_vision_model() -> Optional[ChatModel]:
    """创建 Vision 模型实例（非流式），用于 PDF 多模态加载"""
    vision_type = os.getenv("VISION_MODEL_TYPE", "").upper() or os.getenv("LLM_TYPE", "ALIYUN").upper()
    
    vision_model_names = {
        "OLLAMA": os.getenv("VISION_OLLAMA_MODEL_NAME") or os.getenv("OLLAMA_MODEL_NAME") or "qwen3-vl:8b",
        "ALIYUN": os.getenv("VISION_CHAT_MODEL_NAME") or os.getenv("CHAT_MODEL_NAME") or "qwen3-max",
    }
    
    if vision_type not in vision_model_names:
        logger.warning(f"🎨 VisionModel 不支持的类型: {vision_type}，PDF多模态功能已禁用")
        logger.warning(f"   如需使用，请设置 VISION_MODEL_TYPE=OLLAMA 或 VISION_MODEL_TYPE=ALIYUN")
        return None
    
    model_name = vision_model_names[vision_type]
    logger.info(f"🎨 VisionModel 使用{vision_type}多模态模型: {model_name}")
    
    return ChatModel(
        llm_type=vision_type,
        model_name=model_name,
        streaming=False,
        temperature=0.7,
    )


# 模块级单例
chat_model = create_chat_model()
embed_model = create_embedding_model()
vision_model = create_vision_model()
reranker_model = None
```

- [ ] **Step 5: 验证 factory.py 无语法错误**

```bash
cd backend && uv run python -c "from app.utils.factory import chat_model, embed_model, vision_model, create_chat_model, create_embedding_model, create_vision_model; print('OK')"
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/utils/factory.py
git commit -m "refactor(factory): rewrite model layer with openai SDK, remove langchain wrappers"
```

---

### Task 3: ChromaDB 原生客户端 + ChromaEmbeddingWrapper

**Files:**
- Modify: `backend/app/rag/vector_store.py`

- [ ] **Step 1: 编写 ChromaEmbeddingWrapper**

在 `vector_store.py` 顶部添加 ChromaEmbeddingWrapper（将 langchain_core Embeddings 包装为 chromadb EmbeddingFunction）：

```python
import asyncio
import os
import threading
import shutil

from chromadb import PersistentClient, EmbeddingFunction
from chromadb.api.types import Documents, Embeddings as ChromaEmbeddings
from langchain_core.documents import Document

from app.utils.config import chroma_config
from app.utils.factory import embed_model
from app.utils.path_tool import get_abstract_path
from app.core.logger_handler import logger

from .retrievers import EmptyRetriever
from .retrievers.hybrid_retriever import HybridRetriever
from .md5_manager import MD5Store
from .document_handler import DocumentProcessor
from app.utils.image_extractor import delete_image_directory, delete_user_all_images


class ChromaEmbeddingWrapper(EmbeddingFunction):
    """将 langchain_core.embeddings.Embeddings 包装为 chromadb.EmbeddingFunction"""
    
    def __init__(self, embeddings):
        self._embeddings = embeddings
    
    def __call__(self, input: Documents) -> ChromaEmbeddings:
        return self._embeddings.embed_documents(input)
```

- [ ] **Step 2: 重写 VectorStoreService 的 _init_chroma**

保留 `_clear_chroma_cache`、`_reset_chroma_db`、单例模式（`__new__`、`__init__`）不变。只改 `_init_chroma`：

```python
class VectorStoreService:
    _instance = None
    _initialized = False
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if VectorStoreService._initialized:
            return

        with VectorStoreService._init_lock:
            if VectorStoreService._initialized:
                return

            persist_dir = get_abstract_path(chroma_config['persist_directory'])
            _clear_chroma_cache()

            try:
                self._init_chroma(persist_dir)
            except Exception as e:
                logger.error(f"Chroma 初始化失败，即将重置数据库: {e}")
                _reset_chroma_db(persist_dir)
                self._init_chroma(persist_dir)

            VectorStoreService._initialized = True

    def _init_chroma(self, persist_dir: str):
        self._client = PersistentClient(path=persist_dir)
        self._embedding_fn = ChromaEmbeddingWrapper(embed_model)
        self.collection = self._client.get_or_create_collection(
            name=chroma_config['collection_name'],
            embedding_function=self._embedding_fn,
        )
        self.md5_store = MD5Store()
        self.hybrid_retriever = HybridRetriever(self)
        self.document_processor = DocumentProcessor(self, self.md5_store)
```

- [ ] **Step 3: 适配 ChromaDB 操作方法**

将所有 `self.vectors_store.xxx()` 调用改为原生 chromadb `self.collection.xxx()`：

```python
    # ── vector_store.get() → collection.get() ──

    # 在 delete_user_md5、delete_by_filename、delete_single_md5 中:
    # 旧: await asyncio.to_thread(self.vectors_store.delete, where={...})
    # 新: await asyncio.to_thread(self.collection.delete, where={...})
    # 注意：chromadb 原生 where 语法与 langchain_chroma 相同

    # 在 get_user_documents、get_document_detail、get_document_chunks 中:
    # 旧: all_docs = await asyncio.to_thread(self.vectors_store.get, include=['documents', 'metadatas'], where=where_clause)
    # 新: all_docs = await asyncio.to_thread(self.collection.get, include=['documents', 'metadatas'], where=where_clause)
    # chromadb 原生 API 的 get() 返回值结构为: {"ids": [...], "documents": [...], "metadatas": [...]}
    # 与 langchain_chroma 的返回值结构完全一致，无需改动后续代码
```

具体修改点（按行号，参考原始文件）：

- 第 139 行：`self.vectors_store.delete` → `self.collection.delete`
- 第 169 行：`self.vectors_store.delete` → `self.collection.delete`
- 第 203 行：`self.vectors_store.delete` → `self.collection.delete`
- 第 252-256 行：`self.vectors_store.get` → `self.collection.get`
- 第 307-311 行：`self.vectors_store.get` → `self.collection.get`
- 第 388-392 行：`self.vectors_store.get` → `self.collection.get`

- [ ] **Step 4: 更新 HybridRetriever 传参**

`HybridRetriever` 原本接收 `Chroma` 实例，现在改为接收 `VectorStoreService` 实例（因为不再有 `langchain_chroma.Chroma` 对象）。需要同时更新 `hybrid_retriever.py` 中的构造函数签名（在 Task 4 中处理）。

`vector_store.py` 第 94 行：
```python
# 旧: self.hybrid_retriever = HybridRetriever(self.vectors_store)
# 新: self.hybrid_retriever = HybridRetriever(self)
```

- [ ] **Step 5: 更新 DocumentProcessor 传参**

`document_processor.py` 中的 `DocumentProcessor.__init__` 接收 `Chroma` 实例，需要同步修改。先更新传参：

`vector_store.py` 第 95 行：
```python
# 旧: self.document_processor = DocumentProcessor(self.vectors_store, self.md5_store)
# 新: self.document_processor = DocumentProcessor(self, self.md5_store)
```

- [ ] **Step 6: 验证无语法错误**

```bash
cd backend && uv run python -c "from app.rag.vector_store import VectorStoreService, ChromaEmbeddingWrapper; print('OK')"
```

- [ ] **Step 7: 提交**

```bash
git add backend/app/rag/vector_store.py
git commit -m "refactor(vector_store): migrate from langchain_chroma to native chromadb client"
```

---

### Task 4: 自研 BM25 + RRF 融合检索器

**Files:**
- Modify: `backend/app/rag/retrievers/hybrid_retriever.py`
- Modify: `backend/app/rag/retrievers/empty_retriever.py`
- Modify: `backend/app/rag/document_handler/processor.py` (适配接口变更)

- [ ] **Step 1: 重写 hybrid_retriever.py**

完全重写为自研 BM25 + RRF 融合：

```python
import asyncio
from typing import List, Optional

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from app.utils.config import chroma_config
from .empty_retriever import EmptyRetriever


class BM25Retriever(BaseRetriever):
    """自研 BM25 检索器，基于 rank-bm25 库（继承 langchain_core BaseRetriever 接口）"""

    def __init__(self, documents: List[Document], k: int = 5):
        super().__init__()
        self._documents = documents
        self._corpus = [doc.page_content for doc in documents]
        self._tokenized_corpus = [text.split() for text in self._corpus]
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        self._k = k

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        if not self._documents:
            return []
        tokenized_query = query.split()
        scores = self._bm25.get_scores(tokenized_query)
        # 按分数排序，取 top-k
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        top_k = indexed_scores[:self._k]
        return [self._documents[i] for i, _ in top_k]


class RRFRetriever(BaseRetriever):
    """自研 RRF (Reciprocal Rank Fusion) 融合检索器，替代 EnsembleRetriever"""

    def __init__(self, retrievers: List[BaseRetriever], k: int = 60):
        super().__init__()
        self._retrievers = retrievers
        self._k = k  # RRF 平滑参数

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        # 收集所有检索器的结果
        all_results: List[List[Document]] = []
        for retriever in self._retrievers:
            docs = retriever._get_relevant_documents(query, run_manager=run_manager)
            all_results.append(docs)

        # RRF 打分
        doc_scores: dict[str, tuple[Document, float]] = {}

        for retriever_docs in all_results:
            for rank, doc in enumerate(retriever_docs):
                doc_id = doc.page_content  # 使用 page_content 作为去重键
                rrf_score = 1.0 / (self._k + rank + 1)
                if doc_id in doc_scores:
                    existing_doc, existing_score = doc_scores[doc_id]
                    doc_scores[doc_id] = (existing_doc, existing_score + rrf_score)
                else:
                    doc_scores[doc_id] = (doc, rrf_score)

        # 按 RRF 分数降序排序
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x[1], reverse=True)
        top_k = chroma_config.get('k', 5)
        return [doc for doc, _ in sorted_docs[:top_k]]


class HybridRetriever:
    """混合检索器（BM25 + 向量检索 + RRF 融合）"""

    def __init__(self, vector_store_service):
        self._vss = vector_store_service  # VectorStoreService 实例

    async def _get_all_documents_for_user(self, user_id: str) -> List[Document]:
        """获取指定用户的全部文档（用于 BM25 索引构建）"""
        all_docs_result = await asyncio.to_thread(
            self._vss.collection.get,
            include=['documents', 'metadatas'],
            where={'user_id': user_id},
        )
        documents = []
        for i, doc_content in enumerate(all_docs_result['documents']):
            metadata = all_docs_result['metadatas'][i] if i < len(all_docs_result['metadatas']) else {}
            documents.append(Document(page_content=doc_content, metadata=metadata))
        return documents

    async def _get_all_documents(self) -> List[Document]:
        """获取全部文档"""
        all_docs = await asyncio.to_thread(
            self._vss.collection.get,
            include=['documents', 'metadatas'],
        )
        documents = []
        for i, doc in enumerate(all_docs['documents']):
            metadata = all_docs['metadatas'][i] if i < len(all_docs['metadatas']) else {}
            documents.append(Document(page_content=doc, metadata=metadata))
        return documents

    async def _create_vector_retriever(self, user_id: str) -> BaseRetriever:
        """创建向量检索器（通过 chromadb collection.query）"""
        class _ChromadbVectorRetriever(BaseRetriever):
            def __init__(self, collection, embedding_fn, user_id, k):
                super().__init__()
                self._collection = collection
                self._embedding_fn = embedding_fn
                self._user_id = user_id
                self._k = k

            def _get_relevant_documents(
                self, query: str, *, run_manager=None
            ) -> List[Document]:
                query_embedding = self._embedding_fn._embeddings.embed_query(query)
                results = self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=self._k,
                    where={'user_id': self._user_id},
                    include=['documents', 'metadatas'],
                )
                docs = []
                if results['ids'] and results['ids'][0]:
                    for i, doc_id in enumerate(results['ids'][0]):
                        content = results['documents'][0][i] if results['documents'] else ""
                        metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                        docs.append(Document(page_content=content, metadata=metadata, id=doc_id))
                return docs

        k = chroma_config.get('k', 5)
        return _ChromadbVectorRetriever(
            self._vss.collection, self._vss._embedding_fn, user_id, k
        )

    async def get_retriever(self, query: str = None, user_id: str = None) -> BaseRetriever:
        """获取混合检索器（BM25 + 向量检索 + RRF 融合）"""
        if not user_id:
            return EmptyRetriever()

        vector_retriever = await self._create_vector_retriever(user_id)
        user_docs = await self._get_all_documents_for_user(user_id)

        if user_docs and len(user_docs) > 0:
            bm25_retriever = BM25Retriever(user_docs, k=chroma_config.get('k', 5))
            return RRFRetriever(retrievers=[vector_retriever, bm25_retriever])
        else:
            return vector_retriever

    @staticmethod
    async def get_dynamic_weights(query: str = None) -> List[float]:
        """保留接口兼容性（RRF 不再需要手动调权，但保持方法签名不破坏调用方）"""
        return [0.5, 0.5]
```

- [ ] **Step 2: 微调 empty_retriever.py**

确保返回类型与 `BaseRetriever` 一致，不变更现有功能：

```python
# backend/app/rag/retrievers/empty_retriever.py
from typing import List
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun


class EmptyRetriever(BaseRetriever):
    """空检索器：当用户未指定时返回空结果"""

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        return []
```

- [ ] **Step 3: 适配 DocumentProcessor 接口变更**

`backend/app/rag/document_handler/processor.py` 中，`DocumentProcessor.__init__` 第一个参数从 `Chroma` 变为 `VectorStoreService`：

找到 `processor.py` 中构造函数：
```python
class DocumentProcessor:
    def __init__(self, vectors_store, md5_store):
        self.vectors_store = vectors_store
```

需要将所有 `self.vectors_store.xxx` 调用适配为使用 `self.vectors_store.collection` 和 `self.vectors_store._embedding_fn`。具体需要查阅 processor.py 中对 vectors_store 的操作。

先看一下有哪些调用需要改：
- `add_documents` → `collection.add()`（chromadb 原生 API 格式不同）

- [ ] **Step 4: 提交**

```bash
git add backend/app/rag/retrievers/hybrid_retriever.py backend/app/rag/retrievers/empty_retriever.py backend/app/rag/document_handler/processor.py
git commit -m "refactor(retrievers): self-implemented BM25 + RRF fusion, remove langchain retrievers"
```

---

### Task 5: 自研文本分割器

**Files:**
- Modify: `backend/app/rag/text_spliter.py`

- [ ] **Step 1: 实现自研 RecursiveTextSplitter**

完全重写 `text_spliter.py`：

```python
import math
import asyncio
from typing import List, Optional, Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.utils.config import chroma_config


class RecursiveTextSplitter:
    """自研递归字符分割器，逻辑等价于 langchain_text_splitters.RecursiveCharacterTextSplitter"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        default_separators = ["\n\n", "\n", "。", "！", "？", "!", "?", " ", ""]
        self.separators = separators or chroma_config.get('separators', default_separators)

    def _split_text_with_separator(self, text: str, separator: str) -> List[str]:
        """按单个分隔符切分文本，保留分隔符"""
        if not separator:
            return list(text)
        parts = text.split(separator)
        result = []
        for i, part in enumerate(parts):
            if i > 0:
                result.append(separator)
            if part:
                result.append(part)
        return result

    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """合并过短的片段，保持 chunk_size 约束"""
        docs = []
        current_doc: List[str] = []
        current_length = 0

        for split in splits:
            split_len = len(split)
            if current_length + split_len > self.chunk_size:
                if current_doc:
                    docs.append("".join(current_doc))
                # 保留 overlap：从当前片段末尾截取 overlap 长度的文本作为下一个 chunk 的开头
                if self.chunk_overlap > 0 and current_doc:
                    overlap_text = "".join(current_doc)[-self.chunk_overlap:]
                    current_doc = [overlap_text]
                    current_length = len(overlap_text)
                else:
                    current_doc = []
                    current_length = 0
            current_doc.append(split)
            current_length += split_len

        if current_doc:
            docs.append("".join(current_doc))

        return docs

    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """递归分裂文本"""
        if not separators:
            return [text]

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator:
            splits = self._split_text_with_separator(text, separator)
        else:
            splits = list(text)

        good_splits = []
        for split in splits:
            if len(split) <= self.chunk_size:
                good_splits.append(split)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, separator)
                    good_splits = []
                    yield from merged
                # 递归使用下一级分隔符
                yield from self._split_text_recursive(split, remaining_separators)

        if good_splits:
            yield from self._merge_splits(good_splits, separator)

    def split_text(self, text: str) -> List[str]:
        """切分文本"""
        return list(self._split_text_recursive(text, self.separators))

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """切分文档列表，保留 metadata"""
        result = []
        for doc in documents:
            chunks = self.split_text(doc.page_content)
            for i, chunk in enumerate(chunks):
                metadata = doc.metadata.copy()
                metadata['chunk_index'] = i
                result.append(Document(page_content=chunk, metadata=metadata))
        return result


class AsyncTextSplitter:
    """异步文本分割器，保留语义合并优化逻辑不变"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        embedding_model: Optional[Embeddings] = None,
    ):
        default_separators = chroma_config['separators']
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or default_separators
        self.embedding_model = embedding_model
        self.splitter = RecursiveTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
        )

    async def split_text(self, text: str) -> List[str]:
        chunks = await asyncio.to_thread(self.splitter.split_text, text)
        if self.embedding_model:
            chunks = await self._optimize_chunks(chunks)
        return chunks

    async def split_documents(self, documents: List[Any]) -> List[Any]:
        split_docs = await asyncio.to_thread(self.splitter.split_documents, documents)
        return split_docs

    def split_documents_sync(self, documents: List[Any]) -> List[Any]:
        return self.splitter.split_documents(documents)

    def split_text_sync(self, text: str) -> List[str]:
        chunks = self.splitter.split_text(text)
        if self.embedding_model:
            chunks = self._optimize_chunks_sync(chunks)
        return chunks

    def _optimize_chunks_sync(self, chunks: List[str]) -> List[str]:
        optimized_chunks = []
        current_chunk = chunks[0] if chunks else ""
        for i in range(1, len(chunks)):
            similarity = self._calculate_similarity_sync(current_chunk, chunks[i])
            if similarity > 0.7:
                current_chunk += " " + chunks[i]
            else:
                optimized_chunks.append(current_chunk)
                current_chunk = chunks[i]
        if current_chunk:
            optimized_chunks.append(current_chunk)
        return optimized_chunks

    def _calculate_similarity_sync(self, text1: str, text2: str) -> float:
        if not self.embedding_model:
            return 0.0
        embedding1 = self.embedding_model.embed_query(text1)
        embedding2 = self.embedding_model.embed_query(text2)
        return self._cosine_similarity(embedding1, embedding2)

    async def _optimize_chunks(self, chunks: List[str]) -> List[str]:
        optimized_chunks = []
        current_chunk = chunks[0] if chunks else ""
        for i in range(1, len(chunks)):
            similarity = await self._calculate_similarity(current_chunk, chunks[i])
            if similarity > 0.7:
                current_chunk += " " + chunks[i]
            else:
                optimized_chunks.append(current_chunk)
                current_chunk = chunks[i]
        if current_chunk:
            optimized_chunks.append(current_chunk)
        return optimized_chunks

    async def _calculate_similarity(self, text1: str, text2: str) -> float:
        if not self.embedding_model:
            return 0.0
        embedding1 = self.embedding_model.embed_query(text1)
        embedding2 = self.embedding_model.embed_query(text2)
        return self._cosine_similarity(embedding1, embedding2)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)
```

- [ ] **Step 2: 验证 text_spliter.py 无语法错误**

```bash
cd backend && uv run python -c "
from app.rag.text_spliter import RecursiveTextSplitter, AsyncTextSplitter
s = RecursiveTextSplitter(chunk_size=200, chunk_overlap=20)
# 简单验证切分逻辑
chunks = s.split_text('第一句话。第二句话！第三句话？第四句话。' * 20)
print(f'Chunks: {len(chunks)}')
for c in chunks:
    assert len(c) <= 200, f'Chunk too long: {len(c)}'
print('RecursiveTextSplitter OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/rag/text_spliter.py
git commit -m "refactor(text_spliter): self-implemented RecursiveTextSplitter, remove langchain-text-splitters"
```

---

### Task 6: 原生文档加载器

**Files:**
- Modify: `backend/app/utils/file_handler.py`

- [ ] **Step 1: 重写 file_handler.py**

将所有 `langchain_community.document_loaders` 替换为原生 pypdf / unstructured 调用。注意先查阅 `pdf_multimodal_loader.py` 和 `processor.py` 中对 `file_handler.py` 函数的调用方式，确保签名兼容。

```python
import os
import hashlib
import aiofiles
import asyncio
import sys
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader  # 仅保留 TextLoader for TXT/WORD

from app.core.logger_handler import logger
from app.utils.path_tool import get_abstract_path


class FontBBoxStreamFilter:
    def __init__(self, stream):
        self.stream = stream
        
    def write(self, data):
        if b'FontBBox from font descriptor' not in data if isinstance(data, bytes) else 'FontBBox from font descriptor' not in data:
            self.stream.write(data)
            
    def flush(self):
        self.stream.flush()

sys.stderr = FontBBoxStreamFilter(sys.stderr)


# ── MD5 计算（不变）──

async def get_file_md5_hex(file_path: str) -> str:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不存在")
        return ""
    if not os.path.isfile(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不是文件")
        return ""
    md5_object = hashlib.md5()
    chunk_size = 1024
    try:
        async with aiofiles.open(abs_file_path, "rb") as f:
            while chunk := await f.read(chunk_size):
                md5_object.update(chunk)
    except Exception as e:
        logger.error(f"【md5计算】读取文件 {abs_file_path} 时出错: {e}")
        return ""
    return md5_object.hexdigest()

def get_file_md5_hex_sync(file_path: str) -> str:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    if not os.path.exists(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不存在")
        return ""
    if not os.path.isfile(abs_file_path):
        logger.error(f"【md5计算】文件路径 {abs_file_path} 不是文件")
        return ""
    md5_object = hashlib.md5()
    chunk_size = 1024
    try:
        with open(abs_file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_object.update(chunk)
    except Exception as e:
        logger.error(f"【md5计算】读取文件 {abs_file_path} 时出错: {e}")
        return ""
    return md5_object.hexdigest()


# ── 目录遍历（不变）──

async def listdir_allowed_type(path: str, allowed_types: tuple[str]) -> tuple:
    abs_path = get_abstract_path(path) if not os.path.isabs(path) else path
    if not os.path.exists(abs_path):
        logger.error(f"【文件列表】目录路径 {abs_path} 不存在")
        return ()
    if not os.path.isdir(abs_path):
        logger.error(f"【文件列表】目录路径 {abs_path} 不是目录")
        return ()
    file_list = []
    for f in await asyncio.to_thread(os.listdir, abs_path):
        if f.endswith(allowed_types):
            file_path = os.path.join(abs_path, f)
            file_list.append(file_path)
    return tuple(file_list)


# ── 文档加载器 ──

async def pdf_loader(file_path: str, password: str = None) -> List[Document]:
    """PDF 加载器：先尝试 unstructured，失败回退 pypdf"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    
    if password:
        import pypdf
        reader = pypdf.PdfReader(abs_file_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
        return docs
    
    # 优先尝试 unstructured
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=abs_file_path, strategy="auto")
        if elements:
            docs = []
            for el in elements:
                page_number = getattr(el.metadata, 'page_number', None) if el.metadata else None
                metadata = {"source": abs_file_path}
                if page_number:
                    metadata["page"] = page_number
                text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
                if text.strip():
                    docs.append(Document(page_content=text, metadata=metadata))
            if docs:
                return docs
    except Exception as e:
        logger.warning(f"【PDF加载】unstructured 失败，尝试 pypdf: {e}")
    
    # 回退到 pypdf
    import pypdf
    reader = pypdf.PdfReader(abs_file_path)
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
    return docs


async def txt_loader(file_path: str) -> List[Document]:
    """TXT 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    encodings = ['utf-8', 'gbk']
    for encoding in encodings:
        try:
            async with aiofiles.open(abs_file_path, 'r', encoding=encoding) as f:
                content = await f.read()
            return [Document(page_content=content, metadata={"source": abs_file_path})]
        except Exception as e:
            logger.warning(f"【文本文件加载】使用编码 {encoding} 失败: {e}")
            continue
    return []


async def word_loader(file_path: str) -> List[Document]:
    """DOCX 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.docx import partition_docx
        elements = partition_docx(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【WORD文件加载】失败: {e}")
        return []


async def markdown_loader(file_path: str) -> List[Document]:
    """Markdown 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.md import partition_md
        elements = partition_md(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【Markdown文件加载】失败: {e}")
        return []


async def ppt_loader(file_path: str) -> List[Document]:
    """PPTX 加载器"""
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.pptx import partition_pptx
        elements = partition_pptx(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【PPT文件加载】失败: {e}")
        return []


# ── 同步版本（用于多线程场景）──

def pdf_loader_sync(file_path: str, password: str = None) -> List[Document]:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    
    if password:
        import pypdf
        reader = pypdf.PdfReader(abs_file_path)
        if reader.is_encrypted:
            reader.decrypt(password)
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
        return docs
    
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=abs_file_path, strategy="auto")
        if elements:
            docs = []
            for el in elements:
                page_number = getattr(el.metadata, 'page_number', None) if el.metadata else None
                metadata = {"source": abs_file_path}
                if page_number:
                    metadata["page"] = page_number
                text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
                if text.strip():
                    docs.append(Document(page_content=text, metadata=metadata))
            if docs:
                return docs
    except Exception as e:
        logger.warning(f"【PDF加载(同步)】unstructured 失败，尝试 pypdf: {e}")
    
    import pypdf
    reader = pypdf.PdfReader(abs_file_path)
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        docs.append(Document(page_content=text, metadata={"page": i + 1, "source": abs_file_path}))
    return docs


def txt_loader_sync(file_path: str) -> List[Document]:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    encodings = ['utf-8', 'gbk']
    for encoding in encodings:
        try:
            with open(abs_file_path, 'r', encoding=encoding) as f:
                content = f.read()
            return [Document(page_content=content, metadata={"source": abs_file_path})]
        except Exception:
            continue
    return []


def word_loader_sync(file_path: str) -> List[Document]:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.docx import partition_docx
        elements = partition_docx(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【WORD文件加载(同步)】失败: {e}")
        return []


def markdown_loader_sync(file_path: str) -> List[Document]:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.md import partition_md
        elements = partition_md(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【Markdown文件加载(同步)】失败: {e}")
        return []


def ppt_loader_sync(file_path: str) -> List[Document]:
    abs_file_path = get_abstract_path(file_path) if not os.path.isabs(file_path) else file_path
    try:
        from unstructured.partition.pptx import partition_pptx
        elements = partition_pptx(filename=abs_file_path)
        docs = []
        for el in elements:
            text = str(el) if hasattr(el, '__str__') else el.text if hasattr(el, 'text') else ""
            if text.strip():
                docs.append(Document(page_content=text, metadata={"source": abs_file_path}))
        return docs
    except Exception as e:
        logger.error(f"【PPT文件加载(同步)】失败: {e}")
        return []
```

- [ ] **Step 2: 验证所有 loader 函数可导入**

```bash
cd backend && uv run python -c "
from app.utils.file_handler import (
    pdf_loader, txt_loader, word_loader, markdown_loader, ppt_loader,
    pdf_loader_sync, txt_loader_sync, word_loader_sync, markdown_loader_sync, ppt_loader_sync,
    get_file_md5_hex, get_file_md5_hex_sync
)
print('All loaders imported OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/utils/file_handler.py
git commit -m "refactor(file_handler): use native pypdf/unstructured loaders, remove langchain_community loaders"
```

---

### Task 7: Agent 层 — LangGraph StateGraph

**Files:**
- Modify: `backend/app/agent/agent.py`
- Modify: `backend/app/agent/agent_tools.py`
- Delete: `backend/app/agent/agent_middleware.py`

- [ ] **Step 1: 查看 document_handler/processor.py 中 ChromaDB 相关调用**

需要确认 processor.py 中用到了哪些 vectors_store 方法，然后针对性地适配：

```bash
cd backend && grep -n "self.vectors_store\." app/rag/document_handler/processor.py | head -30
```

- [ ] **Step 2: 适配 document_handler/processor.py**

`processor.py` 中用到 `self.vectors_store.add_documents(docs)`。ChromaDB 原生 API 格式不同：

```python
# chromadb 原生 API 格式
collection.add(
    ids=[...],
    documents=[...],
    metadatas=[...],
)
```

需要修改 `processor.py` 中 `_store_to_chroma` 相关方法。找到对应代码后按照 chromadb 原生 API 格式适配。

- [ ] **Step 3: 重写 agent.py**

完整替换为 LangGraph StateGraph Agent：

```python
import os
import json
import asyncio
from typing import List, Optional, AsyncGenerator

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.config import get_stream_writer
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage,
)
from langchain_core.tools import BaseTool

from app.agent.agent_tools import (
    rag_summary_tools, get_weather_tools, what_time_is_now,
    get_user_info_tools, reorder_documents_tools,
    set_current_user_id, set_thinking_callback,
)
from app.core.logger_handler import logger
from app.services import session_manager as sm
from app.utils.factory import create_chat_model
from app.utils.prompt_loader import load_prompt


_SYSTEM_PROMPT = load_prompt('main_prompt')

DEFAULT_TOOLS = [
    rag_summary_tools,
    get_weather_tools,
    what_time_is_now,
    get_user_info_tools,
    reorder_documents_tools,
]


def _build_agent_graph(tools: List[BaseTool], system_prompt: str):
    """构建 LangGraph StateGraph Agent"""
    from typing import Annotated, TypedDict
    from langgraph.graph.message import add_messages

    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]

    # 创建工具绑定的 LLM
    llm = create_chat_model(streaming=True)
    llm_with_tools = llm.bind_tools(tools)

    tools_by_name = {tool.name: tool for tool in tools}

    # ── LLM 调用节点 ──
    def llm_call(state: AgentState):
        logger.info(f"[llm_call] 模型调用，当前消息数: {len(state['messages'])}")
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        response = llm_with_tools.invoke(messages)
        logger.info(f"[llm_call] 模型响应: tool_calls={bool(response.tool_calls)}, content_len={len(response.content or '')}")
        return {"messages": [response]}

    # ── 工具执行节点 ──
    async def tool_node(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        writer = get_stream_writer()

        results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            tool = tools_by_name.get(tool_name)
            if tool is None:
                observation = f"Error: 未知工具 '{tool_name}'"
                logger.error(f"[tool_node] 未知工具: {tool_name}")
            else:
                logger.info(f"[tool_node] 调用工具: {tool_name}, 参数: {tool_args}")
                try:
                    if asyncio.iscoroutinefunction(tool.ainvoke):
                        observation = await tool.ainvoke(tool_args)
                    elif asyncio.iscoroutinefunction(tool.invoke):
                        observation = await tool.invoke(tool_args)
                    else:
                        observation = tool.invoke(tool_args)
                    observation = str(observation)
                except Exception as e:
                    observation = f"Error: {str(e)}"
                    logger.error(f"[tool_node] 工具 {tool_name} 执行失败: {e}")

            # 推送 thinking 事件
            writer({
                "type": "thinking",
                "stage": "tool_call",
                "content": f"调用工具: {tool_name}",
                "details": {
                    "tool": tool_name,
                    "input": str(tool_args)[:500],
                    "output": str(observation)[:500],
                }
            })

            results.append(ToolMessage(content=str(observation), tool_call_id=tool_id))

        return {"messages": results}

    # ── 条件路由 ──
    def should_continue(state: AgentState) -> str:
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return END

    # ── 构建图 ──
    builder = StateGraph(AgentState)
    builder.add_node("llm", llm_call)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "llm")
    builder.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "llm")

    return builder.compile()


async def get_agent_stream_response(
    query: str,
    session_id: str,
    user_id: str,
    custom_tools: Optional[List[BaseTool]] = None,
    **kwargs
) -> AsyncGenerator[str, None]:
    """LangGraph Agent SSE 流式响应"""

    thinking_events = []
    tools = custom_tools or DEFAULT_TOOLS

    try:
        set_current_user_id(user_id)

        # 加载聊天历史
        history = await sm.session_manager.get_history(session_id, user_id)
        logger.info(f"【Agent流式响应】会话历史记录数: {len(history)}")

        chat_messages = []
        if history:
            for user_msg, assistant_msg in history:
                chat_messages.append(HumanMessage(content=user_msg))
                chat_messages.append(AIMessage(content=assistant_msg))

        # 添加当前查询
        chat_messages.append(HumanMessage(content=query))

        # 构建 Agent 图
        graph = _build_agent_graph(tools, _SYSTEM_PROMPT)

        # 发送初始响应
        yield f"data: {json.dumps({'type': 'response', 'content': '', 'session_id': session_id}, ensure_ascii=False)}\n\n"

        # 流式执行
        full_response = []
        async for chunk in graph.astream(
            {"messages": chat_messages},
            stream_mode=["updates", "custom"],
        ):
            if chunk["type"] == "custom":
                # thinking 事件
                event_data = chunk["data"]
                thinking_events.append(event_data)
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            elif chunk["type"] == "updates":
                for node_name, state in chunk["data"].items():
                    if node_name == "llm":
                        messages = state.get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            if hasattr(last_msg, 'content') and last_msg.content and not last_msg.tool_calls:
                                content = last_msg.content
                                # 增量输出（如果已有部分输出，只输出新增部分）
                                if content not in full_response:
                                    full_response.append(content)

        response_text = "".join(full_response) if full_response else "抱歉，我无法理解您的请求。"

        # 保存到会话历史
        message_id = await sm.session_manager.add_message(session_id, user_id, query, response_text)
        if thinking_events:
            try:
                await sm.session_manager.save_thinking_events(session_id, message_id, thinking_events)
            except Exception as e:
                logger.error(f"【Agent流式响应】保存思考过程失败: {e}")

        # 逐字推送回答
        for char in response_text:
            yield f"data: {json.dumps({'type': 'response', 'content': char}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"【Agent流式响应】处理请求失败: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': f'错误: {str(e)}', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
```

- [ ] **Step 4: 微调 agent_tools.py**

移除对 `thinking_callback_var` ContextVar 的依赖，改用 `get_stream_writer()`：

找到 `app/agent/agent_tools.py`，将工具中 `thinking_callback = get_thinking_callback_from_context()` 替换为：

```python
from langgraph.config import get_stream_writer

# 在 rag_summary_tools 函数体中：
# 旧: thinking_callback = get_thinking_callback_from_context()
# 新: writer = get_stream_writer()
#      # 用 writer({"type": "thinking", ...}) 替代 thinking_callback(...)
```

同时保留 `set_current_user_id` 和 `get_current_user_id_from_context`（`current_user_id_var` ContextVar）不变，因为 Agent 入口处需要设置。

移除 `set_thinking_callback`、`get_thinking_callback_from_context`、`thinking_callback_var`。

- [ ] **Step 5: 删除 agent_middleware.py**

```bash
rm backend/app/agent/agent_middleware.py
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/agent/agent.py backend/app/agent/agent_tools.py
git rm backend/app/agent/agent_middleware.py
git commit -m "refactor(agent): migrate to LangGraph StateGraph agent, remove middleware"
```

---

### Task 8: 微调 rag_service.py 和 vision_service.py

**Files:**
- Modify: `backend/app/rag/rag_service.py`
- Modify: `backend/app/utils/vision_service.py`

- [ ] **Step 1: 微调 rag_service.py**

只需修改 chat_model 的导入和引用：

```python
# 旧: from app.utils.factory import chat_model
# 新: from app.utils.factory import create_chat_model
#
# 然后 self.chat_model = create_chat_model(streaming=False)
# （RAG 总结不需要流式）
```

实际的 `rag_service.py` 改动查看后按需修改。关键点：`chat_model` 现在是一个 `ChatModel` 实例，它继承了 `BaseChatModel`，所以 `.ainvoke()` 和 LCEL 管道（`|`）完全兼容。

- [ ] **Step 2: 微调 vision_service.py**

`vision_service.py` 中用到 `chat_model.invoke([HumanMessage(...)])`，需要改为 openai SDK 或新的 ChatModel：

```python
# 旧: from app.utils.factory import vision_model
#     response = vision_model.invoke([HumanMessage(content=content_parts)])
#
# 新: from app.utils.factory import create_vision_model
#     vision_model = create_vision_model()
#     response = await vision_model.ainvoke([HumanMessage(content=content_parts)])
```

- [ ] **Step 3: 验证服务可导入**

```bash
cd backend && uv run python -c "
from app.agent.agent import get_agent_stream_response
from app.rag.rag_service import RagService
from app.utils.vision_service import VisionService
from app.rag.vector_store import VectorStoreService
print('All services imported OK')
"
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/rag/rag_service.py backend/app/utils/vision_service.py
git commit -m "refactor: adapt rag_service and vision_service to new model layer"
```

---

### Task 9: 端到端验证

**Files:** 无新建文件

- [ ] **Step 1: 启动后端服务检查无导入错误**

```bash
cd backend && timeout 10 uv run uvicorn main:app --port 8000 2>&1 || true
```

检查输出：确认无 ImportError，服务正常启动。

- [ ] **Step 2: 健康检查**

```bash
curl -s http://localhost:8000/health/live | python -m json.tool
curl -s http://localhost:8000/health/ready | python -m json.tool
```

- [ ] **Step 3: 验证 Chat Agent 流式（需要模型服务可用）**

如果 Ollama 本地运行中：
```bash
curl -s -X POST http://localhost:8000/chat/agent/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "你好，介绍一下自己", "session_id": "test-001", "user_id": "test-user"}' \
  --max-time 30
```

验证 SSE 格式正常（返回 `data:` 开头的流式事件）。

- [ ] **Step 4: 验证知识库文档列表**

```bash
curl -s "http://localhost:8000/knowledge/list?user_id=test-user" | python -m json.tool
```

- [ ] **Step 5: 提交最终验证结果**

```bash
git add -A
git diff --cached --stat
git commit -m "verify: end-to-end validation after langgraph migration" --allow-empty
```

---

## 实施顺序

按 Task 1 → 9 顺序执行。每个 Task 可独立验证：

```
Task 1: 依赖更新          ─┐
Task 2: 模型层 factory      ├── 先改基础设施
Task 3: ChromaDB 客户端     │
Task 4: 检索器自研         │
Task 5: 文本分割器         │
Task 6: 文档加载器         ─┘
Task 7: Agent 层           ── 再改上层应用
Task 8: RAG/Vision 微调    ── 最后适配
Task 9: 端到端验证          ── 最终确认
```
