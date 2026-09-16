"""
Comprehensive testing framework for vector store implementations.

This module provides unit tests, integration tests, and performance benchmarks
for all vector store implementations in the RAG system.
"""

from typing import Any, Dict, List

from ragbot.rag.store.factory import VectorStoreFactory


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


class TestVectorStoreFactory:
    """Test cases for VectorStoreFactory."""

    def test_get_available_stores(self):
        """Test getting available store types."""
        stores = VectorStoreFactory.get_available_stores()
        assert isinstance(stores, list)
        assert "faiss" in stores
        assert "chroma" in stores
        assert "qdrant" in stores
        assert "weaviate" in stores

    def test_get_store_info(self):
        """Test getting store information."""
        info = VectorStoreFactory.get_store_info("faiss")
        assert isinstance(info, dict)
        assert "class_name" in info
        assert "module_path" in info
        assert "dependencies" in info
        assert "capabilities" in info

        # Test invalid store type
        invalid_info = VectorStoreFactory.get_store_info("invalid")
        assert invalid_info == {}

    def test_get_all_stores_info(self):
        """Test getting information about all stores."""
        all_info = VectorStoreFactory.get_all_stores_info()
        assert isinstance(all_info, dict)
        assert len(all_info) == 4  # faiss, chroma, qdrant, weaviate

        for store_type, info in all_info.items():
            assert isinstance(info, dict)
            assert "class_name" in info
            assert "capabilities" in info

    def test_recommend_store(self):
        """Test store recommendation based on requirements."""
        # Test development use case
        recommended = VectorStoreFactory.recommend_store(
            use_case="development", dataset_size="small"
        )
        assert recommended in ["faiss", "chroma"]

        # Test production use case
        recommended = VectorStoreFactory.recommend_store(
            use_case="production", dataset_size="large"
        )
        assert recommended in ["qdrant", "weaviate"]

        # Test with features
        recommended = VectorStoreFactory.recommend_store(
            use_case="general",
            dataset_size="medium",
            features_required=["metadata_filtering", "hybrid_search"],
        )
        assert recommended in ["chroma", "qdrant", "weaviate"]

    def test_validate_store_config(self):
        """Test store configuration validation."""
        # Valid FAISS config
        config = {"embedding_dimension": 384}
        result = VectorStoreFactory.validate_store_config("faiss", config)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

        # Invalid FAISS config
        config = {"embedding_dimension": -1}
        result = VectorStoreFactory.validate_store_config("faiss", config)
        assert result["valid"] is False
        assert len(result["errors"]) > 0

        # Valid Chroma config
        config = {"collection_name": "test_collection"}
        result = VectorStoreFactory.validate_store_config("chroma", config)
        assert result["valid"] is True

        # Invalid Chroma config
        config = {"collection_name": ""}
        result = VectorStoreFactory.validate_store_config("chroma", config)
        assert result["valid"] is False

        # Valid Qdrant config
        config = {"url": "http://localhost:6333"}
        result = VectorStoreFactory.validate_store_config("qdrant", config)
        assert result["valid"] is True

        # Invalid Qdrant config
        config = {"url": "invalid_url"}
        result = VectorStoreFactory.validate_store_config("qdrant", config)
        assert result["valid"] is False

    def test_register_unregister_store(self):
        """Test registering and unregistering custom stores."""
        # Register custom store
        VectorStoreFactory.register_store(
            store_type="custom",
            class_name="CustomStore",
            module_path="custom.module",
            dependencies=["custom-package"],
            capabilities={"metadata_filtering": True, "hybrid_search": False},
            description="Custom test store",
            best_for="Testing purposes",
        )

        # Verify registration
        info = VectorStoreFactory.get_store_info("custom")
        assert info["class_name"] == "CustomStore"
        assert info["capabilities"]["metadata_filtering"] is True

        # Unregister custom store
        success = VectorStoreFactory.unregister_store("custom")
        assert success is True

        # Verify unregistration
        info = VectorStoreFactory.get_store_info("custom")
        assert info == {}

        # Test unregistering non-existent store
        success = VectorStoreFactory.unregister_store("non_existent")
        assert success is False
