#!/usr/bin/env python3
"""
Benchmark: Document Ingestion & Vector Store Indexing Throughput

Measures:
- Chunks indexed per second
- Ingestion latency per batch
- Index persistence time across backends (faiss, chroma, qdrant)

Usage:
  python benchmarks/bench_ingest.py --backend faiss --chunks 500 --batch-size 50 --output benchmarks/results_ingest.json
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ragbot.rag.store.factory import VectorStoreFactory
from ragbot.rag.store.base import VectorDocument


def generate_synthetic_documents(count: int, dim: int) -> List[VectorDocument]:
    return [
        VectorDocument(
            id=f"bench_doc_{i:05d}",
            content=(
                f"Synthetic benchmark document chunk {i}. "
                "This document simulates a typical paragraph extracted from a PDF or DOCX file "
                "for evaluating vector store insertion performance."
            ),
            embedding=[0.02 * ((i % 50) + 1)] * dim,
            metadata={"source": "ingest_bench", "chunk_id": i},
        )
        for i in range(count)
    ]


async def run_benchmark_async(backend: str, total_chunks: int, batch_size: int) -> Dict[str, Any]:
    dim = 384
    store_path = Path(f"data/vector_stores/bench_ingest_{backend}")

    store = VectorStoreFactory.create_store(
        backend,
        dimension=dim,
        store_path=str(store_path),
        persist_directory=str(store_path),
    )

    docs = generate_synthetic_documents(total_chunks, dim)

    batch_latencies_ms: List[float] = []
    t_start = time.perf_counter()

    for start_idx in range(0, total_chunks, batch_size):
        batch = docs[start_idx : start_idx + batch_size]
        t0 = time.perf_counter()
        add_result = store.add_documents(batch)
        if inspect.isawaitable(add_result):
            await add_result
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        batch_latencies_ms.append(elapsed_ms)

    total_duration = time.perf_counter() - t_start

    # Clean up test store
    try:
        reset_res = store.reset()
        if inspect.isawaitable(reset_res):
            await reset_res
    except Exception:
        pass

    return {
        "metadata": {
            "benchmark": "ingestion_throughput",
            "backend": backend,
            "timestamp": time.time(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "total_chunks": total_chunks,
            "batch_size": batch_size,
            "vector_dimension": dim,
            "total_duration_seconds": round(total_duration, 3),
            "throughput_chunks_per_sec": round(total_chunks / total_duration, 2) if total_duration > 0 else 0,
        },
        "batch_latencies_ms": {
            "mean": round(sum(batch_latencies_ms) / len(batch_latencies_ms), 2),
            "p50": round(sorted(batch_latencies_ms)[int(len(batch_latencies_ms) * 0.50)], 2),
            "min": round(min(batch_latencies_ms), 2),
            "max": round(max(batch_latencies_ms), 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TenantRAG Ingestion Benchmark")
    parser.add_argument("--backend", choices=["faiss", "chroma", "qdrant"], default="faiss", help="Vector store backend")
    parser.add_argument("--chunks", type=int, default=500, help="Total chunks to index")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for insertion")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    print(f"Running ingestion benchmark for backend '{args.backend}' with {args.chunks} chunks...")
    results = asyncio.run(run_benchmark_async(args.backend, args.chunks, args.batch_size))
    print(json.dumps(results, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
