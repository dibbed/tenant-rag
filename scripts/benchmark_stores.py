#!/usr/bin/env python3
"""
Performance benchmarking script for vector stores.

This script benchmarks different vector store implementations to help users
choose the best option for their use case based on performance metrics.
"""

import asyncio
import time
import psutil
import statistics
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import argparse

from ragbot.rag import VectorStoreFactory, VectorDocument
from ragbot.outputs.logger import logger


class VectorStoreBenchmark:
    """
    Comprehensive benchmarking suite for vector stores.

    Measures:
    - Setup time
    - Document addition time
    - Search performance
    - Memory usage
    - Document retrieval time
    - Batch operation performance
    """

    def __init__(self, document_count: int = 1000, embedding_dimension: int = 1536):
        """
        Initialize benchmark with test parameters.

        Args:
            document_count: Number of documents to use for testing
            embedding_dimension: Dimension of test embeddings
        """
        self.document_count = document_count
        self.embedding_dimension = embedding_dimension
        self.test_documents = self._generate_test_documents()
        self.results: Dict[str, Dict[str, Any]] = {}

    def _generate_test_documents(self) -> List[VectorDocument]:
        """Generate test documents with random embeddings."""
        import random

        documents = []
        for i in range(self.document_count):
            # Generate random embedding
            embedding = [random.random() for _ in range(self.embedding_dimension)]

            # Create test document
            doc = VectorDocument(
                id=f"test_doc_{i:06d}",
                content=f"This is test document number {i}. It contains sample content for benchmarking purposes.",
                embedding=embedding,
                metadata={
                    "source": "benchmark",
                    "doc_type": "test",
                    "index": i,
                    "category": f"category_{i % 10}",
                    "priority": random.choice(["low", "medium", "high"]),
                    "timestamp": time.time(),
                },
            )
            documents.append(doc)

        return documents

    async def benchmark_store(self, store_type: str, **store_kwargs) -> Dict[str, Any]:
        """
        Benchmark a specific store type.

        Args:
            store_type: Type of vector store to benchmark
            **store_kwargs: Additional arguments for store creation

        Returns:
            Dictionary containing benchmark results
        """
        logger.info(f"🔍 Starting benchmark for {store_type}")

        try:
            # Measure setup time
            setup_start = time.time()
            store = VectorStoreFactory.create_store(store_type, **store_kwargs)
            setup_time = time.time() - setup_start

            # Measure memory before operations
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            # Benchmark document addition
            add_times = []
            batch_size = 100

            for i in range(0, len(self.test_documents), batch_size):
                batch = self.test_documents[i : i + batch_size]

                add_start = time.time()
                await store.add_documents(batch)
                add_time = time.time() - add_start
                add_times.append(add_time)

            total_add_time = sum(add_times)
            avg_add_time = statistics.mean(add_times)

            # Measure memory after addition
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage = memory_after - memory_before

            # Benchmark search performance
            search_times = []
            search_results_count = []

            # Test with different query embeddings
            for i in range(20):  # 20 different search queries
                query_embedding = [0.1 + (i * 0.01)] * self.embedding_dimension

                search_start = time.time()
                results = await store.search(query_embedding, top_k=10)
                search_time = time.time() - search_start

                search_times.append(search_time)
                search_results_count.append(len(results.documents))

            avg_search_time = statistics.mean(search_times)
            min_search_time = min(search_times)
            max_search_time = max(search_times)

            # Benchmark document retrieval
            retrieval_times = []
            for i in range(0, min(100, len(self.test_documents)), 10):
                doc_id = f"test_doc_{i:06d}"

                retrieval_start = time.time()
                doc = await store.get_document(doc_id)
                retrieval_time = time.time() - retrieval_start

                if doc:
                    retrieval_times.append(retrieval_time)

            avg_retrieval_time = (
                statistics.mean(retrieval_times) if retrieval_times else 0
            )

            # Benchmark metadata filtering (if supported)
            metadata_search_times = []
            if hasattr(store, "search_with_metadata_filter"):
                for category in range(5):
                    filter_dict = {"category": f"category_{category}"}
                    query_embedding = [0.1] * self.embedding_dimension

                    filter_start = time.time()
                    try:
                        results = await store.search_with_metadata_filter(
                            query_embedding, filter_dict, top_k=5
                        )
                        filter_time = time.time() - filter_start
                        metadata_search_times.append(filter_time)
                    except Exception:
                        # Store doesn't support metadata filtering
                        break

            avg_metadata_search_time = (
                statistics.mean(metadata_search_times)
                if metadata_search_times
                else None
            )

            # Get document count for verification
            doc_count = store.get_document_count()

            # Compile results
            results = {
                "store_type": store_type,
                "document_count": doc_count,
                "embedding_dimension": self.embedding_dimension,
                "setup_time": setup_time,
                "total_add_time": total_add_time,
                "avg_add_time": avg_add_time,
                "memory_usage_mb": memory_usage,
                "avg_search_time": avg_search_time,
                "min_search_time": min_search_time,
                "max_search_time": max_search_time,
                "avg_retrieval_time": avg_retrieval_time,
                "avg_metadata_search_time": avg_metadata_search_time,
                "search_results_avg": statistics.mean(search_results_count),
                "throughput_docs_per_sec": len(self.test_documents) / total_add_time,
                "search_throughput_per_sec": 1 / avg_search_time
                if avg_search_time > 0
                else 0,
                "supports_metadata_filtering": avg_metadata_search_time is not None,
                "benchmark_timestamp": time.time(),
            }

            logger.info(f"✅ Completed benchmark for {store_type}")
            return results

        except Exception as e:
            logger.error(f"❌ Benchmark failed for {store_type}: {e}")
            return {
                "store_type": store_type,
                "error": str(e),
                "benchmark_timestamp": time.time(),
            }

    async def run_all_benchmarks(
        self, stores: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run benchmarks for all available stores.

        Args:
            stores: List of store types to benchmark. If None, benchmarks all available stores.

        Returns:
            Dictionary mapping store types to their benchmark results
        """
        if stores is None:
            stores = [
                "faiss",
                "chroma",
                "qdrant",
            ]  # Skip weaviate due to circular import

        results = {}

        for store_type in stores:
            try:
                result = await self.benchmark_store(store_type)
                results[store_type] = result
            except Exception as e:
                logger.error(f"Failed to benchmark {store_type}: {e}")
                results[store_type] = {
                    "store_type": store_type,
                    "error": str(e),
                    "benchmark_timestamp": time.time(),
                }

        return results

    def generate_report(self, results: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate a human-readable benchmark report.

        Args:
            results: Benchmark results from run_all_benchmarks

        Returns:
            Formatted report string
        """
        report = []
        report.append("🚀 Vector Store Performance Benchmark Report")
        report.append("=" * 50)
        report.append("📊 Test Parameters:")
        report.append(f"   • Document Count: {self.document_count:,}")
        report.append(f"   • Embedding Dimension: {self.embedding_dimension}")
        report.append(f"   • Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Sort results by average search time (performance metric)
        sorted_results = sorted(
            [(k, v) for k, v in results.items() if "error" not in v],
            key=lambda x: x[1].get("avg_search_time", float("inf")),
        )

        if sorted_results:
            report.append("🏆 Performance Rankings (by search speed):")
            for i, (store_type, result) in enumerate(sorted_results, 1):
                search_time = result.get("avg_search_time", 0) * 1000  # Convert to ms
                throughput = result.get("throughput_docs_per_sec", 0)
                memory = result.get("memory_usage_mb", 0)

                report.append(f"   {i}. {store_type.upper()}")
                report.append(f"      • Search: {search_time:.1f}ms")
                report.append(f"      • Throughput: {throughput:.1f} docs/sec")
                report.append(f"      • Memory: {memory:.1f}MB")
            report.append("")

        # Detailed results for each store
        for store_type, result in results.items():
            report.append(f"📈 {store_type.upper()} Detailed Results:")
            report.append("-" * 30)

            if "error" in result:
                report.append(f"   ❌ Error: {result['error']}")
            else:
                report.append(f"   • Setup Time: {result.get('setup_time', 0):.3f}s")
                report.append(
                    f"   • Total Add Time: {result.get('total_add_time', 0):.3f}s"
                )
                report.append(
                    f"   • Avg Search Time: {result.get('avg_search_time', 0) * 1000:.1f}ms"
                )
                report.append(
                    f"   • Min Search Time: {result.get('min_search_time', 0) * 1000:.1f}ms"
                )
                report.append(
                    f"   • Max Search Time: {result.get('max_search_time', 0) * 1000:.1f}ms"
                )
                report.append(
                    f"   • Avg Retrieval Time: {result.get('avg_retrieval_time', 0) * 1000:.1f}ms"
                )
                report.append(
                    f"   • Memory Usage: {result.get('memory_usage_mb', 0):.1f}MB"
                )
                report.append(
                    f"   • Throughput: {result.get('throughput_docs_per_sec', 0):.1f} docs/sec"
                )
                report.append(
                    f"   • Search Throughput: {result.get('search_throughput_per_sec', 0):.1f} searches/sec"
                )
                report.append(
                    f"   • Document Count: {result.get('document_count', 0):,}"
                )
                report.append(
                    f"   • Metadata Filtering: {'✅' if result.get('supports_metadata_filtering') else '❌'}"
                )

                if result.get("avg_metadata_search_time"):
                    report.append(
                        f"   • Metadata Search: {result.get('avg_metadata_search_time', 0) * 1000:.1f}ms"
                    )

            report.append("")

        # Recommendations
        report.append("🎯 Recommendations:")
        report.append("-" * 20)

        if sorted_results:
            fastest = sorted_results[0]
            report.append(
                f"   • Fastest Search: {fastest[0].upper()} ({fastest[1].get('avg_search_time', 0) * 1000:.1f}ms)"
            )

            # Find most memory efficient
            memory_sorted = sorted(
                [(k, v) for k, v in results.items() if "error" not in v],
                key=lambda x: x[1].get("memory_usage_mb", float("inf")),
            )
            if memory_sorted:
                efficient = memory_sorted[0]
                report.append(
                    f"   • Most Memory Efficient: {efficient[0].upper()} ({efficient[1].get('memory_usage_mb', 0):.1f}MB)"
                )

            # Find highest throughput
            throughput_sorted = sorted(
                [(k, v) for k, v in results.items() if "error" not in v],
                key=lambda x: x[1].get("throughput_docs_per_sec", 0),
                reverse=True,
            )
            if throughput_sorted:
                high_throughput = throughput_sorted[0]
                report.append(
                    f"   • Highest Throughput: {high_throughput[0].upper()} ({high_throughput[1].get('throughput_docs_per_sec', 0):.1f} docs/sec)"
                )

        report.append("")
        report.append("💡 Use Cases:")
        report.append("   • Development/Testing: FAISS (fast, simple)")
        report.append("   • RAG Applications: CHROMA (metadata support)")
        report.append("   • Production/Scale: QDRANT (performance + features)")

        return "\n".join(report)

    def save_results(
        self, results: Dict[str, Dict[str, Any]], output_path: str
    ) -> None:
        """
        Save benchmark results to JSON file.

        Args:
            results: Benchmark results
            output_path: Path to save results
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 Results saved to {output_path}")


async def main():
    """Main benchmark execution function."""
    parser = argparse.ArgumentParser(description="Benchmark vector stores")
    parser.add_argument(
        "--stores",
        nargs="+",
        default=["faiss", "chroma", "qdrant"],
        help="Store types to benchmark",
    )
    parser.add_argument(
        "--documents", type=int, default=1000, help="Number of documents to test with"
    )
    parser.add_argument(
        "--dimension", type=int, default=1536, help="Embedding dimension"
    )
    parser.add_argument(
        "--output", default="benchmark_results.json", help="Output file for results"
    )
    parser.add_argument(
        "--report",
        default="benchmark_report.txt",
        help="Output file for human-readable report",
    )

    args = parser.parse_args()

    # Initialize benchmark
    benchmark = VectorStoreBenchmark(
        document_count=args.documents, embedding_dimension=args.dimension
    )

    print("🚀 Starting Vector Store Benchmark...")
    print(f"📊 Testing {args.documents:,} documents with {args.dimension}D embeddings")
    print(f"🎯 Stores: {', '.join(args.stores)}")
    print()

    # Run benchmarks
    results = await benchmark.run_all_benchmarks(args.stores)

    # Save results
    benchmark.save_results(results, args.output)

    # Generate and save report
    report = benchmark.generate_report(results)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\n📁 Detailed results saved to: {args.output}")
    print(f"📄 Report saved to: {args.report}")


if __name__ == "__main__":
    asyncio.run(main())
