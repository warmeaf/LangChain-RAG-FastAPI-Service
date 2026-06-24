import asyncio
import os
from typing import List, Dict, Any

import torch
from sentence_transformers import CrossEncoder
from app.utils.config import rag_config
from app.core.logger_handler import logger


class ReorderService:
    """文档重排序服务 (bge-reranker-large)"""

    def __init__(self):
        model_name = os.getenv("RERANKER_MODEL_PATH") or os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-large")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = None
        self._model_name = model_name

    def _load_model_sync(self):
        model = CrossEncoder(self._model_name, max_length=512, device=self.device)
        return model

    async def _get_model(self):
        if self._model is None:
            logger.info(f"✅ 加载重排序模型: {self._model_name}")
            self._model = await asyncio.to_thread(self._load_model_sync)
            logger.info(f"✅ 模型加载成功，使用设备: {self.device}")
        return self._model

    @property
    async def model(self):
        return await self._get_model()

    async def reorder_documents(
        self, query: str, documents: List[str], thinking_callback=None
    ) -> Dict[str, Any]:
        try:
            if not documents:
                return {"success": True, "documents": [], "error": ""}

            if thinking_callback:
                await thinking_callback({
                    "type": "thinking",
                    "stage": "reorder",
                    "content": f"正在计算 {len(documents)} 个文档的相关性分数..."
                })

            pairs = [(query, doc) for doc in documents]
            model = await self.model

            batch_size = rag_config.get("reranker", {}).get("batch_size", 16)
            with torch.no_grad():
                raw_scores = await asyncio.to_thread(
                    model.predict, pairs, batch_size=batch_size
                )

            min_score = min(raw_scores)
            max_score = max(raw_scores)
            score_range = max_score - min_score if max_score != min_score else 1.0
            normalized_scores = [(s - min_score) / score_range for s in raw_scores]

            scored_documents = []
            for doc, norm_score, raw_score in zip(documents, normalized_scores, raw_scores):
                scored_documents.append({
                    "document": doc,
                    "similarity": float(norm_score),
                })
                logger.info(f"【重排序服务】文档相似度分数: {raw_score:.4f} -> 归一化: {norm_score:.4f}")

            if thinking_callback:
                score_details = []
                for i, (doc, norm_score) in enumerate(zip(documents, normalized_scores), 1):
                    score_details.append({
                        "index": i,
                        "score": round(float(norm_score), 4),
                        "preview": doc[:100] + "..." if len(doc) > 100 else doc,
                    })
                await thinking_callback({
                    "type": "thinking",
                    "stage": "reorder",
                    "content": f"已计算完成 {len(documents)} 个文档的相关性分数，按分数降序排序",
                    "details": {"scores": score_details},
                })

            sorted_docs = sorted(scored_documents, key=lambda x: x["similarity"], reverse=True)
            logger.info(f"【重排序服务】文档重排序成功，返回 {len(sorted_docs)} 个文档")
            return {"success": True, "documents": sorted_docs, "error": ""}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"【重排序服务】重排序失败: {error_msg}")
            return {"success": False, "documents": [], "error": error_msg}

    @staticmethod
    async def format_reorder_result(sorted_docs: List[Dict]) -> str:
        formatted_result = "重排序后的文档列表：\n"
        for i, doc in enumerate(sorted_docs, 1):
            formatted_result += f"{i}. 相似度: {doc.get('similarity', 0):.4f}\n"
            formatted_result += f"   内容: {doc.get('document', '')}\n\n"
        return formatted_result


# 全局重排序服务实例
reorder_service = ReorderService()
