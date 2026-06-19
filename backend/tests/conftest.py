"""共享 fixtures、mocks 和 pytest 配置"""

import pytest
import sys
import os

# 确保 backend 在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════
# Mock fixtures（避免真实 API 调用和模型加载）
# ═══════════════════════════════════════════════

@pytest.fixture(autouse=True)
def mock_chat_model(monkeypatch):
    """拦截 ChatModel 初始化，避免真实 LLM API 调用"""
    try:
        monkeypatch.setattr(
            "app.utils.factory.create_chat_model",
            lambda **kwargs: _FakeChatModel()
        )
    except Exception:
        pass


class _FakeChatModel:
    """假的 ChatModel，返回固定应答"""
    async def ainvoke(self, input_data, **kwargs):
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatResult, ChatGeneration
        prompt = str(input_data)
        if "拆分为多个独立的问题" in prompt:
            msg = AIMessage(content="子问题1\n子问题2\n子问题3")
        elif "语义相同但表达方式不同" in prompt:
            msg = AIMessage(content="变体A\n变体B")
        elif "压缩为" in prompt:
            msg = AIMessage(content="压缩后的摘要内容")
        else:
            msg = AIMessage(content="这是一个假设性回答")
        return ChatResult(generations=[ChatGeneration(message=msg)])


@pytest.fixture(autouse=True)
def mock_embed_model(monkeypatch):
    """拦截 BGE Embedding 模型加载"""
    try:
        monkeypatch.setattr(
            "app.utils.factory.create_embedding_model",
            lambda: _FakeEmbedModel()
        )
    except Exception:
        pass


class _FakeEmbedModel:
    def encode(self, texts, normalize_embeddings=True):
        import numpy as np
        n = len(texts) if isinstance(texts, list) else 1
        arr = np.random.randn(n, 1024).astype(np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            arr = arr / norms
        return arr

    def embed_query(self, text):
        return self.encode([text], normalize_embeddings=True)[0].tolist()


@pytest.fixture(autouse=True)
def mock_vision_model(monkeypatch):
    """拦截 VisionModel 初始化"""
    try:
        monkeypatch.setattr("app.utils.factory.create_vision_model", lambda: None)
    except Exception:
        pass


@pytest.fixture
def mock_db(monkeypatch):
    """mock AsyncSessionLocal（避免真实 MySQL 连接）"""
    try:
        monkeypatch.setattr(
            "app.db.db_config.AsyncSessionLocal",
            _FakeAsyncSessionLocal()
        )
    except Exception:
        pass


class _FakeAsyncSessionLocal:
    def __call__(self):
        return _FakeAsyncSession()


class _FakeAsyncSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, stmt):
        return _FakeResult()

    def add(self, obj):
        pass

    async def commit(self):
        pass


class _FakeResult:
    def scalars(self):
        return _FakeScalars()

    def scalar_one_or_none(self):
        return None

    def scalar(self):
        return 0

    def all(self):
        return []


class _FakeScalars:
    def all(self):
        return []

    def __iter__(self):
        return iter([])
