"""
Integration tests and performance benchmarks for vector stores.
"""

import asyncio
import tempfile
import time

import numpy as np
import pytest

from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.faiss_store import FAISSStore


class TestFAISSStoreIntegration:
    """Integration tests for FAISS store."""

    @pytest.fixture
    def faiss_store(self):
        """Create FAISS store for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FAISSStore(
                store_type="faiss",
                embedding_dimension=384,
                index_path=temp_dir,
                enable_metadata_filtering=True,
                enable_semantic_chunking=True,
                enable_hybrid_search=True,
                enable_reranking=True,
            )
            yield store

    @pytest.mark.asyncio
    async def test_faiss_basic_operations(self, faiss_store):
        """Test basic FAISS operations."""
        # Test adding documents
        docs = [
            VectorDocument(
                id="doc_1",
                content="This is a test document about machine learning.",
                embedding=[0.1] * 384,
                metadata={"category": "tech", "language": "en"},
            ),
            VectorDocument(
                id="doc_2",
                content="Another document about artificial intelligence.",
                embedding=[0.2] * 384,
                metadata={"category": "tech", "language": "en"},
            ),
        ]

        ids = await faiss_store.add_documents(docs)
        assert len(ids) == 2
        assert "doc_1" in ids
        assert "doc_2" in ids

        # Test document count
        count = faiss_store.get_document_count()
        assert count == 2

        # Test search
        query_embedding = [0.15] * 384
        results = await faiss_store.search(query_embedding, top_k=2)
        assert len(results.documents) == 2
        assert results.total_results == 2

        # Test deleting documents
        deleted_ids = await faiss_store.delete_documents(["doc_1"])
        assert len(deleted_ids) == 1
        assert "doc_1" in deleted_ids

        # Verify deletion
        count = faiss_store.get_document_count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_faiss_metadata_filtering(self, faiss_store):
        """Test FAISS metadata filtering."""
        # Add documents with different metadata
        docs = [
            VectorDocument(
                id="tech_doc",
                content="Technology document",
                embedding=[0.1] * 384,
                metadata={"category": "tech", "year": 2023},
            ),
            VectorDocument(
                id="science_doc",
                content="Science document",
                embedding=[0.2] * 384,
                metadata={"category": "science", "year": 2023},
            ),
            VectorDocument(
                id="old_doc",
                content="Old document",
                embedding=[0.3] * 384,
                metadata={"category": "tech", "year": 2020},
            ),
        ]
        await faiss_store.add_documents(docs)

        # Test metadata filtering
        query_embedding = [0.15] * 384
        results = await faiss_store.search_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filter={"category": "tech"},
            top_k=10,
        )

        # Should return only tech documents
        assert len(results.documents) == 2
        for doc in results.documents:
            assert doc.metadata["category"] == "tech"

    @pytest.mark.asyncio
    async def test_faiss_advanced_features(self, faiss_store):
        """Test FAISS advanced features."""
        # Test health check
        health = await faiss_store.health_check()
        assert health["status"] == "healthy"
        assert health["store_type"] == "faiss"

        # Test stats
        stats = await faiss_store.get_stats()
        assert stats["store_type"] == "faiss"
        assert stats["features"]["metadata_filtering"] is True

        # Test store info
        info = faiss_store.get_store_info()
        assert info["store_type"] == "faiss"
        assert info["features"]["semantic_chunking"] is True


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""

    @pytest.fixture
    def benchmark_store(self):
        """Create store for performance testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FAISSStore(
                store_type="faiss",
                embedding_dimension=384,
                index_path=temp_dir,
                batch_size=100,
            )
            yield store

    @pytest.mark.asyncio
    async def test_batch_add_performance(self, benchmark_store):
        """Test batch adding performance."""
        # Create test documents
        docs = []
        for i in range(1000):
            doc = VectorDocument(
                id=f"doc_{i}",
                content=f"Test document number {i}",
                embedding=np.random.random(384).tolist(),
                metadata={"index": i, "batch": "test"},
            )
            docs.append(doc)

        # Measure add time
        start_time = time.time()
        ids = await benchmark_store.add_documents(docs)
        add_time = time.time() - start_time

        assert len(ids) == 1000
        assert add_time < 10.0  # Should complete within 10 seconds

        # Verify document count
        count = benchmark_store.get_document_count()
        assert count == 1000

    @pytest.mark.asyncio
    async def test_search_performance(self, benchmark_store):
        """Test search performance."""
        # Add test documents
        docs = []
        for i in range(1000):
            doc = VectorDocument(
                id=f"doc_{i}",
                content=f"Test document number {i}",
                embedding=np.random.random(384).tolist(),
                metadata={"index": i},
            )
            docs.append(doc)

        await benchmark_store.add_documents(docs)

        # Measure search time
        query_embedding = np.random.random(384).tolist()

        start_time = time.time()
        results = await benchmark_store.search(query_embedding, top_k=10)
        search_time = time.time() - start_time

        assert len(results.documents) == 10
        assert search_time < 1.0  # Should complete within 1 second
        assert results.search_time >= 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, benchmark_store):
        """Test concurrent operations performance."""
        # Add initial documents
        docs = []
        for i in range(100):
            doc = VectorDocument(
                id=f"doc_{i}",
                content=f"Test document {i}",
                embedding=np.random.random(384).tolist(),
                metadata={"index": i},
            )
            docs.append(doc)

        await benchmark_store.add_documents(docs)

        # Test concurrent searches
        async def concurrent_search():
            query_embedding = np.random.random(384).tolist()
            return await benchmark_store.search(query_embedding, top_k=5)

        # Run multiple concurrent searches
        start_time = time.time()
        tasks = [concurrent_search() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time

        assert len(results) == 10
        for result in results:
            assert len(result.documents) == 5

        # Concurrent operations should be reasonably fast
        assert concurrent_time < 5.0


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def error_store(self):
        """Create store for error testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FAISSStore(
                store_type="faiss", embedding_dimension=384, index_path=temp_dir
            )
            yield store

    @pytest.mark.asyncio
    async def test_empty_documents(self, error_store):
        """Test handling empty document lists."""
        # Test empty add
        ids = await error_store.add_documents([])
        assert ids == []

        # Test empty search
        query_embedding = [0.1] * 384
        results = await error_store.search(query_embedding, top_k=10)
        assert len(results.documents) == 0
        assert results.total_results == 0

    @pytest.mark.asyncio
    async def test_invalid_document_ids(self, error_store):
        """Test handling invalid document IDs."""
        # Test deleting non-existent documents
        deleted_ids = await error_store.delete_documents(["non_existent"])
        assert deleted_ids == []

        # Test getting non-existent documents
        docs = await error_store.get_documents(["non_existent"])
        assert docs == []

    @pytest.mark.asyncio
    async def test_malformed_embeddings(self, error_store):
        """Test handling malformed embeddings."""
        # Test wrong embedding dimension
        doc = VectorDocument(
            id="bad_doc",
            content="Test content",
            embedding=[0.1] * 100,  # Wrong dimension
            metadata={},
        )

        # Should handle gracefully or raise appropriate error
        try:
            await error_store.add_documents([doc])
            # If it succeeds, verify it was handled
            count = error_store.get_document_count()
            assert count == 0  # Should not add malformed documents
        except Exception as e:
            # Should raise a clear error
            assert "embedding" in str(e).lower() or "dimension" in str(e).lower()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
