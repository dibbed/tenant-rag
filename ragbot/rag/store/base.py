"""
Base vector store interface for document storage and retrieval.

This module defines the base interface that all vector stores must implement,
providing a consistent API for storing and querying document embeddings.

Design goals:
- Consistent score convention: higher is always better. Backends using L2 must
  map scores to negative distances so sorting by descending works uniformly.
- Clear configuration surface (similarity metric, normalization, index params)
- Optional hooks for metrics/observability
"""

import functools
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager


def log_store_errors(operation: str):
    """
    Decorator for store methods to log and metricize failures uniformly.

    Notes:
    - Success metrics are recorded explicitly in concrete stores to avoid duplicates.
    - This decorator records only failures (success=False) and re-raises.
    """

    def _decorator(fn):
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def _aw(self, *args, **kwargs):
                try:
                    return await fn(self, *args, **kwargs)
                except Exception as e:  # pragma: no cover - logging path
                    try:
                        store_label = getattr(
                            self, "store_type_label", self.__class__.__name__.lower()
                        )
                        logger.error(
                            f"Store operation failed: {operation}",
                            store=store_label,
                            error=str(e),
                        )
                        metrics_manager.record_vector_store_operation(
                            operation=operation,
                            store_type=store_label,
                            success=False,
                            error=str(e),
                        )
                    finally:
                        pass
                    raise

            return _aw
        else:

            @functools.wraps(fn)
            def _w(self, *args, **kwargs):
                try:
                    return fn(self, *args, **kwargs)
                except Exception as e:  # pragma: no cover - logging path
                    try:
                        store_label = getattr(
                            self, "store_type_label", self.__class__.__name__.lower()
                        )
                        logger.error(
                            f"Store operation failed: {operation}",
                            store=store_label,
                            error=str(e),
                        )
                        metrics_manager.record_vector_store_operation(
                            operation=operation,
                            store_type=store_label,
                            success=False,
                            error=str(e),
                        )
                    finally:
                        pass
                    raise

            return _w

    return _decorator


@dataclass
class VectorDocument:
    """
    Represents a document stored in the vector store.

    Attributes:
        id: Unique document identifier
        content: Text content of the document
        embedding: Vector embedding of the content
        metadata: Additional metadata about the document
        score: Similarity score (used in search results). Convention: higher is
            better. Implementations based on L2 should set score = -distance.
    """

    id: str
    content: str
    embedding: List[float]
    metadata: Optional[Dict[str, Any]] = None
    score: Optional[float] = None

    def __post_init__(self) -> None:
        """Post-initialization validation."""
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Document ID must be a non-empty string")
        if not isinstance(self.content, str):
            raise ValueError("Document content must be a string")
        if hasattr(self.embedding, "tolist"):
            self.embedding = self.embedding.tolist()
        elif not isinstance(self.embedding, list):
            try:
                self.embedding = list(self.embedding)
            except Exception:
                raise ValueError("Document embedding must be a list")
        if self.metadata is None:
            self.metadata = {}
        elif not isinstance(self.metadata, dict):
            raise ValueError("Document metadata must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        """Convert VectorDocument to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorDocument":
        """Create VectorDocument from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=data["embedding"],
            metadata=data["metadata"],
            score=data.get("score"),
        )


class SearchResult:
    """
    Flexible search result object used across the codebase and tests.

    Supports two construction styles:
    1) Aggregate result: provide `documents`, `query_embedding`, `total_results`, `search_time`.
    2) Single-item style (used by tests): provide `content`, `metadata`, `score`.
    """

    def __init__(
        self,
        documents: Optional[List[VectorDocument]] = None,
        query_embedding: Optional[List[float]] = None,
        total_results: Optional[int] = None,
        search_time: Optional[float] = None,
        *,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        score: Optional[float] = None,
    ) -> None:
        # Aggregate-style
        if documents is not None:
            self.documents = documents
            self.query_embedding = query_embedding
            self.total_results = (
                total_results if total_results is not None else len(documents)
            )
            self.search_time = search_time
            # For convenience, expose top-level fields when single doc present
            if len(documents) == 1:
                d0 = documents[0]
                self.content = d0.content
                self.metadata = d0.metadata
                self.score = d0.score
            else:
                self.content = None
                self.metadata = {}
                self.score = None
            return

        # Single-item style used in certain tests
        if content is not None:
            self.content = content
            self.metadata = metadata or {}
            self.score = score
            # Also present a `documents` list for compatibility
            try:
                doc = VectorDocument(
                    id=self.metadata.get("id", "result"),
                    content=content,
                    embedding=[],
                    metadata=self.metadata,
                    score=score,
                )
                self.documents = [doc]
            except Exception:
                self.documents = []
            self.query_embedding = query_embedding
            self.total_results = total_results if total_results is not None else 1
            self.search_time = search_time
            return

        # Default empty result
        self.documents = []
        self.query_embedding = query_embedding
        self.total_results = total_results if total_results is not None else 0
        self.search_time = search_time
        self.content = None
        self.metadata = {}
        self.score = None

    def __len__(self) -> int:
        """Return the number of documents in the search result."""
        return len(self.documents) if hasattr(self, "documents") else 0


class BaseVectorStore(ABC):
    """
    Abstract base class for vector stores.

    All vector store implementations must inherit from this class and implement
    the required methods to provide consistent document storage and retrieval.

    This class provides default implementations for some methods and raises
    NotImplementedError for core methods that must be implemented by subclasses.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the vector store with advanced configuration options.

        Args:
            **kwargs: Store-specific configuration options including:
                - store_type: Type of vector store
                - embedding_dimension: Dimension of embeddings
                - similarity_metric: Similarity metric to use
                - normalize_embeddings: Whether to normalize embeddings
                - enable_metadata_filtering: Enable metadata filtering
                - enable_semantic_chunking: Enable semantic chunking
                - enable_hybrid_search: Enable hybrid search
                - enable_reranking: Enable reranking
                - batch_size: Batch size for operations
                - max_retries: Maximum retry attempts
                - timeout: Operation timeout
                - enable_metrics: Enable metrics collection
                - enable_analytics: Enable analytics collection
        """
        self.config = kwargs
        self.store_type = kwargs.get("store_type", "unknown")
        self.embedding_dimension = kwargs.get("embedding_dimension", 768)

        # Similarity metric should be one of: 'cosine', 'ip' (dot product), 'l2'
        self.similarity_metric = kwargs.get("similarity_metric", "cosine")

        # Normalization behavior (applied by implementation where applicable)
        self.normalize_embeddings = kwargs.get("normalize_embeddings", True)

        # Advanced features
        self.enable_metadata_filtering = kwargs.get("enable_metadata_filtering", True)
        self.enable_semantic_chunking = kwargs.get("enable_semantic_chunking", True)
        self.enable_hybrid_search = kwargs.get("enable_hybrid_search", True)
        self.enable_reranking = kwargs.get("enable_reranking", True)

        # Performance settings
        self.batch_size = kwargs.get("batch_size", 100)
        self.max_retries = kwargs.get("max_retries", 3)
        self.timeout = kwargs.get("timeout", 30.0)

        # Monitoring and analytics
        self.enable_metrics = kwargs.get("enable_metrics", True)
        self.enable_analytics = kwargs.get("enable_analytics", True)

        # Optional index configuration hints (implementations may ignore)
        self.index_type = kwargs.get("index_type", "flat")
        self.nlist = kwargs.get("nlist", 100)
        self.nprobe = kwargs.get("nprobe", 10)
        self.hnsw_m = kwargs.get("hnsw_m", 16)
        self.keep_embeddings = kwargs.get("keep_embeddings", True)
        self.index_path = kwargs.get("index_path", "./vector_index")

    def __await__(self):
        """Allow vector store instances to be used directly with await."""
        async def _resolve():
            return self
        return _resolve().__await__()

    @abstractmethod
    def get_store_type(self) -> str:
        """
        Get the store type identifier.

        Returns:
            str: Store type identifier (e.g., "faiss", "chroma", "qdrant", "weaviate")
        """
        # Default implementation: raise NotImplementedError
        # Concrete implementations must override this method
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_store_type method"
        )

    async def add_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents to add
            **kwargs: Additional options for adding documents

        Returns:
            List[str]: List of document IDs that were added

        Raises:
            VectorStoreError: If adding documents fails
        """
        # Default implementation: raise NotImplementedError
        # Concrete implementations must override this method
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement add_documents method"
        )

    async def update_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        """
        Update existing documents in the vector store.

        Args:
            documents: List of documents to update
            **kwargs: Additional options for updating documents

        Returns:
            List[str]: List of document IDs that were updated

        Raises:
            VectorStoreError: If updating documents fails
        """
        # Default implementation: delete and re-add
        # This is a safe fallback but not optimal for performance
        document_ids = [doc.id for doc in documents]

        try:
            # Delete existing documents
            await self.delete_documents(document_ids, **kwargs)

            # Add updated documents
            updated_ids = await self.add_documents(documents, **kwargs)

            logger.info(
                f"Updated {len(documents)} documents using delete-and-add strategy"
            )
            return updated_ids

        except Exception as e:
            logger.error(f"Error updating documents: {e}")
            raise

    async def delete_documents(
        self, document_ids: List[str], **kwargs: Any
    ) -> List[str]:
        """
        Delete documents from the vector store.

        Args:
            document_ids: List of document IDs to delete
            **kwargs: Additional options for deleting documents

        Returns:
            List[str]: List of document IDs that were deleted

        Raises:
            VectorStoreError: If deleting documents fails
        """
        # Default implementation: raise NotImplementedError
        # Concrete implementations must override this method
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement delete_documents method"
        )

    async def search(
        self, query_embedding: List[float], top_k: int = 10, **kwargs: Any
    ) -> SearchResult:
        """
        Search for similar documents using vector similarity.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of top results to return
            **kwargs: Additional search options

        Returns:
            SearchResult: Search results with matching documents

        Raises:
            VectorStoreError: If search fails
        """
        # Default implementation: raise NotImplementedError
        # Concrete implementations must override this method
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement search method"
        )

    # --------- Optional convenience upsert helpers (non-abstract) ---------
    async def add_chunks(
        self, chunks: List[object], *, embedder: Optional[object] = None, **kwargs: Any
    ) -> List[str]:
        """
        Convenience: accept TextChunk-like objects and embed+add.

        Expects each chunk to have `.content` and `.metadata` attributes.
        Requires an `embedder` providing `embed_texts` (async or sync), or precomputed `embeddings` in kwargs.
        """
        if not chunks:
            return []

        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        for ch in chunks:
            content = getattr(ch, "content", "")
            metadata = getattr(ch, "metadata", {}) or {}
            texts.append(content or "")
            metadatas.append(metadata if isinstance(metadata, dict) else {})

        async def _maybe_await(v):
            if hasattr(v, "__await__"):
                return await v
            return v

        # Embed
        if "embeddings" in kwargs and kwargs["embeddings"] is not None:
            embeddings = kwargs.pop("embeddings")
        elif embedder is not None and hasattr(embedder, "embed_texts"):
            embeddings = await _maybe_await(embedder.embed_texts(texts))
        elif embedder is not None and hasattr(embedder, "embed_texts_sync"):
            embeddings = embedder.embed_texts_sync(texts)
        else:
            embeddings = [[0.0] * self.embedding_dimension for _ in texts]

        docs = []
        for i, (t, m) in enumerate(zip(texts, metadatas)):
            ch = chunks[i]
            chunk_id = getattr(ch, "chunk_id", getattr(ch, "id", None))
            doc_id = str(chunk_id if chunk_id is not None else f"chunk_{i}")
            if isinstance(embeddings, dict):
                e = embeddings.get(chunk_id, embeddings.get(doc_id, [0.0] * self.embedding_dimension))
            elif hasattr(embeddings, "__getitem__"):
                e = embeddings[i]
            else:
                e = [0.0] * self.embedding_dimension

            if hasattr(e, "tolist"):
                e = e.tolist()
            elif not isinstance(e, list):
                try:
                    e = list(e)
                except Exception:
                    e = [0.0] * self.embedding_dimension

            chunk_metadata = m.copy() if isinstance(m, dict) else {}
            if "chunk_type" not in chunk_metadata:
                chunk_metadata["chunk_type"] = getattr(ch, "chunk_type", "semantic_chunk")
            if "is_semantic" not in chunk_metadata:
                chunk_metadata["is_semantic"] = getattr(ch, "is_semantic", True)
            if "chunk_id" not in chunk_metadata:
                chunk_metadata["chunk_id"] = doc_id
            if hasattr(ch, "start_index") and "start_index" not in chunk_metadata:
                chunk_metadata["start_index"] = getattr(ch, "start_index", 0)
            if hasattr(ch, "end_index") and "end_index" not in chunk_metadata:
                chunk_metadata["end_index"] = getattr(ch, "end_index", len(t))
            if "chunk_length" not in chunk_metadata:
                chunk_metadata["chunk_length"] = len(t)

            docs.append(VectorDocument(id=doc_id, content=t, embedding=e, metadata=chunk_metadata))

        return await self.add_documents(docs, **kwargs)

    async def add_documents_from_loader(
        self,
        documents: List[object],
        *,
        embedder: Optional[object] = None,
        chunker: Optional[object] = None,
        **kwargs: Any,
    ) -> List[str]:
        """
        Convenience: accept loader Documents and (optionally) a chunker.
        If `chunker` is provided, use it to split; otherwise index whole text.
        """
        if not documents:
            return []

        chunks_like = []
        for i, d in enumerate(documents):
            text = getattr(d, "text", getattr(d, "content", "")) or ""
            metadata = getattr(d, "metadata", {}) or {}
            doc_id = getattr(d, "id", getattr(d, "chunk_id", f"doc_{i}"))
            if chunker is not None and hasattr(chunker, "chunk_with_metadata"):
                try:
                    parts = chunker.chunk_with_metadata(text)
                    chunks_like.extend(parts)
                    continue
                except Exception:
                    pass
            # Fallback: single chunk object shim
            chunk = type(
                "_Chunk",
                (),
                {"content": text, "metadata": metadata, "chunk_id": doc_id, "id": doc_id},
            )
            chunks_like.append(chunk)

        return await self.add_chunks(chunks_like, embedder=embedder, **kwargs)

    # --------- Optional advanced methods (non-abstract) ---------
    async def search_with_metadata_filter(
        self,
        query_embedding: List[float],
        metadata_filter: Dict[str, Any],
        top_k: int = 10,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Search with metadata filtering by delegating to `search` and applying
        post-filtering when backend lacks native filters.

        Args:
            query_embedding: Query vector embedding
            metadata_filter: Metadata filters to apply
            top_k: Number of top results
        """
        res = await self.search(query_embedding, top_k=top_k, **kwargs)
        try:
            filtered = self.filter_documents(res.documents, metadata_filter)
            # Preserve ordering by score
            filtered.sort(key=lambda d: d.score or 0.0, reverse=True)
            return SearchResult(
                documents=filtered,
                query_embedding=res.query_embedding,
                total_results=len(filtered),
                search_time=res.search_time,
            )
        except Exception:
            return res

    async def hybrid_search(
        self,
        query: str,
        query_embedding: List[float],
        alpha: float = 0.7,
        top_k: int = 10,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Optional hybrid search placeholder. Implementations may override with
        backend-specific capabilities. Default falls back to vector search.
        """
        return await self.search(query_embedding, top_k=top_k, **kwargs)

    async def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Optional semantic search helper wrapping `search` and applying a
        similarity threshold.
        """
        res = await self.search(query_embedding, top_k=top_k, **kwargs)
        try:
            if similarity_threshold is None:
                return res
            docs = [
                d
                for d in res.documents
                if d.score is None or d.score >= similarity_threshold
            ]
            return SearchResult(
                documents=docs,
                query_embedding=res.query_embedding,
                total_results=len(docs),
                search_time=res.search_time,
            )
        except Exception:
            return res

    async def get_document(self, document_id: str) -> Optional[VectorDocument]:
        """
        Retrieve a specific document by ID.

        Args:
            document_id: Document ID to retrieve

        Returns:
            Optional[VectorDocument]: Document if found, None otherwise

        Raises:
            VectorStoreError: If retrieval fails
        """
        # Default implementation: return from documents dict if available, otherwise raise NotImplementedError
        if hasattr(self, "documents") and isinstance(self.documents, dict):
            return self.documents.get(document_id)
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_document method"
        )

    async def get_documents(self, document_ids: List[str]) -> List[VectorDocument]:
        """
        Retrieve multiple documents by IDs.

        Args:
            document_ids: List of document IDs to retrieve

        Returns:
            List[VectorDocument]: List of found documents

        Raises:
            VectorStoreError: If retrieval fails
        """
        # Default implementation: call get_document for each ID
        # This is not optimal but provides a working fallback
        documents = []
        for doc_id in document_ids:
            try:
                doc = await self.get_document(doc_id)
                if doc:
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to retrieve document {doc_id}: {e}")
                continue

        return documents

    async def get_documents_by_metadata(
        self, filters: Dict[str, Any]
    ) -> List[VectorDocument]:
        """
        Get documents matching metadata filter criteria.

        Args:
            filters: Dictionary of filter criteria

        Returns:
            List[VectorDocument]: Matching documents
        """
        if hasattr(self, "get_all_documents") and callable(self.get_all_documents):
            res = self.get_all_documents()
            all_docs = await res if hasattr(res, "__await__") else res
        elif hasattr(self, "documents") and isinstance(self.documents, dict):
            all_docs = list(self.documents.values())
        else:
            all_docs = []
        return self.filter_documents(all_docs, filters)

    def get_document_count(self) -> int:
        """
        Get the total number of documents in the store.

        Returns:
            int: Number of documents
        """
        # Default implementation: raise NotImplementedError
        # Concrete implementations must override this method
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_document_count method"
        )

    async def clear(self) -> None:
        """
        Clear all documents from the vector store.

        Raises:
            VectorStoreError: If clearing fails
        """
        # Default implementation: raise NotImplementedError
        # Concrete implementations must override this method
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement clear method"
        )

    async def save(self, path: Optional[str] = None) -> None:
        """
        Save the vector store to disk.

        Args:
            path: Optional path to save to (uses default if None)

        Raises:
            VectorStoreError: If saving fails
        """
        # Default implementation: no-op for stores that handle persistence automatically
        # Concrete implementations can override this method if needed
        logger.debug(
            f"Save called on {self.__class__.__name__} - no-op (automatic persistence)"
        )
        pass

    async def load(self, path: Optional[str] = None) -> None:
        """
        Load the vector store from disk.

        Args:
            path: Optional path to load from (uses default if None)

        Raises:
            VectorStoreError: If loading fails
        """
        # Default implementation: no-op for stores that handle persistence automatically
        # Concrete implementations can override this method if needed
        logger.debug(
            f"Load called on {self.__class__.__name__} - no-op (automatic persistence)"
        )
        pass

    # Optional methods with default implementations

    async def upsert_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        """
        Insert or update documents (upsert operation).

        Args:
            documents: List of documents to upsert
            **kwargs: Additional options

        Returns:
            List[str]: List of document IDs that were upserted
        """
        # Default implementation: try update first, then add
        existing_ids = []
        new_documents = []

        for doc in documents:
            existing_doc = await self.get_document(doc.id)
            if existing_doc:
                existing_ids.append(doc.id)
            else:
                new_documents.append(doc)

        # Update existing documents
        updated_ids = []
        if existing_ids:
            existing_docs = [doc for doc in documents if doc.id in existing_ids]
            updated_ids = await self.update_documents(existing_docs, **kwargs)

        # Add new documents
        added_ids = []
        if new_documents:
            added_ids = await self.add_documents(new_documents, **kwargs)

        return updated_ids + added_ids

    # Optional metric/trace hooks (no-op by default)
    def _on_operation_start(self, op: str, **_kwargs: Any) -> None:
        """Hook invoked before a store operation starts (override if needed)."""
        return None

    def _on_operation_end(self, op: str, duration: float, **_kwargs: Any) -> None:
        """Hook invoked after a store operation ends (override if needed)."""
        return None

    async def search_by_text(
        self, query_text: str, embedder, top_k: int = 10, **kwargs: Any
    ) -> SearchResult:
        """
        Search for similar documents using text query.

        Args:
            query_text: Text query to search for
            embedder: Embedder to generate query embedding
            top_k: Number of top results to return
            **kwargs: Additional search options

        Returns:
            SearchResult: Search results with matching documents
        """
        # Generate embedding for query text
        query_embedding = await embedder.embed_single(query_text)

        # Perform vector search
        return await self.search(query_embedding, top_k, **kwargs)

    def filter_documents(
        self, documents: List[VectorDocument], filters: Dict[str, Any]
    ) -> List[VectorDocument]:
        """
        Filter documents based on metadata criteria.

        Args:
            documents: List of documents to filter
            filters: Dictionary of filter criteria

        Returns:
            List[VectorDocument]: Filtered documents
        """
        filtered_docs = []

        for doc in documents:
            match = True

            for key, value in filters.items():
                if key not in doc.metadata:
                    match = False
                    break

                doc_value = doc.metadata[key]

                # Handle different filter types
                if isinstance(value, dict):
                    # Range or comparison filters
                    if "$gte" in value and doc_value < value["$gte"]:
                        match = False
                        break
                    if "$lte" in value and doc_value > value["$lte"]:
                        match = False
                        break
                    if "$gt" in value and doc_value <= value["$gt"]:
                        match = False
                        break
                    if "$lt" in value and doc_value >= value["$lt"]:
                        match = False
                        break
                    if "$in" in value and doc_value not in value["$in"]:
                        match = False
                        break
                    if "$nin" in value and doc_value in value["$nin"]:
                        match = False
                        break
                elif isinstance(value, list):
                    # List membership
                    if doc_value not in value:
                        match = False
                        break
                else:
                    # Exact match
                    if doc_value != value:
                        match = False
                        break

            if match:
                filtered_docs.append(doc)

        return filtered_docs

    def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Compute similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            float: Similarity score
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            metric = str(self.similarity_metric).lower()

            if metric in ("cosine",):
                # Cosine similarity
                dot_product = np.dot(vec1, vec2)
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)

                if norm1 == 0 or norm2 == 0:
                    return 0.0

                return float(dot_product / (norm1 * norm2))

            elif metric in ("euclidean", "l2"):
                # Euclidean (L2) distance → map to similarity (higher is better)
                distance = np.linalg.norm(vec1 - vec2)
                return float(-distance)

            elif metric in ("dot_product", "ip"):
                # Dot product similarity
                return float(np.dot(vec1, vec2))

            else:
                # Default to cosine similarity
                dot_product = np.dot(vec1, vec2)
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)

                if norm1 == 0 or norm2 == 0:
                    return 0.0

                return float(dot_product / (norm1 * norm2))

        except Exception:
            return 0.0

    def get_store_info(self) -> Dict[str, Any]:
        """
        Get information about the vector store.

        Returns:
            Dict[str, Any]: Store information
        """
        store_type = (
            self.get_store_type()
            if hasattr(self, "get_store_type") and callable(self.get_store_type)
            else getattr(self, "store_type", self.__class__.__name__)
        )
        return {
            "store_type": store_type,
            "embedding_dimension": self.embedding_dimension,
            "similarity_metric": self.similarity_metric,
            "document_count": self.get_document_count(),
            "features": {
                "metadata_filtering": self.enable_metadata_filtering,
                "semantic_chunking": self.enable_semantic_chunking,
                "hybrid_search": self.enable_hybrid_search,
                "reranking": self.enable_reranking,
            },
            "index_path": self.index_path,
            "config": self.config,
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the vector store.

        Returns:
            Dict[str, Any]: Health check results
        """
        store_type = (
            self.get_store_type()
            if hasattr(self, "get_store_type") and callable(self.get_store_type)
            else getattr(self, "store_type", self.__class__.__name__)
        )
        try:
            if hasattr(self, "documents") and self.documents is None:
                raise RuntimeError("Vector store storage is unavailable")
            document_count = self.get_document_count()
            return {
                "status": "healthy",
                "store_type": store_type,
                "document_count": document_count,
                "embedding_dimension": self.embedding_dimension,
                "features": {
                    "metadata_filtering": self.enable_metadata_filtering,
                    "semantic_chunking": self.enable_semantic_chunking,
                    "hybrid_search": self.enable_hybrid_search,
                    "reranking": self.enable_reranking,
                },
                "performance": {
                    "batch_size": self.batch_size,
                    "timeout": self.timeout,
                },
                "test_successful": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "store_type": store_type,
                "error": str(e),
                "test_successful": False,
            }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics.

        Returns:
            Dict[str, Any]: Statistics dictionary
        """
        store_type = (
            self.get_store_type()
            if hasattr(self, "get_store_type") and callable(self.get_store_type)
            else getattr(self, "store_type", self.__class__.__name__)
        )
        try:
            document_count = self.get_document_count()
        except Exception:
            document_count = 0

        return {
            "store_type": store_type,
            "document_count": document_count,
            "embedding_dimension": self.embedding_dimension,
            "similarity_metric": self.similarity_metric,
            "features": {
                "metadata_filtering": self.enable_metadata_filtering,
                "semantic_chunking": self.enable_semantic_chunking,
                "hybrid_search": self.enable_hybrid_search,
                "reranking": self.enable_reranking,
            },
            "performance": {
                "batch_size": self.batch_size,
                "timeout": self.timeout,
            },
        }

    # --------- Maintenance/analytics helpers (optional) ---------

    async def backup(self) -> str:
        """
        Create a backup by delegating to `save` into a temp directory when possible.
        Returns backup directory path.
        """
        import tempfile

        backup_dir = tempfile.mkdtemp(
            prefix=f"ragbot_store_backup_{self.__class__.__name__}_"
        )
        try:
            await self.save(backup_dir)
        except Exception:
            # Best-effort for backends with implicit persistence
            pass
        return backup_dir

    async def restore(self, backup_path: str) -> None:
        """Restore from a backup directory by delegating to `load`."""
        try:
            await self.load(backup_path)
        except Exception:
            return

    async def get_search_analytics(self) -> Dict[str, Any]:
        """Return aggregated search analytics using collected metrics."""
        label = getattr(self, "store_type_label", self.__class__.__name__.lower())
        summary = metrics_manager.get_vector_store_metrics(store_type=label) or {}
        operations = summary.get("operations", {})
        search_stats = operations.get("search", {})

        return {
            "store_type": label,
            "total_searches": search_stats.get("count", 0),
            "documents_returned": search_stats.get("documents", 0),
            "avg_documents_per_search": search_stats.get("avg_documents"),
            "avg_search_duration": search_stats.get("avg_duration"),
            "errors": search_stats.get("errors", 0),
            "last_success": search_stats.get("last_success"),
            "last_failure": search_stats.get("last_failure"),
            "last_updated": search_stats.get("last_updated"),
        }

    async def get_document_analytics(self) -> Dict[str, Any]:
        """Return document analytics derived from metrics and store state."""
        label = getattr(self, "store_type_label", self.__class__.__name__.lower())
        summary = metrics_manager.get_vector_store_metrics(store_type=label) or {}
        operations = summary.get("operations", {})
        add_stats = operations.get("add_documents", {})
        delete_stats = operations.get("delete_documents", {})

        try:
            total_documents = self.get_document_count()
        except Exception:
            total_documents = summary.get("size")

        if total_documents is not None:
            metrics_manager.update_vector_store_size(
                int(total_documents), store_type=label
            )

        return {
            "store_type": label,
            "total_documents": total_documents,
            "documents_added": add_stats.get("documents", 0),
            "add_operations": add_stats.get("count", 0),
            "documents_deleted": delete_stats.get("documents", 0),
            "delete_operations": delete_stats.get("count", 0),
            "last_update": summary.get("last_updated"),
        }
