# 此文件已废弃。
# BM25Retriever 已迁移到 Milvus 2.5 原生 sparse vector。
# 保留空文件避免 import 错误，后续可删除。

raise ImportError(
    "BM25Retriever 已迁移到 Milvus 原生 sparse vector，"
    "请使用 MilvusHybridRetriever (app.rag.retrievers.milvus_hybrid_retriever)"
)
