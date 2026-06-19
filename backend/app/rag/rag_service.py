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
                    key = doc.page_content[:100]
                    if key not in seen:
                        seen.add(key)
                        merged.append(doc)

        logger.info(f"多路检索: {len(queries)}个变体 → {len(merged)}个去重文档")
        return merged

    @traceable
    async def get_documents_and_summary(self, query: str) -> dict:
        if not self.user_id:
            return {"documents": [], "summary": "抱歉，我没有找到相关的信息。"}

        try:
            # ① 查询预处理
            query_variants = await self.query_processor.process(query)
            hyde_variant = await self._generate_hyde(query)
            all_variants = query_variants + [hyde_variant]

            if self.thinking_callback:
                await self.thinking_callback({
                    "type": "thinking",
                    "stage": "query_processing",
                    "content": f"查询预处理完成: {len(all_variants)} 个检索变体",
                })

            # ② 粗排: 多路并行检索 → 合并
            documents = await self.retrieve_documents_batch(all_variants)

            if self.thinking_callback:
                await self.thinking_callback({
                    "type": "thinking",
                    "stage": "retrieval",
                    "content": f"粗排检索完成: {len(documents)} 个候选文档",
                })

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

            if not documents:
                return {"documents": [], "summary": "抱歉，我没有找到相关的信息。"}

            # ③ 精排: Reranker
            doc_contents = [doc.page_content for doc in documents]
            rerank_result = await reorder_service.reorder_documents(
                query, doc_contents, thinking_callback=self.thinking_callback
            )
            if rerank_result["success"]:
                reranked = rerank_result["documents"]
                relevance_scores = [d["similarity"] for d in reranked]
                # 重建 Document 列表 (保留 metadata)
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

            # ④ 多因素排序
            final_docs = await self.ranker.rank(query, ordered_docs, ordered_scores, self.user_id)

            if self.thinking_callback:
                await self.thinking_callback({
                    "type": "thinking",
                    "stage": "ranking",
                    "content": f"多因素排序完成: {len(final_docs)} 篇文档",
                })

            # ⑤ 异步写入 QueryLog（不阻塞主流程）
            asyncio.create_task(self._log_query(query, final_docs))

            # ⑥ 分批总结
            summary = await self._batch_summarize(query, final_docs)

            return {
                "documents": [doc.page_content for doc in final_docs],
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"RAG 流水线失败: {e}", exc_info=True)
            return {"documents": [], "summary": "抱歉，处理您的请求时出现了错误。"}

    async def _generate_hyde(self, query: str) -> str:
        """生成 HyDE 假设文档（作为检索变体之一）"""
        try:
            hyde_prompt = PromptTemplate.from_template(
                "基于以下问题，生成一个详细的假设性回答：\n\n{query}\n\n假设性回答："
            )
            chain = hyde_prompt | self.chat_model | StrOutputParser()
            result = await chain.ainvoke({"query": query})
            return result.strip() if result else query
        except Exception:
            return query

    async def _batch_summarize(self, query: str, documents: list) -> str:
        """直接汇总所有文档原文（不做逐篇总结，保留完整上下文）"""
        if not documents:
            return "抱歉，我没有找到相关的信息。"

        max_docs = rag_config["retrieval"]["max_documents"]
        docs = documents[:max_docs]

        # 直接拼接所有文档原文作为上下文
        combined = ""
        for i, doc in enumerate(docs, 1):
            combined += f"【参考资料{i}】\n{doc.page_content}\n\n"

        try:
            final = await asyncio.wait_for(
                self.chain.ainvoke({"input": query, "context": combined}),
                timeout=30.0,
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
        except Exception:
            pass

    @traceable
    async def rag_summary(self, query: str) -> str:
        result = await self.get_documents_and_summary(query)
        return result.get("summary", "抱歉，处理您的请求时出现了错误。")
