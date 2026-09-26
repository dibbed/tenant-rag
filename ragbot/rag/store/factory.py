"""
Vector Store Factory for creating and managing different vector store instances.

This module provides a factory pattern implementation for creating vector store instances
with automatic fallback mechanisms, capability detection, and store comparison.
"""

import importlib
from typing import Any, Dict, List

from ragbot.outputs.logger import logger
from ragbot.rag.store.base import BaseVectorStore


class AwaitableStoreProxy(BaseVectorStore):
    """Transparent proxy that allows vector stores to be used both synchronously and awaited."""

    def __init__(self, target: Any) -> None:
        self.__dict__["_target"] = target

    def __await__(self):
        async def _resolve():
            return self.__dict__["_target"]
        return _resolve().__await__()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["_target"], name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_target":
            self.__dict__["_target"] = value
        else:
            setattr(self.__dict__["_target"], name, value)

    def get_store_type(self) -> str:
        target = self.__dict__["_target"]
        if hasattr(target, "get_store_type"):
            return target.get_store_type()
        return getattr(target, "store_type", "unknown")

    def add_documents(self, *args: Any, **kwargs: Any) -> Any:
        return self.__dict__["_target"].add_documents(*args, **kwargs)

    def search(self, *args: Any, **kwargs: Any) -> Any:
        return self.__dict__["_target"].search(*args, **kwargs)

    def delete_documents(self, *args: Any, **kwargs: Any) -> Any:
        return self.__dict__["_target"].delete_documents(*args, **kwargs)

    def get_document_count(self, *args: Any, **kwargs: Any) -> Any:
        target = self.__dict__["_target"]
        if hasattr(target, "get_document_count"):
            return target.get_document_count(*args, **kwargs)
        return len(getattr(target, "documents", []))


class VectorStoreFactory:
    """
    Factory for creating vector store instances with advanced features.

    This factory provides:
    - Automatic store creation based on type
    - Fallback mechanisms for unavailable stores
    - Store capability detection and validation
    - Store comparison and recommendation system
    """

    # Registry of available store implementations
    _store_registry: Dict[str, Dict[str, Any]] = {
        "faiss": {
            "class_name": "FAISSVectorStore",
            "module_path": "ragbot.rag.store.faiss_store",
            "dependencies": ["faiss", "numpy"],
            "capabilities": {
                "metadata_filtering": False,
                "hybrid_search": False,
                "reranking": False,
                "batch_operations": True,
                "persistence": True,
                "gpu_support": True,
            },
            "description": "Facebook AI Similarity Search - Fast local vector search",
            "best_for": "Small to medium datasets, local development, offline operation",
        },
        "chroma": {
            "class_name": "ChromaVectorStore",
            "module_path": "ragbot.rag.store.chroma_store",
            "dependencies": ["chromadb"],
            "capabilities": {
                "metadata_filtering": True,
                "hybrid_search": True,
                "reranking": True,
                "batch_operations": True,
                "persistence": True,
                "gpu_support": False,
            },
            "description": "Open-source embedding database with rich metadata support",
            "best_for": "RAG applications, metadata-rich data, easy setup",
        },
        "qdrant": {
            "class_name": "QdrantVectorStore",
            "module_path": "ragbot.rag.store.qdrant_store",
            "dependencies": ["qdrant-client"],
            "capabilities": {
                "metadata_filtering": True,
                "hybrid_search": True,
                "reranking": True,
                "batch_operations": True,
                "persistence": True,
                "gpu_support": False,
            },
            "description": "Vector database for production with high performance",
            "best_for": "Large datasets, production environments, scalability",
        },
    }

    @classmethod
    def create_store(
        cls, store_type: str, allow_fallback: bool = True, **kwargs: Any
    ) -> BaseVectorStore:
        """
        Create a vector store instance based on type.

        Args:
            store_type: Type of vector store to create ("faiss", "chroma", "qdrant")
            allow_fallback: When True (default, legacy behavior), a missing
                dependency or a creation error returns a FAISS fallback store.
                When False, the error is raised as VectorStoreError instead.
                Security (C2): tenant-scoped stores must pass False. The fallback
                store does not keep the tenant partition (for Chroma and Qdrant it
                opens the shared default index), so a silent fallback can mix the
                data of several tenants.
            **kwargs: Additional configuration parameters for the store

        Returns:
            BaseVectorStore: Instance of the requested vector store

        Raises:
            ValueError: If store_type is not supported
            VectorStoreError: If allow_fallback is False and the store cannot be created
            RuntimeError: If store creation and the fallback both fail
        """
        from ragbot.rag.exceptions import VectorStoreError

        store_type = store_type.lower().strip()
        aliases = {
            "chromadb": "chroma",
            "qdrant_client": "qdrant",
            "weaviate_client": "weaviate",
        }
        store_type = aliases.get(store_type, store_type)

        if store_type not in cls._store_registry:
            available_stores = list(cls._store_registry.keys())
            raise ValueError(
                f"Unsupported store type: '{store_type}'. "
                f"Available stores: {available_stores}"
            )

        store_info = cls._store_registry[store_type]

        # Check dependencies
        if not cls._check_dependencies(store_info["dependencies"]):
            if not allow_fallback:
                raise VectorStoreError(
                    f"Dependencies for vector store '{store_type}' are not available",
                    operation="create",
                    store_type=store_type,
                )
            logger.warning(
                f"Dependencies for {store_type} not available, attempting fallback",
                store_type=store_type,
                dependencies=store_info["dependencies"],
            )
            return cls._create_fallback_store(**kwargs)

        try:
            # Import the store module
            module = importlib.import_module(store_info["module_path"])
            store_class = getattr(module, store_info["class_name"])

            # Add store type to kwargs
            kwargs["store_type"] = store_type

            # Create store instance
            store_instance = store_class(**kwargs)

            logger.info(
                f"Successfully created {store_type} vector store",
                store_type=store_type,
                class_name=store_info["class_name"],
            )

            if isinstance(store_instance, AwaitableStoreProxy):
                return store_instance
            return AwaitableStoreProxy(store_instance)

        except ImportError as e:
            logger.error(
                f"Failed to import {store_type} store: {e}",
                store_type=store_type,
                error=str(e),
            )
            if not allow_fallback:
                raise VectorStoreError(
                    f"Failed to import vector store '{store_type}'",
                    operation="create",
                    store_type=store_type,
                    details=str(e),
                ) from e
            return cls._create_fallback_store(**kwargs)

        except Exception as e:
            logger.error(
                f"Failed to create {store_type} store: {e}",
                store_type=store_type,
                error=str(e),
            )
            if not allow_fallback:
                raise VectorStoreError(
                    f"Failed to create vector store '{store_type}'",
                    operation="create",
                    store_type=store_type,
                    details=str(e),
                ) from e
            return cls._create_fallback_store(**kwargs)

    @classmethod
    def get_available_stores(cls) -> List[str]:
        """
        Get list of available vector store types.

        Returns:
            List[str]: List of available store types
        """
        return list(cls._store_registry.keys())

    @classmethod
    def get_store_info(cls, store_type: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific store type.

        Args:
            store_type: Type of vector store to get info for

        Returns:
            Dict[str, Any]: Detailed information about the store type
        """
        store_type = store_type.lower().strip()

        if store_type not in cls._store_registry:
            return {}

        store_info = cls._store_registry[store_type].copy()

        # Add availability status
        store_info["available"] = cls._check_dependencies(store_info["dependencies"])

        return store_info

    @classmethod
    def get_all_stores_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all available store types.

        Returns:
            Dict[str, Dict[str, Any]]: Information about all store types
        """
        return {
            store_type: cls.get_store_info(store_type)
            for store_type in cls._store_registry.keys()
        }

    @classmethod
    def recommend_store(
        cls,
        use_case: str = "general",
        dataset_size: str = "medium",
        features_required: List[str] = None,
    ) -> str:
        """
        Recommend the best store type based on requirements.

        Args:
            use_case: Use case description ("development", "production", "research")
            dataset_size: Size of dataset ("small", "medium", "large", "enterprise")
            features_required: List of required features

        Returns:
            str: Recommended store type
        """
        if features_required is None:
            features_required = []

        # Scoring system
        scores = {}

        for store_type, info in cls._store_registry.items():
            score = 0

            # Check availability
            if not cls._check_dependencies(info["dependencies"]):
                continue

            # Use case scoring
            if use_case == "development":
                if store_type == "faiss":
                    score += 3
                elif store_type == "chroma":
                    score += 2
            elif use_case == "production":
                if store_type == "qdrant":
                    score += 3
                elif store_type == "chroma":
                    score += 1

            # Dataset size scoring
            if dataset_size == "small":
                if store_type == "faiss":
                    score += 3
                elif store_type == "chroma":
                    score += 2
            elif dataset_size in ["large", "enterprise"]:
                if store_type == "qdrant":
                    score += 3
                elif store_type == "chroma":
                    score += 1

            # Feature requirements scoring
            capabilities = info["capabilities"]
            for feature in features_required:
                if capabilities.get(feature, False):
                    score += 2

            scores[store_type] = score

        # Return store with highest score, fallback to faiss
        if scores:
            recommended = max(scores.items(), key=lambda x: x[1])[0]
            logger.info(
                f"Recommended store: {recommended}",
                recommended_store=recommended,
                scores=scores,
                use_case=use_case,
                dataset_size=dataset_size,
                features_required=features_required,
            )
            return recommended

        logger.warning("No suitable store found, falling back to faiss")
        return "faiss"

    @classmethod
    def _check_dependencies(cls, dependencies: List[str]) -> bool:
        """
        Check if all required dependencies are available.

        Args:
            dependencies: List of required package names

        Returns:
            bool: True if all dependencies are available
        """
        package_to_module = {
            "qdrant-client": "qdrant_client",
        }
        for dep in dependencies:
            mod = package_to_module.get(dep, dep.replace("-", "_"))
            try:
                importlib.import_module(mod)
            except ImportError:
                return False
        return True

    @classmethod
    def _create_fallback_store(cls, **kwargs: Any) -> BaseVectorStore:
        """
        Create a fallback store when the requested store is not available.

        Args:
            **kwargs: Configuration parameters

        Returns:
            BaseVectorStore: Fallback store instance (usually FAISS)
        """
        logger.warning("Creating fallback store (FAISS)")

        try:
            # Try FAISS as fallback - directly import and create without going through create_store
            from ragbot.rag.store.faiss_store import FAISSStore
            from ragbot.configs.settings import settings

            # Remove store_type from kwargs to avoid conflicts
            fallback_kwargs = {k: v for k, v in kwargs.items() if k != "store_type"}

            # Ensure path is provided for FAISS fallback
            if "path" not in fallback_kwargs and "store_path" not in fallback_kwargs:
                fallback_kwargs["path"] = str(settings.store_path)

            # Create FAISS store directly
            fallback_store = FAISSStore(**fallback_kwargs)
            return AwaitableStoreProxy(fallback_store)
        except Exception as e:
            logger.error(f"Failed to create fallback store: {e}")
            raise RuntimeError(
                "Unable to create any vector store. "
                "Please ensure at least FAISS dependencies are installed."
            ) from e

    @classmethod
    def register_store(
        cls,
        store_type: str,
        class_name: str,
        module_path: str,
        dependencies: List[str],
        capabilities: Dict[str, bool],
        description: str,
        best_for: str,
    ) -> None:
        """
        Register a new store type with the factory.

        Args:
            store_type: Unique identifier for the store type
            class_name: Name of the store class
            module_path: Python module path to the store class
            dependencies: List of required dependencies
            capabilities: Dictionary of store capabilities
            description: Description of the store
            best_for: Use cases the store is best suited for
        """
        cls._store_registry[store_type.lower()] = {
            "class_name": class_name,
            "module_path": module_path,
            "dependencies": dependencies,
            "capabilities": capabilities,
            "description": description,
            "best_for": best_for,
        }

        logger.info(f"Registered new store type: {store_type}")

    @classmethod
    def unregister_store(cls, store_type: str) -> bool:
        """
        Unregister a store type from the factory.

        Args:
            store_type: Store type to unregister

        Returns:
            bool: True if store was unregistered, False if not found
        """
        store_type = store_type.lower()

        if store_type in cls._store_registry:
            del cls._store_registry[store_type]
            logger.info(f"Unregistered store type: {store_type}")
            return True

        return False

    @classmethod
    def validate_store_config(
        cls, store_type: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate configuration for a specific store type.

        Args:
            store_type: Type of store to validate config for
            config: Configuration dictionary to validate

        Returns:
            Dict[str, Any]: Validation results with errors and warnings
        """
        store_type = store_type.lower()

        if store_type not in cls._store_registry:
            return {
                "valid": False,
                "errors": [f"Unknown store type: {store_type}"],
                "warnings": [],
            }

        errors = []
        warnings = []

        # Basic validation logic (can be extended per store type)
        if store_type == "faiss":
            if "embedding_dimension" in config:
                dim = config["embedding_dimension"]
                if not isinstance(dim, int) or dim <= 0:
                    errors.append("embedding_dimension must be a positive integer")

        elif store_type == "chroma":
            if "collection_name" in config:
                name = config["collection_name"]
                if not isinstance(name, str) or not name.strip():
                    errors.append("collection_name must be a non-empty string")

        elif store_type == "qdrant":
            if "url" in config:
                url = config["url"]
                if not isinstance(url, str) or not url.startswith(
                    ("http://", "https://")
                ):
                    errors.append("url must be a valid HTTP/HTTPS URL")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
