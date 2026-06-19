import math
import time
from typing import List

from langchain_core.documents import Document
from app.utils.config import rag_config
from app.core.logger_handler import logger


class MultiFactorRanker:
    """多因素排序：相关性 + 时间衰减 + 文档权重"""

    def __init__(self):
        ranking_cfg = rag_config.get("ranking", {})
        self.w_relevance = ranking_cfg.get("w_relevance", 0.5)
        self.w_time = ranking_cfg.get("w_time", 0.3)
        self.w_weight = ranking_cfg.get("w_weight", 0.2)
        self.time_decay_lambda = ranking_cfg.get("time_decay_lambda", 1.0)

    async def rank(
        self,
        query: str,
        docs: List[Document],
        relevance_scores: List[float],
    ) -> List[Document]:
        """
        多因素排序
        :param query: 原始查询
        :param docs: 文档列表 (带 metadata)
        :param relevance_scores: 每个文档的 Reranker 相关性分数 [0,1]
        :return: 排序后的文档列表
        """
        now = time.time()
        scored = []

        for i, doc in enumerate(docs):
            rel = relevance_scores[i] if i < len(relevance_scores) else 0.5

            # 时间衰减
            created_at = doc.metadata.get("created_at", now)
            years_ago = (now - created_at) / (365 * 24 * 3600)
            time_decay = math.exp(-self.time_decay_lambda * years_ago)

            # 文档权重
            doc_weight = float(doc.metadata.get("doc_weight", 1.0))

            # 综合得分
            final_score = (
                self.w_relevance * rel +
                self.w_time * time_decay +
                self.w_weight * doc_weight
            )

            scored.append((final_score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)

        max_docs = rag_config["retrieval"]["max_documents"]
        result = [doc for _, doc in scored[:max_docs]]

        if scored:
            logger.info(
                f"多因素排序: {len(docs)}→{len(result)}, "
                f"top_score={scored[0][0]:.4f}"
            )
        return result
