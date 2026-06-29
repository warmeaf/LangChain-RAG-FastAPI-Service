"""向量语义检索工具

从 RagService 拆出，只做检索不含摘要。
内部能力：查询预处理、HyDE 生成、dense 向量检索、重排序（bge-reranker）、chunk 扩展。
"""

import asyncio
from typing import Optional
from contextvars import ContextVar

from langchain_core.tools import tool
from langchain_core.documents import Document

from app.core.logger_handler import logger
from app.rag.milvus_store import MilvusService
from app.rag.reorder_service import reorder_service
from app.rag.query_processor import QueryProcessor

# ContextVar 由 agent graph 在每次请求时设置
current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)


def set_current_user_id(user_id: str):
    """设置当前用户 ID 到上下文"""
    current_user_id_var.set(user_id)


def get_current_user_id() -> str:
    """从上下文获取当前用户 ID"""
    return current_user_id_var.get()


@tool
async def vector_search(query: str, user_id: Optional[str] = None) -> str:
    """在向量数据库中语义检索文档。

    使用 dense 向量进行语义相似度检索，经过重排序和 chunk 扩展后返回相关文档内容。
    适合查找语义相关、概念相似的内容。
    返回每个 chunk 带 [来源: xxx, 相关度: 0.xx] 标注的拼接文本。

    Args:
        query: 检索查询语句（自然语言）
        user_id: 用户ID（系统自动注入，无需手动传入）
    """
    effective_user_id = user_id or get_current_user_id()
    if not effective_user_id:
        return "错误: 无法确定用户身份"

    milvus = MilvusService()
    query_processor = QueryProcessor()

    try:
        # ① 查询预处理 + HyDE
        try:
            query_variants = await asyncio.wait_for(
                query_processor.process(query), timeout=20
            )
            all_variants = query_variants + [query]  # 加上原始 query
        except asyncio.TimeoutError:
            all_variants = [query]
        except Exception as e:
            logger.warning(f"查询预处理失败: {e}")
            all_variants = [query]

        # ② 多路并行检索 → 合并去重
        retriever = await milvus.get_retriever(query, effective_user_id)
        tasks = [retriever.ainvoke(q) for q in all_variants]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        seen = set()
        documents = []
        for result in results:
            if isinstance(result, list):
                for doc in result:
                    key = doc.page_content[:100]  # 去重 key
                    if key not in seen:
                        seen.add(key)
                        documents.append(doc)

        if not documents:
            return "未找到相关文档。"

        # ③ 重排序
        doc_contents = [doc.page_content for doc in documents]
        try:
            rerank_result = await asyncio.wait_for(
                reorder_service.reorder_documents(query, doc_contents),
                timeout=20,
            )
            if rerank_result["success"]:
                content_to_doc = {doc.page_content: doc for doc in documents}
                documents = []
                for rd in rerank_result["documents"][:20]:
                    content = rd["document"]
                    if content in content_to_doc:
                        doc = content_to_doc[content]
                        doc.metadata["_rerank_score"] = rd.get("similarity", 0.5)
                        documents.append(doc)
        except Exception as e:
            logger.warning(f"重排序失败: {e}")

        # ④ 格式化输出
        lines = [f"向量检索结果（共 {len(documents)} 条）:\n"]
        for i, doc in enumerate(documents[:15], 1):
            source = doc.metadata.get("original_filename", "") or doc.metadata.get("source", "")
            score = doc.metadata.get("_rerank_score", "")
            score_str = f", 相关度: {score:.3f}" if isinstance(score, (int, float)) else ""
            lines.append(f"[{i}] [来源: {source}{score_str}]")
            lines.append(doc.page_content[:800])
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"向量检索失败: {e}", exc_info=True)
        return f"向量检索出错: {str(e)}"
