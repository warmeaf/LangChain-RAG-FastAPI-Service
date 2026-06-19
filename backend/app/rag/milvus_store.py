import asyncio
import os
import threading
import uuid
import time
from typing import List

from pymilvus import MilvusClient, DataType
from langchain_core.documents import Document

from app.utils.config import rag_config
from app.utils.factory import embed_model
from app.core.logger_handler import logger

from .retrievers.milvus_retriever import MilvusRetriever
from .md5_manager import MD5Store
from .document_handler import DocumentProcessor


class MilvusService:
    """Milvus 向量数据库服务 (单例, MilvusClient API)"""

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
        if MilvusService._initialized:
            return
        with MilvusService._init_lock:
            if MilvusService._initialized:
                return

            milvus_cfg = rag_config.get("milvus", {})
            host = os.getenv("MILVUS_HOST", milvus_cfg.get("host", "localhost"))
            port = os.getenv("MILVUS_PORT", milvus_cfg.get("port", 19530))
            port = int(port) if isinstance(port, str) else port

            self.client = MilvusClient(uri=f"http://{host}:{port}")
            self.collection_name = milvus_cfg.get("collection_name", "rag_collection")
            self._ensure_collection()

            self.md5_store = MD5Store()
            self.document_processor = DocumentProcessor(self, self.md5_store)

            MilvusService._initialized = True

    def _ensure_collection(self):
        """创建或获取 collection"""
        if self.client.has_collection(self.collection_name):
            logger.info(f"Milvus collection '{self.collection_name}' 已存在，加载完成")
            return

        schema = self.client.create_schema()
        schema.add_field("id", DataType.VARCHAR, max_length=128, is_primary=True)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field("user_id", DataType.VARCHAR, max_length=64, is_partition_key=True)
        schema.add_field("doc_weight", DataType.FLOAT)
        schema.add_field("created_at", DataType.INT64)
        schema.add_field("metadata", DataType.JSON)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type=rag_config["milvus"].get("index_type", "IVF_FLAT"),
            metric_type=rag_config["milvus"].get("metric_type", "COSINE"),
            params={"nlist": rag_config["milvus"].get("nlist", 128)},
        )

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"Milvus collection '{self.collection_name}' 创建完成")

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量向量化文本 (bge-large-zh, 1024维)"""
        return embed_model.encode(texts, normalize_embeddings=True).tolist()

    def add_documents(self, documents: List[Document]) -> List[str]:
        """向 Milvus 添加文档"""
        if not documents:
            return []

        ids = [str(uuid.uuid4()) for _ in documents]
        texts = [doc.page_content for doc in documents]
        embeddings = self._embed_texts(texts)
        now = int(time.time())

        data = []
        for i, doc in enumerate(documents):
            data.append({
                "id": ids[i],
                "text": doc.page_content,
                "embedding": embeddings[i],
                "user_id": doc.metadata.get("user_id", ""),
                "doc_weight": float(doc.metadata.get("doc_weight", 1.0)),
                "created_at": now,
                "metadata": doc.metadata,
            })

        self.client.insert(collection_name=self.collection_name, data=data)
        self.client.flush(collection_name=self.collection_name)
        return ids

    async def get_retriever(self, query: str = None, user_id: str = None):
        """获取混合检索器"""
        if not user_id:
            from .retrievers.empty_retriever import EmptyRetriever
            return EmptyRetriever()

        from .retrievers.bm25_retriever import BM25Retriever
        from .retrievers.rrf_retriever import RRFRetriever

        k = rag_config["retrieval"]["coarse_k"]
        milvus_retriever = MilvusRetriever(self.client, self.collection_name, embed_model, user_id, k)

        all_docs = await self._get_all_documents_for_user(user_id)
        if all_docs:
            bm25_retriever = BM25Retriever(all_docs, k=k)
            return RRFRetriever(retrievers=[milvus_retriever, bm25_retriever])
        return milvus_retriever

    async def _get_all_documents_for_user(self, user_id: str) -> List[Document]:
        """获取用户的所有文档 (供 BM25 用)"""
        def _query():
            return self.client.query(
                collection_name=self.collection_name,
                filter=f'user_id == "{user_id}"',
                output_fields=["text", "metadata"],
                limit=10000,
            )

        results = await asyncio.to_thread(_query)
        documents = []
        for r in results:
            documents.append(Document(
                page_content=r["text"],
                metadata=r.get("metadata", {}),
            ))
        return documents

    async def delete_user_documents(self, user_id: str):
        """删除用户所有文档"""
        self.client.delete(
            collection_name=self.collection_name,
            filter=f'user_id == "{user_id}"',
        )
        await self.md5_store.delete_user_md5(user_id)

    # MD5 代理方法
    async def check_md5_hex(self, md5: str, user_id: str = None) -> bool:
        return await self.md5_store.check_md5_hex(md5, user_id)

    async def save_md5_hex(self, md5: str, filename: str = None,
                            original: str = None, user_id: str = None):
        await self.md5_store.save_md5_hex(md5, filename, original, user_id)

    def save_md5_hex_sync(self, md5: str, filename: str = None,
                           original: str = None, user_id: str = None):
        self.md5_store.save_md5_hex_sync(md5, filename, original, user_id)

    # DocumentProcessor 代理
    async def get_file_document(self, path: str, md5: str = None, user_id: str = None):
        return await self.document_processor.get_file_document(path, md5, user_id)

    def get_file_document_sync(self, path: str, md5: str = None, user_id: str = None):
        return self.document_processor.get_file_document_sync(path, md5, user_id)

    def split_documents_sync(self, docs):
        return self.document_processor.split_documents_sync(docs)

    async def get_document(self, files=None, user_id=None, progress_callback=None):
        await self.document_processor.get_document(files, user_id, progress_callback)

    @staticmethod
    async def get_dynamic_weights(query: str = None):
        return [0.5, 0.5]


# 向后兼容别名
VectorStoreService = MilvusService
