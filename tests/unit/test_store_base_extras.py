"""
Extra tests for BaseVectorStore helpers and defaults.
"""

from typing import Any, List, Optional

import pytest

from ragbot.rag.store.base import BaseVectorStore, VectorDocument, SearchResult


class DummyStore(BaseVectorStore):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._docs: dict[str, VectorDocument] = {}

    async def add_documents(self, documents: List[VectorDocument], **kwargs: Any) -> List[str]:
        for d in documents:
            self._docs[d.id] = d
        return [d.id for d in documents]

    async def update_documents(self, documents: List[VectorDocument], **kwargs: Any) -> List[str]:
        updated = []
        for d in documents:
            if d.id in self._docs:
                self._docs[d.id] = d
                updated.append(d.id)
        return updated

    async def delete_documents(self, document_ids: List[str], **kwargs: Any) -> List[str]:
        deleted = []
        for i in document_ids:
            if i in self._docs:
                del self._docs[i]
                deleted.append(i)
        return deleted

    async def search(self, query_embedding: List[float], top_k: int = 10, **kwargs: Any) -> SearchResult:
        docs = list(self._docs.values())[:top_k]
        return SearchResult(documents=docs, query_embedding=query_embedding, total_results=len(docs))

    async def get_document(self, document_id: str) -> Optional[VectorDocument]:
        return self._docs.get(document_id)

    async def get_documents(self, document_ids: List[str]) -> List[VectorDocument]:
        return [self._docs[i] for i in document_ids if i in self._docs]

    def get_document_count(self) -> int:
        return len(self._docs)

    async def clear(self) -> None:
        self._docs.clear()

    async def save(self, path: Optional[str] = None) -> None:  # pragma: no cover - noop
        return None

    async def load(self, path: Optional[str] = None) -> None:  # pragma: no cover - noop
        return None


@pytest.mark.asyncio
async def test_upsert_documents_and_filters_and_info(monkeypatch):
    store = DummyStore(similarity_metric="cosine")
    d1 = VectorDocument(id="1", content="hello", embedding=[1, 0], metadata={"tag": "a", "num": 5})
    d2 = VectorDocument(id="2", content="world", embedding=[0, 1], metadata={"tag": "b", "num": 10})
    await store.add_documents([d1])

    # Upsert: one update, one add
    updated = await store.upsert_documents([d1, d2])
    assert set(updated) == {"1", "2"}

    # Filter helpers
    docs = [d1, d2]
    eq = store.filter_documents(docs, {"tag": "a"})
    assert [d.id for d in eq] == ["1"]

    rng = store.filter_documents(docs, {"num": {"$gte": 6, "$lte": 10}})
    assert [d.id for d in rng] == ["2"]

    in_list = store.filter_documents(docs, {"tag": ["b", "c"]})
    assert [d.id for d in in_list] == ["2"]

    # compute_similarity variants
    store.similarity_metric = "cosine"
    assert store.compute_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    store.similarity_metric = "euclidean"
    assert store.compute_similarity([1, 0], [0, 1]) < 1.0
    store.similarity_metric = "dot_product"
    assert store.compute_similarity([1, 2], [3, 4]) == 11.0
    store.similarity_metric = "unknown"
    assert store.compute_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    # error path
    assert store.compute_similarity([1, 0], ["x"]) == 0.0

    # Store info
    info = store.get_store_info()
    assert info["store_type"] == "DummyStore"
    assert info["embedding_dimension"] == 768  # default from BaseVectorStore

    # search_by_text delegates to embedder
    class E:
        async def embed_single(self, t: str):
            return [0.0, 0.0]

    res = await store.search_by_text("hi", E())
    assert isinstance(res, SearchResult)
    assert isinstance(res.documents, list)

    # health_check
    health = await store.health_check()
    assert health["status"] == "healthy"

