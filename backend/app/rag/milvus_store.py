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
from app.utils.retry import rag_retry
from app.core.logger_handler import logger

from .retrievers.milvus_retriever import MilvusRetriever
from .md5_manager import MD5Store
from .document_handler import DocumentProcessor


class MilvusService:
    """Milvus 向量数据库服务 (单例, MilvusClient API)"""

    _instance = None
    _initialized = False
    _init_lock = threading.Lock()

    # 查询参数（魔法数字命名化）
    _QUERY_LIMIT = 10000        # 用户文档列表查询上限
    _SEARCH_NPROBE = 16         # IVF_FLAT 搜索 nprobe（召回精度/速度权衡）

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

            # BM25 检索器进程内缓存（user_id → (timestamp, BM25Retriever)）
            # 避免每次请求都拉全量文档 + jieba 分词 + 重建索引
            self._bm25_cache: dict[str, tuple[float, object]] = {}
            self._bm25_cache_ttl = 300  # 5 分钟

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

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量向量化文本 (bge-large-zh, 1024维)"""
        return embed_model.encode(texts, normalize_embeddings=True).tolist()

    async def check_connection(self) -> bool:
        """健康检查：验证 Milvus 连接是否正常"""
        def _probe():
            self.client.list_collections()
            return True
        try:
            return await asyncio.to_thread(_probe)
        except Exception as e:
            logger.error(f"Milvus健康检查失败: {e}")
            return False

    def add_documents(self, documents: List[Document]) -> List[str]:
        """向 Milvus 添加文档"""
        if not documents:
            return []

        ids = [str(uuid.uuid4()) for _ in documents]

        # 给每个 chunk 拼接文档来源前缀，避免跨文档混淆
        texts = []
        for doc in documents:
            source = doc.metadata.get("original_filename") \
                  or doc.metadata.get("source") \
                  or doc.metadata.get("filename", "")
            prefix = f"[文档: {source}] " if source else ""
            texts.append(prefix + doc.page_content)

        embeddings = self._embed_texts(texts)
        now = int(time.time())

        data = []
        for i, doc in enumerate(documents):
            data.append({
                "id": ids[i],
                "text": texts[i],
                "embedding": embeddings[i],
                "user_id": doc.metadata.get("user_id", ""),
                "doc_weight": float(doc.metadata.get("doc_weight", 1.0)),
                "created_at": now,
                "metadata": doc.metadata,
            })

        self.client.insert(collection_name=self.collection_name, data=data)
        self.client.flush(collection_name=self.collection_name)

        # 文档变更，失效对应用户的 BM25 缓存
        for doc in documents:
            uid = doc.metadata.get("user_id")
            if uid:
                self._invalidate_bm25_cache(uid)
        return ids

    @rag_retry(max_attempts=3, max_wait=8)
    async def get_adjacent_chunks(
        self, source: str, chunk_indices: set, user_id: str
    ) -> dict:
        """获取指定 source 和 chunk_index 的 chunk
        返回 {chunk_index: Document} 映射
        """
        if not chunk_indices:
            return {}

        def _query():
            results = self.client.query(
                collection_name=self.collection_name,
                filter=f'user_id == "{user_id}"',
                output_fields=["text", "metadata"],
                limit=self._QUERY_LIMIT,
            )
            result = {}
            for r in results:
                meta = r.get("metadata", {})
                if meta.get("source") == source and meta.get("chunk_index") in chunk_indices:
                    result[meta["chunk_index"]] = Document(
                        page_content=r["text"],
                        metadata=meta,
                    )
            return result

        return await asyncio.to_thread(_query)

    async def get_retriever(self, query: str = None, user_id: str = None):
        """获取混合检索器"""
        if not user_id:
            from .retrievers.empty_retriever import EmptyRetriever
            return EmptyRetriever()

        from .retrievers.bm25_retriever import BM25Retriever
        from .retrievers.rrf_retriever import RRFRetriever

        k = rag_config["retrieval"]["coarse_k"]
        milvus_retriever = MilvusRetriever(self.client, self.collection_name, embed_model, user_id, k)

        bm25_retriever = await self._get_bm25_retriever(user_id, k)
        if bm25_retriever:
            weights = await self.get_dynamic_weights(query)
            return RRFRetriever(retrievers=[milvus_retriever, bm25_retriever], weights=weights)
        return milvus_retriever

    async def _get_bm25_retriever(self, user_id: str, k: int):
        """获取 BM25 检索器（带进程内 TTL 缓存，避免每次重建）"""
        now = time.time()
        cached = self._bm25_cache.get(user_id)
        if cached and (now - cached[0]) < self._bm25_cache_ttl:
            return cached[1]

        # 缓存未命中：拉文档 + 建索引
        from .retrievers.bm25_retriever import BM25Retriever
        all_docs = await self._get_all_documents_for_user(user_id)
        if not all_docs:
            return None
        bm25 = BM25Retriever(all_docs, k=k)
        self._bm25_cache[user_id] = (now, bm25)
        logger.info(f"BM25 索引重建: user={user_id}, docs={len(all_docs)}")
        return bm25

    def _invalidate_bm25_cache(self, user_id: str = None):
        """失效 BM25 缓存（文档变更时调用）"""
        if user_id:
            self._bm25_cache.pop(user_id, None)
        else:
            self._bm25_cache.clear()

    @rag_retry(max_attempts=3, max_wait=8)
    async def _get_all_documents_for_user(self, user_id: str) -> List[Document]:
        """获取用户的所有文档 (供 BM25 用)"""
        def _query():
            return self.client.query(
                collection_name=self.collection_name,
                filter=f'user_id == "{user_id}"',
                output_fields=["text", "metadata"],
                limit=self._QUERY_LIMIT,
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
        self.client.flush(collection_name=self.collection_name)
        await self.md5_store.delete_user_md5(user_id)
        self._invalidate_bm25_cache(user_id)

    # MD5 代理方法
    async def check_md5_hex(self, md5: str, user_id: str = None) -> bool:
        return await self.md5_store.check_md5_hex(md5, user_id)

    async def save_md5_hex(self, md5: str, filename: str = None,
                            original: str = None, user_id: str = None):
        await self.md5_store.save_md5_hex(md5, filename, original, user_id)

    def save_md5_hex_sync(self, md5: str, filename: str = None,
                           original: str = None, user_id: str = None):
        self.md5_store.save_md5_hex_sync(md5, filename, original, user_id)

    async def delete_user_md5(self, user_id: str, delete_documents: bool = True):
        await self.md5_store.delete_user_md5(user_id)
        if delete_documents:
            self.client.delete(
                collection_name=self.collection_name,
                filter=f'user_id == "{user_id}"',
            )
            self.client.flush(collection_name=self.collection_name)
            logger.info(f"【Milvus数据库】已删除用户 {user_id} 的所有文档")
        self._invalidate_bm25_cache(user_id)

    async def delete_single_md5(self, user_id: str, md5_value: str, delete_documents: bool = True):
        """删除单个MD5记录及其对应的知识库内容"""
        success = await self.md5_store.delete_single_md5(user_id, md5_value)
        if not success:
            logger.warning(f"【Milvus数据库】MD5记录 {md5_value} 不存在")
            return False

        logger.info(f"【Milvus数据库】已删除用户 {user_id} 的MD5记录: {md5_value}")

        if delete_documents:
            filter_expr = f'user_id == "{user_id}" && metadata["md5"] == "{md5_value}"'
            self.client.delete(
                collection_name=self.collection_name,
                filter=filter_expr,
            )
            self.client.flush(collection_name=self.collection_name)
            logger.info(f"【Milvus数据库】已删除用户 {user_id} 中MD5为 {md5_value} 的文档")

        # 清理磁盘上该用户的 PDF 提取图片
        from app.utils.image_extractor import delete_image_directory
        delete_image_directory(user_id, md5_value)

        self._invalidate_bm25_cache(user_id)
        return True

    async def delete_by_filename(self, user_id: str, filename: str, delete_documents: bool = True):
        """通过文件名删除MD5记录及其对应的知识库内容"""
        md5_to_delete = await self.md5_store.delete_by_filename(user_id, filename)
        if md5_to_delete is None:
            logger.warning(f"【Milvus数据库】文件 {filename} 不存在于用户 {user_id} 的MD5记录中")
            return False

        logger.info(f"【Milvus数据库】已删除用户 {user_id} 的文件 {filename} 的MD5记录")

        if delete_documents:
            filter_expr = f'user_id == "{user_id}" && metadata["md5"] == "{md5_to_delete}"'
            self.client.delete(
                collection_name=self.collection_name,
                filter=filter_expr,
            )
            self.client.flush(collection_name=self.collection_name)
            logger.info(f"【Milvus数据库】已删除用户 {user_id} 中文件 {filename} 对应的文档")

        # 清理磁盘上该用户的 PDF 提取图片
        from app.utils.image_extractor import delete_image_directory
        delete_image_directory(user_id, md5_to_delete)

        self._invalidate_bm25_cache(user_id)
        return True

    async def get_md5_info(self, user_id: str, md5_value: str):
        return await self.md5_store.get_md5_info(user_id, md5_value)

    async def get_all_md5_records(self, user_id: str):
        return await self.md5_store.get_all_md5_records(user_id)

    # ── 文档查询方法 ──

    async def get_user_documents(self, user_id: str = None):
        """获取用户的知识库文档列表"""
        try:
            def _query():
                if user_id:
                    return self.client.query(
                        collection_name=self.collection_name,
                        filter=f'user_id == "{user_id}"',
                        output_fields=["text", "metadata"],
                        limit=self._QUERY_LIMIT,
                    )
                else:
                    return self.client.query(
                        collection_name=self.collection_name,
                        output_fields=["text", "metadata"],
                        limit=self._QUERY_LIMIT,
                    )

            all_docs = await asyncio.to_thread(_query)
            docs_info = {}

            for doc in all_docs:
                metadata = doc.get("metadata", {})
                content = doc.get("text", "")
                source = metadata.get("source", metadata.get("filename", "unknown"))
                if isinstance(source, str) and "\\" in source:
                    source = os.path.basename(source)
                filename = metadata.get("original_filename", source)

                if filename not in docs_info:
                    docs_info[filename] = {
                        "id": doc.get("id", ""),
                        "filename": filename,
                        "original_filename": metadata.get("original_filename", filename),
                        "user_id": metadata.get("user_id"),
                        "chunk_count": 0,
                        "preview": "",
                        "created_at": metadata.get("created_at"),
                    }

                docs_info[filename]["chunk_count"] += 1
                if not docs_info[filename]["preview"] and content:
                    preview_length = 100
                    docs_info[filename]["preview"] = content[:preview_length] + (
                        "..." if len(content) > preview_length else ""
                    )

            result = list(docs_info.values())
            logger.info(f"获取用户 {user_id} 的知识库文档，共 {len(result)} 个文件")
            return result
        except Exception as e:
            logger.error(f"获取用户 {user_id} 的知识库文档时出错: {e}")
            raise

    async def get_document_detail(self, user_id: str, filename: str):
        """获取文档的详细内容"""
        try:
            def _query():
                return self.client.query(
                    collection_name=self.collection_name,
                    filter=f'user_id == "{user_id}"',
                    output_fields=["text", "metadata"],
                    limit=self._QUERY_LIMIT,
                )

            all_docs = await asyncio.to_thread(_query)
            doc_info = None
            full_content = []
            chunk_count = 0

            for doc in all_docs:
                metadata = doc.get("metadata", {})
                content = doc.get("text", "")
                source = metadata.get("source", "")
                if isinstance(source, str):
                    source_name = os.path.basename(source)
                else:
                    source_name = str(source)
                original_filename = metadata.get("original_filename", "")

                if source_name == filename or original_filename == filename:
                    if not doc_info:
                        doc_info = {
                            "id": doc.get("id", ""),
                            "filename": filename,
                            "user_id": metadata.get("user_id"),
                            "chunk_count": 0,
                            "content": "",
                            "images": [],
                            "md5": metadata.get("md5"),
                            "created_at": metadata.get("created_at"),
                        }
                    chunk_count += 1
                    full_content.append(content)

            if doc_info:
                doc_info["chunk_count"] = chunk_count
                doc_info["content"] = "\n".join(full_content)

            return doc_info
        except Exception as e:
            logger.error(f"获取文档详情 {filename} 时出错: {e}")
            raise

    async def get_document_chunks(self, user_id: str, filename: str):
        """获取文档的所有切片信息"""
        try:
            def _query():
                return self.client.query(
                    collection_name=self.collection_name,
                    filter=f'user_id == "{user_id}"',
                    output_fields=["text", "metadata"],
                    limit=self._QUERY_LIMIT,
                )

            all_docs = await asyncio.to_thread(_query)
            chunks = []
            chunk_index = 0

            for doc in all_docs:
                metadata = doc.get("metadata", {})
                content = doc.get("text", "")
                source = metadata.get("source", "")
                if isinstance(source, str):
                    source_name = os.path.basename(source)
                else:
                    source_name = str(source)
                original_filename = metadata.get("original_filename", "")

                if source_name == filename or original_filename == filename:
                    chunks.append({
                        "chunk_id": doc.get("id", ""),
                        "index": chunk_index,
                        "content": content,
                        "metadata": metadata,
                        "images": [],
                    })
                    chunk_index += 1

            return {
                "filename": filename,
                "total_chunks": len(chunks),
                "chunks": chunks,
            }
        except Exception as e:
            logger.error(f"获取文档切片 {filename} 时出错: {e}")
            raise

    # DocumentProcessor 代理
    async def get_file_document(self, path: str, md5: str = None, user_id: str = None):
        return await self.document_processor.get_file_document(path, md5, user_id)

    def get_file_document_sync(self, path: str, md5: str = None, user_id: str = None):
        return self.document_processor.get_file_document_sync(path, md5, user_id)

    def split_documents_sync(self, docs):
        return self.document_processor.split_documents_sync(docs)

    async def get_document(self, files=None, user_id=None, progress_callback=None):
        await self.document_processor.get_document(files, user_id, progress_callback)

    def add_image_vectors(self, image_data: list) -> List[str]:
        """向图片 collection 添加图片向量"""
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
        search_params = {"metric_type": "COSINE", "params": {"nprobe": self._SEARCH_NPROBE}}

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


# 向后兼容别名
VectorStoreService = MilvusService
