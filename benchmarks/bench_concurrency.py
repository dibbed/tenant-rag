#!/usr/bin/env python3
"""
Benchmark: Multi-Tenant Concurrency & Lock Contention

Measures:
- Async query throughput across N concurrent tenants
- Zero lock collisions / PermissionError on FAISS stores under concurrent writes
- Total requests per second (RPS) and latency distribution

Usage:
  python benchmarks/bench_concurrency.py --concurrency 20 --tenants 5 --output benchmarks/results_concurrency.json
"""

from __future__ import annotations

import argparse
import asyncio
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

from ragbot.rag.store.faiss_store import FAISSVectorStore
from ragbot.rag.store.base import VectorDocument


async def worker_task(
    worker_id: int,
    tenant_id: str,
    store: FAISSVectorStore,
    operations: int,
    results: List[float],
    errors: List[str],
) -> None:
    dim = store.embedding_dimension
    for op_i in range(operations):
        t0 = time.perf_counter()
        try:
            if op_i % 3 == 0:
                # Write operation (exercises async_lock)
                doc = VectorDocument(
                    id=f"t_{tenant_id}_w_{worker_id}_op_{op_i}",
                    content=f"Tenant {tenant_id} write payload from worker {worker_id}",
                    embedding=[0.01 * (worker_id + 1)] * dim,
                    metadata={"tenant_id": tenant_id, "worker_id": worker_id},
                )
                await store.add_documents([doc])
            else:
                # Read / search operation
                query_emb = [0.01 * (worker_id + 1)] * dim
                matches = await store.search(query_emb, top_k=2)
                _ = matches.total_results if hasattr(matches, "total_results") else 0

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            results.append(elapsed_ms)
        except Exception as exc:
            errors.append(f"Worker {worker_id} on {tenant_id}: {type(exc).__name__}: {str(exc)}")


async def run_benchmark(concurrency: int, tenant_count: int, ops_per_worker: int) -> Dict[str, Any]:
    tenants = [f"tenant_bench_{i:02d}" for i in range(tenant_count)]
    stores: Dict[str, FAISSVectorStore] = {}

    for t in tenants:
        store_path = Path(f"data/vector_stores/bench_concurrent_{t}")
        stores[t] = FAISSVectorStore(dimension=128, store_path=str(store_path))
        # Initial document
        await stores[t].add_documents([
            VectorDocument(
                id="init_doc",
                content=f"Initial seed document for {t}",
                embedding=[0.05] * 128,
                metadata={"tenant_id": t},
            )
        ])

    latencies: List[float] = []
    errors: List[str] = []

    tasks = []
    t_start = time.perf_counter()

    for w_id in range(concurrency):
        tenant_id = tenants[w_id % tenant_count]
        store = stores[tenant_id]
        tasks.append(
            worker_task(w_id, tenant_id, store, ops_per_worker, latencies, errors)
        )

    await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - t_start

    # Clean up test stores
    for t, s in stores.items():
        try:
            s.reset()
        except Exception:
            pass

    sorted_l = sorted(latencies) if latencies else [0.0]
    total_ops = len(latencies)

    return {
        "metadata": {
            "benchmark": "multi_tenant_concurrency",
            "timestamp": time.time(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "concurrency_workers": concurrency,
            "tenant_count": tenant_count,
            "operations_per_worker": ops_per_worker,
            "total_operations": total_ops,
            "total_duration_seconds": round(total_duration, 3),
            "throughput_ops_per_second": round(total_ops / total_duration, 2) if total_duration > 0 else 0,
            "error_count": len(errors),
            "errors": errors[:5],
        },
        "latencies_ms": {
            "mean": round(sum(sorted_l) / len(sorted_l), 2),
            "p50": round(sorted_l[int(len(sorted_l) * 0.50)], 2),
            "p90": round(sorted_l[int(len(sorted_l) * 0.90)], 2),
            "p99": round(sorted_l[min(int(len(sorted_l) * 0.99), len(sorted_l) - 1)], 2),
            "min": round(sorted_l[0], 2),
            "max": round(sorted_l[-1], 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TenantRAG Multi-Tenant Concurrency Benchmark")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent worker tasks")
    parser.add_argument("--tenants", type=int, default=3, help="Number of distinct tenants")
    parser.add_argument("--ops", type=int, default=15, help="Operations per worker")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    print(f"Running concurrency benchmark ({args.concurrency} workers, {args.tenants} tenants)...")
    results = asyncio.run(run_benchmark(args.concurrency, args.tenants, args.ops))
    print(json.dumps(results, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
