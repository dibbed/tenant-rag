"""
Tests for DocumentRetriever context length limiting and query path selection.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ragbot.rag.retrieve.retriever import DocumentRetriever
from ragbot.rag.store.base import VectorDocument


@pytest.mark.asyncio
async def test_retriever_limits_context_length():
    # Mock vector store with query returning long content
    mock_store = MagicMock()
    mock_store.query = AsyncMock()

    long_text = "A" * 10000
    docs = [
        VectorDocument(id="d1", content=long_text, embedding=[0.0], metadata={}),
        VectorDocument(id="d2", content="short", embedding=[0.0], metadata={}),
    ]
    mock_store.query.return_value = docs

    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 768)

    retriever = DocumentRetriever(
        vector_store=mock_store,
        embedder=mock_embedder,
        top_k=2,
        max_context_length=100,  # force truncation
    )

    results = await retriever.retrieve("question?", top_k=2)
    assert isinstance(results, list)
    assert len(results) == 2
    # First doc should be truncated
    assert len(results[0].content) <= 103  # includes '...'
    assert results[0].metadata.get("truncated") is True

