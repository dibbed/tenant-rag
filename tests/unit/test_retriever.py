"""
Retriever tests for similarity search functionality.

This module tests the retriever component that performs similarity search
and context retrieval from vector stores.
"""

from types import SimpleNamespace
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest

from ragbot.rag.exceptions import RAGError, RetrievalError
from ragbot.rag.retrieve.retriever import DocumentRetriever, Retriever
from ragbot.rag import SearchResult, VectorDocument


class TestRetriever:
    """Comprehensive test suite for retriever functionality."""

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        """Create a mock vector store for testing."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock()
        return mock_store

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Create a mock embedder for testing."""
        mock_embedder = MagicMock()
        mock_embedder.embed_single = AsyncMock()
        return mock_embedder

    @pytest.fixture
    def retriever(
        self, mock_vector_store: MagicMock, mock_embedder: MagicMock
    ) -> Retriever:
        """Create a retriever instance for testing."""
        return Retriever(vector_store=mock_vector_store, embedder=mock_embedder)

    @pytest.fixture
    def sample_search_result(self) -> SearchResult:
        """Create sample search result for testing."""
        docs = [
            VectorDocument(
                id="doc1",
                content="First relevant document content.",
                embedding=[0.1] * 768,
                metadata={"source": "doc1.txt"},
                score=0.95,
            ),
            VectorDocument(
                id="doc2",
                content="Second relevant document content.",
                embedding=[0.1] * 768,
                metadata={"source": "doc2.txt"},
                score=0.87,
            ),
            VectorDocument(
                id="doc3",
                content="Third relevant document content.",
                embedding=[0.1] * 768,
                metadata={"source": "doc3.txt"},
                score=0.75,
            ),
        ]
        return SearchResult(documents=docs, total_results=3, search_time=0.1)

    @pytest.mark.asyncio
    async def test_retrieve_basic(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_result: SearchResult,
    ) -> None:
        """Test basic retrieval functionality."""
        query = "Test query for retrieval"
        query_embedding = [0.1] * 768

        # Configure mocks
        mock_embedder.embed_single.return_value = query_embedding
        mock_vector_store.search.return_value = sample_search_result

        # Perform retrieval
        results = await retriever.retrieve(query, top_k=3)

        # Verify results
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(result, VectorDocument) for result in results)

        # Verify mock calls
        mock_embedder.embed_single.assert_called_once_with(query)
        mock_vector_store.search.assert_called_once_with(
            query_embedding,
            top_k=6,  # 3*2 for filtering
            filters=None,
            similarity_threshold=None,
        )

    @pytest.mark.asyncio
    async def test_retrieve_with_similarity_threshold(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test retrieval with similarity threshold."""
        query = "Test query"
        query_embedding = [0.1] * 768
        threshold = 0.8

        # Filter results based on threshold
        filtered_results = [r for r in sample_search_results if r.score >= threshold]

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = filtered_results

        results = await retriever.retrieve(
            query, top_k=5, similarity_threshold=threshold
        )

        assert len(results) == 2  # Only 2 results above 0.8 threshold
        assert all(result.score >= threshold for result in results)

        mock_vector_store.query.assert_called_once_with(
            query_embedding, top_k=5, similarity_threshold=threshold
        )

    @pytest.mark.asyncio
    async def test_retrieve_empty_query(
        self, retriever: Retriever, mock_embedder: MagicMock
    ) -> None:
        """Test handling of empty query."""
        empty_query = ""

        with pytest.raises(ValueError, match="empty"):
            await retriever.retrieve(empty_query)

        mock_embedder.embed_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_no_results(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test handling when no results are found."""
        query = "Query with no matches"
        query_embedding = [0.1] * 768

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = []

        results = await retriever.retrieve(query, top_k=5)

        assert results == []
        mock_vector_store.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_multilingual_query(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test retrieval with multilingual queries."""
        queries = ["English query text", "متن جستجوی فارسی", "نص البحث العربي"]

        for query in queries:
            query_embedding = [0.2] * 768
            mock_embedder.embed_text.return_value = query_embedding
            mock_vector_store.query.return_value = sample_search_results

            results = await retriever.retrieve(query, top_k=3)

            assert isinstance(results, list)
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_retrieve_with_metadata_filtering(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test retrieval with metadata filtering."""
        query = "Test query"
        query_embedding = [0.1] * 768

        # Create results with different metadata
        filtered_results = [
            SearchResult(
                content="English content",
                metadata={"source": "doc1.txt", "language": "en"},
                score=0.9,
            ),
            SearchResult(
                content="More English content",
                metadata={"source": "doc2.txt", "language": "en"},
                score=0.8,
            ),
        ]

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = filtered_results

        # Test retrieval with metadata filter if supported
        if hasattr(retriever, "retrieve_with_filter"):
            results = await retriever.retrieve_with_filter(
                query, top_k=5, metadata_filter={"language": "en"}
            )

            assert all(r.metadata.get("language") == "en" for r in results)
        else:
            # Basic retrieval without filtering
            results = await retriever.retrieve(query, top_k=5)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_retrieve_error_handling_embedding_failure(
        self, retriever: Retriever, mock_embedder: MagicMock
    ) -> None:
        """Test error handling when embedding fails."""
        query = "Test query"

        # Simulate embedding failure
        mock_embedder.embed_text.side_effect = Exception("Embedding failed")

        with pytest.raises(RAGError, match="Failed to embed query"):
            await retriever.retrieve(query)

    @pytest.mark.asyncio
    async def test_retrieve_error_handling_vector_store_failure(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test error handling when vector store query fails."""
        query = "Test query"
        query_embedding = [0.1] * 768

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.side_effect = Exception("Vector store failed")

        with pytest.raises(RAGError, match="Failed to query vector store"):
            await retriever.retrieve(query)

    @pytest.mark.asyncio
    async def test_retrieve_result_ranking(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test that results are properly ranked by relevance."""
        query = "Test query"
        query_embedding = [0.1] * 768

        # Create unordered results
        unordered_results = [
            SearchResult(content="Low relevance", metadata={}, score=0.5),
            SearchResult(content="High relevance", metadata={}, score=0.95),
            SearchResult(content="Medium relevance", metadata={}, score=0.7),
        ]

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = unordered_results

        results = await retriever.retrieve(query, top_k=3)

        # Results should be ordered by score (highest first)
        scores = [result.score for result in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_retrieve_top_k_limiting(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test that top_k parameter properly limits results."""
        query = "Test query"
        query_embedding = [0.1] * 768

        # Return more results than requested
        extended_results = sample_search_results + [
            SearchResult(content="Fourth result", metadata={}, score=0.6),
            SearchResult(content="Fifth result", metadata={}, score=0.5),
        ]

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = extended_results

        results = await retriever.retrieve(query, top_k=2)

        assert len(results) == 2
        # Should return the highest scoring results
        assert results[0].score >= results[1].score

    @pytest.mark.asyncio
    async def test_retrieve_with_context_window(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test retrieval with context window considerations."""
        query = "Test query"
        query_embedding = [0.1] * 768

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = sample_search_results

        # Test with context window limit if supported
        if hasattr(retriever, "retrieve_with_context_limit"):
            results = await retriever.retrieve_with_context_limit(
                query, top_k=5, max_context_length=1000
            )

            # Should respect context length limits
            total_length = sum(len(r.content) for r in results)
            assert total_length <= 1000
        else:
            # Basic retrieval
            results = await retriever.retrieve(query, top_k=5)
            assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_retrieve_performance(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test retrieval performance with large result sets."""
        import time

        query = "Performance test query"
        query_embedding = [0.1] * 768

        # Create large result set
        large_results = []
        for i in range(1000):
            large_results.append(
                SearchResult(
                    content=f"Document {i} content",
                    metadata={"id": i},
                    score=0.9 - (i * 0.0001),
                )
            )

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = large_results

        start_time = time.time()
        results = await retriever.retrieve(query, top_k=10)
        end_time = time.time()

        # Should complete quickly even with large result sets
        assert end_time - start_time < 1.0  # Less than 1 second
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_retrieve_with_query_expansion(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test retrieval with query expansion if supported."""
        query = "AI machine learning"

        # Test query expansion if implemented
        if hasattr(retriever, "expand_query"):
            expanded_query = await retriever.expand_query(query)
            assert isinstance(expanded_query, str)
            assert len(expanded_query) >= len(query)

        # Standard retrieval
        query_embedding = [0.1] * 768
        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = sample_search_results

        results = await retriever.retrieve(query, top_k=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_retrieve_with_reranking(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test retrieval with result reranking if supported."""
        query = "Test query for reranking"
        query_embedding = [0.1] * 768

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = sample_search_results

        # Test reranking if implemented
        if hasattr(retriever, "rerank_results"):
            results = await retriever.retrieve(query, top_k=5)
            reranked_results = await retriever.rerank_results(results, query)

            assert len(reranked_results) <= len(results)
            assert all(isinstance(r, SearchResult) for r in reranked_results)
        else:
            # Standard retrieval
            results = await retriever.retrieve(query, top_k=5)
            assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_concurrent_retrievals(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
        sample_search_results: List[SearchResult],
    ) -> None:
        """Test concurrent retrieval operations."""
        import asyncio

        queries = [f"Query {i}" for i in range(10)]
        query_embedding = [0.1] * 768

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = sample_search_results

        # Run concurrent retrievals
        tasks = [retriever.retrieve(query, top_k=3) for query in queries]
        results_list = await asyncio.gather(*tasks)

        assert len(results_list) == 10
        assert all(len(results) == 3 for results in results_list)

    @pytest.mark.asyncio
    async def test_retrieve_memory_efficiency(
        self,
        retriever: Retriever,
        mock_vector_store: MagicMock,
        mock_embedder: MagicMock,
    ) -> None:
        """Test memory efficiency with large retrievals."""
        query = "Memory test query"
        query_embedding = [0.1] * 768

        # Create large content results
        large_results = []
        for i in range(100):
            large_content = "Large document content " * 1000  # Large content
            large_results.append(
                SearchResult(
                    content=large_content, metadata={"id": i}, score=0.9 - (i * 0.001)
                )
            )

        mock_embedder.embed_text.return_value = query_embedding
        mock_vector_store.query.return_value = large_results

        # Should handle large content without memory issues
        results = await retriever.retrieve(query, top_k=50)

        assert len(results) == 50
        assert all(len(r.content) > 1000 for r in results)


@pytest.mark.asyncio
async def test_retriever_uses_search_path_when_query_missing():
    # Vector store exposes only search()
    mock_store = MagicMock()
    docs = [
        VectorDocument(id="a", content="foo", embedding=[0.0], metadata={}, score=0.1),
        VectorDocument(id="b", content="bar", embedding=[0.0], metadata={}, score=0.2),
    ]
    mock_store.search = AsyncMock(return_value=SearchResult(documents=docs))

    mock_embedder = MagicMock()
    mock_embedder.embed_single = AsyncMock(return_value=[0.2] * 8)

    r = DocumentRetriever(mock_store, mock_embedder, top_k=1)
    res = await r.retrieve("hello")
    assert isinstance(res, list)
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
    bad_embedder.embed_text = AsyncMock(side_effect=RuntimeError("nope"))
    r = DocumentRetriever(mock_store, bad_embedder)
    with pytest.raises(Exception):
        await r.retrieve("q")


@pytest.mark.asyncio
async def test_retriever_limits_context_length():
    mock_store = MagicMock()
    mock_store.query = AsyncMock()

    long_text = "A" * 10000
    docs = [
        VectorDocument(id="d1", content=long_text, embedding=[0.0], metadata={}),
        VectorDocument(id="d2", content="short", embedding=[0.0], metadata={}),
    ]
    mock_store.query.return_value = docs

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
    assert len(results[0].content) <= 103
    assert results[0].metadata.get("truncated") is True


@pytest.mark.asyncio
async def test_embed_texts_fallback_and_list_search_result():
    docs = [VectorDocument(id="x", content="c", embedding=[], metadata={}, score=0.3)]
    store = MagicMock()
    store.search = AsyncMock(return_value=docs)

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
    st = SimpleNamespace()
    emb = SimpleNamespace()
    r = DocumentRetriever(st, emb)
    info = r.get_retriever_info()
    assert info["vector_store_type"] == type(st).__name__

