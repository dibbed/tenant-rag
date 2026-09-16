"""
More path coverage for DocumentRetriever and legacy retrieve_topk.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ragbot.rag.exceptions import RetrievalError
from ragbot.rag.retrieve.retriever import DocumentRetriever
from ragbot.rag.store.base import SearchResult, VectorDocument


@pytest.mark.asyncio
async def test_embed_texts_fallback_and_list_search_result():
    # Vector store returns a plain list (no .documents attribute)
    docs = [VectorDocument(id="x", content="c", embedding=[], metadata={}, score=0.3)]
    store = MagicMock()
    store.search = AsyncMock(return_value=docs)

    # Embedder exposes embed_texts
    embedder = MagicMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])

    r = DocumentRetriever(store, embedder)
    res = await r.retrieve("q")
    assert [d.id for d in res] == ["x"]


@pytest.mark.asyncio
async def test_asyncmock_query_preferred_over_search():
    store = MagicMock()
    store.query = AsyncMock(
        return_value=[
            VectorDocument(id="a", content="c", embedding=[], metadata={}, score=0.1)
        ]
    )
    store.search = AsyncMock(return_value=SearchResult(documents=[]))

    embedder = MagicMock()
    embedder.embed_single = AsyncMock(return_value=[0.5])

    r = DocumentRetriever(store, embedder, top_k=1)
    out = await r.retrieve("q")
    assert len(out) == 1 and out[0].id == "a"


@pytest.mark.asyncio
async def test_vector_store_query_error_wrapped():
    store = MagicMock()
    store.query = AsyncMock(side_effect=TypeError("bad call"))

    embedder = MagicMock()
    embedder.embed_single = AsyncMock(return_value=[0.5])

    r = DocumentRetriever(store, embedder)
    with pytest.raises(RetrievalError):
        await r.retrieve("q")


@pytest.mark.asyncio
async def test_retrieve_by_embedding_error_wraps():
    store = MagicMock()
    store.search = AsyncMock(side_effect=RuntimeError("boom"))
    r = DocumentRetriever(store, MagicMock())
    with pytest.raises(RetrievalError):
        await r.retrieve_by_embedding([0.1, 0.2])


def test_get_retriever_info():
    # Info
    st = SimpleNamespace()
    emb = SimpleNamespace()
    r = DocumentRetriever(st, emb)
    info = r.get_retriever_info()
    assert info["vector_store_type"] == type(st).__name__

    # Ensure retriever info is populated
