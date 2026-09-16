"""
End-to-end tests for the complete vector store system.

This module provides comprehensive end-to-end testing scenarios that simulate
real-world usage of the vector store system with all RAG components.
"""

import asyncio
import os
import shutil
import tempfile
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ragbot.configs.settings import VectorStoreConfig
from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.factory import VectorStoreFactory
import ragbot.services.rag_service as _rag_service_mod
RAGService = lambda *args, **kwargs: _rag_service_mod.RAGService(*args, **kwargs)


class TestVectorStoreE2E:
    """End-to-end tests for vector store system."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_config(self, temp_dir) -> VectorStoreConfig:
        """Create sample configuration for testing."""
        return VectorStoreConfig(
            default_store="faiss",
            faiss_config={
                "index_type": "HNSW",
                "metric": "cosine",
                "dimension": 384,
                "index_path": os.path.join(temp_dir, "faiss_index"),
            },
            chroma_config={
                "collection_name": "test_collection",
                "persist_directory": os.path.join(temp_dir, "chroma_db"),
            },
            qdrant_config={
                "collection_name": "test_collection",
                "host": "localhost",
                "port": 6333,
            },
            weaviate_config={
                "class_name": "TestDocument",
                "url": "http://localhost:8080",
            },
        )

    @pytest.fixture
    def sample_documents(self) -> List[VectorDocument]:
        """Create comprehensive sample documents for testing."""
        return [
            VectorDocument(
                id="ml_intro",
                content="Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed.",
                embedding=[0.1] * 384,
                metadata={
                    "source": "ml_guide.pdf",
                    "page": 1,
                    "section": "introduction",
                    "topic": "machine_learning",
                    "difficulty": "beginner",
                    "language": "english",
                },
            ),
            VectorDocument(
                id="dl_basics",
                content="Deep learning uses artificial neural networks with multiple layers to model and understand complex patterns in data.",
                embedding=[0.2] * 384,
                metadata={
                    "source": "dl_guide.pdf",
                    "page": 1,
                    "section": "basics",
                    "topic": "deep_learning",
                    "difficulty": "intermediate",
                    "language": "english",
                },
            ),
            VectorDocument(
                id="nlp_applications",
                content="Natural language processing combines computational linguistics with machine learning to help computers understand human language.",
                embedding=[0.3] * 384,
                metadata={
                    "source": "nlp_guide.pdf",
                    "page": 1,
                    "section": "applications",
                    "topic": "nlp",
                    "difficulty": "intermediate",
                    "language": "english",
                },
            ),
            VectorDocument(
                id="ai_ethics",
                content="Artificial intelligence ethics involves ensuring AI systems are fair, transparent, and beneficial to society.",
                embedding=[0.4] * 384,
                metadata={
                    "source": "ai_ethics.pdf",
                    "page": 1,
                    "section": "overview",
                    "topic": "ai_ethics",
                    "difficulty": "advanced",
                    "language": "english",
                },
            ),
            VectorDocument(
                id="ml_algorithms",
                content="Common machine learning algorithms include linear regression, decision trees, random forests, and support vector machines.",
                embedding=[0.5] * 384,
                metadata={
                    "source": "ml_algorithms.pdf",
                    "page": 2,
                    "section": "algorithms",
                    "topic": "machine_learning",
                    "difficulty": "intermediate",
                    "language": "english",
                },
            ),
        ]


class TestCompleteWorkflowE2E(TestVectorStoreE2E):
    """Test complete workflows from document ingestion to query answering."""

    @pytest.mark.asyncio
    async def test_faiss_complete_workflow(
        self, sample_config, sample_documents, temp_dir
    ):
        """Test complete FAISS workflow from ingestion to querying."""
        with patch("ragbot.rag.store.faiss_store.FAISSVectorStore") as mock_faiss_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in sample_documents]
            )
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(
                        id="ml_intro", score=0.95, content=sample_documents[0].content
                    ),
                    Mock(
                        id="ml_algorithms",
                        score=0.85,
                        content=sample_documents[4].content,
                    ),
                ]
            )
            mock_store.get_documents_by_metadata = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", content=sample_documents[0].content),
                    Mock(id="ml_algorithms", content=sample_documents[4].content),
                ]
            )
            mock_store.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "document_count": 5,
                    "store_type": "faiss",
                }
            )
            mock_store.get_stats = AsyncMock(
                return_value={
                    "total_documents": 5,
                    "store_type": "faiss",
                    "memory_usage": "25MB",
                }
            )
            mock_faiss_class.return_value = mock_store

            # Step 1: Create store
            store = await VectorStoreFactory.create_store(
                store_type="faiss",
                config=sample_config,
                index_path=os.path.join(temp_dir, "faiss_index"),
            )

            # Step 2: Add documents
            added_ids = await store.add_documents(sample_documents)
            assert len(added_ids) == 5
            assert "ml_intro" in added_ids

            # Step 3: Search documents
            search_results = await store.search("machine learning algorithms", top_k=2)
            assert len(search_results) == 2
            assert search_results[0].id == "ml_intro"
            assert search_results[0].score == 0.95

            # Step 4: Filter by metadata
            filtered_results = await store.get_documents_by_metadata(
                metadata_filter={"topic": "machine_learning"}
            )
            assert len(filtered_results) == 2

            # Step 5: Health check
            health = await store.health_check()
            assert health["status"] == "healthy"
            assert health["document_count"] == 5

            # Step 6: Get statistics
            stats = await store.get_stats()
            assert stats["total_documents"] == 5
            assert stats["store_type"] == "faiss"

    @pytest.mark.asyncio
    async def test_chroma_complete_workflow(
        self, sample_config, sample_documents, temp_dir
    ):
        """Test complete Chroma workflow with advanced features."""
        with patch(
            "ragbot.rag.store.chroma_store.ChromaVectorStore"
        ) as mock_chroma_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in sample_documents]
            )
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.search_with_metadata_filter = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.semantic_search = AsyncMock(
                return_value=[
                    Mock(
                        id="ml_intro", score=0.95, content=sample_documents[0].content
                    ),
                    Mock(
                        id="ml_algorithms",
                        score=0.85,
                        content=sample_documents[4].content,
                    ),
                ]
            )
            mock_store.get_documents_by_metadata = AsyncMock(
                return_value=[Mock(id="ml_intro", content=sample_documents[0].content)]
            )
            mock_store.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "document_count": 5,
                    "store_type": "chroma",
                }
            )
            mock_chroma_class.return_value = mock_store

            # Create Chroma store
            store = await VectorStoreFactory.create_store(
                store_type="chroma",
                config=sample_config,
                collection_name="test_collection",
            )

            # Add documents
            added_ids = await store.add_documents(sample_documents)
            assert len(added_ids) == 5

            # Test basic search
            search_results = await store.search("machine learning", top_k=1)
            assert len(search_results) == 1

            # Test metadata filtering
            filtered_results = await store.search_with_metadata_filter(
                query="machine learning",
                metadata_filter={"difficulty": "beginner"},
                top_k=1,
            )
            assert len(filtered_results) == 1

            # Test semantic search with reranking
            semantic_results = await store.semantic_search(
                query="machine learning algorithms", top_k=2, rerank=True
            )
            assert len(semantic_results) == 2

            # Test metadata-based retrieval
            metadata_results = await store.get_documents_by_metadata(
                metadata_filter={"topic": "machine_learning"}
            )
            assert len(metadata_results) == 1

    @pytest.mark.asyncio
    async def test_qdrant_complete_workflow(
        self, sample_config, sample_documents, temp_dir
    ):
        """Test complete Qdrant workflow with advanced features."""
        with patch(
            "ragbot.rag.store.qdrant_store.QdrantVectorStore"
        ) as mock_qdrant_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in sample_documents]
            )
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.search_with_metadata_filter = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.semantic_search = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "document_count": 5,
                    "store_type": "qdrant",
                }
            )
            mock_qdrant_class.return_value = mock_store

            # Create Qdrant store
            store = await VectorStoreFactory.create_store(
                store_type="qdrant",
                config=sample_config,
                collection_name="test_collection",
            )

            # Add documents
            added_ids = await store.add_documents(sample_documents)
            assert len(added_ids) == 5

            # Test search with payload filtering
            search_results = await store.search_with_metadata_filter(
                query="machine learning",
                metadata_filter={"difficulty": "beginner"},
                top_k=1,
            )
            assert len(search_results) == 1

            # Test hybrid search
            hybrid_results = await store.semantic_search(
                query="machine learning algorithms", top_k=2, rerank=True
            )
            assert len(hybrid_results) == 1

    @pytest.mark.asyncio
    async def test_weaviate_complete_workflow(
        self, sample_config, sample_documents, temp_dir
    ):
        """Test complete Weaviate workflow with GraphQL features."""
        with patch(
            "ragbot.rag.store.weaviate_store.WeaviateVectorStore"
        ) as mock_weaviate_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in sample_documents]
            )
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.search_with_metadata_filter = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "document_count": 5,
                    "store_type": "weaviate",
                }
            )
            mock_weaviate_class.return_value = mock_store

            # Create Weaviate store
            store = await VectorStoreFactory.create_store(
                store_type="weaviate", config=sample_config, class_name="TestDocument"
            )

            # Add documents
            added_ids = await store.add_documents(sample_documents)
            assert len(added_ids) == 5

            # Test GraphQL search
            search_results = await store.search("machine learning", top_k=1)
            assert len(search_results) == 1

            # Test GraphQL filtering
            filtered_results = await store.search_with_metadata_filter(
                query="machine learning",
                metadata_filter={"topic": "machine_learning"},
                top_k=1,
            )
            assert len(filtered_results) == 1


class TestRAGServiceIntegrationE2E(TestVectorStoreE2E):
    """Test integration with RAG service."""

    @pytest.mark.asyncio
    async def test_rag_service_with_faiss(self, sample_config, sample_documents):
        """Test RAG service integration with FAISS store."""
        with patch("ragbot.services.rag_service.RAGService") as mock_rag_service_class:
            mock_rag_service = Mock()
            mock_rag_service.process_query = AsyncMock(
                return_value={
                    "answer": "Machine learning is a subset of artificial intelligence that enables computers to learn from data.",
                    "sources": ["ml_intro", "ml_algorithms"],
                    "confidence": 0.95,
                }
            )
            mock_rag_service_class.return_value = mock_rag_service

            # Mock vector store creation
            with patch(
                "ragbot.rag.store.factory.VectorStoreFactory.create_store"
            ) as mock_factory:
                mock_store = Mock()
                mock_store.search = AsyncMock(
                    return_value=[
                        Mock(
                            id="ml_intro",
                            score=0.95,
                            content=sample_documents[0].content,
                        ),
                        Mock(
                            id="ml_algorithms",
                            score=0.85,
                            content=sample_documents[4].content,
                        ),
                    ]
                )
                mock_factory.return_value = mock_store

                # Create RAG service
                rag_service = RAGService(config=sample_config)

                # Process query
                result = await rag_service.process_query("What is machine learning?")

                assert result["answer"] is not None
                assert len(result["sources"]) == 2
                assert result["confidence"] > 0.9

    @pytest.mark.asyncio
    async def test_rag_service_with_chroma(self, sample_config, sample_documents):
        """Test RAG service integration with Chroma store."""
        with patch("ragbot.services.rag_service.RAGService") as mock_rag_service_class:
            mock_rag_service = Mock()
            mock_rag_service.process_query_with_metadata = AsyncMock(
                return_value={
                    "answer": "Machine learning algorithms can be supervised or unsupervised.",
                    "sources": ["ml_intro"],
                    "metadata": {"topic": "machine_learning", "difficulty": "beginner"},
                    "confidence": 0.92,
                }
            )
            mock_rag_service_class.return_value = mock_rag_service

            # Mock vector store creation
            with patch(
                "ragbot.rag.store.factory.VectorStoreFactory.create_store"
            ) as mock_factory:
                mock_store = Mock()
                mock_store.search_with_metadata_filter = AsyncMock(
                    return_value=[
                        Mock(
                            id="ml_intro",
                            score=0.95,
                            content=sample_documents[0].content,
                        )
                    ]
                )
                mock_factory.return_value = mock_store

                # Create RAG service
                rag_service = RAGService(config=sample_config)

                # Process query with metadata filtering
                result = await rag_service.process_query_with_metadata(
                    query="What is machine learning?",
                    metadata_filter={"difficulty": "beginner"},
                )

                assert result["answer"] is not None
                assert result["metadata"]["topic"] == "machine_learning"
                assert result["confidence"] > 0.9


class TestPerformanceE2E(TestVectorStoreE2E):
    """Test performance characteristics of vector stores."""

    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, sample_config, temp_dir):
        """Test performance with large datasets."""
        # Create large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append(
                VectorDocument(
                    id=f"doc_{i}",
                    content=f"Document {i} content about machine learning, artificial intelligence, and data science.",
                    embedding=[0.1 + (i % 10) * 0.01] * 384,
                    metadata={
                        "batch_id": i // 100,
                        "source": f"large_dataset_{i}.pdf",
                        "topic": ["ml", "ai", "data_science"][i % 3],
                    },
                )
            )

        with patch("ragbot.rag.store.faiss_store.FAISSVectorStore") as mock_faiss_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in large_dataset]
            )
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(id="doc_0", score=0.95, content=large_dataset[0].content)
                ]
            )
            mock_store.get_stats = AsyncMock(
                return_value={
                    "total_documents": 1000,
                    "store_type": "faiss",
                    "memory_usage": "500MB",
                    "index_size": "100MB",
                }
            )
            mock_faiss_class.return_value = mock_store

            # Create store
            store = await VectorStoreFactory.create_store(
                store_type="faiss",
                config=sample_config,
                index_path=os.path.join(temp_dir, "large_faiss_index"),
            )

            # Test batch adding
            added_ids = await store.add_documents(large_dataset)
            assert len(added_ids) == 1000

            # Test search performance
            search_results = await store.search("machine learning", top_k=1)
            assert len(search_results) == 1

            # Test statistics
            stats = await store.get_stats()
            assert stats["total_documents"] == 1000
            assert "memory_usage" in stats

    @pytest.mark.asyncio
    async def test_concurrent_operations_performance(
        self, sample_config, sample_documents
    ):
        """Test concurrent operations performance."""
        with patch(
            "ragbot.rag.store.chroma_store.ChromaVectorStore"
        ) as mock_chroma_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in sample_documents]
            )
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(id="ml_intro", score=0.95, content=sample_documents[0].content)
                ]
            )
            mock_store.health_check = AsyncMock(
                return_value={
                    "status": "healthy",
                    "document_count": 5,
                    "store_type": "chroma",
                }
            )
            mock_chroma_class.return_value = mock_store

            # Create store
            store = await VectorStoreFactory.create_store(
                store_type="chroma",
                config=sample_config,
                collection_name="test_collection",
            )

            # Test concurrent operations
            tasks = []

            # Add documents
            tasks.append(store.add_documents(sample_documents))

            # Multiple searches
            for i in range(5):
                tasks.append(store.search(f"query {i}", top_k=1))

            # Health checks
            for _ in range(3):
                tasks.append(store.health_check())

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks)

            # Verify results
            assert len(results) == 9
            assert results[0] == [doc.id for doc in sample_documents]  # add_documents
            assert all(len(result) == 1 for result in results[1:6])  # searches
            assert all(
                result["status"] == "healthy" for result in results[6:9]
            )  # health checks


class TestErrorHandlingE2E(TestVectorStoreE2E):
    """Test error handling and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_store_creation_failure(self, sample_config):
        """Test handling of store creation failures."""
        with patch(
            "ragbot.rag.store.factory.VectorStoreFactory.create_store"
        ) as mock_factory:
            mock_factory.side_effect = Exception("Store creation failed")

            with pytest.raises(Exception, match="Store creation failed"):
                await VectorStoreFactory.create_store(
                    store_type="invalid_store", config=sample_config
                )

    @pytest.mark.asyncio
    async def test_document_addition_failure(self, sample_config, sample_documents):
        """Test handling of document addition failures."""
        with patch("ragbot.rag.store.faiss_store.FAISSVectorStore") as mock_faiss_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                side_effect=Exception("Document addition failed")
            )
            mock_faiss_class.return_value = mock_store

            store = await VectorStoreFactory.create_store(
                store_type="faiss", config=sample_config, index_path="/tmp/test_faiss"
            )

            with pytest.raises(Exception, match="Document addition failed"):
                await store.add_documents(sample_documents)

    @pytest.mark.asyncio
    async def test_search_failure_recovery(self, sample_config, sample_documents):
        """Test search failure and recovery."""
        with patch(
            "ragbot.rag.store.chroma_store.ChromaVectorStore"
        ) as mock_chroma_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[doc.id for doc in sample_documents]
            )
            mock_store.search = AsyncMock(side_effect=Exception("Search failed"))
            mock_store.health_check = AsyncMock(
                return_value={
                    "status": "unhealthy",
                    "error": "Search service unavailable",
                    "store_type": "chroma",
                }
            )
            mock_chroma_class.return_value = mock_store

            store = await VectorStoreFactory.create_store(
                store_type="chroma",
                config=sample_config,
                collection_name="test_collection",
            )

            # Add documents successfully
            added_ids = await store.add_documents(sample_documents)
            assert len(added_ids) == 5

            # Search fails
            with pytest.raises(Exception, match="Search failed"):
                await store.search("test query", top_k=1)

            # Health check shows unhealthy status
            health = await store.health_check()
            assert health["status"] == "unhealthy"
            assert "error" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
