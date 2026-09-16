"""
End-to-end testing scenarios for vector store implementations.
"""

import asyncio
import tempfile

import pytest

from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.faiss_store import FAISSStore


class TestEndToEndScenarios:
    """End-to-end testing scenarios."""

    @pytest.fixture
    def test_store(self):
        """Create test store for E2E scenarios."""
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
    async def test_complete_document_lifecycle(self, test_store):
        """Test complete document lifecycle: add, search, update, delete."""
        # 1. Add documents
        docs = [
            VectorDocument(
                id="doc_1",
                content="Machine learning is a subset of artificial intelligence.",
                embedding=[0.1] * 384,
                metadata={"category": "AI", "year": 2023, "source": "textbook"},
            ),
            VectorDocument(
                id="doc_2",
                content="Deep learning uses neural networks with multiple layers.",
                embedding=[0.2] * 384,
                metadata={"category": "AI", "year": 2023, "source": "research"},
            ),
            VectorDocument(
                id="doc_3",
                content="Natural language processing helps computers understand text.",
                embedding=[0.3] * 384,
                metadata={"category": "NLP", "year": 2023, "source": "article"},
            ),
        ]

        added_ids = await test_store.add_documents(docs)
        assert len(added_ids) == 3
        assert test_store.get_document_count() == 3

        # 2. Search documents
        query_embedding = [0.15] * 384
        search_results = await test_store.search(query_embedding, top_k=3)
        assert len(search_results.documents) == 3

        # 3. Search with metadata filter
        filtered_results = await test_store.search_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filter={"category": "AI"},
            top_k=10,
        )
        assert len(filtered_results.documents) == 2
        for doc in filtered_results.documents:
            assert doc.metadata["category"] == "AI"

        # 4. Update document
        updated_doc = VectorDocument(
            id="doc_1",
            content="Machine learning is a powerful subset of artificial intelligence.",
            embedding=[0.11] * 384,
            metadata={"category": "AI", "year": 2024, "source": "updated_textbook"},
        )

        updated_ids = await test_store.update_documents([updated_doc])
        assert len(updated_ids) == 1
        assert "doc_1" in updated_ids

        # Verify update
        retrieved_doc = await test_store.get_document("doc_1")
        assert (
            retrieved_doc.content
            == "Machine learning is a powerful subset of artificial intelligence."
        )
        assert retrieved_doc.metadata["year"] == 2024

        # 5. Delete document
        deleted_ids = await test_store.delete_documents(["doc_3"])
        assert len(deleted_ids) == 1
        assert "doc_3" in deleted_ids
        assert test_store.get_document_count() == 2

        # 6. Verify final state
        final_results = await test_store.search(query_embedding, top_k=10)
        assert len(final_results.documents) == 2
        doc_ids = [doc.id for doc in final_results.documents]
        assert "doc_1" in doc_ids
        assert "doc_2" in doc_ids
        assert "doc_3" not in doc_ids

    @pytest.mark.asyncio
    async def test_semantic_chunking_workflow(self, test_store):
        """Test semantic chunking workflow with chunks."""
        # Simulate chunks from semantic chunker
        chunks = [
            MockChunk("chunk_1", "Machine learning algorithms", 0, 30, {"topic": "ML"}),
            MockChunk(
                "chunk_2", "are designed to learn patterns", 30, 60, {"topic": "ML"}
            ),
            MockChunk(
                "chunk_3",
                "from data without explicit programming.",
                60,
                90,
                {"topic": "ML"},
            ),
            MockChunk("chunk_4", "Deep learning is a subset", 90, 120, {"topic": "DL"}),
            MockChunk(
                "chunk_5",
                "of machine learning using neural networks.",
                120,
                150,
                {"topic": "DL"},
            ),
        ]

        # Generate embeddings for chunks
        embeddings = {}
        for i, chunk in enumerate(chunks):
            embeddings[chunk.chunk_id] = [0.1 + i * 0.1] * 384

        # Add chunks to store
        chunk_ids = await test_store.add_chunks(chunks, embeddings=embeddings)
        assert len(chunk_ids) == 5
        assert test_store.get_document_count() == 5

        # Search for ML-related content
        query_embedding = [0.15] * 384
        ml_results = await test_store.search_with_metadata_filter(
            query_embedding=query_embedding, metadata_filter={"topic": "ML"}, top_k=10
        )
        assert len(ml_results.documents) == 3

        # Search for DL-related content
        dl_results = await test_store.search_with_metadata_filter(
            query_embedding=query_embedding, metadata_filter={"topic": "DL"}, top_k=10
        )
        assert len(dl_results.documents) == 2

        # Verify chunk metadata
        for doc in ml_results.documents:
            assert doc.metadata["chunk_type"] == "semantic_chunk"
            assert doc.metadata["is_semantic"] is True
            assert "start_index" in doc.metadata
            assert "end_index" in doc.metadata

    @pytest.mark.asyncio
    async def test_loader_integration_workflow(self, test_store):
        """Test integration with document loaders."""
        # Simulate documents from different loaders
        loader_docs = [
            MockLoaderDoc(
                "pdf_doc_1", "PDF content about AI", "pdf", "file", "application/pdf"
            ),
            MockLoaderDoc(
                "url_doc_1", "Web content about ML", "url", "web", "text/html"
            ),
            MockLoaderDoc(
                "docx_doc_1",
                "Word document about NLP",
                "docx",
                "file",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ]

        # Generate embeddings
        embeddings = {}
        for i, doc in enumerate(loader_docs):
            embeddings[doc.id] = [0.2 + i * 0.1] * 384

        # Add documents from loaders
        doc_ids = await test_store.add_documents_from_loader(
            loader_docs, embeddings=embeddings
        )
        assert len(doc_ids) == 3
        assert test_store.get_document_count() == 3

        # Verify enhanced metadata
        for doc_id in doc_ids:
            doc = await test_store.get_document(doc_id)
            assert "loader_type" in doc.metadata
            assert "source_type" in doc.metadata
            assert "mime_type" in doc.metadata

        # Search by loader type
        pdf_results = await test_store.get_documents_by_metadata({"loader_type": "pdf"})
        assert len(pdf_results) == 1
        assert pdf_results[0].metadata["loader_type"] == "pdf"

        # Search by source type
        file_results = await test_store.get_documents_by_metadata(
            {"source_type": "file"}
        )
        assert len(file_results) == 2  # PDF and DOCX

    @pytest.mark.asyncio
    async def test_hybrid_search_scenario(self, test_store):
        """Test hybrid search scenario combining semantic and keyword search."""
        # Add diverse documents
        docs = [
            VectorDocument(
                id="ai_doc",
                content="Artificial intelligence and machine learning are transforming industries.",
                embedding=[0.9] * 384,
                metadata={
                    "domain": "technology",
                    "keywords": ["AI", "ML", "transformation"],
                },
            ),
            VectorDocument(
                id="ml_doc",
                content="Machine learning algorithms can learn from data automatically.",
                embedding=[0.8] * 384,
                metadata={
                    "domain": "technology",
                    "keywords": ["ML", "algorithms", "data"],
                },
            ),
            VectorDocument(
                id="cooking_doc",
                content="Cooking recipes require precise measurements and timing.",
                embedding=[0.1] * 384,
                metadata={
                    "domain": "culinary",
                    "keywords": ["cooking", "recipes", "measurements"],
                },
            ),
        ]

        await test_store.add_documents(docs)

        # Test semantic search with threshold
        query_embedding = [0.85] * 384
        semantic_results = await test_store.semantic_search(
            query_embedding=query_embedding, top_k=5, similarity_threshold=0.7
        )

        # Should return high-similarity documents
        assert len(semantic_results.documents) >= 2
        for doc in semantic_results.documents:
            assert doc.score >= 0.7

        # Test metadata filtering
        tech_results = await test_store.search_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filter={"domain": "technology"},
            top_k=10,
        )
        assert len(tech_results.documents) == 2
        for doc in tech_results.documents:
            assert doc.metadata["domain"] == "technology"

    @pytest.mark.asyncio
    async def test_performance_under_load(self, test_store):
        """Test performance under concurrent load."""
        # Add initial documents
        docs = []
        for i in range(100):
            doc = VectorDocument(
                id=f"load_doc_{i}",
                content=f"Load test document {i}",
                embedding=[0.1 + (i % 10) * 0.1] * 384,
                metadata={"batch": "load_test", "index": i},
            )
            docs.append(doc)

        await test_store.add_documents(docs)

        # Concurrent search operations
        async def concurrent_search_operation():
            query_embedding = [0.15] * 384
            results = await test_store.search(query_embedding, top_k=5)
            return len(results.documents)

        # Run multiple concurrent operations
        tasks = [concurrent_search_operation() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # All operations should succeed
        assert len(results) == 20
        for result in results:
            assert result == 5

        # Test concurrent metadata filtering
        async def concurrent_filter_operation():
            query_embedding = [0.15] * 384
            results = await test_store.search_with_metadata_filter(
                query_embedding=query_embedding,
                metadata_filter={"batch": "load_test"},
                top_k=10,
            )
            return len(results.documents)

        filter_tasks = [concurrent_filter_operation() for _ in range(10)]
        filter_results = await asyncio.gather(*filter_tasks)

        assert len(filter_results) == 10
        for result in filter_results:
            assert result == 10  # All 100 documents match the filter

    @pytest.mark.asyncio
    async def test_store_health_and_monitoring(self, test_store):
        """Test store health monitoring and analytics."""
        # Add some documents
        docs = [
            VectorDocument(
                id="health_doc_1",
                content="Health monitoring test document",
                embedding=[0.1] * 384,
                metadata={"test": "health"},
            )
        ]
        await test_store.add_documents(docs)

        # Test health check
        health = await test_store.health_check()
        assert health["status"] == "healthy"
        assert health["store_type"] == "faiss"
        assert health["document_count"] == 1
        assert "features" in health
        assert "performance" in health

        # Test store stats
        stats = await test_store.get_stats()
        assert stats["store_type"] == "faiss"
        assert stats["document_count"] == 1
        assert stats["features"]["metadata_filtering"] is True
        assert stats["features"]["semantic_chunking"] is True

        # Test store info
        info = test_store.get_store_info()
        assert info["store_type"] == "faiss"
        assert info["document_count"] == 1
        assert info["features"]["hybrid_search"] is True

        # Test search analytics
        search_analytics = await test_store.get_search_analytics()
        assert "store_type" in search_analytics
        assert "total_searches" in search_analytics

        # Test document analytics
        doc_analytics = await test_store.get_document_analytics()
        assert "store_type" in doc_analytics
        assert "total_documents" in doc_analytics


class MockChunk:
    """Mock chunk for testing."""

    def __init__(
        self,
        chunk_id: str,
        content: str,
        start_index: int,
        end_index: int,
        metadata: dict,
    ):
        self.chunk_id = chunk_id
        self.content = content
        self.start_index = start_index
        self.end_index = end_index
        self.metadata = metadata
        self.length = len(content)


class MockLoaderDoc:
    """Mock loader document for testing."""

    def __init__(
        self,
        doc_id: str,
        content: str,
        loader_type: str,
        source_type: str,
        mime_type: str,
    ):
        self.id = doc_id
        self.content = content
        self.loader_type = loader_type
        self.source_type = source_type
        self.mime_type = mime_type
        self.metadata = {
            "loader_type": loader_type,
            "source_type": source_type,
            "mime_type": mime_type,
        }


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
