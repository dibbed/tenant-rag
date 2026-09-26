"""
Integration tests for vector stores with RAG system components.

This module tests the integration between vector stores and other RAG components
like embeddings, chunkers, loaders, and QA systems.
"""

import asyncio
import importlib.util
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ragbot.configs.settings import VectorStoreConfig
from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.factory import VectorStoreFactory


# These tests create a "chroma" store through VectorStoreFactory with a mocked
# ChromaVectorStore class. The factory uses the class only when chromadb can be
# imported, so the tests need the optional chromadb package
# (pip install -e ".[vectorstores]").
requires_chromadb = pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None,
    reason="chromadb is optional (vectorstores extra) and not installed",
)


class TestVectorStoreRAGIntegration:
    """Test integration between vector stores and RAG components."""

    @pytest.fixture
    def sample_config(self) -> VectorStoreConfig:
        """Create sample configuration for testing."""
        return VectorStoreConfig(
            default_store="faiss",
            faiss_config={
                "index_type": "HNSW",
                "metric": "cosine",
                "dimension": 384,  # sentence-transformers dimension
            },
            chroma_config={
                "collection_name": "test_collection",
                "persist_directory": "/tmp/test_chroma",
            },
            qdrant_config={
                "collection_name": "test_collection",
                "host": "localhost",
                "port": 6333,
            },
        )

    @pytest.fixture
    def sample_documents(self) -> List[VectorDocument]:
        """Create sample documents for testing."""
        return [
            VectorDocument(
                id="doc1",
                content="Machine learning is a subset of artificial intelligence that focuses on algorithms.",
                embedding=[0.1] * 384,  # Mock embedding
                metadata={
                    "source": "ml_guide.pdf",
                    "page": 1,
                    "topic": "machine_learning",
                },
            ),
            VectorDocument(
                id="doc2",
                content="Deep learning uses neural networks with multiple layers to process data.",
                embedding=[0.2] * 384,
                metadata={
                    "source": "ml_guide.pdf",
                    "page": 2,
                    "topic": "deep_learning",
                },
            ),
            VectorDocument(
                id="doc3",
                content="Natural language processing helps computers understand human language.",
                embedding=[0.3] * 384,
                metadata={"source": "nlp_guide.pdf", "page": 1, "topic": "nlp"},
            ),
        ]


class TestVectorStoreEmbeddingIntegration(TestVectorStoreRAGIntegration):
    """Test vector store integration with embedding services."""

    @pytest.mark.asyncio
    async def test_faiss_with_embeddings(self, sample_config, sample_documents):
        """Test FAISS store with embedding generation."""
        with patch("ragbot.rag.store.faiss_store.FAISSVectorStore") as mock_faiss_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(return_value=["doc1", "doc2", "doc3"])
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(
                        id="doc1", score=0.9, content="Machine learning is a subset..."
                    )
                ]
            )
            mock_faiss_class.return_value = mock_store

            # Create store via factory
            store = await VectorStoreFactory.create_store(
                store_type="faiss", config=sample_config, index_path="/tmp/test_faiss"
            )

            # Test adding documents
            result = await store.add_documents(sample_documents)
            assert result == ["doc1", "doc2", "doc3"]

            # Test search
            search_results = await store.search("machine learning", top_k=1)
            assert len(search_results) == 1
            assert search_results[0].id == "doc1"

    @pytest.mark.asyncio
    @requires_chromadb
    async def test_chroma_with_embeddings(self, sample_config, sample_documents):
        """Test Chroma store with embedding generation."""
        with patch(
            "ragbot.rag.store.chroma_store.ChromaVectorStore"
        ) as mock_chroma_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(return_value=["doc1", "doc2", "doc3"])
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(
                        id="doc1", score=0.9, content="Machine learning is a subset..."
                    )
                ]
            )
            mock_store.search_with_metadata_filter = AsyncMock(
                return_value=[
                    Mock(
                        id="doc1", score=0.9, content="Machine learning is a subset..."
                    )
                ]
            )
            mock_chroma_class.return_value = mock_store

            # Create store via factory
            store = await VectorStoreFactory.create_store(
                store_type="chroma",
                config=sample_config,
                collection_name="test_collection",
            )

            # Test adding documents
            result = await store.add_documents(sample_documents)
            assert result == ["doc1", "doc2", "doc3"]

            # Test search with metadata filtering
            search_results = await store.search_with_metadata_filter(
                query="machine learning",
                metadata_filter={"topic": "machine_learning"},
                top_k=1,
            )
            assert len(search_results) == 1

    @pytest.mark.asyncio
    async def test_qdrant_with_embeddings(self, sample_config, sample_documents):
        """Test Qdrant store with embedding generation."""
        with patch(
            "ragbot.rag.store.qdrant_store.QdrantVectorStore"
        ) as mock_qdrant_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(return_value=["doc1", "doc2", "doc3"])
            mock_store.search = AsyncMock(
                return_value=[
                    Mock(
                        id="doc1", score=0.9, content="Machine learning is a subset..."
                    )
                ]
            )
            mock_store.semantic_search = AsyncMock(
                return_value=[
                    Mock(
                        id="doc1", score=0.9, content="Machine learning is a subset..."
                    )
                ]
            )
            mock_qdrant_class.return_value = mock_store

            # Create store via factory
            store = await VectorStoreFactory.create_store(
                store_type="qdrant",
                config=sample_config,
                collection_name="test_collection",
            )

            # Test adding documents
            result = await store.add_documents(sample_documents)
            assert result == ["doc1", "doc2", "doc3"]

            # Test hybrid search
            search_results = await store.semantic_search(
                query="machine learning", top_k=2, rerank=True
            )
            assert len(search_results) == 1


class TestVectorStoreChunkerIntegration(TestVectorStoreRAGIntegration):
    """Test vector store integration with chunking services."""

    @pytest.mark.asyncio
    async def test_store_with_semantic_chunker(self, sample_config):
        """Test vector store with semantic chunker."""
        with patch("ragbot.rag.chunkers.SemanticChunker") as mock_chunker_class:
            mock_chunker = Mock()
            mock_chunks = [
                VectorDocument(
                    id="chunk1",
                    content="Machine learning algorithms can be supervised or unsupervised.",
                    embedding=[0.1] * 384,
                    metadata={"chunk_id": 1, "source": "ml_guide.pdf", "page": 1},
                ),
                VectorDocument(
                    id="chunk2",
                    content="Deep learning uses neural networks with multiple hidden layers.",
                    embedding=[0.2] * 384,
                    metadata={"chunk_id": 2, "source": "ml_guide.pdf", "page": 2},
                ),
            ]
            mock_chunker.chunk_documents.return_value = mock_chunks
            mock_chunker_class.return_value = mock_chunker

            # Test with FAISS store
            with patch(
                "ragbot.rag.store.faiss_store.FAISSVectorStore"
            ) as mock_faiss_class:
                mock_store = Mock()
                mock_store.add_chunks = AsyncMock(return_value=["chunk1", "chunk2"])
                mock_faiss_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="faiss",
                    config=sample_config,
                    index_path="/tmp/test_faiss",
                )

                # Test adding chunks
                result = await store.add_chunks(mock_chunks)
                assert result == ["chunk1", "chunk2"]

    @pytest.mark.asyncio
    async def test_store_with_hierarchical_chunker(self, sample_config):
        """Test vector store with hierarchical chunker."""
        with patch("ragbot.rag.chunkers.HierarchicalChunker") as mock_chunker_class:
            mock_chunker = Mock()
            mock_chunks = [
                VectorDocument(
                    id="hierarchical_chunk1",
                    content="Introduction to machine learning concepts and applications.",
                    embedding=[0.1] * 384,
                    metadata={
                        "chunk_id": 1,
                        "level": "section",
                        "parent_id": None,
                        "source": "ml_guide.pdf",
                    },
                ),
                VectorDocument(
                    id="hierarchical_chunk2",
                    content="Supervised learning algorithms and their use cases.",
                    embedding=[0.2] * 384,
                    metadata={
                        "chunk_id": 2,
                        "level": "subsection",
                        "parent_id": "hierarchical_chunk1",
                        "source": "ml_guide.pdf",
                    },
                ),
            ]
            mock_chunker.chunk_documents.return_value = mock_chunks
            mock_chunker_class.return_value = mock_chunker

            # Test with Chroma store
            with patch(
                "ragbot.rag.store.chroma_store.ChromaVectorStore"
            ) as mock_chroma_class:
                mock_store = Mock()
                mock_store.add_chunks = AsyncMock(
                    return_value=["hierarchical_chunk1", "hierarchical_chunk2"]
                )
                mock_chroma_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="chroma",
                    config=sample_config,
                    collection_name="test_collection",
                )

                # Test adding hierarchical chunks
                result = await store.add_chunks(mock_chunks)
                assert result == ["hierarchical_chunk1", "hierarchical_chunk2"]


class TestVectorStoreLoaderIntegration(TestVectorStoreRAGIntegration):
    """Test vector store integration with document loaders."""

    @pytest.mark.asyncio
    async def test_store_with_pdf_loader(self, sample_config):
        """Test vector store with PDF loader."""
        with patch("ragbot.rag.loaders.PDFLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_documents = [
                VectorDocument(
                    id="pdf_doc1",
                    content="Machine learning fundamentals and applications in industry.",
                    embedding=[0.1] * 384,
                    metadata={
                        "source": "ml_fundamentals.pdf",
                        "page": 1,
                        "file_type": "pdf",
                    },
                )
            ]
            mock_loader.load_documents.return_value = mock_documents
            mock_loader_class.return_value = mock_loader

            # Test with Qdrant store
            with patch(
                "ragbot.rag.store.qdrant_store.QdrantVectorStore"
            ) as mock_qdrant_class:
                mock_store = Mock()
                mock_store.add_documents_from_loader = AsyncMock(
                    return_value=["pdf_doc1"]
                )
                mock_qdrant_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="qdrant",
                    config=sample_config,
                    collection_name="test_collection",
                )

                # Test adding documents from loader
                result = await store.add_documents_from_loader(mock_loader)
                assert result == ["pdf_doc1"]

    @pytest.mark.asyncio
    @requires_chromadb
    async def test_store_with_url_loader(self, sample_config):
        """Test vector store with URL loader."""
        with patch("ragbot.rag.loaders.URLLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_documents = [
                VectorDocument(
                    id="url_doc1",
                    content="Latest developments in artificial intelligence and machine learning.",
                    embedding=[0.1] * 384,
                    metadata={
                        "source": "https://example.com/ai-news",
                        "url": "https://example.com/ai-news",
                    },
                )
            ]
            mock_loader.load_documents.return_value = mock_documents
            mock_loader_class.return_value = mock_loader

            # Test with Chroma store
            with patch(
                "ragbot.rag.store.chroma_store.ChromaVectorStore"
            ) as mock_chroma_class:
                mock_store = Mock()
                mock_store.add_documents_from_loader = AsyncMock(
                    return_value=["url_doc1"]
                )
                mock_chroma_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="chroma",
                    config=sample_config,
                    collection_name="test_collection",
                )

                # Test adding documents from URL loader
                result = await store.add_documents_from_loader(mock_loader)
                assert result == ["url_doc1"]

    @pytest.mark.asyncio
    async def test_store_with_multiple_loaders(self, sample_config):
        """Test vector store with multiple document loaders."""
        # Mock PDF loader
        with patch("ragbot.rag.loaders.PDFLoader") as mock_pdf_loader_class:
            mock_pdf_loader = Mock()
            mock_pdf_docs = [
                VectorDocument(
                    id="pdf_doc1",
                    content="PDF content about machine learning.",
                    embedding=[0.1] * 384,
                    metadata={"source": "ml.pdf", "type": "pdf"},
                )
            ]
            mock_pdf_loader.load_documents.return_value = mock_pdf_docs
            mock_pdf_loader_class.return_value = mock_pdf_loader

            # Mock DOCX loader
        with patch("ragbot.rag.loaders.DOCXLoader") as mock_docx_loader_class:
            mock_docx_loader = Mock()
            mock_docx_docs = [
                VectorDocument(
                    id="docx_doc1",
                    content="DOCX content about deep learning.",
                    embedding=[0.2] * 384,
                    metadata={"source": "dl.docx", "type": "docx"},
                )
            ]
            mock_docx_loader.load_documents.return_value = mock_docx_docs
            mock_docx_loader_class.return_value = mock_docx_loader

            # Test with FAISS store
            with patch(
                "ragbot.rag.store.faiss_store.FAISSVectorStore"
            ) as mock_faiss_class:
                mock_store = Mock()
                mock_store.add_documents_from_loader = AsyncMock(
                    side_effect=[["pdf_doc1"], ["docx_doc1"]]
                )
                mock_faiss_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="faiss",
                    config=sample_config,
                    index_path="/tmp/test_faiss",
                )

                # Test adding documents from multiple loaders
                pdf_result = await store.add_documents_from_loader(mock_pdf_loader)
                docx_result = await store.add_documents_from_loader(mock_docx_loader)

                assert pdf_result == ["pdf_doc1"]
                assert docx_result == ["docx_doc1"]


class TestVectorStoreQAIntegration(TestVectorStoreRAGIntegration):
    """Test vector store integration with QA systems."""

    @pytest.mark.asyncio
    @requires_chromadb
    async def test_store_with_qa_generator(self, sample_config, sample_documents):
        """Test vector store with QA generator."""
        with patch("ragbot.rag.qa.QAGenerator") as mock_qa_class:
            mock_qa = Mock()
            mock_qa.generate_answer.return_value = (
                "Machine learning is a subset of AI that focuses on algorithms."
            )
            mock_qa_class.return_value = mock_qa

            # Test with Chroma store
            with patch(
                "ragbot.rag.store.chroma_store.ChromaVectorStore"
            ) as mock_chroma_class:
                mock_store = Mock()
                mock_store.search = AsyncMock(
                    return_value=[
                        Mock(
                            id="doc1",
                            score=0.9,
                            content="Machine learning is a subset of artificial intelligence...",
                        )
                    ]
                )
                mock_chroma_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="chroma",
                    config=sample_config,
                    collection_name="test_collection",
                )

                # Test search for QA
                search_results = await store.search(
                    "What is machine learning?", top_k=1
                )
                assert len(search_results) == 1
                assert search_results[0].id == "doc1"

    @pytest.mark.asyncio
    async def test_store_with_advanced_qa(self, sample_config):
        """Test vector store with advanced QA features."""
        with patch("ragbot.rag.qa.QAGenerator") as mock_qa_class:
            mock_qa = Mock()
            mock_qa.generate_answer_with_context.return_value = {
                "answer": "Machine learning algorithms can be supervised or unsupervised.",
                "confidence": 0.95,
                "sources": ["doc1", "doc2"],
            }
            mock_qa_class.return_value = mock_qa

            # Test with Qdrant store
            with patch(
                "ragbot.rag.store.qdrant_store.QdrantVectorStore"
            ) as mock_qdrant_class:
                mock_store = Mock()
                mock_store.semantic_search = AsyncMock(
                    return_value=[
                        Mock(
                            id="doc1",
                            score=0.9,
                            content="Supervised learning uses labeled data...",
                        ),
                        Mock(
                            id="doc2",
                            score=0.8,
                            content="Unsupervised learning finds patterns in unlabeled data...",
                        ),
                    ]
                )
                mock_qdrant_class.return_value = mock_store

                store = await VectorStoreFactory.create_store(
                    store_type="qdrant",
                    config=sample_config,
                    collection_name="test_collection",
                )

                # Test semantic search for advanced QA
                search_results = await store.semantic_search(
                    query="What are the types of machine learning?",
                    top_k=2,
                    rerank=True,
                )
                assert len(search_results) == 2


class TestVectorStorePerformanceIntegration(TestVectorStoreRAGIntegration):
    """Test vector store performance and optimization features."""

    @pytest.mark.asyncio
    async def test_batch_operations(self, sample_config):
        """Test batch operations for performance."""
        # Create large batch of documents
        large_batch = []
        for i in range(100):
            large_batch.append(
                VectorDocument(
                    id=f"doc_{i}",
                    content=f"Document {i} content about machine learning and AI.",
                    embedding=[0.1] * 384,
                    metadata={"batch_id": i, "source": f"batch_doc_{i}.pdf"},
                )
            )

        # Test with FAISS store
        with patch("ragbot.rag.store.faiss_store.FAISSVectorStore") as mock_faiss_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(
                return_value=[f"doc_{i}" for i in range(100)]
            )
            mock_store.get_stats = AsyncMock(
                return_value={
                    "total_documents": 100,
                    "store_type": "faiss",
                    "memory_usage": "50MB",
                }
            )
            mock_faiss_class.return_value = mock_store

            store = await VectorStoreFactory.create_store(
                store_type="faiss", config=sample_config, index_path="/tmp/test_faiss"
            )

            # Test batch adding
            result = await store.add_documents(large_batch)
            assert len(result) == 100

            # Test stats
            stats = await store.get_stats()
            assert stats["total_documents"] == 100

    @pytest.mark.asyncio
    @requires_chromadb
    async def test_concurrent_operations(self, sample_config):
        """Test concurrent operations for performance."""
        with patch(
            "ragbot.rag.store.chroma_store.ChromaVectorStore"
        ) as mock_chroma_class:
            mock_store = Mock()
            mock_store.add_documents = AsyncMock(return_value=["doc1", "doc2"])
            mock_store.search = AsyncMock(
                return_value=[Mock(id="doc1", score=0.9, content="Test content")]
            )
            mock_store.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_chroma_class.return_value = mock_store

            store = await VectorStoreFactory.create_store(
                store_type="chroma",
                config=sample_config,
                collection_name="test_collection",
            )

            # Test concurrent operations
            documents = [
                VectorDocument(
                    id="doc1",
                    content="Test document 1",
                    embedding=[0.1] * 384,
                    metadata={"source": "test1.pdf"},
                ),
                VectorDocument(
                    id="doc2",
                    content="Test document 2",
                    embedding=[0.2] * 384,
                    metadata={"source": "test2.pdf"},
                ),
            ]

            # Run concurrent operations
            tasks = [
                store.add_documents(documents),
                store.search("test query", top_k=1),
                store.health_check(),
            ]

            results = await asyncio.gather(*tasks)
            assert len(results) == 3
            assert results[0] == ["doc1", "doc2"]  # add_documents result
            assert len(results[1]) == 1  # search result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
