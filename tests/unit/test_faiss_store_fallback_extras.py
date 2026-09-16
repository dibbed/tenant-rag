"""
Extended tests for FAISSStore fallback implementation (in-memory).
"""

from pathlib import Path

import pytest

from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.faiss_store import FAISSStore


@pytest.mark.asyncio
async def test_faiss_fallback_add_update_delete_save_load(tmp_path: Path):
    store_path = tmp_path / "faiss_fallback"
    store = FAISSStore(store_path=str(store_path))

    # Add via add_documents directly
    docs = [
        VectorDocument(id="a", content="foo", embedding=[0.0] * store.embedding_dimension, metadata={}),
        VectorDocument(id="b", content="bar", embedding=[0.0] * store.embedding_dimension, metadata={}),
    ]
    added = await store.add_documents(docs)
    assert set(added) == {"a", "b"}
    assert store.count() == 2

    # Update a doc
    docs[0].content = "foo2"
    updated = await store.update_documents([docs[0]])
    assert updated == ["a"]

    # Search should return results
    res = await store.search([0.1] * store.embedding_dimension, top_k=1)
    assert res.documents and len(res.documents) == 1

    # Query result may be an awaitable list wrapper or a direct list
    import asyncio
    qr = store.query([0.1] * store.embedding_dimension, top_k=2)
    if asyncio.iscoroutine(qr) or hasattr(qr, "__await__"):
        qres = await qr  # type: ignore[func-returns-value]
    else:
        qres = qr  # type: ignore[assignment]
    assert isinstance(qres, list)
    assert len(qres) <= 2

    # get_documents
    got = await store.get_documents(["a", "b", "c"])
    assert [d.id for d in got] == ["a", "b"]

    # Persist and reload
    await store.save()
    store2 = FAISSStore(store_path=str(store_path))
    await store2.load()
    assert store2.count() == 2

    # Delete and clear
    deleted = await store2.delete_documents(["a"])  # type: ignore
    assert deleted == ["a"]
    assert store2.count() == 1
    await store2.clear()
    assert store2.count() == 0
