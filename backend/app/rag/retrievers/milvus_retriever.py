from typing import List

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun


class MilvusRetriever(BaseRetriever):
    """Milvus 向量检索器 (MilvusClient API)"""

    def __init__(self, client, collection_name: str, embed_model, user_id: str, k: int):
        super().__init__()
        self._client = client
        self._collection_name = collection_name
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
        results = self._client.search(
            collection_name=self._collection_name,
            data=query_embedding,
            limit=self._k,
            filter=f'user_id == "{self._user_id}"',
            search_params=search_params,
            output_fields=["text", "metadata"],
        )

        docs = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                docs.append(Document(
                    page_content=entity.get("text", ""),
                    metadata=entity.get("metadata", {}),
                ))
        return docs
