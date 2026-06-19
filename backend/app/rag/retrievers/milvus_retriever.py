from typing import List

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun


class MilvusRetriever(BaseRetriever):
    """Milvus 向量检索器"""

    def __init__(self, collection, embed_model, user_id: str, k: int):
        super().__init__()
        self._collection = collection
        self._embed_model = embed_model
        self._user_id = user_id
        self._k = k

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        query_embedding = self._embed_model.encode(
            [query], normalize_embeddings=True
        ).tolist()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = self._collection.search(
            data=query_embedding,
            anns_field="embedding",
            param=search_params,
            limit=self._k,
            expr=f'user_id == "{self._user_id}"',
            output_fields=["text", "metadata"],
        )

        docs = []
        for hits in results:
            for hit in hits:
                docs.append(Document(
                    page_content=hit.entity.get("text", ""),
                    metadata=hit.entity.get("metadata", {}),
                ))
        return docs
