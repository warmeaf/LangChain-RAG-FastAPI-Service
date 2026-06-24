from typing import List

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pymilvus import AnnSearchRequest, WeightedRanker, RRFRanker


class MilvusHybridRetriever(BaseRetriever):
    """Milvus 原生 hybrid search：dense（向量）+ sparse（BM25）融合检索。

    用 Milvus 2.5 的 hybrid_search + WeightedRanker 替代自研 RRF，
    支持运行时动态权重切换（balanced/precise/semantic）。
    """

    client: object
    collection_name: str
    embed_model: object
    user_id: str
    k: int
    dense_weight: float
    sparse_weight: float
    nprobe: int = 16
    reranker: str = "weighted"
    rrf_k: int = 60

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        # ① 编码 query → dense 向量
        query_embedding = self.embed_model.encode(
            [query], normalize_embeddings=True
        ).tolist()

        # ② 构造 dense 检索请求
        dense_req = AnnSearchRequest(
            data=query_embedding,
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": self.nprobe}},
            limit=self.k,
            expr=f'user_id == "{self.user_id}"',
        )

        # ③ 构造 sparse 检索请求（传原始文本，BM25 Function 自动转换）
        sparse_req = AnnSearchRequest(
            data=[query],
            anns_field="sparse",
            param={"metric_type": "BM25"},
            limit=self.k,
            expr=f'user_id == "{self.user_id}"',
        )

        # ④ 选择 reranker（运行时动态权重）
        if self.reranker == "rrf":
            ranker = RRFRanker(self.rrf_k)
        else:
            # WeightedRanker 参数顺序对应 reqs 列表顺序：[dense_req, sparse_req]
            ranker = WeightedRanker(self.dense_weight, self.sparse_weight)

        # ⑤ 执行 hybrid search
        results = self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=ranker,
            limit=self.k,
            output_fields=["text", "metadata"],
        )

        # ⑥ 转换结果为 Document 列表
        docs = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                docs.append(Document(
                    page_content=entity.get("text", ""),
                    metadata=entity.get("metadata", {}),
                ))
        return docs
