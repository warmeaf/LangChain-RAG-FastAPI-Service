import os
import json
from typing import Optional, List, AsyncIterator

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.embeddings import Embeddings
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

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
        self._provider_type = llm_type  # for vision_service detection
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
    def model_name(self) -> str:
        """公开的模型名称属性（兼容 vision_service.py 等外部使用者）"""
        return self._model_name

    @property
    def provider_type(self) -> str:
        """提供商类型：OLLAMA / ALIYUN / DEEPSEEK（用于外部检测）"""
        return self._provider_type

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
        """绑定工具，返回新的 ChatModel 实例"""
        tool_schemas = []
        for tool in tools:
            if hasattr(tool, "args_schema") and tool.args_schema:
                try:
                    schema = tool.args_schema.model_json_schema()
                except Exception:
                    schema = {"type": "object", "properties": {}}
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
                # 支持多模态 content（list 类型）和纯文本 content
                openai_msgs.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry = {"role": "assistant", "content": msg.content or ""}
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc["id"] if isinstance(tc, dict) else tc.id,
                            "type": "function",
                            "function": {
                                "name": tc["name"] if isinstance(tc, dict) else tc.name,
                                "arguments": json.dumps(
                            tc["args"] if isinstance(tc, dict) else tc.args,
                            ensure_ascii=False
                        ),
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
            tool_calls=tool_calls if tool_calls else [],
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
                    tc_dict = {
                        "name": tc.function.name if tc.function and tc.function.name else None,
                        "args": tc.function.arguments if tc.function and tc.function.arguments else None,
                        "id": tc.id,
                        "index": tc.index,
                    }
                    tool_call_chunks.append(tc_dict)
            yield AIMessageChunk(
                content=content,
                tool_call_chunks=tool_call_chunks if tool_call_chunks else [],
            )


class DashScopeEmbeddingsWrapper(Embeddings):
    """阿里云DashScope嵌入模型封装（直接使用 dashscope SDK）"""

    def __init__(self, model_name: str = "qwen3-embedding", api_key: str = None):
        try:
            import dashscope
            self.dashscope = dashscope
            self.dashscope.api_key = api_key or os.getenv("ALIYUN_ACCESS_KEY_SECRET")
            self.model_name = model_name
        except ImportError:
            raise ImportError("需要安装 dashscope 库: pip install dashscope")

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


# ── 工厂函数 ──

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

    if llm_type == "DEEPSEEK" and extra_body is None:
        extra_body = {"thinking": {"type": "disabled"}}

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
        base_url = (os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1")
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

    return create_chat_model(
        llm_type=vision_type,
        model_name=model_name,
        streaming=False,
        temperature=0.7,
    )


# 模块级单例（兼容旧代码的 import）
chat_model = create_chat_model()
embed_model = create_embedding_model()
vision_model = create_vision_model()
reranker_model = None
