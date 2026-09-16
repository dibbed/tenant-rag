import asyncio

import pytest

from ragbot.rag.store.base import BaseVectorStore, VectorDocument
from ragbot.outputs.metrics import metrics_manager


class _DummyStore(BaseVectorStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store_type_label = "dummy"

    async def add_documents(self, documents, **kwargs):
        return [d.id for d in documents]

    async def update_documents(self, documents, **kwargs):
        return [d.id for d in documents]

    async def delete_documents(self, document_ids, **kwargs):
        return document_ids

    async def search(self, query_embedding, top_k=10, **kwargs):
        return type("_R", (), {"documents": []})

    async def get_document(self, document_id):
        return None

    async def get_documents(self, document_ids):
        return []

    def get_document_count(self) -> int:
        return 42

    async def clear(self):
        return None

    async def save(self, path=None):
        return None

    async def load(self, path=None):
        return None


@pytest.mark.asyncio
async def test_base_analytics_aggregate():
    store = _DummyStore(embedding_dimension=4)

    # feed some vector-store operations into metrics
    metrics_manager.record_vector_store_operation(
        operation="search", store_type=store.store_type_label, document_count=3, success=True, duration=0.01
    )
    metrics_manager.record_vector_store_operation(
        operation="add_documents", store_type=store.store_type_label, document_count=5, success=True, duration=0.02
    )
    metrics_manager.update_vector_store_size(42, store_type=store.store_type_label)

    s = await store.get_search_analytics()
    d = await store.get_document_analytics()

    assert s["store_type"] == "dummy"
    assert s["total_searches"] >= 1
    assert d["total_documents"] == 42
