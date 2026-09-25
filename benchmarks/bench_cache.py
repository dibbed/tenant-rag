#!/usr/bin/env python3
"""
Benchmark: Semantic Cache Latency & Hit Rate

Measures:
- Cold miss latency (embedding generation + cache population)
- Warm hit latency (embedding generation + cosine matching)
- Percentiles: p50, p90, p99, mean

Usage:
  python benchmarks/bench_cache.py --iterations 50 --output benchmarks/results_cache.json
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

from ragbot.caching.semantic_cache import SemanticCache


async def run_benchmark(iterations: int, tenant_id: str) -> Dict[str, Any]:
    cache = SemanticCache(similarity_threshold=0.85, max_size=1000)

    sample_queries = [
        ("What is Retrieval-Augmented Generation?", "RAG combines search with generative LLMs."),
        ("How does multi-tenancy work in vector search?", "It isolates index files per customer."),
        ("What is semantic caching?", "Semantic caching returns stored answers for similar queries."),
        ("How are API keys validated?", "API keys are hashed with SHA-256 and matched in SQLite."),
        ("Which vector databases are supported?", "FAISS, ChromaDB, and Qdrant are supported."),
    ]

    # Pre-populate cache
    for q, a in sample_queries:
        await cache.cache_answer(
            query=q,
            answer=a,
            context=["Reference context"],
            metadata={"source": "benchmark"},
            tenant_id=tenant_id,
        )

    # Warm hit benchmark
    hit_total_lats: List[float] = []
    hit_embed_lats: List[float] = []
    hit_lookup_lats: List[float] = []

    for _ in range(iterations):
        for q, _ in sample_queries:
            t0 = time.perf_counter()
            q_emb = await cache._get_query_embedding(q)
            t_emb = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            match = await cache._find_best_match(q_emb, tenant_id=tenant_id)
            t_lookup = (time.perf_counter() - t1) * 1000.0

            assert match is not None
            hit_embed_lats.append(t_emb)
            hit_lookup_lats.append(t_lookup)
            hit_total_lats.append(t_emb + t_lookup)

    # Miss benchmark (novel queries)
    miss_total_lats: List[float] = []
    miss_embed_lats: List[float] = []
    miss_lookup_lats: List[float] = []

    for i in range(iterations):
        novel_query = f"Novel benchmark query number {i} with completely distinct semantics {time.time()}"
        t0 = time.perf_counter()
        q_emb = await cache._get_query_embedding(novel_query)
        t_emb = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        match = await cache._find_best_match(q_emb, tenant_id=tenant_id)
        t_lookup = (time.perf_counter() - t1) * 1000.0

        assert match is None
        miss_embed_lats.append(t_emb)
        miss_lookup_lats.append(t_lookup)
        miss_total_lats.append(t_emb + t_lookup)

    await cache.clear_cache()

    def calc_stats(lats: List[float]) -> Dict[str, float]:
        sorted_l = sorted(lats)
        n = len(sorted_l)
        return {
            "count": n,
            "mean_ms": round(sum(sorted_l) / n, 2),
            "p50_ms": round(sorted_l[int(n * 0.50)], 2),
            "p90_ms": round(sorted_l[int(n * 0.90)], 2),
            "p99_ms": round(sorted_l[min(int(n * 0.99), n - 1)], 2),
            "min_ms": round(sorted_l[0], 2),
            "max_ms": round(sorted_l[-1], 2),
        }

    return {
        "metadata": {
            "benchmark": "semantic_cache",
            "timestamp": time.time(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "iterations_per_query": iterations,
            "tenant_id": tenant_id,
        },
        "warm_hits": {
            "total_ms": calc_stats(hit_total_lats),
            "embedding_ms": calc_stats(hit_embed_lats),
            "cache_lookup_ms": calc_stats(hit_lookup_lats),
        },
        "cold_misses": {
            "total_ms": calc_stats(miss_total_lats),
            "embedding_ms": calc_stats(miss_embed_lats),
            "cache_lookup_ms": calc_stats(miss_lookup_lats),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TenantRAG Semantic Cache Benchmark")
    parser.add_argument("--iterations", type=int, default=20, help="Iterations per sample query")
    parser.add_argument("--tenant-id", type=str, default="bench_tenant_01", help="Tenant ID")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    print(f"Running semantic cache benchmark ({args.iterations} iterations)...")
    results = asyncio.run(run_benchmark(args.iterations, args.tenant_id))
    print(json.dumps(results, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
