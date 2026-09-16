"""
Additional tests for DocumentRetriever to cover search-path, retrieve_by_embedding,
error paths, and health checks.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ragbot.rag.retrieve.retriever import DocumentRetriever
from ragbot.rag.store.base import VectorDocument, SearchResult


@pytest.mark.asyncio
async def test_retriever_uses_search_path_when_query_missing():
    # Vector store exposes only search()
    mock_store = MagicMock()
    docs = [
        VectorDocument(id="a", content="foo", embedding=[0.0], metadata={}, score=0.1),
        VectorDocument(id="b", content="bar", embedding=[0.0], metadata={}, score=0.2),
    ]
    mock_store.search = AsyncMock(return_value=SearchResult(documents=docs))

    # Embedder exposes embed_single, not embed_text
    mock_embedder = MagicMock()
    mock_embedder.embed_single = AsyncMock(return_value=[0.2] * 8)

    r = DocumentRetriever(mock_store, mock_embedder, top_k=1)
    res = await r.retrieve("hello")
    assert isinstance(res, list)
    # top_k limit enforced after sorting
    assert len(res) == 1
    assert res[0].id in {"a", "b"}


@pytest.mark.asyncio
async def test_retrieve_by_embedding_with_threshold_filter():
    mock_store = MagicMock()
    docs = [
        VectorDocument(id="hi", content="x", embedding=[0.0], metadata={}, score=0.9),
        VectorDocument(id="lo", content="y", embedding=[0.0], metadata={}, score=0.1),
    ]
    mock_store.search = AsyncMock(return_value=SearchResult(documents=docs))

    r = DocumentRetriever(mock_store, MagicMock(), top_k=2)
    r.similarity_threshold = 0.5
    out = await r.retrieve_by_embedding([0.3, 0.2, 0.1])
    assert [d.id for d in out] == ["hi"]


@pytest.mark.asyncio
async def test_retriever_health_check_healthy_and_unhealthy():
    # Healthy path
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=SearchResult(documents=[]))
    mock_embedder = MagicMock()
    mock_embedder.embed_single = AsyncMock(return_value=[0.0])
    r = DocumentRetriever(mock_store, mock_embedder)
    ok = await r.health_check()
    assert ok["status"] == "healthy"

    # Unhealthy path: embedding fails
    bad_embedder = MagicMock()
    bad_embedder.embed_single = AsyncMock(side_effect=RuntimeError("boom"))
    r2 = DocumentRetriever(mock_store, bad_embedder)
    bad = await r2.health_check()
    assert bad["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_retriever_embedding_failure_raises():
    mock_store = MagicMock()
    mock_store.query = AsyncMock(return_value=[])
    bad_embedder = MagicMock()
    # Present embed_text to hit that branch
    bad_embedder.embed_text = AsyncMock(side_effect=RuntimeError("nope"))
    r = DocumentRetriever(mock_store, bad_embedder)
    with pytest.raises(Exception):
        await r.retrieve("q")

