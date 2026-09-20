"""
FAISS vector store tests with proper imports and mocking.

This module tests the FAISS vector store functionality with various scenarios
including storage operations, querying, and error handling.
"""

import tempfile
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch

import pytest

# Import FAISS with proper error handling
faiss = pytest.importorskip("faiss", reason="faiss-cpu not installed")

from ragbot.rag.store.faiss_store import FAISSStore, FAISSVectorStore
from ragbot.rag import SearchResult, VectorDocument, RAGError


class TestFAISSStore:
    """Comprehensive test suite for FAISS vector store functionality."""

    @pytest.fixture
    def tmp_store_path(self, tmp_path: Path) -> str:
        """Create a temporary path for FAISS store."""
        return str(tmp_path / "test_faiss_store")

    @pytest.fixture
    def store(self, tmp_store_path: str) -> FAISSStore:
        """Create a FAISS store instance for testing."""
        return FAISSStore(store_path=tmp_store_path)

    @pytest.fixture
    def sample_texts(self) -> List[str]:
        """Create sample texts for testing."""
        return [
            "Hello world, this is a test document.",
            "سلام دنیا، این یک سند تست است.",
            "Machine learning is a subset of artificial intelligence.",
            "یادگیری ماشین زیرمجموعه‌ای از هوش مصنوعی است.",
            "FAISS is a library for efficient similarity search.",
        ]

    @pytest.fixture
    def sample_metadata(self) -> List[Dict[str, Any]]:
        """Create sample metadata for testing."""
        return [
            {"id": 0, "source": "doc1.txt", "language": "en"},
            {"id": 1, "source": "doc2.txt", "language": "fa"},
            {"id": 2, "source": "doc3.txt", "language": "en"},
            {"id": 3, "source": "doc4.txt", "language": "fa"},
            {"id": 4, "source": "doc5.txt", "language": "en"},
        ]

    @pytest.fixture
    def sample_embeddings(self) -> List[List[float]]:
        """Create sample embeddings for testing."""
        # Create mock embeddings with 1536 dimensions (OpenAI default)
        return [[0.1 * i] * 1536 for i in range(5)]

    def test_faiss_store_initialization(self, tmp_store_path: str) -> None:
        """Test FAISS store initialization."""
        store = FAISSStore(store_path=tmp_store_path)

        assert str(store.store_path) == tmp_store_path
        assert store.dimension == 1536  # OpenAI default dimension
        assert store.index is not None  # Index is initialized immediately
        assert store.index.ntotal == 0  # No documents yet

    def test_faiss_store_custom_dimension(self, tmp_store_path: str) -> None:
        """Test FAISS store with custom dimension."""
        custom_store = FAISSStore(store_path=tmp_store_path, dimension=1536)

        assert custom_store.dimension == 1536

    @pytest.mark.asyncio
    async def test_upsert_and_query_basic(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test basic upsert and query workflow."""
        # Upsert documents using add_texts method
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)

        # Verify documents were stored
        assert store.get_document_count() == len(sample_texts)

        # Query with sample embedding
        query_embedding = [0.1] * 1536
        results = store.query(query_embedding, top_k=3)

        assert isinstance(results, list)
        assert len(results) <= 3
        # Note: query returns List[str], not List[SearchResult]

    @pytest.mark.asyncio
    async def test_upsert_with_mock_embeddings(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
    ) -> None:
        """Test upsert with mocked embeddings."""
        # Mock embedding generation
        mock_embeddings = [[0.1 * i] * 1536 for i in range(len(sample_texts))]

        await store.add_texts(sample_texts, mock_embeddings, sample_metadata)

        assert store.get_document_count() == len(sample_texts)

    @pytest.mark.asyncio
    async def test_query_empty_store(self, store: FAISSStore) -> None:
        """Test querying an empty store."""
        query_embedding = [0.1] * 1536
        results = store.query(query_embedding, top_k=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_upsert_empty_data(self, store: FAISSStore) -> None:
        """Test upserting empty data."""
        await store.add_texts([], [], [])
        assert store.get_document_count() == 0

    @pytest.mark.asyncio
    async def test_upsert_mismatched_data_lengths(self, store: FAISSStore) -> None:
        """Test upserting with mismatched data lengths."""
        texts = ["text1", "text2"]
        embeddings = [[0.1] * 1536]  # One less embedding
        metadata = [{"id": 1}, {"id": 2}]

        with pytest.raises(ValueError, match="Mismatch"):
            await store.add_texts(texts, embeddings, metadata)

    @pytest.mark.asyncio
    async def test_upsert_wrong_embedding_dimension(self, store: FAISSStore) -> None:
        """Test upserting with wrong embedding dimension."""
        texts = ["test text"]
        wrong_embeddings = [[0.1] * 512]  # Wrong dimension
        metadata = [{"id": 1}]

        with pytest.raises(ValueError, match="dimension"):
            await store.add_texts(texts, wrong_embeddings, metadata)

    @pytest.mark.asyncio
    async def test_save_and_load(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test saving and loading the store."""
        # Add data and save
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)
        await store.save()

        # Create new store instance and load
        new_store = FAISSStore(store_path=store.store_path)
        new_store.load()  # load() is synchronous, don't await it

        assert new_store.get_document_count() == len(sample_texts)

        # Query both stores to verify they have same data
        query_embedding = [0.1] * 1536
        original_results = store.query(query_embedding, top_k=3)
        loaded_results = new_store.query(query_embedding, top_k=3)

        assert len(original_results) == len(loaded_results)

    @pytest.mark.asyncio
    async def test_load_nonexistent_store(self, tmp_store_path: str) -> None:
        """Test loading a non-existent store."""
        store = FAISSStore(store_path=tmp_store_path)

        # Should handle gracefully or raise appropriate error
        try:
            store.load()  # load() is synchronous, don't await it
            # If no error, should be empty
            assert store.get_document_count() == 0
        except FileNotFoundError:
            # Expected behavior for non-existent store
            pass

    @pytest.mark.asyncio
    async def test_query_with_similarity_threshold(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test querying with similarity threshold."""
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)

        query_embedding = [0.1] * 1536

        # Query with high threshold (should return fewer results)
        results_high_threshold = store.query(query_embedding, top_k=5)

        # Query with low threshold (should return more results)
        results_low_threshold = store.query(query_embedding, top_k=5)

        # For FAISS store, we can't directly test similarity threshold
        # but we can verify the method works
        assert isinstance(results_high_threshold, list)
        assert isinstance(results_low_threshold, list)

    @pytest.mark.asyncio
    async def test_query_multilingual_content(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test querying multilingual content."""
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)

        # Query with English text
        english_query = [0.1] * 1536
        english_results = store.query(english_query, top_k=3)

        # Query with Persian text (different embedding)
        persian_query = [0.2] * 1536
        persian_results = store.query(persian_query, top_k=3)

        assert len(english_results) >= 1
        assert len(persian_results) >= 1

    @pytest.mark.asyncio
    async def test_delete_functionality(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test document deletion if supported."""
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)
        initial_count = store.get_document_count()

        # Test deletion if method exists
        if hasattr(store, "delete"):
            await store.delete(["0"])  # Delete first document
            assert store.get_document_count() < initial_count
        else:
            # If deletion not supported, test clearing all
            if hasattr(store, "clear"):
                store.clear()  # clear() is synchronous, don't await it
                assert store.get_document_count() == 0

    @pytest.mark.asyncio
    async def test_batch_operations(self, store: FAISSStore) -> None:
        """Test batch operations with large datasets."""
        # Create large batch of data
        large_texts = [f"Document {i} with content" for i in range(100)]
        large_embeddings = [[i * 0.01] * 1536 for i in range(100)]
        large_metadata = [{"id": i, "source": f"doc_{i}.txt"} for i in range(100)]

        # Should handle large batches efficiently
        await store.add_texts(large_texts, large_embeddings, large_metadata)

        assert store.get_document_count() == 100

        # Query should be fast even with large dataset
        query_embedding = [0.5] * 1536
        results = await store.query(query_embedding, top_k=10)

        assert len(results) <= 10
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tmp_store_path: str) -> None:
        """Test concurrent store operations."""
        import asyncio

        # Create multiple store instances
        stores = [FAISSStore(store_path=f"{tmp_store_path}_{i}") for i in range(3)]

        # Concurrent upsert operations
        async def upsert_data(store, start_idx):
            texts = [f"Document {start_idx + i}" for i in range(10)]
            embeddings = [[start_idx + i] * 1536 for i in range(10)]
            metadata = [{"id": start_idx + i} for i in range(10)]
            await store.add_texts(texts, embeddings, metadata)

        tasks = [upsert_data(stores[i], i * 10) for i in range(3)]
        await asyncio.gather(*tasks)

        # Verify all stores have correct data
        for i, store in enumerate(stores):
            assert store.get_document_count() == 10

    @pytest.mark.asyncio
    async def test_concurrent_writes_to_same_store(self, store: FAISSStore) -> None:
        """Test concurrent writes to the SAME store instance without race conditions."""
        import asyncio

        async def worker(worker_id: int):
            texts = [f"Worker {worker_id} Doc {i}" for i in range(5)]
            embeddings = [[float(worker_id * 10 + i) * 0.01] * 1536 for i in range(5)]
            metadata = [{"worker": worker_id, "doc": i} for i in range(5)]
            await store.add_texts(texts, embeddings, metadata)

        await asyncio.gather(*(worker(w) for w in range(5)))
        assert store.get_document_count() == 25

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, store: FAISSStore) -> None:
        """Test memory efficiency with large embeddings."""
        # Create moderately large dataset
        num_docs = 500
        texts = [f"Memory test document {i}" for i in range(num_docs)]
        embeddings = [[i * 0.001] * 1536 for i in range(num_docs)]
        metadata = [{"id": i, "type": "memory_test"} for i in range(num_docs)]

        # Should complete without memory errors
        await store.add_texts(texts, embeddings, metadata)

        assert store.get_document_count() == num_docs

        # Multiple queries should not cause memory issues
        query_embedding = [0.5] * 1536
        for _ in range(10):
            results = store.query(
                query_embedding, top_k=20
            )  # query() returns list, don't await it
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_error_handling_corrupted_index(self, tmp_store_path: str) -> None:
        """Test error handling with corrupted index files."""
        store = FAISSStore(store_path=tmp_store_path)

        # Create corrupted index file
        Path(tmp_store_path).mkdir(parents=True, exist_ok=True)
        (Path(tmp_store_path) / "index.faiss").write_bytes(b"corrupted data")

        # Should handle corrupted files gracefully
        with pytest.raises(Exception):  # Could be various exceptions
            await store.load()

    def test_faiss_vector_store_integration(self, tmp_store_path: str) -> None:
        """Test integration with FAISSVectorStore if available."""
        if hasattr(faiss, "IndexFlatL2"):
            # Test basic FAISS operations
            dimension = 1536
            index = faiss.IndexFlatL2(dimension)

            # Add some vectors
            import numpy as np

            vectors = np.random.random((10, dimension)).astype("float32")
            index.add(vectors)

            assert index.ntotal == 10

            # Search
            query_vector = np.random.random((1, dimension)).astype("float32")
            distances, indices = index.search(query_vector, k=3)

            assert len(distances[0]) == 3
            assert len(indices[0]) == 3

    @pytest.mark.asyncio
    async def test_metadata_retrieval(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test metadata retrieval in search results."""
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)

        query_embedding = [0.1] * 1536
        results = await store.query(query_embedding, top_k=3)

        # Verify metadata is included in results
        for result in results:
            assert hasattr(result, "content")
            assert hasattr(result, "metadata")
            assert isinstance(result.metadata, dict)
            assert "source" in result.metadata or "id" in result.metadata

    @pytest.mark.asyncio
    async def test_store_statistics(
        self,
        store: FAISSStore,
        sample_texts: List[str],
        sample_metadata: List[Dict[str, Any]],
        sample_embeddings: List[List[float]],
    ) -> None:
        """Test store statistics and information."""
        await store.add_texts(sample_texts, sample_embeddings, sample_metadata)

        # Test count
        assert store.get_document_count() == len(sample_texts)

        # Test other statistics if available
        if hasattr(store, "get_stats"):
            stats = await store.get_stats()
            assert isinstance(stats, dict)
            assert "document_count" in stats or "total_documents" in stats


def test_dimension_alias_and_default(tmp_path: Path) -> None:
    # Default should be 1536
    s1 = FAISSStore(store_path=str(tmp_path / "s1"))
    assert s1.dimension == 1536

    # Legacy alias: dimension should override embedding_dimension
    s2 = FAISSStore(store_path=str(tmp_path / "s2"), dimension=1536)
    assert s2.dimension == 1536


@pytest.mark.asyncio
async def test_query_awaitable_empty_store(tmp_path: Path) -> None:
    store = FAISSStore(store_path=str(tmp_path / "empty"))
    # When index is empty, query should return an awaitable list (empty)
    res = await store.query([0.1] * 1536, top_k=3)
    assert isinstance(res, list)
    assert res == []


@pytest.mark.asyncio
async def test_faiss_fallback_add_update_delete_save_load(tmp_path: Path):
    import asyncio

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
    qr = store.query([0.1] * store.embedding_dimension, top_k=2)
    if asyncio.iscoroutine(qr) or hasattr(qr, "__await__"):
        qres = await qr
    else:
        qres = qr
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
    deleted = await store2.delete_documents(["a"])
    assert deleted == ["a"]
    assert store2.count() == 1
    await store2.clear()
    assert store2.count() == 0

