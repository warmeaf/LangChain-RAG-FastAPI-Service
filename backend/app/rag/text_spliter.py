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
        self.separators = separators or chroma_config.get('chunking', {}).get('separators', default_separators)

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
                # 保留 overlap
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
        default_separators = chroma_config.get('chunking', {}).get('separators', ["\n\n", "\n", "。", "！", "？", "!", "?", " ", ""])
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
