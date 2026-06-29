"""关键词检索工具（BM25）

从 MilvusHybridRetriever 拆出 BM25 分支，封装为独立工具。
基于 Milvus 2.5 内置 BM25 Function（sparse 字段 + SPARSE_INVERTED_INDEX）。
"""

from typing import Optional
from contextvars import ContextVar

from langchain_core.tools import tool
from langchain_core.documents import Document

from app.core.logger_handler import logger
from app.rag.milvus_store import MilvusService

current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)


@tool
async def keyword_search(query: str, user_id: Optional[str] = None) -> str:
    """使用 BM25 关键词检索文档。

    基于 Milvus 内置 BM25 算法进行精确关键词匹配，适合查找专有名词、
    精确术语、ID、公司名等需要精确匹配的内容。
    返回每个 chunk 带 [来源: xxx, 相关度: 0.xx] 标注的拼接文本。

    Args:
        query: 检索关键词或短语
        user_id: 用户ID（系统自动注入，无需手动传入）
    """
    from app.agent.tools.vector_search import get_current_user_id
    effective_user_id = user_id or get_current_user_id()
    if not effective_user_id:
        return "错误: 无法确定用户身份"

    milvus = MilvusService()

    try:
        from pymilvus import AnnSearchRequest

        expr = f'user_id == "{effective_user_id}"'

        # 仅 sparse BM25 检索
        sparse_req = AnnSearchRequest(
            data=[query],
            anns_field="sparse",
            param={"metric_type": "BM25"},
            limit=30,
            expr=expr,
        )

        results = milvus.client.hybrid_search(
            collection_name=milvus.collection_name,
            reqs=[sparse_req],
            ranker=None,  # 单路检索无需 ranker
            limit=30,
            output_fields=["text", "metadata"],
        )

        # 转换结果
        docs = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                score = hit.get("distance", 0)
                docs.append({
                    "content": entity.get("text", ""),
                    "metadata": entity.get("metadata", {}),
                    "score": score,
                })

        if not docs:
            return "未找到相关文档。"

        # 格式化输出
        lines = [f"关键词检索结果（共 {len(docs)} 条）:\n"]
        for i, doc in enumerate(docs[:15], 1):
            source = doc["metadata"].get("original_filename", "") or doc["metadata"].get("source", "")
            score = doc.get("score", 0)
            lines.append(f"[{i}] [来源: {source}, BM25分数: {score:.3f}]")
            lines.append(doc["content"][:800])
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"关键词检索失败: {e}", exc_info=True)
        return f"关键词检索出错: {str(e)}"
