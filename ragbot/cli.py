"""
Simple CLI for RAG Telegram Assistant: batch ingest, ingest, query, reset, status.

Usage examples:
  - ragbot-cli batch-ingest --dir ./docs --pattern "*.pdf" --recursive
  - ragbot-cli ingest --file sample.pdf
  - ragbot-cli ingest --url https://example.com
  - ragbot-cli query --question "What is RAG?" --lang en --top-k 4
  - ragbot-cli reset
  - ragbot-cli status
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import List, Optional

from ragbot.outputs.logger import logger
from ragbot.services.integration_service import get_integration_service
from ragbot.security import EncryptionManager, KeyManager, SecureBackupManager
from ragbot.rag import QueryAggregator, AdvancedFilter, QueryOptimizer
from ragbot.utils.config_migration import migrate_env_file
from ragbot.utils.migration import migrate_stores, verify_migration
from ragbot.utils.vector_store_migration import migrate_store_command


async def _get_rag_service():
    integration = await get_integration_service()
    return await integration.get_rag_service()


async def cmd_status(_args: argparse.Namespace) -> int:
    rag = await _get_rag_service()
    hs = await rag.get_health_status()
    print("status:", hs.overall_status)
    print("uptime:", f"{hs.uptime:.2f}s")
    print("documents:", hs.document_count)
    return 0


async def cmd_performance(_args: argparse.Namespace) -> int:
    """Show performance metrics"""
    try:
        integration = await get_integration_service()

        # Get performance summary
        perf_summary = await integration.get_performance_summary()
    except Exception as e:
        print("error:", str(e))
        return 1
    print("Performance Summary:")
    if "error" in perf_summary:
        print("error:", perf_summary["error"])
        return 1

    if "no_data" in perf_summary:
        print("No performance data available yet")
        return 0

    print(
        "average_response_time:", f"{perf_summary.get('average_response_time', 0):.3f}s"
    )
    print("total_requests:", perf_summary.get("total_requests", 0))
    print("error_rate:", f"{perf_summary.get('error_rate', 0):.2%}")
    print("cpu_usage:", f"{perf_summary.get('cpu_usage', 0):.1f}%")
    print("memory_usage:", f"{perf_summary.get('memory_usage', 0):.1f}%")
    print("active_connections:", perf_summary.get("active_connections", 0))

    # Get resource summary
    resource_summary = await integration.get_resource_summary()
    print("\nResource Summary:")
    if "error" in resource_summary:
        print("error:", resource_summary["error"])
        return 1

    if "no_data" in resource_summary:
        print("No resource data available yet")
        return 0

    current = resource_summary.get("current", {})
    averages = resource_summary.get("averages", {})

    print("current_cpu:", f"{current.get('cpu_percent', 0):.1f}%")
    print("current_memory:", f"{current.get('memory_percent', 0):.1f}%")
    print("current_disk:", f"{current.get('disk_usage', 0):.1f}%")
    print("avg_cpu:", f"{averages.get('cpu_percent', 0):.1f}%")
    print("avg_memory:", f"{averages.get('memory_percent', 0):.1f}%")

    alerts = resource_summary.get("alerts", [])
    if alerts:
        print(f"\nActive Alerts ({len(alerts)}):")
        for alert in alerts[-5:]:  # Show last 5 alerts
            print(
                f"- {alert.get('severity', 'unknown')}: {alert.get('message', 'No message')}"
            )

    return 0


async def cmd_reset(_args: argparse.Namespace) -> int:
    rag = await _get_rag_service()
    ok = await rag.reset_store()
    print("reset:", "success" if ok else "failed")
    return 0 if ok else 1


async def cmd_query(args: argparse.Namespace) -> int:
    rag = await _get_rag_service()
    res = await rag.query_documents(
        question=args.question,
        lang=args.lang,
        top_k=args.top_k,
        similarity_threshold=args.threshold,
    )
    print("answer:")
    print(res.answer)
    if res.sources:
        print("\nsources:")
        for s in res.sources:
            print("-", s)
    print("\nconfidence:", f"{res.confidence_score:.2f}")
    print("processing_time:", f"{res.processing_time:.2f}s")
    return 0


async def cmd_ingest(args: argparse.Namespace) -> int:
    rag = await _get_rag_service()
    source: Optional[str] = None
    source_type: Optional[str] = None
    if args.file:
        source = args.file
        source_type = args.type or "pdf" if source.lower().endswith(".pdf") else None
    elif args.url:
        source = args.url
        source_type = args.type or "url"
    elif args.text:
        source = args.text
        source_type = args.type or "text"
    else:
        print("Provide one of --file/--url/--text")
        return 2

    res = await rag.ingest_document(source, source_type)
    print("success:", res.success)
    print("document_id:", res.document_id)
    print("chunks:", res.chunks_created)
    print("processing_time:", f"{res.processing_time:.2f}s")
    if res.error_message:
        print("error:", res.error_message)
    return 0 if res.success else 1


async def cmd_batch_ingest(args: argparse.Namespace) -> int:
    rag = await _get_rag_service()
    # Build default patterns: only PDF unless flags are provided
    if args.pattern:
        patterns: Optional[List[str]] = args.pattern
    else:
        patterns = ["*.pdf"]
        if getattr(args, "include_txt", False):
            patterns.append("*.txt")
        if getattr(args, "include_docx", False):
            patterns.append("*.docx")
    summary = await rag.batch_ingest(
        sources=args.sources,
        directory=args.dir,
        patterns=patterns,
        recursive=not args.no_recursive,
        source_type=args.type,
        max_concurrency=args.max_concurrency,
    )
    print("total:", summary["total"])  # type: ignore
    print("succeeded:", summary["succeeded"])  # type: ignore
    print("failed:", summary["failed"])  # type: ignore
    print("duration:", f"{summary['duration']:.2f}s")  # type: ignore
    # Show a brief table
    for r in summary["results"][:10]:  # type: ignore
        status = "ok" if r.get("success") else "fail"
        src = r.get("source") or r.get("document_metadata", {}).get("source")
        print(f"- {status} {r.get('document_id')}  src={src}")
    if summary["total"] > 10:  # type: ignore
        print("... (showing first 10)")
    return 0 if summary["failed"] == 0 else 1  # type: ignore


async def cmd_migrate(args: argparse.Namespace) -> int:
    """Migrate vector data between providers."""
    try:
        src = (args.source or "faiss").lower()
        tgt = (args.target or "chromadb").lower()

        # Progress printer
        def _progress(ev):
            total = ev.get("total") or 0
            mig = ev.get("migrated") or 0
            fail = ev.get("failed") or 0
            phase = ev.get("phase") or "migrating"
            if total:
                print(f"[{phase}] {mig + fail}/{total} (migrated={mig}, failed={fail})")
            else:
                print(f"[{phase}] migrated={mig}, failed={fail}")

        summary = await migrate_stores(
            src,
            tgt,
            batch_size=getattr(args, "batch_size", 500),
            rollback_on_failure=getattr(args, "rollback", False),
            progress_cb=None if getattr(args, "no_progress", False) else _progress,
        )
        print("status:", summary.get("status", "unknown"))
        print("migrated:", summary.get("migrated", 0))
        print("failed:", summary.get("failed", 0))
        if "target_count" in summary:
            print("target_count:", summary["target_count"])  # type: ignore
        if summary.get("rolled_back"):
            print("rolled_back:", summary.get("rolled_back"))
        return 0 if summary.get("status") == "ok" else 1
    except Exception as e:
        print("error:", str(e))
        return 1


async def cmd_verify_migration(args: argparse.Namespace) -> int:
    """Verify migration between providers."""
    try:
        src = (args.source or "faiss").lower()
        tgt = (args.target or "chromadb").lower()
        sample = args.sample or []
        res = await verify_migration(src, tgt, sample_ids=sample)
        print("source_count:", res.get("source_count"))
        print("target_count:", res.get("target_count"))
        print("match:", res.get("match"))
        if res.get("mismatches"):
            print("mismatches:", res.get("mismatches"))
        return 0 if res.get("match") else 1
    except Exception as e:
        print("error:", str(e))
        return 1


async def cmd_migrate_store(args: argparse.Namespace) -> int:
    """Migrate data between vector stores with advanced features."""
    try:
        success = await migrate_store_command(
            source=args.source,
            target=args.target,
            batch_size=args.batch_size,
            validate=not args.no_validate,
            backup=not args.no_backup,
            report_path=args.report,
        )
        return 0 if success else 1
    except Exception as e:
        print(f"Migration error: {e}")
        return 1


async def cmd_benchmark_stores(args: argparse.Namespace) -> int:
    """Benchmark vector store performance."""
    try:
        from ragbot.benchmark import VectorStoreBenchmark

        # Initialize benchmark
        benchmark = VectorStoreBenchmark(
            document_count=args.documents, embedding_dimension=args.dimension
        )

        print("🚀 Starting Vector Store Benchmark...")
        print(
            f"📊 Testing {args.documents:,} documents with {args.dimension}D embeddings"
        )
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

        return 0

    except Exception as e:
        print(f"Benchmark error: {e}")
        return 1


def cmd_config_migrate(args: argparse.Namespace) -> int:
    """Migrate .env vector-store keys to the new schema."""
    try:
        summary = migrate_env_file(args.input, args.output)
        print("input:", summary["input"])  # type: ignore
        print("output:", summary["output"])  # type: ignore
        print("changed_keys:", summary["changed_keys"])  # type: ignore
        return 0
    except Exception as e:
        print("error:", str(e))
        return 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ragbot-cli", description="RAG Assistant CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    # status
    sp = sub.add_parser("status", help="Show health status")
    sp.set_defaults(func=cmd_status)

    # performance
    sp = sub.add_parser("performance", help="Show performance metrics")
    sp.set_defaults(func=cmd_performance)

    # reset
    sp = sub.add_parser("reset", help="Reset vector store")
    sp.set_defaults(func=cmd_reset)

    # query
    sp = sub.add_parser("query", help="Ask a question against the knowledge base")
    sp.add_argument("--question", required=True)
    sp.add_argument("--lang", default="fa", choices=["fa", "en"])
    sp.add_argument("--top-k", type=int, default=None)
    sp.add_argument("--threshold", type=float, default=None)
    sp.set_defaults(func=cmd_query)

    # ingest single
    sp = sub.add_parser("ingest", help="Ingest a single source (file/url/text)")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--url")
    g.add_argument("--text")
    sp.add_argument("--type", choices=["pdf", "docx", "url", "text"], default=None)
    sp.set_defaults(func=cmd_ingest)

    # batch ingest
    sp = sub.add_parser(
        "batch-ingest", help="Batch-ingest a directory or list of sources"
    )
    sp.add_argument("--dir", help="Directory to scan", default=None)
    sp.add_argument(
        "--pattern",
        action="append",
        help="Glob pattern(s), e.g. --pattern *.pdf",
        default=None,
    )
    sp.add_argument(
        "--include-txt",
        action="store_true",
        help="Include *.txt when scanning (default is only *.pdf)",
    )
    sp.add_argument(
        "--include-docx",
        action="store_true",
        help="Include *.docx when scanning (default is only *.pdf)",
    )
    sp.add_argument(
        "--no-recursive", action="store_true", help="Disable recursive scan"
    )
    sp.add_argument(
        "--type",
        choices=["pdf", "docx", "url", "text"],
        default=None,
        help="Force source type",
    )
    sp.add_argument("--max-concurrency", type=int, default=4)
    sp.add_argument("sources", nargs="*", help="Optional explicit sources (files/urls)")
    sp.set_defaults(func=cmd_batch_ingest)

    # migrate
    sp = sub.add_parser("migrate", help="Migrate vector data between providers")
    sp.add_argument(
        "--source", required=True, help="Source provider (faiss/chroma/qdrant/weaviate)"
    )
    sp.add_argument(
        "--target", required=True, help="Target provider (faiss/chroma/qdrant/weaviate)"
    )
    sp.add_argument("--batch-size", type=int, default=500, help="Migration batch size")
    sp.add_argument("--rollback", action="store_true", help="Rollback on first failure")
    sp.add_argument(
        "--no-progress", action="store_true", help="Disable live progress output"
    )
    sp.set_defaults(func=cmd_migrate)

    # verify-migration
    sp = sub.add_parser("verify-migration", help="Verify migration correctness")
    sp.add_argument("--source", required=True)
    sp.add_argument("--target", required=True)
    sp.add_argument(
        "--sample", action="append", help="Sample document ID to verify", default=None
    )
    sp.set_defaults(func=cmd_verify_migration)

    # (second migrate parser removed; consolidated above)

    # migrate-store (new comprehensive migration)
    sp = sub.add_parser(
        "migrate-store",
        help="Migrate data between vector stores with advanced features",
    )
    sp.add_argument(
        "--source",
        required=True,
        choices=["faiss", "chroma", "qdrant", "weaviate"],
        help="Source vector store type",
    )
    sp.add_argument(
        "--target",
        required=True,
        choices=["faiss", "chroma", "qdrant", "weaviate"],
        help="Target vector store type",
    )
    sp.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to migrate in each batch",
    )
    sp.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation of migrated documents",
    )
    sp.add_argument(
        "--no-backup", action="store_true", help="Skip creating backup of target store"
    )
    sp.add_argument(
        "--report",
        default="migration_report.json",
        help="Path to save migration report",
    )
    sp.add_argument(
        "--resume-from-batch",
        type=int,
        default=0,
        help="Resume migration from specific batch number",
    )
    sp.set_defaults(func=cmd_migrate_store)

    # benchmark-stores
    sp = sub.add_parser("benchmark-stores", help="Benchmark vector store performance")
    sp.add_argument(
        "--stores",
        nargs="+",
        default=["faiss", "chroma", "qdrant"],
        choices=["faiss", "chroma", "qdrant", "weaviate"],
        help="Store types to benchmark",
    )
    sp.add_argument(
        "--documents", type=int, default=1000, help="Number of documents to test with"
    )
    sp.add_argument("--dimension", type=int, default=1536, help="Embedding dimension")
    sp.add_argument(
        "--output", default="benchmark_results.json", help="Output file for results"
    )
    sp.add_argument(
        "--report",
        default="benchmark_report.txt",
        help="Output file for human-readable report",
    )
    sp.set_defaults(func=cmd_benchmark_stores)

    # config-migrate
    sp = sub.add_parser(
        "config-migrate", help="Migrate .env vector-store keys to new schema"
    )
    sp.add_argument("--input", required=True, help="Input .env path")
    sp.add_argument("--output", required=True, help="Output .env path")
    sp.set_defaults(func=lambda a: cmd_config_migrate(a))

    # Security commands
    sp = sub.add_parser("security", help="Security management commands")
    sp.add_argument("--list-keys", action="store_true", help="List encryption keys")
    sp.add_argument("--rotate-keys", action="store_true", help="Rotate encryption keys")
    sp.add_argument("--backup", action="store_true", help="Create encrypted backup")
    sp.add_argument("--restore", help="Restore from backup")
    sp.set_defaults(func=cmd_security)

    # Query commands
    sp = sub.add_parser("query-advanced", help="Advanced query features")
    sp.add_argument("--aggregate", help="Run aggregation query")
    sp.add_argument("--filter", help="Apply advanced filters")
    sp.add_argument("--optimize", action="store_true", help="Optimize query")
    sp.set_defaults(func=cmd_query_advanced)

    return p


async def cmd_security(args: argparse.Namespace) -> int:
    """Security management commands"""
    try:
        if args.list_keys:
            key_manager = KeyManager()
            keys = await key_manager.list_keys()
            print("Encryption Keys:")
            for key in keys:
                print(f"  - {key['key_id']}: {key['algorithm']} ({key['status']})")
            return 0

        elif args.rotate_keys:
            encryption_manager = EncryptionManager()
            result = await encryption_manager.rotate_encryption_keys()
            if result.success:
                print(
                    f"Key rotation successful: {result.old_key_id} -> {result.new_key_id}"
                )
                return 0
            else:
                print(f"Key rotation failed: {result.errors}")
                return 1

        elif args.backup:
            rag = await _get_rag_service()
            backup_manager = SecureBackupManager()
            result = await backup_manager.create_encrypted_backup([rag.vector_store])
            if result.status.value == "completed":
                print(f"Backup created: {result.backup_id}")
                return 0
            else:
                print(f"Backup failed: {result.errors}")
                return 1

        elif args.restore:
            backup_manager = SecureBackupManager()
            result = await backup_manager.restore_from_backup(args.restore)
            if result.status == "completed":
                print(f"Restore completed: {result.restore_id}")
                return 0
            else:
                print(f"Restore failed: {result.errors}")
                return 1

        else:
            print("Please specify a security action")
            return 1

    except Exception as e:
        print(f"Security command error: {e}")
        return 1


async def cmd_query_advanced(args: argparse.Namespace) -> int:
    """Advanced query features"""
    try:
        rag = await _get_rag_service()

        if args.aggregate:
            aggregator = QueryAggregator()
            # Example aggregation query
            result = await aggregator.group_by_metadata(
                rag.vector_store, group_by="category", filters={"status": "active"}
            )
            print(f"Aggregation result: {result}")
            return 0

        elif args.filter:
            advanced_filter = AdvancedFilter()
            # Example advanced filter
            result = await advanced_filter.range_filter(
                rag.vector_store, field="score", min_value=0.8, max_value=1.0
            )
            print(f"Filtered documents: {len(result)}")
            return 0

        elif args.optimize:
            optimizer = QueryOptimizer()
            # Example query optimization
            stats = optimizer.get_optimization_statistics()
            print(f"Optimization statistics: {stats}")
            return 0

        else:
            print("Please specify a query action")
            return 1

    except Exception as e:
        print(f"Query command error: {e}")
        return 1



def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser"""
    parser = argparse.ArgumentParser(
        prog="ragbot-cli", description="RAG Telegram Assistant CLI"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    parser_status = subparsers.add_parser("status", help="Show system status")
    parser_status.set_defaults(func=cmd_status, cmd="status")

    # Performance command
    parser_perf = subparsers.add_parser("performance", help="Show performance metrics")
    parser_perf.set_defaults(func=cmd_performance, cmd="performance")

    # Reset command
    parser_reset = subparsers.add_parser("reset", help="Reset vector store")
    parser_reset.set_defaults(func=cmd_reset, cmd="reset")

    # Query command
    parser_query = subparsers.add_parser("query", help="Query documents")
    parser_query.add_argument("--question", required=True, help="Question to ask")
    parser_query.add_argument("--lang", default="fa", help="Response language")
    parser_query.add_argument(
        "--top-k", type=int, default=None, help="Number of documents to retrieve"
    )
    parser_query.add_argument(
        "--threshold", type=float, default=None, help="Similarity threshold"
    )
    parser_query.set_defaults(func=cmd_query, cmd="query")

    # Ingest command
    parser_ingest = subparsers.add_parser("ingest", help="Ingest documents")
    parser_ingest.add_argument("--file", help="File path to ingest")
    parser_ingest.add_argument("--url", help="URL to ingest")
    parser_ingest.add_argument("--text", help="Text content to ingest")
    parser_ingest.add_argument("--type", help="Document type (pdf, docx, html, text, etc.)")
    parser_ingest.set_defaults(func=cmd_ingest, cmd="ingest")

    # Batch ingest command
    parser_ingest_batch = subparsers.add_parser(
        "batch-ingest", help="Batch ingest documents"
    )
    parser_ingest_batch.add_argument("--dir", help="Directory to scan")
    parser_ingest_batch.add_argument(
        "--pattern", action="append", help="File pattern to match"
    )
    parser_ingest_batch.add_argument(
        "--recursive", action="store_true", default=True, help="Recurse subdirectories"
    )
    parser_ingest_batch.add_argument(
        "--no-recursive", action="store_true", help="Do not recurse subdirectories"
    )
    parser_ingest_batch.add_argument(
        "--include-txt", action="store_true", help="Include text files"
    )
    parser_ingest_batch.add_argument(
        "--include-docx", action="store_true", help="Include Word documents"
    )
    parser_ingest_batch.add_argument(
        "--type", help="File type filter"
    )
    parser_ingest_batch.add_argument(
        "--max-concurrency", type=int, default=4, help="Maximum concurrent ingestions"
    )
    parser_ingest_batch.add_argument(
        "sources", nargs="*", default=[], help="Individual file sources to ingest"
    )
    parser_ingest_batch.set_defaults(func=cmd_batch_ingest, cmd="batch-ingest")

    # Security command
    parser_security = subparsers.add_parser("security", help="Security operations")
    parser_security.add_argument(
        "action", choices=["backup", "restore", "rotate-keys"], help="Security action"
    )
    parser_security.add_argument("--backup-path", help="Backup file path (for restore)")
    parser_security.set_defaults(func=cmd_security, cmd="security")

    # Query Advanced command
    parser_query_advanced = subparsers.add_parser(
        "query-advanced", help="Advanced queries"
    )
    parser_query_advanced.add_argument(
        "--aggregate", action="store_true", help="Run aggregation query"
    )
    parser_query_advanced.add_argument(
        "--filter", action="store_true", help="Run advanced filter"
    )
    parser_query_advanced.add_argument(
        "--optimize", action="store_true", help="Run query optimization"
    )
    parser_query_advanced.add_argument(
        "--score", action="store_true", help="Run custom scoring"
    )
    parser_query_advanced.set_defaults(func=cmd_query_advanced, cmd="query-advanced")

    # Analytics commands
    parser_analytics = subparsers.add_parser("analytics", help="Analytics commands")
    analytics_sub = parser_analytics.add_subparsers(dest="analytics_cmd", required=True)

    # ML Insights
    parser_ml_insights = analytics_sub.add_parser("ml-insights", help="Get ML insights")
    parser_ml_insights.set_defaults(func=cmd_ml_insights)

    # Predictive Analytics
    parser_predictive = analytics_sub.add_parser(
        "predictive", help="Get predictive analytics"
    )
    parser_predictive.set_defaults(func=cmd_predictive_analytics)

    # User Analytics
    parser_user_analytics = analytics_sub.add_parser("user", help="Get user analytics")
    parser_user_analytics.add_argument("--user-id", required=True, help="User ID")
    parser_user_analytics.set_defaults(func=cmd_user_analytics)

    # Comprehensive Report
    parser_comprehensive = analytics_sub.add_parser(
        "comprehensive", help="Get comprehensive analytics report"
    )
    parser_comprehensive.add_argument(
        "--days", type=int, default=30, help="Number of days"
    )
    parser_comprehensive.set_defaults(func=cmd_comprehensive_analytics)

    return parser


# Analytics command functions
async def cmd_ml_insights(args) -> int:
    """Get ML insights"""
    try:
        service = await _get_rag_service()
        insights = await service.get_ml_insights()

        print("🤖 ML Insights:")
        print(json.dumps(insights, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        logger.error(f"Error getting ML insights: {e}")
        return 1


async def cmd_predictive_analytics(args) -> int:
    """Get predictive analytics"""
    try:
        service = await _get_rag_service()
        analytics = await service.get_predictive_analytics()

        print("🔮 Predictive Analytics:")
        print(json.dumps(analytics, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        logger.error(f"Error getting predictive analytics: {e}")
        return 1


async def cmd_user_analytics(args) -> int:
    """Get user analytics"""
    try:
        service = await _get_rag_service()
        analytics = await service.get_advanced_user_analytics(args.user_id)

        print(f"👤 User Analytics for {args.user_id}:")
        print(json.dumps(analytics, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        return 1


async def cmd_comprehensive_analytics(args) -> int:
    """Get comprehensive analytics report"""
    try:
        service = await _get_rag_service()
        report = await service.get_comprehensive_analytics_report(args.days)

        print(f"📊 Comprehensive Analytics Report ({args.days} days):")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        logger.error(f"Error getting comprehensive analytics: {e}")
        return 1




def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        exit_code = asyncio.run(args.func(args))
    except KeyboardInterrupt:
        logger.info("Interrupted")
        exit_code = 130
    except Exception as e:  # pragma: no cover
        logger.error(f"CLI error: {e}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
