#!/usr/bin/env python3
"""
End-to-end reset → ingest → query checker

- Clears vector store and caches (L1/L2/semantic)
- Ingests a specified DOCX
- Asks a diagnostic question
- Prints a compact summary of retrieval and chunking

Usage:
  python examples/e2e_reset_ingest_query.py "C:/path/to/file.docx" "سوال شما چیست؟"
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import get_integration_service


async def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python examples/e2e_reset_ingest_query.py <docx_path> <question>")
        sys.exit(1)

    docx_path = Path(sys.argv[1])
    question = sys.argv[2]

    if not docx_path.exists():
        print(f"File not found: {docx_path}")
        sys.exit(2)

    # Ensure HF cache paths (optional): leverage existing cache if present
    cache_dir = Path.cwd() / "cache" / "sentence_transformers"
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(cache_dir))
    os.environ.setdefault("HF_HOME", str(cache_dir))

    logger.info("E2E check starting", file=str(docx_path), question=question)

    integration = await get_integration_service()

    # Components
    components: Dict[str, Any] = integration.components
    vector_store = components.get("vector_store")
    cache = components.get("cache")
    rag_service = components.get("rag_service")

    # Full reset: vector store + caches
    if vector_store is not None and hasattr(vector_store, "clear"):
        logger.info("Resetting vector store")
        await vector_store.clear()
    if cache is not None:
        try:
            logger.info("Clearing L1/L2 caches")
            await cache.clear()
        except Exception:
            pass
        try:
            if hasattr(cache, "clear_semantic_cache"):
                logger.info("Clearing semantic cache")
                await cache.clear_semantic_cache()
        except Exception:
            pass

    # Ingest document
    logger.info("Starting document ingestion", path=str(docx_path))
    ingest_res = await rag_service.ingest_document(str(docx_path), source_type="docx")
    logger.info(
        "Ingestion summary",
        chunks_added=getattr(ingest_res, "chunks_added", None),
        duration_s=getattr(ingest_res, "duration", None),
    )

    # Ask the query
    logger.info("Querying...", q=question)
    result = await rag_service.query_documents(question, settings.default_lang)

    # Compact print
    print("\n===== E2E Summary =====")
    print("Strategy:", getattr(settings.advanced_chunking, "chunking_strategy", "n/a"))
    sources = getattr(result, "sources", []) or []
    print("Answer length:", len(getattr(result, "answer", "")))
    print(getattr(result, "answer", ""))
    print("Sources:", len(sources))
    for i, s in enumerate(sources[:3]):
        meta = getattr(s, "metadata", {}) or {}
        print(
            f"- S{i}: score={getattr(s, 'score', None)} type={meta.get('chunk_type')} parent={meta.get('parent_id')}"
        )

    print(
        "\nNote: Check logs for 'AdaptiveChunker strategy selected' and 'Full chunking pipeline applied'."
    )


if __name__ == "__main__":
    asyncio.run(main())
