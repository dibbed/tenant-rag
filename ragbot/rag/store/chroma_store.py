"""
Chroma vector store implementation.

Provides an async-friendly wrapper around chromadb PersistentClient with
SearchResult/VectorDocument compatibility and optional metadata filtering.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.store.base import (
    BaseVectorStore,
    SearchResult,
    VectorDocument,
    log_store_errors,
)

try:
    import chromadb  # type: ignore

    CHROMA_AVAILABLE = True
except Exception:
    CHROMA_AVAILABLE = False


class ChromaVectorStore(BaseVectorStore):
    """Chroma-based vector store with persistence and metadata support."""

    _DUP_KEYS = {
        "language",
        "source_type",
        "mime_type",
        "source",
        "document_id",
        "page",
        "chunk_index",
        "total_chunks",
        "span_start",
        "span_end",
        "file_name",
        "canonical_url",
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.store_type_label = "chroma"
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb not installed. Please install 'chromadb'.")

        store_cfg = getattr(settings, "store", object())
        default_chroma_path = str(settings.store_path / "chroma")
        self.persist_directory: str = kwargs.get(
            "persist_directory",
            getattr(store_cfg, "chroma_persist_directory", default_chroma_path),
        )
        self.collection_name: str = kwargs.get(
            "collection_name", getattr(store_cfg, "chroma_collection_name", "ragbot")
        )
        # Map to cosine|l2|ip
        self.distance_function: str = kwargs.get(
            "distance_function",
            getattr(store_cfg, "chroma_distance_function", "cosine"),
        )

        # Create client/collection (blocking)
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=chromadb.Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": self.distance_function,
                "ragbot_provider": "chroma",
            },
        )

        try:
            logger.info(
                "Chroma store initialized",
                collection_name=self.collection_name,
                persist_directory=self.persist_directory,
                distance_function=self.distance_function,
            )
        except Exception:
            pass

    def get_store_type(self) -> str:
        """Get the store type identifier."""
        return "chroma"

    # -------------- helpers --------------
    async def _to_thread(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _build_where_clause(
        self, metadata_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not metadata_filter:
            return {}
        if "$and" in metadata_filter or "$or" in metadata_filter:
            return metadata_filter

        where: Dict[str, Any] = {}
        for k, v in metadata_filter.items():
            if isinstance(v, dict):
                w: Dict[str, Any] = {}
                for op, val in v.items():
                    if op in {
                        "$eq",
                        "$ne",
                        "$gt",
                        "$gte",
                        "$lt",
                        "$lte",
                        "$in",
                        "$nin",
                        "$contains",
                        "$not_contains",
                    }:
                        w[op] = val
                if not w and ("$and" in v or "$or" in v):
                    # passthrough compound (rare)
                    where[k] = v
                elif w:
                    where[k] = w
            elif isinstance(v, list):
                where[k] = {"$in": v}
            else:
                where[k] = {"$eq": v}

        if len(where) > 1:
            return {"$and": [{k: v} for k, v in where.items()]}
        return where

    # -------------- interface --------------
    @log_store_errors("add_documents")
    async def add_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        if not documents:
            return []
        ids = [d.id for d in documents]
        texts = [d.content for d in documents]
        metadatas = [self._prepare_metadata(d.metadata or {}) for d in documents]
        embeddings = [d.embedding for d in documents]

        started = time.time()

        def _upsert():
            # chroma add/upsert are sync; auto-batch for large inserts
            batch_size = int(
                kwargs.get(
                    "batch_size",
                    getattr(
                        getattr(settings, "store", object()), "chroma_batch_size", 1000
                    ),
                )
            )
            if batch_size <= 0:
                batch_size = len(ids)
            for i in range(0, len(ids), batch_size):
                s_ids = ids[i : i + batch_size]
                s_txt = texts[i : i + batch_size]
                s_meta = metadatas[i : i + batch_size]
                s_emb = embeddings[i : i + batch_size]
                try:
                    self.collection.upsert(
                        ids=s_ids, documents=s_txt, metadatas=s_meta, embeddings=s_emb
                    )
                except Exception:
                    # fallback to add (older versions)
                    self.collection.add(
                        ids=s_ids, documents=s_txt, metadatas=s_meta, embeddings=s_emb
                    )

        await self._to_thread(_upsert)
        duration = time.time() - started
        metrics_manager.record_vector_store_operation(
            operation="add_documents",
            store_type=self.store_type_label,
            document_count=len(documents),
            success=True,
            duration=duration,
        )
        await self._sync_metrics_size()
        return ids

    @log_store_errors("add_texts")
    async def add_texts(
        self,
        texts: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        if not texts:
            return []
        if embeddings is None:
            # store without embeddings: Chroma can embed if client configured; we keep vectors explicit path
            embeddings = [[0.0] * int(self.embedding_dimension) for _ in texts]
        normalized_meta = [
            self._prepare_metadata(m) for m in (metadata or [{} for _ in texts])
        ]
        docs = []
        for i, t in enumerate(texts):
            doc_meta = normalized_meta[i] if i < len(normalized_meta) else {}
            emb = embeddings[i] if i < len(embeddings) else []
            docs.append(
                VectorDocument(
                    id=f"text_{hash(t)}_{i}",
                    content=t or "",
                    embedding=emb,
                    metadata=doc_meta,
                )
            )
        return await self.add_documents(docs)

    @log_store_errors("update_documents")
    async def update_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        # Upsert semantics
        return await self.add_documents(documents, **kwargs)

    @log_store_errors("delete_documents")
    async def delete_documents(
        self, document_ids: List[str], **kwargs: Any
    ) -> List[str]:
        if not document_ids:
            return []

        started = time.time()

        def _delete():
            self.collection.delete(ids=document_ids)

        await self._to_thread(_delete)
        duration = time.time() - started
        metrics_manager.record_vector_store_operation(
            operation="delete_documents",
            store_type=self.store_type_label,
            document_count=len(document_ids),
            success=True,
            duration=duration,
        )
        await self._sync_metrics_size()
        return document_ids

    @log_store_errors("search")
    async def search(
        self, query_embedding: List[float], top_k: int = 10, **kwargs: Any
    ) -> SearchResult:
        where = self._build_where_clause(kwargs.get("filters"))

        started = time.time()

        def _query():
            return self.collection.query(
                query_embeddings=[query_embedding],
                n_results=int(top_k),
                where=where or None,
                include=["documents", "metadatas", "distances"],
            )

        try:
            results = await self._to_thread(_query)
            duration = time.time() - started
            documents: List[VectorDocument] = []
            ids = results.get("ids") or [[]]
            docs = results.get("documents") or [[]]
            metas = results.get("metadatas") or [[]]
            dists = results.get("distances") or [[]]

            for doc_id, content, meta, dist in zip(ids[0], docs[0], metas[0], dists[0]):
                # Convert distance to similarity where higher is better
                if self.distance_function.lower() == "cosine":
                    score = 1.0 - float(dist)
                else:
                    score = -float(dist)
                documents.append(
                    VectorDocument(
                        id=str(doc_id),
                        content=content or "",
                        embedding=query_embedding,
                        metadata=meta or {},
                        score=score,
                    )
                )
            # Optional threshold filtering
            thr = kwargs.get("similarity_threshold")
            if thr is not None:
                try:
                    t = float(thr)
                    documents = [
                        d for d in documents if d.score is None or d.score >= t
                    ]
                except Exception:
                    pass
            # Sort by score desc
            try:
                documents.sort(key=lambda d: d.score or 0.0, reverse=True)
            except Exception:
                pass

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
                search_time=None,
            )
        except Exception as e:
            try:
                logger.error(f"Chroma search failed: {e}")
            except Exception:
                pass
            raise

    def _sanitize_metadata_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._sanitize_metadata_value(v) for v in value]
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _prepare_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        # Extract span if present before sanitization
        span = metadata.get("span")
        if isinstance(span, dict):
            if "start" in span:
                normalized["span_start"] = span["start"]
            if "end" in span:
                normalized["span_end"] = span["end"]

        for key, value in metadata.items():
            if key == "span" and isinstance(value, dict):
                continue  # already flattened into span_start / span_end
            normalized[key] = self._sanitize_metadata_value(value)

        for key in self._DUP_KEYS:
            if key in normalized:
                normalized.setdefault(key, normalized[key])

        return normalized

    @log_store_errors("get_document")
    async def get_document(self, document_id: str) -> Optional[VectorDocument]:
        def _get():
            # get by ids
            return self.collection.get(
                ids=[document_id],
                include=["documents", "metadatas", "embeddings"],
            )  # type: ignore

        try:
            res = await self._to_thread(_get)
            ids = res.get("ids") or []
            if not ids:
                return None
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            embs = res.get("embeddings") or []
            return VectorDocument(
                id=str(ids[0]),
                content=docs[0] if docs else "",
                embedding=embs[0] if embs is not None and len(embs) > 0 else [],
                metadata=metas[0] if metas else {},
            )
        except Exception:
            return None

    @log_store_errors("get_documents")
    async def get_documents(self, document_ids: List[str]) -> List[VectorDocument]:
        if not document_ids:
            return []

        def _get():
            return self.collection.get(
                ids=document_ids,
                include=["documents", "metadatas", "embeddings"],
            )  # type: ignore

        try:
            res = await self._to_thread(_get)
            ids = res.get("ids") or []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            embs = res.get("embeddings") or []
            out: List[VectorDocument] = []
            for i, doc_id in enumerate(ids):
                out.append(
                    VectorDocument(
                        id=str(doc_id),
                        content=docs[i] if i < len(docs) else "",
                        embedding=embs[i] if embs is not None and i < len(embs) else [],
                        metadata=metas[i] if metas and i < len(metas) else {},
                    )
                )
            return out
        except Exception:
            return []

    def get_document_count(self) -> int:
        try:
            return int(self.collection.count())  # type: ignore[attr-defined]
        except Exception:
            return 0

    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: Optional[float] = None,
    ) -> List[VectorDocument]:
        """Compatibility method: return list of VectorDocuments, optionally thresholded."""
        res = await self.search(query_embedding, top_k=top_k)
        docs = list(res.documents)
        if similarity_threshold is not None:
            docs = [
                d for d in docs if d.score is None or d.score >= similarity_threshold
            ]
        # ensure sorted
        try:
            docs.sort(key=lambda d: d.score or 0.0, reverse=True)
        except Exception:
            pass
        return docs

    @log_store_errors("clear")
    async def clear(self) -> None:
        started = time.time()

        def _clear():
            # drop and recreate
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": self.distance_function},
            )

        await self._to_thread(_clear)
        duration = time.time() - started
        metrics_manager.record_vector_store_operation(
            operation="clear",
            store_type=self.store_type_label,
            document_count=0,
            success=True,
            duration=duration,
        )
        await self._sync_metrics_size()

    @log_store_errors("save")
    async def save(self, path: Optional[str] = None) -> None:
        # Persistence handled by Chroma automatically
        return None

    @log_store_errors("load")
    async def load(self, path: Optional[str] = None) -> None:
        # Persistence handled by Chroma automatically
        return None

    def count(self) -> int:  # compatibility helper
        return self.get_document_count()

    async def health_check(self) -> Dict[str, Any]:  # type: ignore[override]
        """
        Perform comprehensive health check on the Chroma vector store.

        Returns:
            Dict[str, Any]: Health check results including store status, capabilities,
                and performance metrics.
        """
        try:
            doc_count = self.get_document_count()
            collection_info = await self._get_collection_info()

            return {
                "status": "healthy",
                "store_type": "chroma",
                "document_count": doc_count,
                "embedding_dimension": self.embedding_dimension,
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
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
                "collection_info": collection_info,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "store_type": "chroma",
                "error": str(e),
            }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the Chroma vector store.

        Returns:
            Dict[str, Any]: Store statistics including document count, collection info,
                and performance metrics.
        """
        try:
            doc_count = self.get_document_count()
            collection_info = await self._get_collection_info()

            return {
                "store_type": "chroma",
                "document_count": doc_count,
                "embedding_dimension": self.embedding_dimension,
                "similarity_metric": self.similarity_metric,
                "normalize_embeddings": self.normalize_embeddings,
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
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
                "collection_info": collection_info,
            }
        except Exception as e:
            logger.error(f"Error getting Chroma store stats: {e}")
            return {
                "store_type": "chroma",
                "error": str(e),
            }

    def get_store_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about this Chroma store instance.

        Returns:
            Dict[str, Any]: Store information including capabilities and configuration.
        """
        try:
            doc_count = self.get_document_count()
            return {
                "store_type": "chroma",
                "embedding_dimension": self.embedding_dimension,
                "similarity_metric": self.similarity_metric,
                "normalize_embeddings": self.normalize_embeddings,
                "document_count": doc_count,
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
                "features": {
                    "metadata_filtering": self.enable_metadata_filtering,
                    "semantic_chunking": self.enable_semantic_chunking,
                    "hybrid_search": self.enable_hybrid_search,
                    "reranking": self.enable_reranking,
                },
            }
        except Exception as e:
            logger.error(f"Error getting Chroma store info: {e}")
            return {
                "store_type": "chroma",
                "error": str(e),
            }

    async def _get_collection_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the Chroma collection.

        Returns:
            Dict[str, Any]: Collection information including metadata and settings.
        """
        try:

            def _get_info():
                return {
                    "name": self.collection_name,
                    "count": self.collection.count(),
                    "metadata": self.collection.metadata or {},
                }

            return await self._to_thread(_get_info)
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}

    async def add_chunks(self, chunks: List[Any], **kwargs: Any) -> List[str]:
        """
        Add text chunks with semantic metadata to Chroma store.

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
        Add documents directly from loaders with rich metadata to Chroma store.

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

    async def get_documents_by_metadata(
        self, metadata_filter: Dict[str, Any]
    ) -> List[VectorDocument]:
        """
        Get documents filtered by metadata from Chroma store.

        Args:
            metadata_filter: Metadata filters to apply

        Returns:
            List[VectorDocument]: List of documents matching the filter
        """
        try:
            # Convert metadata filter to Chroma where clause
            where = self._build_where_clause(metadata_filter)

            def _get():
                return self.collection.get(
                    where=where, include=["documents", "metadatas"]
                )

            results = await self._to_thread(_get)

            documents: List[VectorDocument] = []
            ids = results.get("ids", [])
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])

            for doc_id, content, meta in zip(ids, docs, metas):
                documents.append(
                    VectorDocument(
                        id=str(doc_id),
                        content=content or "",
                        embedding=[],  # No embedding needed for metadata-only retrieval
                        metadata=meta or {},
                    )
                )

            return documents

        except Exception as e:
            logger.error(f"Error getting documents by metadata from Chroma store: {e}")
            return []

    async def search_with_metadata_filter(
        self,
        query_embedding: List[float],
        metadata_filter: Dict[str, Any],
        top_k: int = 10,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Search with metadata filtering using Chroma's native where clause.

        Args:
            query_embedding: Query vector embedding
            metadata_filter: Metadata filters to apply
            top_k: Number of top results

        Returns:
            SearchResult: Search results with matching documents
        """
        # Use the regular search method with filters
        return await self.search(
            query_embedding, top_k, filters=metadata_filter, **kwargs
        )

    async def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Perform semantic search with similarity threshold filtering.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of top results
            similarity_threshold: Minimum similarity score
            **kwargs: Additional options

        Returns:
            SearchResult: Filtered search results
        """
        try:
            # Perform regular search with higher top_k to account for filtering
            results = await self.search(query_embedding, top_k=top_k * 2, **kwargs)

            # Filter by similarity threshold
            filtered_docs = []
            for doc in results.documents:
                if doc.score is None or doc.score >= similarity_threshold:
                    filtered_docs.append(doc)

            # Sort by score and limit to top_k
            filtered_docs.sort(key=lambda d: d.score or 0.0, reverse=True)
            filtered_docs = filtered_docs[:top_k]

            return SearchResult(
                documents=filtered_docs,
                query_embedding=query_embedding,
                total_results=len(filtered_docs),
                search_time=results.search_time,
            )

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return SearchResult(
                documents=[],
                query_embedding=query_embedding,
                total_results=0,
                search_time=0.0,
            )

    # ---------- Hybrid search & reranking ----------
    def _extract_keywords(self, query: str) -> List[str]:
        q = (query or "").strip().lower()
        words = [w for w in q.replace("\n", " ").split(" ") if len(w) > 2]
        seen: Dict[str, None] = {}
        out: List[str] = []
        for w in words:
            if w not in seen:
                seen[w] = None
                out.append(w)
        return out[:16]

    async def _keyword_search(
        self, query: str, top_k: int = 20
    ) -> List[VectorDocument]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        id_scores: Dict[str, float] = {}
        id_meta: Dict[str, Dict[str, Any]] = {}
        id_doc: Dict[str, str] = {}
        for kw in keywords[:8]:
            try:
                res = await self._to_thread(
                    lambda keyword=kw: self.collection.query(
                        query_texts=[keyword],
                        n_results=top_k,
                        where_document={"$contains": keyword},
                        include=["documents", "metadatas"],
                    )
                )
            except Exception:
                continue
            ids = res.get("ids") or [[]]
            docs = res.get("documents") or [[]]
            metas = res.get("metadatas") or [[]]
            for i, doc_id in enumerate(ids[0]):
                id_scores[doc_id] = id_scores.get(doc_id, 0.0) + 1.0
                if i < len(metas[0]):
                    id_meta[doc_id] = metas[0][i] or {}
                if i < len(docs[0]):
                    id_doc[doc_id] = docs[0][i] or ""
        if not id_scores:
            return []
        max_score = max(id_scores.values()) or 1.0
        results: List[VectorDocument] = []
        for doc_id, sc in id_scores.items():
            results.append(
                VectorDocument(
                    id=str(doc_id),
                    content=id_doc.get(doc_id, ""),
                    embedding=[],
                    metadata=id_meta.get(doc_id, {}),
                    score=float(sc / max_score),
                )
            )
        results.sort(key=lambda d: d.score or 0.0, reverse=True)
        return results[:top_k]

    def _combine_semantic_keyword(
        self,
        semantic: List[VectorDocument],
        keyword: List[VectorDocument],
        alpha: float = 0.7,
        top_k: int = 10,
    ) -> List[VectorDocument]:
        combined: Dict[str, VectorDocument] = {}
        kw_map = {d.id: d for d in keyword}
        for d in semantic:
            kw_score = kw_map.get(d.id).score if d.id in kw_map else 0.0
            combined[d.id] = VectorDocument(
                id=d.id,
                content=d.content,
                embedding=d.embedding,
                metadata=d.metadata,
                score=(d.score or 0.0) * alpha + (kw_score or 0.0) * (1 - alpha),
            )
        for d in keyword:
            if d.id not in combined:
                combined[d.id] = VectorDocument(
                    id=d.id,
                    content=d.content,
                    embedding=d.embedding,
                    metadata=d.metadata,
                    score=(d.score or 0.0) * (1 - alpha),
                )
        out = list(combined.values())
        out.sort(key=lambda x: x.score or 0.0, reverse=True)
        return out[:top_k]

    def _simple_rerank(
        self, query: str, documents: List[VectorDocument]
    ) -> List[VectorDocument]:
        q_words = set((query or "").lower().split())
        rescored: List[VectorDocument] = []
        for d in documents:
            doc_words = set((d.content or "").lower().split())
            overlap = len(q_words & doc_words) / max(len(q_words) or 1, 1)
            score = (d.score or 0.0) * 0.8 + overlap * 0.2
            rescored.append(
                VectorDocument(
                    id=d.id,
                    content=d.content,
                    embedding=d.embedding,
                    metadata=d.metadata,
                    score=score,
                )
            )
        rescored.sort(key=lambda x: x.score or 0.0, reverse=True)
        return rescored

    @log_store_errors("hybrid_search")
    async def hybrid_search(
        self,
        query: str,
        query_embedding: List[float],
        alpha: float = 0.7,
        top_k: int = 10,
        **kwargs: Any,
    ) -> SearchResult:
        sem = await self.search(query_embedding, top_k=top_k * 2, **kwargs)
        kw = await self._keyword_search(query, top_k=top_k * 2)
        combined = self._combine_semantic_keyword(
            sem.documents, kw, alpha=alpha, top_k=top_k
        )
        if kwargs.get("enable_reranking", True) and combined:
            try:
                combined = self._simple_rerank(query, combined)
            except Exception:
                pass
        return SearchResult(
            documents=combined,
            query_embedding=query_embedding,
            total_results=len(combined),
        )

    # ---------- Advanced collection management ----------
    @log_store_errors("recreate_collection")
    async def recreate_collection(
        self,
        *,
        hnsw_construction_ef: int = 200,
        hnsw_search_ef: int = 50,
        hnsw_m: int = 16,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """Recreate collection with new HNSW parameters (best-effort)."""
        docs: List[VectorDocument] = []
        async for d in self.iter_all_documents(batch_size=batch_size):  # type: ignore
            docs.append(d)
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": self.distance_function,
                "hnsw:construction_ef": int(hnsw_construction_ef),
                "hnsw:search_ef": int(hnsw_search_ef),
                "hnsw:M": int(hnsw_m),
            },
        )
        await self.add_documents(docs, batch_size=batch_size)
        return {"status": "ok", "reinserted": len(docs)}

    async def _sync_metrics_size(self) -> None:
        try:
            size = await self._to_thread(lambda: self.get_document_count())
        except Exception:
            try:
                size = self.get_document_count()
            except Exception:
                return
        metrics_manager.update_vector_store_size(size, store_type=self.store_type_label)

    # --------- Optional iteration helpers for migration ---------
    async def iter_all_documents(self, batch_size: int = 1000):  # pragma: no cover
        """Yield all documents in batches (best-effort)."""
        offset = 0
        while True:

            def _get(current_offset=offset):
                return self.collection.get(  # type: ignore
                    include=["documents", "metadatas", "embeddings"],
                    limit=batch_size,
                    offset=current_offset,
                )

            res = await self._to_thread(_get)
            ids = res.get("ids") or []
            if not ids:
                break
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            embs = res.get("embeddings") or []
            for i, doc_id in enumerate(ids):
                yield VectorDocument(
                    id=str(doc_id),
                    content=docs[i] if i < len(docs) else "",
                    embedding=embs[i] if embs is not None and i < len(embs) else [],
                    metadata=metas[i] if metas and i < len(metas) else {},
                )
            offset += len(ids)
