import asyncio
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langsmith import traceable

from app.rag.milvus_store import MilvusService
from app.rag.reorder_service import reorder_service
from app.rag.query_processor import QueryProcessor
from app.rag.multi_factor_ranker import MultiFactorRanker
from app.utils.config import rag_config
from app.utils.factory import chat_model
from app.utils.prompt_loader import load_prompt
from app.core.logger_handler import logger


class RagService:
    """企业级 RAG 服务：查询预处理 → 粗排 → 精排 → 多因素排序 → 总结"""

    # 流水线超时配置（秒）——单阶段超时降级，总超时兜底
    _TIMEOUT_TOTAL = 60          # 整条流水线总超时
    _TIMEOUT_PREPROCESS = 20     # ① 查询预处理
    _TIMEOUT_HYDE = 15           #    HyDE 生成
    _TIMEOUT_RETRIEVE = 15       # ② 粗排检索
    _TIMEOUT_IMAGE = 8           #    图片检索（非关键通路）
    _TIMEOUT_RERANK = 20         # ③ 精排
    _TIMEOUT_RANK = 10           # ④ 多因素排序
    _TIMEOUT_EXPAND = 10         #    chunk 扩展
    _TIMEOUT_SUMMARY = 30        # ⑥ 分批总结

    # 文档去重：按内容前缀去重，避免重复 chunk 进入下游
    _DEDUP_CONTENT_PREFIX = 100

    # 上下文组装预算：按字符数截断（1 中文字 ≈ 1.5 token，6000 字符 ≈ 9K token）
    # 为 64K context window 留足输出空间，防御性保护
    _MAX_CONTEXT_CHARS = 6000

    def __init__(self, user_id: str = None, thinking_callback=None):
        self.milvus = MilvusService()
        self.retriever = None
        self.user_id = user_id
        self.prompt_text = load_prompt(prompt_type="rag_summary_prompt")
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.chat_model = chat_model
        self.chain = self.prompt_template | self.chat_model | StrOutputParser()
        self.query_processor = QueryProcessor()
        self.ranker = MultiFactorRanker()
        self.thinking_callback = thinking_callback
        self._log_task = None

    async def initialize_retriever(self, query: str = None):
        if self.retriever is None:
            if self.thinking_callback:
                await self.thinking_callback({
                    "type": "thinking",
                    "stage": "retrieval",
                    "content": "初始化 Milvus 混合检索器...",
                })
            self.retriever = await self.milvus.get_retriever(query, self.user_id)

    @traceable
    async def retrieve_documents_batch(self, queries: list) -> list:
        """并行检索多个查询变体，合并去重结果"""
        await self.initialize_retriever(queries[0] if queries else "")

        tasks = [self.retriever.ainvoke(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        seen = set()
        merged = []
        for result in results:
            if isinstance(result, list):
                for doc in result:
                    key = self._dedup_key(doc)
                    if key not in seen:
                        seen.add(key)
                        merged.append(doc)

        logger.info(f"多路检索: {len(queries)}个变体 → {len(merged)}个去重文档")
        return merged

    @staticmethod
    def _dedup_key(doc) -> str:
        """生成文档去重 key（取内容前缀，与图片去重保持一致）"""
        return doc.page_content[:RagService._DEDUP_CONTENT_PREFIX]

    @traceable
    async def get_documents_and_summary(self, query: str) -> dict:
        if not self.user_id:
            return {"documents": [], "summary": "抱歉，我没有找到相关的信息。"}

        try:
            return await asyncio.wait_for(self._pipeline_inner(query), timeout=self._TIMEOUT_TOTAL)
        except asyncio.TimeoutError:
            logger.error("RAG 流水线总超时(%ss)，query=%s", self._TIMEOUT_TOTAL, query[:100])
            return {"documents": [], "summary": "抱歉，处理您的请求超时，请稍后重试。"}
        except Exception as e:
            logger.error(f"RAG 流水线失败: {e}", exc_info=True)
            return {"documents": [], "summary": "抱歉，处理您的请求时出现了错误。"}

    async def _pipeline_inner(self, query: str) -> dict:
        """RAG 流水线主体（由 get_documents_and_summary 包 60s 总超时）"""

        # ① 查询预处理（超时降级：用原始 query）
        try:
            query_variants = await asyncio.wait_for(
                self.query_processor.process(query), timeout=self._TIMEOUT_PREPROCESS
            )
            hyde_variant = await asyncio.wait_for(
                self._generate_hyde(query), timeout=self._TIMEOUT_HYDE
            )
            all_variants = query_variants + [hyde_variant]
        except asyncio.TimeoutError:
            logger.warning("查询预处理超时，使用原始查询")
            all_variants = [query]

        if self.thinking_callback:
            await self.thinking_callback({
                "type": "thinking",
                "stage": "query_processing",
                "content": f"查询预处理完成: {len(all_variants)} 个检索变体",
            })

        # ② 粗排: 多路并行检索 → 合并（超时降级：返回空）
        try:
            documents = await asyncio.wait_for(
                self.retrieve_documents_batch(all_variants), timeout=self._TIMEOUT_RETRIEVE
            )
        except asyncio.TimeoutError:
            logger.warning("粗排检索超时")
            documents = []

        if self.thinking_callback:
            await self.thinking_callback({
                "type": "thinking",
                "stage": "retrieval",
                "content": f"粗排检索完成: {len(documents)} 个候选文档",
            })

        # 图片视觉检索通路（跨模态 CLIP，超时8s降级：跳过）
        image_docs = []
        if rag_config.get("image_retrieval", {}).get("enabled", True):
            try:
                image_docs = await asyncio.wait_for(
                    self.milvus.search_images(
                        query, self.user_id,
                        top_k=rag_config.get("image_retrieval", {}).get("max_image_chunks", 5)
                    ),
                    timeout=self._TIMEOUT_IMAGE,
                )
            except asyncio.TimeoutError:
                logger.warning("图片检索超时，跳过图片通路")
            except Exception as e:
                logger.warning(f"图片检索失败，跳过图片通路: {e}", exc_info=True)

        if image_docs:
            existing_keys = set(self._dedup_key(doc) for doc in documents)
            for idoc in image_docs:
                if self._dedup_key(idoc) not in existing_keys:
                    documents.append(idoc)

        if self.thinking_callback:
            await self.thinking_callback({
                "type": "thinking",
                "stage": "retrieval",
                "content": f"粗排检索完成: {len(documents)} 个候选文档 (含 {len(image_docs)} 个图片结果)",
            })

        if not documents:
            return {"documents": [], "summary": "抱歉，我没有找到相关的信息。"}

        # ③ 精排: Reranker（超时降级：用粗排结果）
        doc_contents = [doc.page_content for doc in documents]
        try:
            rerank_result = await asyncio.wait_for(
                reorder_service.reorder_documents(
                    query, doc_contents, thinking_callback=self.thinking_callback
                ),
                timeout=self._TIMEOUT_RERANK,
            )
            if rerank_result["success"]:
                reranked = rerank_result["documents"]
                content_to_doc = {doc.page_content: doc for doc in documents}
                ordered_docs = []
                ordered_scores = []
                for rd in reranked:
                    content = rd["document"]
                    if content in content_to_doc:
                        ordered_docs.append(content_to_doc[content])
                        ordered_scores.append(rd["similarity"])
            else:
                ordered_docs = documents
                ordered_scores = [0.5] * len(documents)
        except asyncio.TimeoutError:
            logger.warning("精排超时，使用粗排结果")
            ordered_docs = documents
            ordered_scores = [0.5] * len(documents)

        # ④ 多因素排序 + chunk扩展（超时降级：用精排结果）
        try:
            final_docs = await asyncio.wait_for(
                self.ranker.rank(query, ordered_docs, ordered_scores, self.user_id),
                timeout=self._TIMEOUT_RANK,
            )
            final_docs = await asyncio.wait_for(
                self._expand_adjacent_chunks(final_docs), timeout=self._TIMEOUT_EXPAND
            )
        except asyncio.TimeoutError:
            logger.warning("多因素排序/扩展超时，使用精排结果")
            final_docs = ordered_docs

        if self.thinking_callback:
            await self.thinking_callback({
                "type": "thinking",
                "stage": "ranking",
                "content": f"多因素排序完成: {len(final_docs)} 篇文档",
            })

        # ⑤ 异步写入 QueryLog（不阻塞主流程，保留 task 引用避免 GC）
        self._log_task = asyncio.create_task(self._log_query(query, final_docs))
        self._log_task.add_done_callback(self._on_log_done)

        # ⑥ 分批总结（内部已有 30s 超时）
        summary = await self._batch_summarize(query, final_docs)

        return {
            "documents": [doc.page_content for doc in final_docs],
            "summary": summary,
        }

    def _on_log_done(self, task):
        """create_task 完成回调：记录未捕获异常"""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"查询日志异步写入失败: {exc}", exc_info=exc)

    async def _expand_adjacent_chunks(self, docs: list) -> list:
        """为检索到的文档补充相邻 chunk（上下文扩展）"""
        from langchain_core.documents import Document

        if not docs or not self.user_id:
            return docs

        # 按 source 分组，收集需要扩展的 chunk_index
        source_neighbors: dict[str, set] = {}
        existing = set()
        for doc in docs:
            src = doc.metadata.get("source", "")
            ci = doc.metadata.get("chunk_index")
            if src and ci is not None:
                existing.add((src, ci))
                source_neighbors.setdefault(src, set())
                source_neighbors[src].add(ci - 1)
                source_neighbors[src].add(ci + 1)

        # 并行查询所有需要的相邻 chunk
        tasks = []
        for src, indices in source_neighbors.items():
            # 排除已存在的和负数索引
            needed = {i for i in indices if i >= 0 and (src, i) not in existing}
            if needed:
                tasks.append(self.milvus.get_adjacent_chunks(src, needed, self.user_id))

        if not tasks:
            return docs

        results = await asyncio.gather(*tasks)
        for chunk_map in results:
            for ci, chunk_doc in chunk_map.items():
                docs.append(chunk_doc)

        return docs

    async def _generate_hyde(self, query: str) -> str:
        """生成 HyDE 假设文档（作为检索变体之一）"""
        try:
            hyde_prompt = PromptTemplate.from_template(
                "基于以下问题，生成一个详细的假设性回答：\n\n{query}\n\n假设性回答："
            )
            chain = hyde_prompt | self.chat_model | StrOutputParser()
            result = await chain.ainvoke({"query": query})
            return result.strip() if result else query
        except Exception as e:
            logger.debug(f"HyDE 生成失败，使用原始查询: {e}")
            return query

    async def _batch_summarize(self, query: str, documents: list) -> str:
        """直接汇总所有文档原文（不做逐篇总结，保留完整上下文）"""
        if not documents:
            return "抱歉，我没有找到相关的信息。"

        max_docs = rag_config["retrieval"]["max_documents"]
        docs = documents[:max_docs]

        # 拼接文档原文作为上下文，带 [编号] 供 LLM 引用，按字符预算截断
        combined = ""
        total_chars = 0
        for i, doc in enumerate(docs, 1):
            chunk_text = f"[{i}] {doc.page_content}\n\n"
            if total_chars + len(chunk_text) > self._MAX_CONTEXT_CHARS:
                logger.info(f"上下文达字符预算({self._MAX_CONTEXT_CHARS})，截断于第 {i} 篇文档")
                break
            combined += chunk_text
            total_chars += len(chunk_text)

        try:
            final = await asyncio.wait_for(
                self.chain.ainvoke({"input": query, "context": combined}),
                timeout=self._TIMEOUT_SUMMARY,
            )
            return final
        except asyncio.TimeoutError:
            return "生成摘要超时，请稍后重试。"

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
        except Exception as e:
            logger.error(f"查询日志写入失败: {e}", exc_info=True)

    @traceable
    async def rag_summary(self, query: str) -> str:
        result = await self.get_documents_and_summary(query)
        return result.get("summary", "抱歉，处理您的请求时出现了错误。")
