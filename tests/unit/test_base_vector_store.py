"""
Test cases for BaseVectorStore advanced methods.
"""

from typing import Any, Dict, List, Optional

import pytest

from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.store.base import BaseVectorStore, SearchResult, VectorDocument


class MockVectorDocument:
    """Mock vector document for testing."""

    def __init__(
        self,
        id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any] = None,
    ):
        self.id = id
        self.content = content
        self.embedding = embedding
        self.metadata = metadata or {}
        self.score = None


class TestBaseVectorStore:
    """Test cases for BaseVectorStore abstract class."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock vector store for testing."""

        class MockStore(BaseVectorStore):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.documents = {}
                self.document_count = 0

            def get_store_type(self) -> str:
                return "unknown"

            async def add_documents(
                self, documents: List[VectorDocument], **kwargs
            ) -> List[str]:
                ids = []
                for doc in documents:
                    self.documents[doc.id] = doc
                    self.document_count += 1
                    ids.append(doc.id)
                return ids

            async def search(
                self, query_embedding: List[float], top_k: int = 10, **kwargs
            ) -> SearchResult:
                # Simple mock search - return all documents with dummy scores
                docs = list(self.documents.values())[:top_k]
                for i, doc in enumerate(docs):
                    doc.score = 1.0 - (i * 0.2)  # Decreasing scores

                return SearchResult(
                    documents=docs,
                    query_embedding=query_embedding,
                    total_results=len(docs),
                    search_time=0.1,
                )

            async def delete_documents(
                self, document_ids: List[str], **kwargs
            ) -> List[str]:
                deleted = []
                for doc_id in document_ids:
                    if doc_id in self.documents:
                        del self.documents[doc_id]
                        self.document_count -= 1
                        deleted.append(doc_id)
                return deleted

            def get_document_count(self) -> int:
                return self.document_count

            async def clear(self) -> None:
                self.documents.clear()
                self.document_count = 0

            async def save(self, path: Optional[str] = None) -> None:
                pass

            async def load(self, path: Optional[str] = None) -> None:
                pass

        return MockStore()

    @pytest.mark.asyncio
    async def test_initialization(self, mock_store):
        """Test store initialization with advanced features."""
        assert mock_store.store_type == "unknown"
        assert mock_store.embedding_dimension == 768
        assert mock_store.enable_metadata_filtering is True
        assert mock_store.enable_semantic_chunking is True
        assert mock_store.enable_hybrid_search is True
        assert mock_store.enable_reranking is True
        assert mock_store.batch_size == 100
        assert mock_store.max_retries == 3
        assert mock_store.timeout == 30.0
        assert mock_store.enable_metrics is True
        assert mock_store.enable_analytics is True

    @pytest.mark.asyncio
    async def test_add_chunks(self, mock_store):
        """Test adding text chunks with semantic metadata."""
        chunks = [
            MockVectorDocument(
                "chunk_1", "Test content 1", [0.1] * 768, {"type": "text"}
            ),
            MockVectorDocument(
                "chunk_2", "Test content 2", [0.2] * 768, {"type": "text"}
            ),
        ]

        embeddings = {"chunk_1": [0.1] * 768, "chunk_2": [0.2] * 768}

        ids = await mock_store.add_chunks(chunks, embeddings=embeddings)
        assert len(ids) == 2
        assert "chunk_1" in ids
        assert "chunk_2" in ids

        # Verify enhanced metadata
        doc1 = mock_store.documents["chunk_1"]
        assert doc1.metadata["chunk_type"] == "semantic_chunk"
        assert doc1.metadata["is_semantic"] is True
        assert doc1.metadata["chunk_length"] == len("Test content 1")

    @pytest.mark.asyncio
    async def test_add_documents_from_loader(self, mock_store):
        """Test adding documents from loaders with rich metadata."""
        loader_docs = [
            MockVectorDocument(
                "doc_1",
                "Document content",
                [0.1] * 768,
                {
                    "loader_type": "pdf",
                    "source_type": "file",
                    "mime_type": "application/pdf",
                },
            )
        ]

        embeddings = {"doc_1": [0.1] * 768}

        ids = await mock_store.add_documents_from_loader(
            loader_docs, embeddings=embeddings
        )
        assert len(ids) == 1
        assert "doc_1" in ids

        # Verify enhanced metadata
        doc = mock_store.documents["doc_1"]
        assert doc.metadata["loader_type"] == "pdf"
        assert doc.metadata["source_type"] == "file"
        assert doc.metadata["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_update_documents(self, mock_store):
        """Test updating existing documents."""
        # Add initial document
        doc = VectorDocument(
            id="test_doc",
            content="Original content",
            embedding=[0.1] * 768,
            metadata={"version": 1},
        )
        await mock_store.add_documents([doc])

        # Update document
        updated_doc = VectorDocument(
            id="test_doc",
            content="Updated content",
            embedding=[0.2] * 768,
            metadata={"version": 2},
        )

        ids = await mock_store.update_documents([updated_doc])
        assert len(ids) == 1
        assert "test_doc" in ids

        # Verify update
        stored_doc = mock_store.documents["test_doc"]
        assert stored_doc.content == "Updated content"
        assert stored_doc.metadata["version"] == 2

    @pytest.mark.asyncio
    async def test_get_document(self, mock_store):
        """Test getting a specific document by ID."""
        # Add test document
        doc = VectorDocument(
            id="test_doc", content="Test content", embedding=[0.1] * 768
        )
        await mock_store.add_documents([doc])

        # Get document
        retrieved_doc = await mock_store.get_document("test_doc")
        assert retrieved_doc is not None
        assert retrieved_doc.id == "test_doc"
        assert retrieved_doc.content == "Test content"

        # Test non-existent document
        non_existent = await mock_store.get_document("non_existent")
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_get_documents(self, mock_store):
        """Test getting multiple documents by IDs."""
        # Add test documents
        docs = [
            VectorDocument(id="doc_1", content="Content 1", embedding=[0.1] * 768),
            VectorDocument(id="doc_2", content="Content 2", embedding=[0.2] * 768),
            VectorDocument(id="doc_3", content="Content 3", embedding=[0.3] * 768),
        ]
        await mock_store.add_documents(docs)

        # Get specific documents
        retrieved_docs = await mock_store.get_documents(["doc_1", "doc_3"])
        assert len(retrieved_docs) == 2

        doc_ids = [doc.id for doc in retrieved_docs]
        assert "doc_1" in doc_ids
        assert "doc_3" in doc_ids

    @pytest.mark.asyncio
    async def test_get_documents_by_metadata(self, mock_store):
        """Test getting documents filtered by metadata."""
        # Add test documents with different metadata
        docs = [
            VectorDocument(
                id="doc_1",
                content="Content 1",
                embedding=[0.1] * 768,
                metadata={"category": "tech", "language": "en"},
            ),
            VectorDocument(
                id="doc_2",
                content="Content 2",
                embedding=[0.2] * 768,
                metadata={"category": "science", "language": "en"},
            ),
            VectorDocument(
                id="doc_3",
                content="Content 3",
                embedding=[0.3] * 768,
                metadata={"category": "tech", "language": "fa"},
            ),
        ]
        await mock_store.add_documents(docs)

        # Filter by category
        tech_docs = await mock_store.get_documents_by_metadata({"category": "tech"})
        assert len(tech_docs) == 2

        # Filter by language
        en_docs = await mock_store.get_documents_by_metadata({"language": "en"})
        assert len(en_docs) == 2

    @pytest.mark.asyncio
    async def test_semantic_search(self, mock_store):
        """Test semantic search with similarity threshold."""
        # Add test documents
        docs = [
            VectorDocument(
                id="doc_1",
                content="Machine learning algorithms",
                embedding=[0.9] * 768,
                metadata={},
            ),
            VectorDocument(
                id="doc_2",
                content="Deep learning neural networks",
                embedding=[0.8] * 768,
                metadata={},
            ),
            VectorDocument(
                id="doc_3",
                content="Cooking recipes",
                embedding=[0.1] * 768,
                metadata={},
            ),
        ]
        await mock_store.add_documents(docs)

        # Search with high similarity threshold
        query_embedding = [0.9] * 768
        results = await mock_store.semantic_search(
            query_embedding=query_embedding, top_k=10, similarity_threshold=0.7
        )

        # Should only return high-similarity documents
        assert len(results.documents) <= 2
        for doc in results.documents:
            assert doc.score >= 0.7

    @pytest.mark.asyncio
    async def test_health_check(self, mock_store):
        """Test health check functionality."""
        health = await mock_store.health_check()

        assert health["status"] == "healthy"
        assert health["store_type"] == "unknown"
        assert "document_count" in health
        assert "embedding_dimension" in health
        assert "features" in health
        assert "performance" in health

        # Test unhealthy state
        mock_store.documents = None  # Simulate error
        health = await mock_store.health_check()
        assert health["status"] == "unhealthy"
        assert "error" in health

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_store):
        """Test getting store statistics."""
        stats = await mock_store.get_stats()

        assert stats["store_type"] == "unknown"
        assert "document_count" in stats
        assert "embedding_dimension" in stats
        assert "similarity_metric" in stats
        assert "features" in stats
        assert "performance" in stats

    def test_get_store_info(self, mock_store):
        """Test getting store information."""
        info = mock_store.get_store_info()

        assert info["store_type"] == "unknown"
        assert "embedding_dimension" in info
        assert "similarity_metric" in info
        assert "features" in info


class DummyStore(BaseVectorStore):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._docs: dict[str, VectorDocument] = {}
        self.store_type_label = kwargs.get("store_type_label", "DummyStore")
        self._doc_count = kwargs.get("document_count", None)

    def get_store_type(self) -> str:
        return getattr(self, "store_type_label", "DummyStore")

    async def add_documents(self, documents: List[VectorDocument], **kwargs: Any) -> List[str]:
        for d in documents:
            self._docs[d.id] = d
        return [d.id for d in documents]

    async def update_documents(self, documents: List[VectorDocument], **kwargs: Any) -> List[str]:
        updated = []
        for d in documents:
            if d.id in self._docs:
                self._docs[d.id] = d
                updated.append(d.id)
        return updated

    async def delete_documents(self, document_ids: List[str], **kwargs: Any) -> List[str]:
        deleted = []
        for i in document_ids:
            if i in self._docs:
                del self._docs[i]
                deleted.append(i)
        return deleted

    async def search(self, query_embedding: List[float], top_k: int = 10, **kwargs: Any) -> SearchResult:
        docs = list(self._docs.values())[:top_k]
        return SearchResult(documents=docs, query_embedding=query_embedding, total_results=len(docs))

    async def get_document(self, document_id: str) -> Optional[VectorDocument]:
        return self._docs.get(document_id)

    async def get_documents(self, document_ids: List[str]) -> List[VectorDocument]:
        return [self._docs[i] for i in document_ids if i in self._docs]

    def get_document_count(self) -> int:
        if self._doc_count is not None:
            return self._doc_count
        return len(self._docs)

    async def clear(self) -> None:
        self._docs.clear()

    async def save(self, path: Optional[str] = None) -> None:
        return None

    async def load(self, path: Optional[str] = None) -> None:
        return None


@pytest.mark.asyncio
async def test_upsert_documents_and_filters_and_info(monkeypatch):
    store = DummyStore(similarity_metric="cosine")
    d1 = VectorDocument(id="1", content="hello", embedding=[1, 0], metadata={"tag": "a", "num": 5})
    d2 = VectorDocument(id="2", content="world", embedding=[0, 1], metadata={"tag": "b", "num": 10})
    await store.add_documents([d1])

    # Upsert: one update, one add
    updated = await store.upsert_documents([d1, d2])
    assert set(updated) == {"1", "2"}

    # Filter helpers
    docs = [d1, d2]
    eq = store.filter_documents(docs, {"tag": "a"})
    assert [d.id for d in eq] == ["1"]

    rng = store.filter_documents(docs, {"num": {"$gte": 6, "$lte": 10}})
    assert [d.id for d in rng] == ["2"]

    in_list = store.filter_documents(docs, {"tag": ["b", "c"]})
    assert [d.id for d in in_list] == ["2"]

    # compute_similarity variants
    store.similarity_metric = "cosine"
    assert store.compute_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    store.similarity_metric = "euclidean"
    assert store.compute_similarity([1, 0], [0, 1]) < 1.0
    store.similarity_metric = "dot_product"
    assert store.compute_similarity([1, 2], [3, 4]) == 11.0
    store.similarity_metric = "unknown"
    assert store.compute_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert store.compute_similarity([1, 0], ["x"]) == 0.0

    # Store info
    info = store.get_store_info()
    assert info["store_type"] == "DummyStore"
    assert info["embedding_dimension"] == 768

    class E:
        async def embed_single(self, t: str):
            return [0.0, 0.0]

    res = await store.search_by_text("hi", E())
    assert isinstance(res, SearchResult)
    assert isinstance(res.documents, list)

    health = await store.health_check()
    assert health["status"] == "healthy"


@pytest.mark.asyncio
async def test_base_analytics_aggregate():
    store = DummyStore(embedding_dimension=4, store_type_label="dummy", document_count=42)

    metrics_manager.record_vector_store_operation(
        operation="search", store_type=store.store_type_label, document_count=3, success=True, duration=0.01
    )
    metrics_manager.record_vector_store_operation(
        operation="add_documents", store_type=store.store_type_label, document_count=5, success=True, duration=0.02
    )
    metrics_manager.update_vector_store_size(42, store_type=store.store_type_label)

    s = await store.get_search_analytics()
    d = await store.get_document_analytics()

    assert s["store_type"] == "dummy"
    assert s["total_searches"] >= 1
    assert d["total_documents"] == 42

