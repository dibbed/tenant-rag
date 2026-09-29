"""
Qdrant vector store implementation.

Async-friendly wrapper around qdrant-client with metadata support.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.store.base import (
    BaseVectorStore,
    SearchResult,
    VectorDocument,
    log_store_errors,
)

T = TypeVar("T")


try:
    from qdrant_client import QdrantClient
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

    _DUP_KEYS: ClassVar[set[str]] = {
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

    @staticmethod
    def _to_qdrant_id(doc_id: Any) -> str:
        s = str(doc_id)
        try:
            return str(uuid.UUID(s))
        except Exception:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, s))

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
        self.path: str | None = kwargs.get(
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
        with contextlib.suppress(Exception):
            self._ensure_payload_indexes()

        with contextlib.suppress(Exception):
            logger.info(
                "Qdrant store initialized",
                url=self.url,
                collection_name=self.collection_name,
                vector_size=self.vector_size,
            )

    def get_store_type(self) -> str:
        """Get the store type identifier."""
        return "qdrant"

    async def _to_thread(
        self, fn: Callable[..., T], *args: Any, **kwargs: Any
    ) -> T:
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _distance(self) -> Distance:
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
            with contextlib.suppress(Exception):
                logger.error(f"Qdrant ensure collection failed: {e}")
            raise

    def _ensure_payload_indexes(self) -> None:
        """Create payload indexes for frequently queried metadata keys (best-effort)."""
        try:
            # Prefer enum when available, fallback to string schema types
            payload_schema_type: Any = None
            try:
                from qdrant_client.models import PayloadSchemaType as _PayloadSchemaType

                payload_schema_type = _PayloadSchemaType
            except Exception:
                try:
                    from qdrant_client.http.models import (
                        PayloadSchemaType as _PayloadSchemaType,
                    )

                    payload_schema_type = _PayloadSchemaType
                except Exception:
                    pass

            def _schema(t: str) -> Any:
                if payload_schema_type is None:
                    return t
                # Map simple strings to enum
                mapping = {
                    "keyword": getattr(payload_schema_type, "KEYWORD", None),
                    "integer": getattr(payload_schema_type, "INTEGER", None),
                    "float": getattr(payload_schema_type, "FLOAT", None),
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
                # Ignore if the index already exists or is unsupported.
                with contextlib.suppress(Exception):
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name=field_name,
                        field_schema=field_schema,
                    )
        except Exception:
            return

    def _build_filter(
        self, metadata_filter: dict[str, Any] | None = None
    ) -> Filter | None:
        if not metadata_filter:
            return None
        must: list[Any] = []
        must_not: list[Any] = []
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
            key = k if k in dup_set or "." in k else f"metadata.{k}"
            if isinstance(v, dict):
                # Membership
                if "$in" in v:
                    must.append(FieldCondition(key=key, match=MatchAny(any=v["$in"])))
                if "$nin" in v:
                    must_not.append(
                        FieldCondition(key=key, match=MatchAny(any=v["$nin"]))
                    )
                # Range
                rng: dict[str, Any] = {}
                if "$gte" in v:
                    rng["gte"] = v["$gte"]
                if "$gt" in v:
                    rng["gt"] = v["$gt"]
                if "$lte" in v:
                    rng["lte"] = v["$lte"]
                if "$lt" in v:
                    rng["lt"] = v["$lt"]
                if rng:
                    must.append(FieldCondition(key=key, range=Range(**rng)))
                # Equality
                if "$eq" in v:
                    must.append(
                        FieldCondition(key=key, match=MatchValue(value=v["$eq"]))
                    )
                if "$ne" in v:
                    must_not.append(
                        FieldCondition(key=key, match=MatchValue(value=v["$ne"]))
                    )
            elif isinstance(v, list):
                must.append(FieldCondition(key=key, match=MatchAny(any=v)))
            else:
                must.append(FieldCondition(key=key, match=MatchValue(value=v)))
        return Filter(must=must, must_not=must_not) if (must or must_not) else None

    def _recreate_collection_with_size(self, size: int) -> None:
        with contextlib.suppress(Exception):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=size, distance=self._distance()),
        )
        self.vector_size = size

    @log_store_errors("add_documents")
    async def add_documents(
        self, documents: list[VectorDocument], **kwargs: Any
    ) -> list[str]:
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

        def _payload_for(d: VectorDocument) -> dict[str, Any]:
            normalized_meta, duplicates = self._prepare_metadata(d.metadata or {})
            payload: dict[str, Any] = {
                "content": d.content,
                "metadata": normalized_meta,
                "_doc_id": d.id,
            }
            payload.update(duplicates)
            return payload

        points = [
            PointStruct(
                id=self._to_qdrant_id(d.id),
                vector=d.embedding,
                payload=_payload_for(d),
            )
            for d in documents
        ]

        started = time.time()

        def _upsert() -> None:
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
        texts: list[str],
        embeddings: list[list[float]] | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        if not texts:
            return []
        if embeddings is None:
            embeddings = [[0.0] * int(self.vector_size) for _ in texts]
        normalized_meta = [
            self._prepare_metadata(m)[0] for m in (metadata or [{} for _ in texts])
        ]
        docs: list[VectorDocument] = []
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
        self, documents: list[VectorDocument], **kwargs: Any
    ) -> list[str]:
        return await self.add_documents(documents, **kwargs)

    @log_store_errors("delete_documents")
    async def delete_documents(
        self, document_ids: list[str], **kwargs: Any
    ) -> list[str]:
        if not document_ids:
            return []

        started = time.time()

        def _delete() -> None:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[self._to_qdrant_id(i) for i in document_ids],
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
        self, query_embedding: list[float], top_k: int = 10, **kwargs: Any
    ) -> SearchResult:
        flt = self._build_filter(kwargs.get("filters"))

        started = time.time()

        def _search() -> Any:
            if hasattr(self.client, "search"):
                return self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=int(top_k),
                    query_filter=flt,
                )
            resp = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=int(top_k),
                query_filter=flt,
            )
            return getattr(resp, "points", resp)

        res = await self._to_thread(_search)
        duration = time.time() - started
        docs: list[VectorDocument] = []
        for pt in res:
            try:
                payload = pt.payload or {}
                content = payload.get("content", "")
                metadata = payload.get("metadata", {})
                doc_id = payload.get("_doc_id", str(pt.id))
            except Exception:
                content, metadata, doc_id = "", {}, str(pt.id)
            docs.append(
                VectorDocument(
                    id=doc_id,
                    content=content,
                    embedding=query_embedding,
                    metadata=metadata,
                    score=float(getattr(pt, "score", 0.0)),
                )
            )
        with contextlib.suppress(Exception):
            docs.sort(key=lambda d: d.score or 0.0, reverse=True)
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
        query_embedding: list[float],
        top_k: int = 10,
        similarity_threshold: float | None = None,
    ) -> list[VectorDocument]:
        """Compatibility method returning list of documents with optional threshold."""
        res = await self.search(query_embedding, top_k=top_k)
        docs = list(res.documents)
        if similarity_threshold is not None:
            docs = [
                d for d in docs if d.score is None or d.score >= similarity_threshold
            ]
        with contextlib.suppress(Exception):
            docs.sort(key=lambda d: d.score or 0.0, reverse=True)
        return docs

    @log_store_errors("get_document")
    async def get_document(self, document_id: str) -> VectorDocument | None:
        def _retrieve() -> Any:
            return self.client.retrieve(
                collection_name=self.collection_name, ids=[self._to_qdrant_id(document_id)]
            )

        pts = await self._to_thread(_retrieve)
        if not pts:
            return None
        pt = pts[0]
        try:
            payload = pt.payload or {}
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
            doc_id = payload.get("_doc_id", str(pt.id))
        except Exception:
            content, metadata, doc_id = "", {}, str(pt.id)
        return VectorDocument(
            id=doc_id, content=content, embedding=[], metadata=metadata
        )

    @log_store_errors("get_documents")
    async def get_documents(self, document_ids: list[str]) -> list[VectorDocument]:
        if not document_ids:
            return []

        def _retrieve() -> Any:
            return self.client.retrieve(
                collection_name=self.collection_name,
                ids=[self._to_qdrant_id(i) for i in document_ids],
            )

        pts = await self._to_thread(_retrieve)
        out: list[VectorDocument] = []
        for pt in pts or []:
            try:
                payload = pt.payload or {}
                content = payload.get("content", "")
                metadata = payload.get("metadata", {})
                doc_id = payload.get("_doc_id", str(pt.id))
            except Exception:
                content, metadata, doc_id = "", {}, str(pt.id)
            out.append(
                VectorDocument(
                    id=doc_id, content=content, embedding=[], metadata=metadata
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

        def _clear() -> None:
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
    async def save(self, path: str | None = None) -> None:
        return None  # managed by Qdrant

    @log_store_errors("load")
    async def load(self, path: str | None = None) -> None:
        return None  # managed by Qdrant

    def count(self) -> int:  # compatibility helper
        return self.get_document_count()

    async def health_check(self) -> dict[str, Any]:
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
        hnsw_m: int | None = None,
        hnsw_ef_construct: int | None = None,
    ) -> dict[str, Any]:
        """Attempt to update HNSW config in-place. Falls back to no-op if unsupported."""
        try:
            from qdrant_client.models import HnswConfigDiff

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
    ) -> dict[str, Any]:
        """Recreate the collection with new HNSW parameters (best-effort)."""
        docs: list[VectorDocument] = [
            d async for d in self.iter_all_documents(batch_size=batch_size)
        ]
        with contextlib.suppress(Exception):
            self.client.delete_collection(self.collection_name)
        # Recreate
        try:
            from qdrant_client.models import HnswConfigDiff

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
    def _extract_keywords(self, query: str) -> list[str]:
        q = (query or "").strip().lower()
        words = [w for w in q.replace("\n", " ").split(" ") if len(w) > 2]
        seen: dict[str, None] = {}
        out: list[str] = []
        for w in words:
            if w not in seen:
                seen[w] = None
                out.append(w)
        return out[:16]

    def _simple_rerank(
        self, query: str, documents: list[VectorDocument]
    ) -> list[VectorDocument]:
        q_words = set((query or "").lower().split())
        rescored: list[VectorDocument] = []
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
        query_embedding: list[float],
        alpha: float = 0.7,
        top_k: int = 10,
        **kwargs: Any,
    ) -> SearchResult:
        sem_res = await self.search(query_embedding, top_k=top_k * 2)
        sem_docs = sem_res.documents
        q_words = set((query or "").lower().split())
        rescored: list[VectorDocument] = []
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
            with contextlib.suppress(Exception):
                out = self._simple_rerank(query, out)
        return SearchResult(
            documents=out, query_embedding=query_embedding, total_results=len(out)
        )

    # --------- Optional iteration helpers for migration ---------
    async def iter_all_documents(
        self, batch_size: int = 1000
    ) -> AsyncIterator[VectorDocument]:  # pragma: no cover
        offset = None
        while True:

            def _scroll(current_offset: Any = offset) -> Any:
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
        if isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, list):
            return [self._sanitize_metadata_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._sanitize_metadata_value(v) for k, v in value.items()}
        return str(value)

    def _prepare_metadata(
        self, metadata: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        normalized: dict[str, Any] = {}
        for key, value in metadata.items():
            normalized[key] = self._sanitize_metadata_value(value)

        span = normalized.get("span")
        if isinstance(span, dict):
            if "start" in span and "span_start" not in normalized:
                normalized["span_start"] = span["start"]
            if "end" in span and "span_end" not in normalized:
                normalized["span_end"] = span["end"]

        duplicates: dict[str, Any] = {}
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

    async def get_stats(self) -> dict[str, Any]:
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

    def get_store_info(self) -> dict[str, Any]:
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

    async def _get_collection_info(self) -> dict[str, Any]:
        """
        Get detailed information about the Qdrant collection.

        Returns:
            Dict[str, Any]: Collection information including metadata and settings.
        """
        try:

            def _get_info() -> dict[str, Any]:
                return {
                    "name": self.collection_name,
                    "count": self.client.count(self.collection_name).count,
                    "info": self.client.get_collection(self.collection_name),
                }

            return await self._to_thread(_get_info)
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}

    async def add_chunks(self, chunks: list[Any], **kwargs: Any) -> list[str]:
        """
        Add text chunks with semantic metadata to Qdrant store.

        Args:
            chunks: List of text chunks to add
            **kwargs: Additional options including embeddings

        Returns:
            List[str]: List of chunk IDs that were added
        """
        # Convert chunks to VectorDocuments
        documents: list[VectorDocument] = []
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
        self, documents: list[Any], **kwargs: Any
    ) -> list[str]:
        """
        Add documents directly from loaders with rich metadata to Qdrant store.

        Args:
            documents: List of documents from loaders
            **kwargs: Additional options including embeddings

        Returns:
            List[str]: List of document IDs that were added
        """
        # Convert loader documents to VectorDocuments
        vector_docs: list[VectorDocument] = []
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
        self, metadata_filter: dict[str, Any]
    ) -> list[VectorDocument]:
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
        query_embedding: list[float],
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
