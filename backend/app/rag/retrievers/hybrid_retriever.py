import asyncio
from typing import List, Optional

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from app.utils.config import chroma_config
from .empty_retriever import EmptyRetriever


class BM25Retriever(BaseRetriever):
    """自研 BM25 检索器，基于 rank-bm25 库"""

    def __init__(self, documents: List[Document], k: int = 5):
        super().__init__()
        self._documents = documents
        self._corpus = [doc.page_content for doc in documents]
        self._tokenized_corpus = [text.split() for text in self._corpus]
        self._bm25 = BM25Okapi(self._tokenized_corpus) if self._tokenized_corpus else None
        self._k = k

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        if not self._documents or self._bm25 is None:
            return []
        tokenized_query = query.split()
        scores = self._bm25.get_scores(tokenized_query)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        top_k = indexed_scores[:self._k]
        return [self._documents[i] for i, _ in top_k]


class RRFRetriever(BaseRetriever):
    """自研 RRF (Reciprocal Rank Fusion) 融合检索器，支持动态权重"""

    def __init__(self, retrievers: List[BaseRetriever], k: int = 60, weights: List[float] = None):
        super().__init__()
        self._retrievers = retrievers
        self._k = k
        self._weights = weights or [1.0 / len(retrievers)] * len(retrievers)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        all_results: List[List[Document]] = []
        for retriever in self._retrievers:
            docs = retriever._get_relevant_documents(query, run_manager=run_manager)
            all_results.append(docs)

        doc_scores: dict[str, tuple[Document, float]] = {}

        for i, retriever_docs in enumerate(all_results):
            weight = self._weights[i] if i < len(self._weights) else 1.0 / len(self._retrievers)
            for rank, doc in enumerate(retriever_docs):
                doc_id = doc.page_content
                rrf_score = weight / (self._k + rank + 1)
                if doc_id in doc_scores:
                    existing_doc, existing_score = doc_scores[doc_id]
                    doc_scores[doc_id] = (existing_doc, existing_score + rrf_score)
                else:
                    doc_scores[doc_id] = (doc, rrf_score)

        sorted_docs = sorted(doc_scores.values(), key=lambda x: x[1], reverse=True)
        top_k = chroma_config.get('retrieval', {}).get('coarse_k', 100)
        return [doc for doc, _ in sorted_docs[:top_k]]


class ChromadbVectorRetriever(BaseRetriever):
    """基于 chromadb 原生客户端查询的向量检索器"""

    def __init__(self, collection, embedding_fn, user_id: str, k: int):
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

    async def get_bm25_retriever(self, user_id: str = None):
        """获取 BM25 检索器"""
        if not user_id:
            return None
        docs = await self._get_all_documents_for_user(user_id)
        if docs:
            return BM25Retriever(documents=docs, k=chroma_config.get('retrieval', {}).get('coarse_k', 100))
        return None

    async def _create_vector_retriever(self, user_id: str) -> BaseRetriever:
        """创建向量检索器"""
        k = chroma_config.get('retrieval', {}).get('coarse_k', 100)
        return ChromadbVectorRetriever(
            self._vss.collection, self._vss._embedding_fn, user_id, k
        )

    async def get_retriever(self, query: str = None, user_id: str = None) -> BaseRetriever:
        """获取混合检索器（BM25 + 向量检索 + RRF 融合）"""
        if not user_id:
            return EmptyRetriever()

        vector_retriever = await self._create_vector_retriever(user_id)
        user_docs = await self._get_all_documents_for_user(user_id)

        if user_docs and len(user_docs) > 0:
            bm25_retriever = BM25Retriever(user_docs, k=chroma_config.get('retrieval', {}).get('coarse_k', 100))
            return RRFRetriever(retrievers=[vector_retriever, bm25_retriever])
        else:
            return vector_retriever

    @staticmethod
    async def get_dynamic_weights(query: str = None) -> List[float]:
        """保留接口兼容性（RRF 不再需要手动调权，返回默认权重）"""
        return [0.5, 0.5]
