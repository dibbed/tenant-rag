"""
Qdrant vector store implementation.

Async-friendly wrapper around qdrant-client with metadata support.
"""

from __future__ import annotations

import asyncio
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
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchAny,
        MatchValue,
        PointStruct,
        Range,
        VectorParams,
    )

    QDRANT_AVAILABLE = True
except Exception:
    QDRANT_AVAILABLE = False


class QdrantVectorStore(BaseVectorStore):
    """Qdrant-based vector store implementation."""

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
        self.store_type_label = "qdrant"
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "qdrant-client not installed. Please install 'qdrant-client'."
            )

        store_cfg = getattr(settings, "store", object())
        self.url: str = kwargs.get(
            "url", getattr(store_cfg, "qdrant_url", "http://localhost:6333")
        )
        self.collection_name: str = kwargs.get(
            "collection_name", getattr(store_cfg, "qdrant_collection_name", "ragbot")
        )
        self.vector_size: int = int(
            kwargs.get(
                "vector_size",
                getattr(store_cfg, "qdrant_vector_size", self.embedding_dimension),
            )
        )
        default_qdrant_path = str(settings.store_path / "qdrant")
        self.path: Optional[str] = kwargs.get(
            "path", getattr(store_cfg, "qdrant_path", default_qdrant_path)
        )

        timeout = kwargs.get("timeout", getattr(store_cfg, "qdrant_timeout", 30))
        if self.path:
            self.client = QdrantClient(path=self.path, timeout=timeout)
        else:
            self.client = QdrantClient(url=self.url, timeout=timeout)
        # Ensure collection exists
        self._ensure_collection_exists()
        # Best-effort payload indexes for common metadata keys
        try:
            self._ensure_payload_indexes()
        except Exception:
            pass

        try:
            logger.info(
                "Qdrant store initialized",
                url=self.url,
                collection_name=self.collection_name,
                vector_size=self.vector_size,
            )
        except Exception:
            pass

    def get_store_type(self) -> str:
        """Get the store type identifier."""
        return "qdrant"

    async def _to_thread(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _distance(self):
        metric = str(self.similarity_metric).lower()
        if metric == "cosine":
            return Distance.COSINE
        if metric in ("l2", "euclidean"):
            return Distance.EUCLID
        return Distance.DOT

    def _ensure_collection_exists(self) -> None:
        try:
            cols = self.client.get_collections()
            names = [c.name for c in cols.collections]
            if self.collection_name not in names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size, distance=self._distance()
                    ),
                )
        except Exception as e:
            try:
                logger.error(f"Qdrant ensure collection failed: {e}")
            except Exception:
                pass
            raise

    def _ensure_payload_indexes(self) -> None:
        """Create payload indexes for frequently queried metadata keys (best-effort)."""
        try:
            # Prefer enum when available, fallback to string schema types
            try:
                from qdrant_client.models import PayloadSchemaType  # type: ignore
            except Exception:
                try:
                    from qdrant_client.http.models import (
                        PayloadSchemaType,  # type: ignore
                    )
                except Exception:
                    PayloadSchemaType = None  # type: ignore

            def _schema(t: str):
                if PayloadSchemaType is None:
                    return t
                # Map simple strings to enum
                mapping = {
                    "keyword": getattr(PayloadSchemaType, "KEYWORD", None),
                    "integer": getattr(PayloadSchemaType, "INTEGER", None),
                    "float": getattr(PayloadSchemaType, "FLOAT", None),
                }
                return mapping.get(t, t)

            # Create indexes on top-level duplicated keys for faster filtering
            idx_specs = [
                ("language", _schema("keyword")),
                ("source_type", _schema("keyword")),
                ("mime_type", _schema("keyword")),
                ("source", _schema("keyword")),
                ("document_id", _schema("keyword")),
                ("page", _schema("integer")),
                ("chunk_index", _schema("integer")),
                ("total_chunks", _schema("integer")),
                ("span_start", _schema("integer")),
                ("span_end", _schema("integer")),
            ]
            for field_name, field_schema in idx_specs:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=field_schema,
                    )
                except Exception:
                    # Ignore if already exists or unsupported
                    pass
        except Exception:
            return

    def _build_filter(
        self, metadata_filter: Optional[Dict[str, Any]] = None
    ) -> Optional[Filter]:
        if not metadata_filter:
            return None
        must: List[Any] = []
        must_not: List[Any] = []
        dup_set = {
            "language",
            "source_type",
            "mime_type",
            "source",
            "document_id",
            "page",
            "chunk_index",
            "total_chunks",
        }
        for k, v in metadata_filter.items():
            # Resolve key: prefer top-level duplicated keys; allow dotted paths; else nested under metadata.
            if k in dup_set:
                key = k
            elif "." in k:
                key = k
            else:
                key = f"metadata.{k}"
            if isinstance(v, dict):
                # Membership
                if "$in" in v:
                    must.append(FieldCondition(key=key, match=MatchAny(any=v["$in"])))  # type: ignore
                if "$nin" in v:
                    must_not.append(
                        FieldCondition(key=key, match=MatchAny(any=v["$nin"]))
                    )  # type: ignore
                # Range
                rng: Dict[str, Any] = {}
                if "$gte" in v:
                    rng["gte"] = v["$gte"]
                if "$gt" in v:
                    rng["gt"] = v["$gt"]
                if "$lte" in v:
                    rng["lte"] = v["$lte"]
                if "$lt" in v:
                    rng["lt"] = v["$lt"]
                if rng:
                    must.append(FieldCondition(key=key, range=Range(**rng)))  # type: ignore
                # Equality
                if "$eq" in v:
                    must.append(
                        FieldCondition(key=key, match=MatchValue(value=v["$eq"]))
                    )  # type: ignore
                if "$ne" in v:
                    must_not.append(
                        FieldCondition(key=key, match=MatchValue(value=v["$ne"]))
                    )  # type: ignore
            elif isinstance(v, list):
                must.append(FieldCondition(key=key, match=MatchAny(any=v)))  # type: ignore
            else:
                must.append(FieldCondition(key=key, match=MatchValue(value=v)))  # type: ignore
        return Filter(must=must, must_not=must_not) if (must or must_not) else None

    def _recreate_collection_with_size(self, size: int) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=size, distance=self._distance()),
        )
        self.vector_size = size

    @log_store_errors("add_documents")
    async def add_documents(
        self, documents: List[VectorDocument], **kwargs: Any
    ) -> List[str]:
        if not documents:
            return []
        # Validate / auto-adjust dimension for empty collection
        emb_len = None
        for d in documents:
            try:
                emb_len = len(d.embedding)
                break
            except Exception:
                continue
        if emb_len and emb_len != int(self.vector_size):
            # Check empty collection: if empty, recreate; otherwise error
            try:
                if self.get_document_count() == 0:
                    self._recreate_collection_with_size(int(emb_len))
                else:
                    raise ValueError(
                        f"Embedding dimension mismatch: store={self.vector_size}, given={emb_len}"
                    )
            except Exception:
                pass

        def _payload_for(d: VectorDocument) -> Dict[str, Any]:
            normalized_meta, duplicates = self._prepare_metadata(d.metadata or {})
            payload: Dict[str, Any] = {
                "content": d.content,
                "metadata": normalized_meta,
            }
            payload.update(duplicates)
            return payload

        points = [
            PointStruct(id=d.id, vector=d.embedding, payload=_payload_for(d))
            for d in documents
        ]

        started = time.time()

        def _upsert():
            # Auto-batch for large inserts
            batch_size = int(
                kwargs.get(
                    "batch_size",
                    getattr(
                        getattr(settings, "store", object()), "qdrant_batch_size", 1000
                    ),
                )
            )
            if batch_size <= 0:
                batch_size = len(points)
            for i in range(0, len(points), batch_size):
                chunk = points[i : i + batch_size]
                self.client.upsert(collection_name=self.collection_name, points=chunk)

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
        return [d.id for d in documents]

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
            embeddings = [[0.0] * int(self.vector_size) for _ in texts]
        normalized_meta = [
            self._prepare_metadata(m) for m in (metadata or [{} for _ in texts])
        ]
        docs: List[VectorDocument] = []
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
        return await self.add_documents(documents, **kwargs)

    @log_store_errors("delete_documents")
    async def delete_documents(
        self, document_ids: List[str], **kwargs: Any
    ) -> List[str]:
        if not document_ids:
            return []

        started = time.time()

        def _delete():
            self.client.delete(
                collection_name=self.collection_name, points_selector=document_ids
            )

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
        flt = self._build_filter(kwargs.get("filters"))

        started = time.time()

        def _search():
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=int(top_k),
                query_filter=flt,
            )

        res = await self._to_thread(_search)
        duration = time.time() - started
        docs: List[VectorDocument] = []
        for pt in res:
            try:
                content = (pt.payload or {}).get("content", "")
                metadata = (pt.payload or {}).get("metadata", {})
            except Exception:
                content, metadata = "", {}
            docs.append(
                VectorDocument(
                    id=str(pt.id),
                    content=content,
                    embedding=query_embedding,
                    metadata=metadata,
                    score=float(getattr(pt, "score", 0.0)),
                )
            )
        try:
            docs.sort(key=lambda d: d.score or 0.0, reverse=True)
        except Exception:
            pass
        # Optional threshold filtering
        thr = kwargs.get("similarity_threshold")
        if thr is not None:
            try:
                t = float(thr)
                docs = [d for d in docs if d.score is None or d.score >= t]
            except Exception:
                pass
        metrics_manager.record_vector_store_operation(
            operation="search",
            store_type=self.store_type_label,
            document_count=len(docs),
            success=True,
            duration=duration,
        )
        return SearchResult(
            documents=docs, query_embedding=query_embedding, total_results=len(docs)
        )

    @log_store_errors("query")
    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: Optional[float] = None,
    ) -> List[VectorDocument]:
        """Compatibility method returning list of documents with optional threshold."""
        res = await self.search(query_embedding, top_k=top_k)
        docs = list(res.documents)
        if similarity_threshold is not None:
            docs = [
                d for d in docs if d.score is None or d.score >= similarity_threshold
            ]
        try:
            docs.sort(key=lambda d: d.score or 0.0, reverse=True)
        except Exception:
            pass
        return docs

    @log_store_errors("get_document")
    async def get_document(self, document_id: str) -> Optional[VectorDocument]:
        def _retrieve():
            return self.client.retrieve(
                collection_name=self.collection_name, ids=[document_id]
            )

        pts = await self._to_thread(_retrieve)
        if not pts:
            return None
        pt = pts[0]
        try:
            payload = pt.payload or {}
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
        except Exception:
            content, metadata = "", {}
        return VectorDocument(
            id=str(pt.id), content=content, embedding=[], metadata=metadata
        )

    @log_store_errors("get_documents")
    async def get_documents(self, document_ids: List[str]) -> List[VectorDocument]:
        if not document_ids:
            return []

        def _retrieve():
            return self.client.retrieve(
                collection_name=self.collection_name, ids=document_ids
            )

        pts = await self._to_thread(_retrieve)
        out: List[VectorDocument] = []
        for pt in pts or []:
            try:
                payload = pt.payload or {}
                content = payload.get("content", "")
                metadata = payload.get("metadata", {})
            except Exception:
                content, metadata = "", {}
            out.append(
                VectorDocument(
                    id=str(pt.id), content=content, embedding=[], metadata=metadata
                )
            )
        return out

    def get_document_count(self) -> int:
        try:
            info = self.client.get_collection(self.collection_name)
            return int(getattr(info, "points_count", 0))
        except Exception:
            return 0

    @log_store_errors("clear")
    async def clear(self) -> None:
        started = time.time()

        def _clear():
            self.client.delete_collection(self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=self._distance()
                ),
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
        return None  # managed by Qdrant

    @log_store_errors("load")
    async def load(self, path: Optional[str] = None) -> None:
        return None  # managed by Qdrant

    def count(self) -> int:  # compatibility helper
        return self.get_document_count()

    async def health_check(self) -> Dict[str, Any]:  # type: ignore[override]
        try:
            _ = self.get_document_count()
            return {
                "status": "healthy",
                "store_type": "QdrantVectorStore",
                "test_successful": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "store_type": "QdrantVectorStore",
                "error": str(e),
                "test_successful": False,
            }

    # ---------- Advanced collection management ----------
    @log_store_errors("update_hnsw_config")
    async def update_hnsw_config(
        self,
        *,
        hnsw_m: Optional[int] = None,
        hnsw_ef_construct: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Attempt to update HNSW config in-place. Falls back to no-op if unsupported."""
        try:
            from qdrant_client.models import HnswConfigDiff  # type: ignore

            diff = HnswConfigDiff(m=hnsw_m, ef_construct=hnsw_ef_construct)
            self.client.update_collection(
                collection_name=self.collection_name, hnsw_config=diff
            )
            return {"status": "ok", "updated": True}
        except Exception:
            return {"status": "noop", "updated": False}

    @log_store_errors("recreate_collection")
    async def recreate_collection(
        self,
        *,
        hnsw_m: int = 16,
        hnsw_ef_construct: int = 200,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """Recreate the collection with new HNSW parameters (best-effort)."""
        docs: List[VectorDocument] = []
        async for d in self.iter_all_documents(batch_size=batch_size):  # type: ignore
            docs.append(d)
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        # Recreate
        try:
            from qdrant_client.models import HnswConfigDiff  # type: ignore

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=self._distance()
                ),
                hnsw_config=HnswConfigDiff(
                    m=int(hnsw_m), ef_construct=int(hnsw_ef_construct)
                ),
            )
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=self._distance()
                ),
            )
        await self.add_documents(docs, batch_size=batch_size)
        return {"status": "ok", "reinserted": len(docs)}

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
        sem_res = await self.search(query_embedding, top_k=top_k * 2)
        sem_docs = sem_res.documents
        q_words = set((query or "").lower().split())
        rescored: List[VectorDocument] = []
        for d in sem_docs:
            doc_words = set((d.content or "").lower().split())
            overlap = len(q_words & doc_words) / max(len(q_words) or 1, 1)
            score = (d.score or 0.0) * alpha + overlap * (1 - alpha)
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
        out = rescored[:top_k]
        if kwargs.get("enable_reranking", True) and out:
            try:
                out = self._simple_rerank(query, out)
            except Exception:
                pass
        return SearchResult(
            documents=out, query_embedding=query_embedding, total_results=len(out)
        )

    # --------- Optional iteration helpers for migration ---------
    async def iter_all_documents(self, batch_size: int = 1000):  # pragma: no cover
        offset = None
        while True:

            def _scroll(current_offset=offset):
                return self.client.scroll(
                    collection_name=self.collection_name,
                    with_payload=True,
                    with_vectors=True,
                    limit=batch_size,
                    offset=current_offset,
                )

            points, next_offset = await self._to_thread(_scroll)
            if not points:
                break
            for pt in points:
                try:
                    content = (pt.payload or {}).get("content", "")
                    metadata = (pt.payload or {}).get("metadata", {})
                except Exception:
                    content, metadata = "", {}
                yield VectorDocument(
                    id=str(pt.id),
                    content=content,
                    embedding=list(getattr(pt, "vector", []) or []),
                    metadata=metadata,
                )
            offset = next_offset

    # --------- Helpers ---------

    def _sanitize_metadata_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._sanitize_metadata_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._sanitize_metadata_value(v) for k, v in value.items()}
        return str(value)

    def _prepare_metadata(
        self, metadata: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        normalized: Dict[str, Any] = {}
        for key, value in metadata.items():
            normalized[key] = self._sanitize_metadata_value(value)

        span = normalized.get("span")
        if isinstance(span, dict):
            if "start" in span and "span_start" not in normalized:
                normalized["span_start"] = span["start"]
            if "end" in span and "span_end" not in normalized:
                normalized["span_end"] = span["end"]

        duplicates: Dict[str, Any] = {}
        for key in self._DUP_KEYS:
            if key in normalized:
                duplicates[key] = normalized[key]

        return normalized, duplicates

    async def _sync_metrics_size(self) -> None:
        try:
            size = await self._to_thread(lambda: self.get_document_count())
        except Exception:
            try:
                size = self.get_document_count()
            except Exception:
                return
        metrics_manager.update_vector_store_size(size, store_type=self.store_type_label)

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the Qdrant vector store.

        Returns:
            Dict[str, Any]: Store statistics including document count, collection info,
                and performance metrics.
        """
        try:
            doc_count = self.get_document_count()
            collection_info = await self._get_collection_info()

            return {
                "store_type": "qdrant",
                "document_count": doc_count,
                "embedding_dimension": self.embedding_dimension,
                "similarity_metric": self.similarity_metric,
                "normalize_embeddings": self.normalize_embeddings,
                "collection_name": self.collection_name,
                "url": self.url,
                "vector_size": self.vector_size,
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
            logger.error(f"Error getting Qdrant store stats: {e}")
            return {
                "store_type": "qdrant",
                "error": str(e),
            }

    def get_store_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about this Qdrant store instance.

        Returns:
            Dict[str, Any]: Store information including capabilities and configuration.
        """
        try:
            doc_count = self.get_document_count()
            return {
                "store_type": "qdrant",
                "embedding_dimension": self.embedding_dimension,
                "similarity_metric": self.similarity_metric,
                "normalize_embeddings": self.normalize_embeddings,
                "document_count": doc_count,
                "collection_name": self.collection_name,
                "url": self.url,
                "vector_size": self.vector_size,
                "features": {
                    "metadata_filtering": self.enable_metadata_filtering,
                    "semantic_chunking": self.enable_semantic_chunking,
                    "hybrid_search": self.enable_hybrid_search,
                    "reranking": self.enable_reranking,
                },
            }
        except Exception as e:
            logger.error(f"Error getting Qdrant store info: {e}")
            return {
                "store_type": "qdrant",
                "error": str(e),
            }

    async def _get_collection_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the Qdrant collection.

        Returns:
            Dict[str, Any]: Collection information including metadata and settings.
        """
        try:

            def _get_info():
                return {
                    "name": self.collection_name,
                    "count": self.client.count(self.collection_name).count,
                    "info": self.client.get_collection(self.collection_name),
                }

            return await self._to_thread(_get_info)
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}

    async def add_chunks(self, chunks: List[Any], **kwargs: Any) -> List[str]:
        """
        Add text chunks with semantic metadata to Qdrant store.

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
        Add documents directly from loaders with rich metadata to Qdrant store.

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
        Get documents filtered by metadata from Qdrant store.

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
            logger.error(f"Error getting documents by metadata from Qdrant store: {e}")
            return []

    async def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        **kwargs: Any,
    ) -> SearchResult:
        """
        Semantic search with similarity threshold in Qdrant store.

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
            logger.error(f"Error in semantic search in Qdrant store: {e}")
            raise
