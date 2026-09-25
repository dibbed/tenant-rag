#!/usr/bin/env python3
"""
Benchmark: Process Memory Footprint (RSS)

Measures:
- Baseline Python process memory (idle)
- Memory after importing core modules (FastAPI, FAISS, PyTorch)
- Memory after initializing TenantManager and loading vector store
- Memory after indexing N document chunks

Usage:
  python benchmarks/bench_memory.py --chunks 1000 --output benchmarks/results_memory.json
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict

import psutil

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_rss_mb() -> float:
    """Return Resident Set Size (RSS) memory in Megabytes."""
    gc.collect()
    process = psutil.Process(os.getpid())
    return round(process.memory_info().rss / (1024 * 1024), 2)


async def run_benchmark_async(chunk_count: int) -> Dict[str, Any]:
    stages: Dict[str, float] = {}

    stages["01_baseline_idle_mb"] = get_rss_mb()

    # Import heavy packages
    import faiss
    import torch
    from sentence_transformers import SentenceTransformer
    from ragbot.multi_tenant.tenant_manager import TenantManager
    from ragbot.rag.store.faiss_store import FAISSVectorStore
    from ragbot.rag.store.base import VectorDocument

    stages["02_after_imports_mb"] = get_rss_mb()

    # Initialize TenantManager
    tm = TenantManager(db_path=Path("data/tenants/bench_tenants.db"))
    store = FAISSVectorStore(dimension=384, store_path="data/vector_stores/bench_mem")

    stages["03_after_init_empty_store_mb"] = get_rss_mb()

    # Generate synthetic embeddings and add to store
    sample_emb = [0.05] * store.embedding_dimension
    docs = [
        VectorDocument(
            id=f"doc_{i}",
            content=f"Synthetic document content chunk number {i} for memory benchmark testing.",
            embedding=sample_emb,
            metadata={"source": "memory_bench", "chunk_index": i},
        )
        for i in range(chunk_count)
    ]

    t0 = time.perf_counter()
    await store.add_documents(docs)
    ingest_time = round(time.perf_counter() - t0, 3)

    stages["04_after_indexing_chunks_mb"] = get_rss_mb()
    stages["memory_delta_mb"] = round(
        stages["04_after_indexing_chunks_mb"] - stages["01_baseline_idle_mb"], 2
    )

    # Cleanup temporary benchmark store
    try:
        store.reset()
    except Exception:
        pass

    return {
        "metadata": {
            "benchmark": "memory_footprint",
            "timestamp": time.time(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "chunks_indexed": chunk_count,
            "indexing_duration_seconds": ingest_time,
        },
        "stages": stages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TenantRAG Memory Benchmark")
    parser.add_argument("--chunks", type=int, default=1000, help="Number of synthetic chunks to index")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    print(f"Running memory benchmark with {args.chunks} chunks...")
    results = asyncio.run(run_benchmark_async(args.chunks))
    print(json.dumps(results, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
