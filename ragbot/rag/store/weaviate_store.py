"""
Weaviate vector store implementation.

Provides an async-friendly wrapper around weaviate-client with
SearchResult/VectorDocument compatibility and advanced features.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.store.base import (
    BaseVectorStore,
    SearchResult,
    VectorDocument,
    log_store_errors,
)

try:
    import weaviate  # type: ignore

    WEAVIATE_AVAILABLE = True
except Exception:
    WEAVIATE_AVAILABLE = False


class WeaviateVectorStore(BaseVectorStore):
    """
    Weaviate-based vector store implementation with advanced features.

    This implementation provides:
    - GraphQL-native vector search
    - Advanced metadata filtering
    - Multi-modal support (future)
    - Enterprise-grade scalability
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize Weaviate vector store with advanced configuration.

        Args:
            **kwargs: Configuration options including:
                - url: Weaviate server URL
                - api_key: Weaviate API key
                - class_name: Weaviate class name
                - enable_graphql: Enable GraphQL features
                - enable_multi_modal: Enable multi-modal support
        """
        super().__init__(**kwargs)

        if not WEAVIATE_AVAILABLE:
            raise ImportError(
                "weaviate-client not installed. Please install 'weaviate-client'."
            )

        self.store_type_label = "weaviate"

        # Weaviate-specific configuration
        self.url: str = kwargs.get("url", "http://localhost:8080")
        self.api_key: Optional[str] = kwargs.get("api_key", None)
        self.class_name: str = kwargs.get("class_name", "RagBot")
        self.enable_graphql: bool = kwargs.get("enable_graphql", True)
        self.enable_multi_modal: bool = kwargs.get("enable_multi_modal", False)

        # Initialize Weaviate client
        self._initialize_client()

        # Ensure schema exists
        self._ensure_schema_exists()

        logger.info(
            "Weaviate store initialized",
            url=self.url,
            class_name=self.class_name,
            enable_graphql=self.enable_graphql,
        )

    def get_store_type(self) -> str:
        """Get the store type identifier."""
        return "weaviate"

    def _initialize_client(self) -> None:
        """Initialize Weaviate client with configuration."""
        try:
            if self.api_key:
                self.client = weaviate.Client(
                    url=self.url,
                    auth_client_secret=weaviate.AuthApiKey(api_key=self.api_key),
                )
            else:
                self.client = weaviate.Client(url=self.url)
        except Exception as e:
            logger.error(f"Failed to initialize Weaviate client: {e}")
            raise

    def _ensure_schema_exists(self) -> None:
        """Ensure Weaviate schema exists for the class."""
        try:
            if not self.client.schema.exists(self.class_name):
                self._create_schema()
        except Exception as e:
            logger.error(f"Failed to ensure schema exists: {e}")
            raise

    def _create_schema(self) -> None:
        """Create Weaviate schema for the class."""
        schema = {
            "class": self.class_name,
            "description": "RAG Bot document storage",
            "vectorizer": "none",  # We provide our own embeddings
            "properties": [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "Document content",
                },
                {
                    "name": "metadata",
                    "dataType": ["object"],
                    "description": "Document metadata",
                },
                {
                    "name": "document_id",
                    "dataType": ["string"],
                    "description": "Document ID",
                },
            ],
        }

        self.client.schema.create_class(schema)

    async def _to_thread(self, fn, *args, **kwargs):
        """Run function in thread pool."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    @log_store_errors("add_documents")
    async def add_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        """
        Add documents to Weaviate store.

        Args:
            documents: List of documents to add
            **kwargs: Additional options

        Returns:
            List[str]: List of document IDs that were added
        """
        if not documents:
            return []

        started = time.time()
        added_ids = []

        def _add_docs():
            nonlocal added_ids
            for doc in documents:
                try:
                    # Prepare Weaviate object
                    weaviate_object = {
                        "content": doc.content,
                        "metadata": doc.metadata,
                        "document_id": doc.id,
                    }

                    # Add to Weaviate
                    self.client.data_object.create(
                        data_object=weaviate_object,
                        class_name=self.class_name,
                        vector=doc.embedding,
                    )

                    added_ids.append(doc.id)

                except Exception as e:
                    logger.error(f"Failed to add document {doc.id}: {e}")

        await self._to_thread(_add_docs)

        duration = time.time() - started
        metrics_manager.record_vector_store_operation(
            operation="add_documents",
            store_type=self.store_type_label,
            document_count=len(added_ids),
            success=True,
            duration=duration,
        )

        return added_ids

    @log_store_errors("search")
    async def search(
        self, query_embedding: List[float], top_k: int = 10, **kwargs: Any
    ) -> SearchResult:
        """
        Search documents in Weaviate store.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of top results
            **kwargs: Additional options

        Returns:
            SearchResult: Search results
        """
        started = time.time()

        def _search():
            try:
                # Perform vector search
                result = (
                    self.client.query.get(
                        self.class_name, ["content", "metadata", "document_id"]
                    )
                    .with_near_vector(
                        {
                            "vector": query_embedding,
                            "certainty": 0.7,  # Similarity threshold
                        }
                    )
                    .with_limit(top_k)
                    .do()
                )

                documents = []
                if result and "data" in result and "Get" in result["data"]:
                    for item in result["data"]["Get"][self.class_name]:
                        doc = VectorDocument(
                            id=item.get("document_id", ""),
                            content=item.get("content", ""),
                            embedding=query_embedding,  # We don't store embeddings in Weaviate
                            metadata=item.get("metadata", {}),
                            score=item.get("_additional", {}).get("certainty", 0.0),
                        )
                        documents.append(doc)

                return documents

            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []

        documents = await self._to_thread(_search)
        duration = time.time() - started

        metrics_manager.record_vector_store_operation(
            operation="search",
            store_type=self.store_type_label,
            document_count=len(documents),
            success=True,
            duration=duration,
        )

        return SearchResult(
            documents=documents,
            query_embedding=query_embedding,
            total_results=len(documents),
            search_time=duration,
        )

    @log_store_errors("search_with_metadata_filter")
    async def search_with_metadata_filter(
        self,
        query_embedding: List[float],
        metadata_filter: Dict[str, Any],
        top_k: int = 10,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Search documents with metadata filter in Weaviate store.

        Args:
            query_embedding: Query vector embedding
            metadata_filter: Metadata filters to apply
            top_k: Number of top results
            **kwargs: Additional options

        Returns:
            SearchResult: Filtered search results
        """
        started = time.time()

        def _search_with_filter():
            try:
                # Build GraphQL where clause
                where_clause = self._build_where_clause(metadata_filter)

                # Perform vector search with filter
                query = (
                    self.client.query.get(
                        self.class_name, ["content", "metadata", "document_id"]
                    )
                    .with_near_vector({"vector": query_embedding, "certainty": 0.7})
                    .with_limit(top_k)
                )

                if where_clause:
                    query = query.with_where(where_clause)

                result = query.do()

                documents = []
                if result and "data" in result and "Get" in result["data"]:
                    for item in result["data"]["Get"][self.class_name]:
                        doc = VectorDocument(
                            id=item.get("document_id", ""),
                            content=item.get("content", ""),
                            embedding=query_embedding,
                            metadata=item.get("metadata", {}),
                            score=item.get("_additional", {}).get("certainty", 0.0),
                        )
                        documents.append(doc)

                return documents

            except Exception as e:
                logger.error(f"Search with filter failed: {e}")
                return []

        documents = await self._to_thread(_search_with_filter)
        duration = time.time() - started

        return SearchResult(
            documents=documents,
            query_embedding=query_embedding,
            total_results=len(documents),
            search_time=duration,
        )

    def _build_where_clause(self, metadata_filter: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Weaviate where clause from metadata filter.

        Args:
            metadata_filter: Metadata filters

        Returns:
            Dict[str, Any]: Weaviate where clause
        """
        if not metadata_filter:
            return {}

        conditions = []
        for key, value in metadata_filter.items():
            if isinstance(value, str):
                conditions.append(
                    {
                        "path": ["metadata", key],
                        "operator": "Equal",
                        "valueString": value,
                    }
                )
            elif isinstance(value, (int, float)):
                conditions.append(
                    {
                        "path": ["metadata", key],
                        "operator": "Equal",
                        "valueNumber": value,
                    }
                )
            elif isinstance(value, bool):
                conditions.append(
                    {
                        "path": ["metadata", key],
                        "operator": "Equal",
                        "valueBoolean": value,
                    }
                )

        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"operator": "And", "operands": conditions}

        return {}

    @log_store_errors("delete_documents")
    async def delete_documents(
        self, document_ids: List[str], **kwargs: Any
    ) -> List[str]:
        """
        Delete documents from Weaviate store.

        Args:
            document_ids: List of document IDs to delete
            **kwargs: Additional options

        Returns:
            List[str]: List of document IDs that were deleted
        """
        if not document_ids:
            return []

        started = time.time()
        deleted_ids = []

        def _delete_docs():
            nonlocal deleted_ids
            for doc_id in document_ids:
                try:
                    # Find object by document_id
                    result = (
                        self.client.query.get(self.class_name, ["document_id"])
                        .with_where(
                            {
                                "path": ["document_id"],
                                "operator": "Equal",
                                "valueString": doc_id,
                            }
                        )
                        .do()
                    )

                    if result and "data" in result and "Get" in result["data"]:
                        objects = result["data"]["Get"][self.class_name]
                        for obj in objects:
                            # Delete by object ID
                            self.client.data_object.delete(
                                uuid=obj["_additional"]["id"],
                                class_name=self.class_name,
                            )
                            deleted_ids.append(doc_id)

                except Exception as e:
                    logger.error(f"Failed to delete document {doc_id}: {e}")

        await self._to_thread(_delete_docs)

        duration = time.time() - started
        metrics_manager.record_vector_store_operation(
            operation="delete_documents",
            store_type=self.store_type_label,
            document_count=len(deleted_ids),
            success=True,
            duration=duration,
        )

        return deleted_ids

    def get_document_count(self) -> int:
        """
        Get total document count in Weaviate store.

        Returns:
            int: Number of documents
        """
        try:
            result = self.client.query.aggregate(self.class_name).with_meta_count().do()
            if result and "data" in result and "Aggregate" in result["data"]:
                return result["data"]["Aggregate"][self.class_name][0]["meta"]["count"]
            return 0
        except Exception:
            return 0

    @log_store_errors("clear")
    async def clear(self) -> None:
        """Clear all documents from Weaviate store."""
        started = time.time()

        def _clear():
            # Delete all objects in the class
            self.client.schema.delete_class(self.class_name)
            # Recreate schema
            self._create_schema()

        await self._to_thread(_clear)

        duration = time.time() - started
        metrics_manager.record_vector_store_operation(
            operation="clear",
            store_type=self.store_type_label,
            document_count=0,
            success=True,
            duration=duration,
        )

    @log_store_errors("save")
    async def save(self, path: Optional[str] = None) -> None:
        """Save Weaviate store (handled automatically by Weaviate)."""
        # Persistence handled by Weaviate automatically
        pass

    @log_store_errors("load")
    async def load(self, path: Optional[str] = None) -> None:
        """Load Weaviate store (handled automatically by Weaviate)."""
        # Persistence handled by Weaviate automatically
        pass

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on the Weaviate vector store.

        Returns:
            Dict[str, Any]: Health check results including store status, capabilities,
                and performance metrics.
        """
        try:
            doc_count = self.get_document_count()
            schema_info = await self._get_schema_info()

            return {
                "status": "healthy",
                "store_type": "weaviate",
                "document_count": doc_count,
                "embedding_dimension": self.embedding_dimension,
                "class_name": self.class_name,
                "url": self.url,
                "enable_graphql": self.enable_graphql,
                "enable_multi_modal": self.enable_multi_modal,
                "features": {
                    "metadata_filtering": self.enable_metadata_filtering,
                    "semantic_chunking": self.enable_semantic_chunking,
                    "hybrid_search": self.enable_hybrid_search,
                    "reranking": self.enable_reranking,
                },
                "performance": {
                    "batch_size": self.batch_size,
                    "max_retries": self.max_retries,
                    "timeout": self.timeout,
                },
                "schema_info": schema_info,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "store_type": "weaviate",
                "error": str(e),
            }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the Weaviate vector store.

        Returns:
            Dict[str, Any]: Store statistics including document count, schema info,
                and performance metrics.
        """
        try:
            doc_count = self.get_document_count()
            schema_info = await self._get_schema_info()

            return {
                "store_type": "weaviate",
                "document_count": doc_count,
                "embedding_dimension": self.embedding_dimension,
                "similarity_metric": self.similarity_metric,
                "normalize_embeddings": self.normalize_embeddings,
                "class_name": self.class_name,
                "url": self.url,
                "enable_graphql": self.enable_graphql,
                "enable_multi_modal": self.enable_multi_modal,
                "features": {
                    "metadata_filtering": self.enable_metadata_filtering,
                    "semantic_chunking": self.enable_semantic_chunking,
                    "hybrid_search": self.enable_hybrid_search,
                    "reranking": self.enable_reranking,
                },
                "performance": {
                    "batch_size": self.batch_size,
                    "max_retries": self.max_retries,
                    "timeout": self.timeout,
                },
                "schema_info": schema_info,
            }
        except Exception as e:
            logger.error(f"Error getting Weaviate store stats: {e}")
            return {
                "store_type": "weaviate",
                "error": str(e),
            }

    def get_store_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about this Weaviate store instance.

        Returns:
            Dict[str, Any]: Store information including capabilities and configuration.
        """
        try:
            doc_count = self.get_document_count()
            return {
                "store_type": "weaviate",
                "embedding_dimension": self.embedding_dimension,
                "similarity_metric": self.similarity_metric,
                "normalize_embeddings": self.normalize_embeddings,
                "document_count": doc_count,
                "class_name": self.class_name,
                "url": self.url,
                "enable_graphql": self.enable_graphql,
                "enable_multi_modal": self.enable_multi_modal,
                "features": {
                    "metadata_filtering": self.enable_metadata_filtering,
                    "semantic_chunking": self.enable_semantic_chunking,
                    "hybrid_search": self.enable_hybrid_search,
                    "reranking": self.enable_reranking,
                },
            }
        except Exception as e:
            logger.error(f"Error getting Weaviate store info: {e}")
            return {
                "store_type": "weaviate",
                "error": str(e),
            }

    async def _get_schema_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the Weaviate schema.

        Returns:
            Dict[str, Any]: Schema information including class details.
        """
        try:

            def _get_info():
                return {
                    "class_name": self.class_name,
                    "exists": self.client.schema.exists(self.class_name),
                    "schema": self.client.schema.get(self.class_name)
                    if self.client.schema.exists(self.class_name)
                    else None,
                }

            return await self._to_thread(_get_info)
        except Exception as e:
            logger.error(f"Error getting schema info: {e}")
            return {"error": str(e)}

    # Advanced methods implementation
    async def add_chunks(self, chunks: List[Any], **kwargs: Any) -> List[str]:
        """
        Add text chunks with semantic metadata to Weaviate store.

        Args:
            chunks: List of text chunks to add
            **kwargs: Additional options including embeddings

        Returns:
            List[str]: List of chunk IDs that were added
        """
        # Convert chunks to VectorDocuments
        documents = []
        for i, chunk in enumerate(chunks):
            # Extract content and metadata from chunk
            content = getattr(chunk, "content", str(chunk))
            metadata = getattr(chunk, "metadata", {}) or {}
            chunk_id = getattr(chunk, "chunk_id", f"chunk_{i}")

            # Generate embedding for chunk (this would be done by the embedder)
            embedding = kwargs.get("embeddings", {}).get(
                chunk_id, [0.0] * self.embedding_dimension
            )

            # Enhanced metadata for chunks
            enhanced_metadata = metadata.copy()
            enhanced_metadata.update(
                {
                    "chunk_type": "semantic_chunk",
                    "chunk_id": chunk_id,
                    "start_index": getattr(chunk, "start_index", 0),
                    "end_index": getattr(chunk, "end_index", len(content)),
                    "chunk_length": len(content),
                    "is_semantic": True,
                }
            )

            doc = VectorDocument(
                id=chunk_id,
                content=content,
                embedding=embedding,
                metadata=enhanced_metadata,
            )
            documents.append(doc)

        return await self.add_documents(documents, **kwargs)

    async def add_documents_from_loader(
        self, documents: List[Any], **kwargs: Any
    ) -> List[str]:
        """
        Add documents directly from loaders with rich metadata to Weaviate store.

        Args:
            documents: List of documents from loaders
            **kwargs: Additional options including embeddings

        Returns:
            List[str]: List of document IDs that were added
        """
        # Convert loader documents to VectorDocuments
        vector_docs = []
        for doc in documents:
            # Extract document information
            doc_id = getattr(doc, "id", f"doc_{len(vector_docs)}")
            content = getattr(doc, "content", "")
            metadata = getattr(doc, "metadata", {}) or {}

            # Generate embedding (this would be done by the embedder)
            embedding = kwargs.get("embeddings", {}).get(
                doc_id, [0.0] * self.embedding_dimension
            )

            # Enhanced metadata from loader
            enhanced_metadata = metadata.copy()
            enhanced_metadata.update(
                {
                    "loader_type": getattr(doc, "loader_type", "unknown"),
                    "source_type": getattr(doc, "source_type", "unknown"),
                    "mime_type": getattr(doc, "mime_type", "unknown"),
                    "language": getattr(doc, "language", "unknown"),
                    "page_count": getattr(doc, "page_count", 0),
                    "word_count": getattr(doc, "word_count", 0),
                    "character_count": getattr(doc, "character_count", 0),
                    "has_images": getattr(doc, "has_images", False),
                    "has_tables": getattr(doc, "has_tables", False),
                    "extracted_at": getattr(doc, "extracted_at", "unknown"),
                    "processing_time": getattr(doc, "processing_time", 0.0),
                }
            )

            vector_doc = VectorDocument(
                id=doc_id,
                content=content,
                embedding=embedding,
                metadata=enhanced_metadata,
            )
            vector_docs.append(vector_doc)

        return await self.add_documents(vector_docs, **kwargs)

    async def update_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        """
        Update existing documents in the Weaviate vector store.

        Args:
            documents: List of documents to update
            **kwargs: Additional options

        Returns:
            List[str]: List of document IDs that were updated
        """
        # Default implementation: delete and re-add
        document_ids = [doc.id for doc in documents]

        try:
            # Delete existing documents
            await self.delete_documents(document_ids, **kwargs)

            # Add updated documents
            updated_ids = await self.add_documents(documents, **kwargs)

            logger.info(f"Updated {len(documents)} documents in Weaviate store")
            return updated_ids

        except Exception as e:
            logger.error(f"Error updating documents in Weaviate store: {e}")
            raise

    async def get_document(self, document_id: str) -> Optional[VectorDocument]:
        """
        Get a specific document by ID from Weaviate store.

        Args:
            document_id: ID of the document to retrieve

        Returns:
            Optional[VectorDocument]: Document if found, None otherwise
        """
        try:
            documents = await self.get_documents([document_id])
            return documents[0] if documents else None
        except Exception as e:
            logger.error(
                f"Error getting document {document_id} from Weaviate store: {e}"
            )
            return None

    async def get_documents(self, document_ids: List[str]) -> List[VectorDocument]:
        """
        Get multiple documents by IDs from Weaviate store.

        Args:
            document_ids: List of document IDs to retrieve

        Returns:
            List[VectorDocument]: List of documents found
        """
        try:

            def _get_docs():
                documents = []
                for doc_id in document_ids:
                    result = (
                        self.client.query.get(
                            self.class_name, ["content", "metadata", "document_id"]
                        )
                        .with_where(
                            {
                                "path": ["document_id"],
                                "operator": "Equal",
                                "valueString": doc_id,
                            }
                        )
                        .do()
                    )

                    if result and "data" in result and "Get" in result["data"]:
                        items = result["data"]["Get"][self.class_name]
                        for item in items:
                            doc = VectorDocument(
                                id=item.get("document_id", ""),
                                content=item.get("content", ""),
                                embedding=[0.0] * self.embedding_dimension,
                                metadata=item.get("metadata", {}),
                            )
                            documents.append(doc)

                return documents

            return await self._to_thread(_get_docs)
        except Exception as e:
            logger.error(f"Error getting documents from Weaviate store: {e}")
            return []

    async def get_documents_by_metadata(
        self, metadata_filter: Dict[str, Any]
    ) -> List[VectorDocument]:
        """
        Get documents filtered by metadata from Weaviate store.

        Args:
            metadata_filter: Metadata filters to apply

        Returns:
            List[VectorDocument]: List of documents matching the filter
        """
        try:
            # Create a dummy embedding for search
            dummy_embedding = [0.0] * self.embedding_dimension

            # Search with metadata filter
            results = await self.search_with_metadata_filter(
                dummy_embedding, metadata_filter, top_k=1000
            )

            return results.documents

        except Exception as e:
            logger.error(
                f"Error getting documents by metadata from Weaviate store: {e}"
            )
            return []

    async def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Semantic search with similarity threshold in Weaviate store.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of top results
            similarity_threshold: Minimum similarity score
            **kwargs: Additional options

        Returns:
            SearchResult: Search results with similarity filtering
        """
        try:
            # Perform search
            results = await self.search(query_embedding, top_k=top_k * 2, **kwargs)

            # Filter by similarity threshold
            filtered_docs = [
                doc
                for doc in results.documents
                if doc.score and doc.score >= similarity_threshold
            ]

            # Limit to top_k
            filtered_docs = filtered_docs[:top_k]

            return SearchResult(
                documents=filtered_docs,
                query_embedding=query_embedding,
                total_results=len(filtered_docs),
                search_time=results.search_time,
            )

        except Exception as e:
            logger.error(f"Error in semantic search in Weaviate store: {e}")
            raise
