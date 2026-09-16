"""
Vector store migration utilities.

Supports migrating documents between providers via store-specific iteration
helpers when available. Falls back gracefully when full export is not possible.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional

from ragbot.outputs.logger import logger
from ragbot.rag import BaseVectorStore, VectorDocument, VectorStoreFactory
from ragbot.configs.settings import settings


async def _iter_docs_generic(store: BaseVectorStore) -> AsyncIterator[VectorDocument]:
    # Prefer store-specific iterators
    if hasattr(store, "iter_all_documents") and callable(
        getattr(store, "iter_all_documents")
    ):
        async for d in store.iter_all_documents():  # type: ignore[attr-defined]
            yield d
        return

    # FAISS fallback (in-memory store) introspection
    docs = getattr(store, "documents", None)
    if isinstance(docs, dict):
        for d in docs.values():
            if isinstance(d, VectorDocument):
                yield d
        return

    # Last resort: attempt sampling via count and bail
    count = 0
    try:
        count = int(store.get_document_count())
    except Exception:
        pass
    if count == 0:
        return
    raise NotImplementedError(
        "Source store does not support full iteration of documents"
    )


async def migrate_stores(
    source_type: str,
    target_type: str,
    *,
    batch_size: int = 500,
    source_kwargs: Optional[Dict[str, Any]] = None,
    target_kwargs: Optional[Dict[str, Any]] = None,
    rollback_on_failure: bool = False,
    progress_cb: Optional[Any] = None,
) -> Dict[str, Any]:
    """Migrate documents from one store to another.

    Returns a summary dict.
    """
    source_kwargs = source_kwargs or {}
    target_kwargs = target_kwargs or {}

    src = VectorStoreFactory.create_store(source_type, **source_kwargs)
    tgt = VectorStoreFactory.create_store(target_type, **target_kwargs)

    migrated = 0
    failed = 0
    total = 0
    batch: List[VectorDocument] = []
    migrated_ids: List[str] = []

    # Try to estimate total for progress
    try:
        total = int(src.get_document_count())
    except Exception:
        total = 0

    try:
        async for doc in _iter_docs_generic(src):
            batch.append(doc)
            if len(batch) >= batch_size:
                try:
                    added = await tgt.add_documents(batch)
                    migrated += len(batch)
                    if isinstance(added, list):
                        migrated_ids.extend(added)
                except Exception as e:
                    failed += len(batch)
                    try:
                        logger.error(f"Migration batch failed: {e}")
                    except Exception:
                        pass
                    # Rollback previously migrated docs if requested
                    if rollback_on_failure and migrated_ids:
                        try:
                            await tgt.delete_documents(migrated_ids)
                            logger.warning(
                                "Rollback completed after failure",
                                count=len(migrated_ids),
                            )
                        except Exception as rb:
                            logger.error(f"Rollback failed: {rb}")
                        return {
                            "status": "rolled_back",
                            "migrated": migrated,
                            "failed": failed,
                            "rolled_back": len(migrated_ids),
                        }
                batch = []
                # Progress callback after each batch
                if callable(progress_cb):
                    try:
                        progress_cb(
                            {
                                "migrated": migrated,
                                "failed": failed,
                                "total": total,
                                "phase": "migrating",
                            }
                        )
                    except Exception:
                        pass
        if batch:
            try:
                added = await tgt.add_documents(batch)
                migrated += len(batch)
                if isinstance(added, list):
                    migrated_ids.extend(added)
            except Exception as e:
                failed += len(batch)
                try:
                    logger.error(f"Migration batch failed: {e}")
                except Exception:
                    pass
                if rollback_on_failure and migrated_ids:
                    try:
                        await tgt.delete_documents(migrated_ids)
                        logger.warning(
                            "Rollback completed after failure", count=len(migrated_ids)
                        )
                    except Exception as rb:
                        logger.error(f"Rollback failed: {rb}")
                    return {
                        "status": "rolled_back",
                        "migrated": migrated,
                        "failed": failed,
                        "rolled_back": len(migrated_ids),
                    }
        # Final progress callback
        if callable(progress_cb):
            try:
                progress_cb(
                    {
                        "migrated": migrated,
                        "failed": failed,
                        "total": total,
                        "phase": "completed",
                    }
                )
            except Exception:
                pass
    except NotImplementedError as e:
        return {
            "status": "unsupported",
            "error": str(e),
            "migrated": migrated,
            "failed": failed,
        }

    return {
        "status": "ok",
        "migrated": migrated,
        "failed": failed,
        "target_count": tgt.get_document_count(),
        "rolled_back": 0,
    }


async def verify_migration(
    source_type: str,
    target_type: str,
    *,
    source_kwargs: Optional[Dict[str, Any]] = None,
    target_kwargs: Optional[Dict[str, Any]] = None,
    sample_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Verify migration by comparing counts and sampling a few IDs if provided."""
    source_kwargs = source_kwargs or {}
    target_kwargs = target_kwargs or {}

    src = VectorStoreFactory.create_store(source_type, **source_kwargs)
    tgt = VectorStoreFactory.create_store(target_type, **target_kwargs)

    src_count = src.get_document_count()
    tgt_count = tgt.get_document_count()

    result: Dict[str, Any] = {"source_count": src_count, "target_count": tgt_count}

    if sample_ids:
        mismatches: List[str] = []
        for doc_id in sample_ids:
            sdoc = await src.get_document(doc_id)
            tdoc = await tgt.get_document(doc_id)
            if not sdoc or not tdoc or (sdoc.content or "") != (tdoc.content or ""):
                mismatches.append(doc_id)
        result["mismatches"] = mismatches
        result["match"] = len(mismatches) == 0
    else:
        result["match"] = src_count == tgt_count

    return result
