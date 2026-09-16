"""
Metrics collection and monitoring for RAGBot.

This module provides Prometheus metrics collection for monitoring
system performance, user activity, and error rates.
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


class MetricsManager:
    """
    Centralized metrics collection and management.

    This class provides a unified interface for collecting and exposing
    application metrics using Prometheus when available, with graceful
    degradation when not available.
    """

    def __init__(self) -> None:
        """Initialize metrics manager."""
        self.enabled = PROMETHEUS_AVAILABLE and settings.monitoring.enable_metrics
        self._metrics: Dict[str, Any] = {}
        self._in_memory_metrics: Dict[str, Any] = defaultdict(int)
        self._vector_store_metrics: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
            lambda: defaultdict(
                lambda: {
                    "count": 0,
                    "documents": 0,
                    "errors": 0,
                    "durations": [],
                    "last_error": None,
                    "last_success": None,
                    "last_failure": None,
                    "last_updated": None,
                }
            )
        )

        if self.enabled:
            # Clear any existing metrics from previous instances (for testing)
            self._clear_existing_metrics()
            self._setup_prometheus_metrics()

        logger.info(
            f"Metrics manager initialized (enabled: {self.enabled})",
            prometheus_available=PROMETHEUS_AVAILABLE,
            metrics_enabled=settings.monitoring.enable_metrics,
        )

    def _clear_existing_metrics(self) -> None:
        """Clear existing metrics from registry to prevent duplicates."""
        if not PROMETHEUS_AVAILABLE:
            return

        from prometheus_client import REGISTRY

        # Get list of collectors to remove
        collectors_to_remove = []
        for collector in list(REGISTRY._collector_to_names.keys()):
            names = REGISTRY._collector_to_names.get(collector, set())
            if any(name.startswith("ragbot_") for name in names):
                collectors_to_remove.append(collector)

        # Remove ragbot metrics
        for collector in collectors_to_remove:
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                # Already removed
                pass

    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics collectors."""
        # Application info
        self._metrics["app_info"] = Info(
            "ragbot_app_info", "RAGBot application information"
        )
        self._metrics["app_info"].info(
            {
                "version": "1.0.0",
                "vector_db": settings.vector_db,
                "llm_provider": settings.llm.provider,
                "embedding_provider": settings.embedding.provider,
            }
        )

        # User metrics
        self._metrics["users_total"] = Gauge(
            "ragbot_users_total", "Total number of users"
        )

        self._metrics["active_users"] = Gauge(
            "ragbot_active_users", "Number of active users in the last hour"
        )

        # Document metrics
        self._metrics["documents_processed_total"] = Counter(
            "ragbot_documents_processed_total",
            "Total number of documents processed",
            ["document_type", "status"],
        )

        self._metrics["document_chunks_total"] = Counter(
            "ragbot_document_chunks_total", "Total number of document chunks created"
        )

        self._metrics["document_processing_duration"] = Histogram(
            "ragbot_document_processing_duration_seconds",
            "Time spent processing documents",
            ["document_type"],
        )

        # Query metrics
        self._metrics["queries_total"] = Counter(
            "ragbot_queries_total",
            "Total number of queries processed",
            ["language", "status"],
        )

        self._metrics["query_duration"] = Histogram(
            "ragbot_query_duration_seconds",
            "Time spent processing queries",
            ["language"],
        )

        self._metrics["retrieval_duration"] = Histogram(
            "ragbot_retrieval_duration_seconds", "Time spent on document retrieval"
        )

        self._metrics["llm_duration"] = Histogram(
            "ragbot_llm_duration_seconds", "Time spent on LLM generation"
        )

        # Error metrics
        self._metrics["errors_total"] = Counter(
            "ragbot_errors_total", "Total number of errors", ["error_type", "component"]
        )

        # System metrics
        self._metrics["vector_store_size"] = Gauge(
            "ragbot_vector_store_size", "Number of vectors in the store"
        )

        self._metrics["memory_usage_bytes"] = Gauge(
            "ragbot_memory_usage_bytes", "Memory usage in bytes"
        )

        # Rate limiting metrics
        self._metrics["rate_limit_hits_total"] = Counter(
            "ragbot_rate_limit_hits_total",
            "Total number of rate limit hits",
            ["user_id"],
        )

        # Advanced Retrieval Metrics (Phase 1)
        self._metrics["retrieval_recall_at_1"] = Gauge(
            "ragbot_retrieval_recall_at_1_total",
            "Recall@1 metric for retrieval performance",
        )

        self._metrics["retrieval_recall_at_3"] = Gauge(
            "ragbot_retrieval_recall_at_3_total",
            "Recall@3 metric for retrieval performance",
        )

        self._metrics["retrieval_recall_at_5"] = Gauge(
            "ragbot_retrieval_recall_at_5_total",
            "Recall@5 metric for retrieval performance",
        )

        self._metrics["retrieval_recall_at_10"] = Gauge(
            "ragbot_retrieval_recall_at_10_total",
            "Recall@10 metric for retrieval performance",
        )

        self._metrics["retrieval_recall_by_strategy"] = Gauge(
            "ragbot_retrieval_recall_at_k_by_strategy",
            "Recall@K by chunking strategy",
            ["strategy", "k"],
        )

        self._metrics["retrieval_mrr"] = Gauge(
            "ragbot_retrieval_mrr_total", "Mean Reciprocal Rank for retrieval"
        )

        self._metrics["retrieval_mrr_by_type"] = Gauge(
            "ragbot_retrieval_mrr_by_query_type", "MRR by query type", ["type"]
        )

        self._metrics["retrieval_ndcg_at_5"] = Gauge(
            "ragbot_retrieval_ndcg_at_5_total", "NDCG@5 metric for retrieval"
        )

        self._metrics["retrieval_ndcg_at_10"] = Gauge(
            "ragbot_retrieval_ndcg_at_10_total", "NDCG@10 metric for retrieval"
        )

        self._metrics["retrieval_ndcg_by_strategy"] = Gauge(
            "ragbot_retrieval_ndcg_by_chunking_strategy",
            "NDCG by chunking strategy",
            ["strategy"],
        )

        # Query Expansion Metrics
        self._metrics["query_expansion_recall_delta"] = Histogram(
            "ragbot_query_expansion_recall_delta_total",
            "Recall improvement from query expansion",
            buckets=[-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5, 1.0],
        )

        self._metrics["query_expansion_mrr_improvement"] = Histogram(
            "ragbot_query_expansion_mrr_improvement_total",
            "MRR improvement from query expansion",
            buckets=[-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5, 1.0],
        )

        self._metrics["query_expansion_timeout_rate"] = Counter(
            "ragbot_query_expansion_timeout_rate_total", "Query expansion timeout rate"
        )

        self._metrics["query_expansion_fallback_rate"] = Counter(
            "ragbot_query_expansion_fallback_rate_total",
            "Query expansion fallback rate",
        )

        # Reranker Performance Metrics (Phase 2)
        self._metrics["reranker_latency"] = Histogram(
            "ragbot_reranker_latency_seconds",
            "Reranker processing latency",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )

        self._metrics["reranker_latency_by_model"] = Histogram(
            "ragbot_reranker_latency_by_model_seconds",
            "Reranker latency by model",
            ["model_name"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )

        self._metrics["reranker_timeout_rate"] = Counter(
            "ragbot_reranker_timeout_rate_total", "Reranker timeout rate"
        )

        self._metrics["reranker_fallback_rate"] = Counter(
            "ragbot_reranker_fallback_rate_total", "Reranker fallback rate"
        )

        self._metrics["reranker_batch_size"] = Histogram(
            "ragbot_reranker_batch_size_total",
            "Reranker batch size distribution",
            buckets=[1, 5, 10, 20, 32, 50, 100],
        )

        self._metrics["reranker_quality_score"] = Histogram(
            "ragbot_reranker_quality_score_total",
            "Reranker quality score distribution",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["reranker_quality_by_model"] = Histogram(
            "ragbot_reranker_quality_by_model_total",
            "Reranker quality by model",
            ["model_name"],
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["reranker_model_loading_time"] = Histogram(
            "ragbot_reranker_model_loading_time_seconds",
            "Reranker model loading time",
            ["model_name"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
        )

        self._metrics["reranker_cache_hit_rate"] = Gauge(
            "ragbot_reranker_cache_hit_rate_total", "Reranker cache hit rate"
        )

        self._metrics["reranker_throughput"] = Gauge(
            "ragbot_reranker_throughput_docs_per_second",
            "Reranker throughput in documents per second",
        )

        # Cache Analytics Metrics (Phase 3)
        self._metrics["cache_hit_rate"] = Gauge(
            "ragbot_cache_hit_rate_total", "Cache hit rate percentage"
        )

        self._metrics["cache_miss_rate"] = Gauge(
            "ragbot_cache_miss_rate_total", "Cache miss rate percentage"
        )

        self._metrics["cache_size"] = Gauge(
            "ragbot_cache_size_total", "Current cache size in entries"
        )

        self._metrics["cache_memory_usage"] = Gauge(
            "ragbot_cache_memory_usage_bytes", "Cache memory usage in bytes"
        )

        self._metrics["cache_eviction_rate"] = Counter(
            "ragbot_cache_eviction_rate_total", "Cache eviction rate"
        )

        self._metrics["cache_access_frequency"] = Histogram(
            "ragbot_cache_access_frequency_total",
            "Cache access frequency distribution",
            buckets=[1, 5, 10, 20, 50, 100, 200],
        )

        self._metrics["cache_confidence_score"] = Histogram(
            "ragbot_cache_confidence_score_total",
            "Cache confidence score distribution",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["cache_deduplication_ratio"] = Gauge(
            "ragbot_cache_deduplication_ratio_total", "Cache deduplication ratio"
        )

        self._metrics["cache_similarity_threshold"] = Gauge(
            "ragbot_cache_similarity_threshold_total", "Cache similarity threshold"
        )

        self._metrics["cache_ttl_expired"] = Counter(
            "ragbot_cache_ttl_expired_total", "Cache entries expired due to TTL"
        )

        self._metrics["cache_embedding_generation_time"] = Histogram(
            "ragbot_cache_embedding_generation_time_seconds",
            "Time spent generating embeddings for cache",
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
        )

        self._metrics["cache_similarity_computation_time"] = Histogram(
            "ragbot_cache_similarity_computation_time_seconds",
            "Time spent computing similarities",
            buckets=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2],
        )

        # Quality & Confidence Metrics (Phase 4)
        self._metrics["answer_confidence_score"] = Histogram(
            "ragbot_answer_confidence_score_total",
            "Answer confidence score distribution",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["answer_confidence_by_model"] = Histogram(
            "ragbot_answer_confidence_by_model_total",
            "Answer confidence score by LLM model",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
            labelnames=["model_name"],
        )

        self._metrics["response_quality_score"] = Histogram(
            "ragbot_response_quality_score_total",
            "Response quality score distribution",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["response_accuracy"] = Histogram(
            "ragbot_response_accuracy_total",
            "Response accuracy score",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["user_satisfaction_score"] = Histogram(
            "ragbot_user_satisfaction_score_total",
            "User satisfaction score distribution",
            buckets=[1.0, 2.0, 3.0, 4.0, 5.0],
        )

        self._metrics["content_relevance_score"] = Histogram(
            "ragbot_content_relevance_score_total",
            "Content relevance score",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["low_confidence_responses"] = Counter(
            "ragbot_low_confidence_responses_total",
            "Number of responses below confidence threshold",
        )

        self._metrics["high_quality_responses"] = Counter(
            "ragbot_high_quality_responses_total",
            "Number of high quality responses",
        )

        self._metrics["response_length_distribution"] = Histogram(
            "ragbot_response_length_distribution_total",
            "Response length distribution",
            buckets=[10, 50, 100, 200, 500, 1000, 2000],
        )

        self._metrics["context_utilization_ratio"] = Histogram(
            "ragbot_context_utilization_ratio_total",
            "Context utilization ratio",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["answer_completeness_score"] = Histogram(
            "ragbot_answer_completeness_score_total",
            "Answer completeness score",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["factual_accuracy_score"] = Histogram(
            "ragbot_factual_accuracy_score_total",
            "Factual accuracy score",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self._metrics["response_coherence_score"] = Histogram(
            "ragbot_response_coherence_score_total",
            "Response coherence score",
            buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        # System Performance & Resource Metrics (Phase 5)
        self._metrics["system_cpu_usage"] = Gauge(
            "ragbot_system_cpu_usage_percent",
            "System CPU usage percentage",
        )

        self._metrics["system_memory_usage"] = Gauge(
            "ragbot_system_memory_usage_bytes",
            "System memory usage in bytes",
        )

        self._metrics["system_memory_percent"] = Gauge(
            "ragbot_system_memory_usage_percent",
            "System memory usage percentage",
        )

        self._metrics["system_disk_usage"] = Gauge(
            "ragbot_system_disk_usage_bytes",
            "System disk usage in bytes",
        )

        self._metrics["system_disk_percent"] = Gauge(
            "ragbot_system_disk_usage_percent",
            "System disk usage percentage",
        )

        self._metrics["system_network_latency"] = Histogram(
            "ragbot_system_network_latency_seconds",
            "System network latency in seconds",
            buckets=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5],
        )

        self._metrics["system_response_time"] = Histogram(
            "ragbot_system_response_time_seconds",
            "System response time in seconds",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        self._metrics["system_throughput"] = Gauge(
            "ragbot_system_throughput_requests_per_second",
            "System throughput in requests per second",
        )

        self._metrics["system_concurrent_users"] = Gauge(
            "ragbot_system_concurrent_users_total",
            "Number of concurrent users",
        )

        self._metrics["system_queue_length"] = Gauge(
            "ragbot_system_queue_length_total",
            "System queue length",
        )

        self._metrics["system_error_rate"] = Gauge(
            "ragbot_system_error_rate_percent",
            "System error rate percentage",
        )

        self._metrics["system_gpu_usage"] = Gauge(
            "ragbot_system_gpu_usage_percent",
            "System GPU usage percentage",
        )

        self._metrics["system_gpu_memory"] = Gauge(
            "ragbot_system_gpu_memory_usage_bytes",
            "System GPU memory usage in bytes",
        )

    def start_metrics_server(self) -> None:
        """Start Prometheus metrics HTTP server."""
        if not self.enabled:
            logger.warning(
                "Metrics server not started - Prometheus not available or disabled"
            )
            return

        try:
            start_http_server(settings.monitoring.metrics_port)
            logger.info(
                f"Metrics server started on port {settings.monitoring.metrics_port}",
                port=settings.monitoring.metrics_port,
            )
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    def record_user_activity(self, user_id: int) -> None:
        """Record user activity."""
        if self.enabled:
            # This would typically update active users gauge
            # For now, we'll increment in-memory counter
            pass

        self._in_memory_metrics["user_activity"] += 1
        logger.debug("User activity recorded", user_id=user_id)

    def record_document_processing(
        self,
        document_type: str,
        status: str = "success",
        duration: Optional[float] = None,
        chunk_count: Optional[int] = None,
    ) -> None:
        """
        Record document processing metrics.

        Args:
            document_type: Type of document (pdf, url, text)
            status: Processing status (success, error)
            duration: Processing duration in seconds
            chunk_count: Number of chunks created
        """
        if self.enabled:
            self._metrics["documents_processed_total"].labels(
                document_type=document_type, status=status
            ).inc()

            if duration is not None:
                self._metrics["document_processing_duration"].labels(
                    document_type=document_type
                ).observe(duration)

            if chunk_count is not None:
                self._metrics["document_chunks_total"].inc(chunk_count)

        self._in_memory_metrics[f"documents_{status}"] += 1

        logger.log_structured(
            "info",
            "document_processed",
            document_type=document_type,
            status=status,
            duration=duration,
            chunk_count=chunk_count,
        )

    def record_query_processing(
        self,
        language: str,
        status: str = "success",
        total_duration: Optional[float] = None,
        retrieval_duration: Optional[float] = None,
        llm_duration: Optional[float] = None,
    ) -> None:
        """
        Record query processing metrics.

        Args:
            language: Query language (fa, en)
            status: Processing status (success, error)
            total_duration: Total processing duration
            retrieval_duration: Retrieval duration
            llm_duration: LLM generation duration
        """
        if self.enabled:
            self._metrics["queries_total"].labels(
                language=language, status=status
            ).inc()

            if total_duration is not None:
                self._metrics["query_duration"].labels(language=language).observe(
                    total_duration
                )

            if retrieval_duration is not None:
                self._metrics["retrieval_duration"].observe(retrieval_duration)

            if llm_duration is not None:
                self._metrics["llm_duration"].observe(llm_duration)

        self._in_memory_metrics[f"queries_{status}"] += 1

        logger.log_performance(
            "query_processing",
            total_duration or 0,
            language=language,
            status=status,
            retrieval_duration=retrieval_duration,
            llm_duration=llm_duration,
        )

    def record_error(self, error_type: str, component: str) -> None:
        """
        Record error occurrence.

        Args:
            error_type: Type of error
            component: Component where error occurred
        """
        if self.enabled:
            self._metrics["errors_total"].labels(
                error_type=error_type, component=component
            ).inc()

        self._in_memory_metrics["errors"] += 1

        logger.log_structured(
            "error", "error_recorded", error_type=error_type, component=component
        )

    def record_rate_limit_hit(self, user_id: int) -> None:
        """Record rate limit hit."""
        if self.enabled:
            self._metrics["rate_limit_hits_total"].labels(user_id=str(user_id)).inc()

        self._in_memory_metrics["rate_limit_hits"] += 1

        logger.log_structured("warning", "rate_limit_hit", user_id=user_id)

    def update_vector_store_size(self, size: int, store_type: Optional[str] = None) -> None:
        """Update vector store size metric."""
        key = "vector_store_size" if store_type is None else f"vector_store_size::{store_type}"
        if self.enabled and store_type is None and "vector_store_size" in self._metrics:
            self._metrics["vector_store_size"].set(size)

        self._in_memory_metrics[key] = size

    def record_vector_store_operation(
        self,
        operation: str,
        store_type: str,
        *,
        document_count: int = 0,
        success: bool = True,
        error: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> None:
        data = self._vector_store_metrics[store_type][operation]
        data["count"] += 1
        if document_count:
            data["documents"] += max(document_count, 0)
        if not success:
            data["errors"] += 1
            data["last_error"] = error
            data["last_failure"] = time.time()
        else:
            data["last_success"] = time.time()
        if duration is not None:
            try:
                data["durations"].append(float(duration))
            except (TypeError, ValueError):
                pass
            if len(data["durations"]) > 1000:
                data["durations"] = data["durations"][-1000:]
        data["last_updated"] = time.time()

    def get_vector_store_metrics(self, store_type: Optional[str] = None) -> Dict[str, Any]:
        """Return aggregated vector store metrics."""

        def _summarize(st: str) -> Dict[str, Any]:
            operations: Dict[str, Any] = {}
            for op, stats in self._vector_store_metrics.get(st, {}).items():
                count = stats.get("count", 0)
                documents = stats.get("documents", 0)
                durations = stats.get("durations", [])
                avg_docs = (documents / count) if count else None
                avg_duration = (
                    float(sum(durations) / len(durations))
                    if durations and len(durations) > 0
                    else None
                )
                operations[op] = {
                    "count": count,
                    "documents": documents,
                    "avg_documents": avg_docs,
                    "errors": stats.get("errors", 0),
                    "avg_duration": avg_duration,
                    "last_success": stats.get("last_success"),
                    "last_failure": stats.get("last_failure"),
                    "last_error": stats.get("last_error"),
                    "last_updated": stats.get("last_updated"),
                }
            size_key = f"vector_store_size::{st}"
            size = self._in_memory_metrics.get(size_key)
            last_updated = None
            if operations:
                last_updated = max(
                    (op_stats.get("last_updated") or 0) for op_stats in operations.values()
                )
            return {
                "store_type": st,
                "size": size,
                "operations": operations,
                "last_updated": last_updated,
            }

        if store_type:
            return _summarize(store_type)
        return {st: _summarize(st) for st in self._vector_store_metrics.keys()}

    def update_memory_usage(self, bytes_used: int) -> None:
        """Update memory usage metric."""
        if self.enabled:
            self._metrics["memory_usage_bytes"].set(bytes_used)

        self._in_memory_metrics["memory_usage"] = bytes_used

    @contextmanager
    def time_operation(self, operation_name: str, **labels: str):
        """
        Context manager for timing operations.

        Args:
            operation_name: Name of the operation
            **labels: Additional labels for the metric
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time

            if self.enabled and operation_name in self._metrics:
                metric = self._metrics[operation_name]
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

            logger.log_performance(operation_name, duration, **labels)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        if self.enabled:
            # In a real implementation, you'd collect current values from Prometheus
            return {
                "status": "prometheus_enabled",
                "metrics_port": settings.monitoring.metrics_port,
            }
        else:
            return {
                "status": "in_memory_only",
                "metrics": dict(self._in_memory_metrics),
            }

    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status."""
        return {
            "metrics_enabled": self.enabled,
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "metrics_port": settings.monitoring.metrics_port if self.enabled else None,
            "total_metrics_collected": len(self._in_memory_metrics),
        }


class RetrievalEvaluator:
    """
    Advanced retrieval evaluation metrics calculator.

    This class provides comprehensive evaluation metrics for retrieval performance
    including Recall@K, MRR, NDCG, and query expansion effectiveness.
    """

    def __init__(self):
        """Initialize retrieval evaluator."""
        self.ground_truth_cache: Dict[str, List[str]] = {}
        self.evaluation_history: List[Dict[str, Any]] = []

    def calculate_recall_at_k(
        self, retrieved_docs: List[str], relevant_docs: List[str], k: int
    ) -> float:
        """
        Calculate Recall@K metric.

        Args:
            retrieved_docs: List of retrieved document IDs
            relevant_docs: List of relevant document IDs
            k: Number of top documents to consider

        Returns:
            Recall@K score (0.0 to 1.0)
        """
        if not relevant_docs:
            return 0.0

        retrieved_top_k = retrieved_docs[:k]
        relevant_retrieved = set(retrieved_top_k) & set(relevant_docs)

        recall = len(relevant_retrieved) / len(relevant_docs)

        logger.debug(
            f"Recall@{k} calculated",
            retrieved_count=len(retrieved_top_k),
            relevant_count=len(relevant_docs),
            intersection_count=len(relevant_retrieved),
            recall_score=recall,
        )

        return recall

    def calculate_mrr(
        self, retrieved_docs: List[str], relevant_docs: List[str]
    ) -> float:
        """
        Calculate Mean Reciprocal Rank.

        Args:
            retrieved_docs: List of retrieved document IDs
            relevant_docs: List of relevant document IDs

        Returns:
            MRR score (0.0 to 1.0)
        """
        if not relevant_docs:
            return 0.0

        relevant_set = set(relevant_docs)

        for rank, doc_id in enumerate(retrieved_docs, 1):
            if doc_id in relevant_set:
                mrr = 1.0 / rank

                logger.debug("MRR calculated", first_relevant_rank=rank, mrr_score=mrr)

                return mrr

        return 0.0

    def calculate_ndcg_at_k(
        self, retrieved_docs: List[str], relevant_docs: List[str], k: int
    ) -> float:
        """
        Calculate NDCG@K metric.

        Args:
            retrieved_docs: List of retrieved document IDs
            relevant_docs: List of relevant document IDs
            k: Number of top documents to consider

        Returns:
            NDCG@K score (0.0 to 1.0)
        """
        if not relevant_docs:
            return 0.0

        # Create relevance scores (binary for simplicity)
        retrieved_top_k = retrieved_docs[:k]
        relevance_scores = [
            1.0 if doc in relevant_docs else 0.0 for doc in retrieved_top_k
        ]

        # Calculate DCG
        dcg = 0.0
        for i, score in enumerate(relevance_scores):
            dcg += score / np.log2(i + 2)  # i+2 because log2(1) = 0

        # Calculate IDCG (ideal DCG)
        ideal_scores = [1.0] * min(len(relevant_docs), k)
        idcg = 0.0
        for i, score in enumerate(ideal_scores):
            idcg += score / np.log2(i + 2)

        # Calculate NDCG
        ndcg = dcg / idcg if idcg > 0 else 0.0

        logger.debug(f"NDCG@{k} calculated", dcg=dcg, idcg=idcg, ndcg_score=ndcg)

        return ndcg

    def evaluate_query_expansion(
        self,
        original_query: str,
        expanded_query: str,
        original_results: List[str],
        expanded_results: List[str],
        relevant_docs: List[str],
    ) -> Dict[str, float]:
        """
        Evaluate query expansion effectiveness.

        Args:
            original_query: Original query string
            expanded_query: Expanded query string
            original_results: Results from original query
            expanded_results: Results from expanded query
            relevant_docs: Ground truth relevant documents

        Returns:
            Dictionary with evaluation metrics
        """
        # Calculate metrics for both queries
        original_recall_5 = self.calculate_recall_at_k(
            original_results, relevant_docs, 5
        )
        expanded_recall_5 = self.calculate_recall_at_k(
            expanded_results, relevant_docs, 5
        )

        original_mrr = self.calculate_mrr(original_results, relevant_docs)
        expanded_mrr = self.calculate_mrr(expanded_results, relevant_docs)

        original_ndcg_10 = self.calculate_ndcg_at_k(original_results, relevant_docs, 10)
        expanded_ndcg_10 = self.calculate_ndcg_at_k(expanded_results, relevant_docs, 10)

        # Calculate improvements
        recall_delta = expanded_recall_5 - original_recall_5
        mrr_improvement = expanded_mrr - original_mrr
        ndcg_improvement = expanded_ndcg_10 - original_ndcg_10

        evaluation = {
            "original_recall_5": original_recall_5,
            "expanded_recall_5": expanded_recall_5,
            "recall_delta": recall_delta,
            "original_mrr": original_mrr,
            "expanded_mrr": expanded_mrr,
            "mrr_improvement": mrr_improvement,
            "original_ndcg_10": original_ndcg_10,
            "expanded_ndcg_10": expanded_ndcg_10,
            "ndcg_improvement": ndcg_improvement,
            "improvement_ratio": recall_delta / original_recall_5
            if original_recall_5 > 0
            else 0.0,
        }

        # Store evaluation history
        self.evaluation_history.append(
            {
                "timestamp": time.time(),
                "original_query": original_query,
                "expanded_query": expanded_query,
                "evaluation": evaluation,
            }
        )

        logger.info(
            "Query expansion evaluation completed",
            recall_delta=recall_delta,
            mrr_improvement=mrr_improvement,
            ndcg_improvement=ndcg_improvement,
        )

        return evaluation

    def record_evaluation_metrics(
        self, metrics_manager: "MetricsManager", evaluation: Dict[str, float]
    ) -> None:
        """
        Record evaluation metrics to Prometheus.

        Args:
            metrics_manager: MetricsManager instance
            evaluation: Evaluation results dictionary
        """
        if not metrics_manager.enabled:
            return

        # Record Recall@K metrics
        metrics_manager._metrics["retrieval_recall_at_1"].set(
            evaluation.get("recall_at_1", 0.0)
        )
        metrics_manager._metrics["retrieval_recall_at_3"].set(
            evaluation.get("recall_at_3", 0.0)
        )
        metrics_manager._metrics["retrieval_recall_at_5"].set(
            evaluation.get("recall_at_5", 0.0)
        )
        metrics_manager._metrics["retrieval_recall_at_10"].set(
            evaluation.get("recall_at_10", 0.0)
        )

        # Record MRR
        metrics_manager._metrics["retrieval_mrr"].set(evaluation.get("mrr", 0.0))

        # Record NDCG
        metrics_manager._metrics["retrieval_ndcg_at_5"].set(
            evaluation.get("ndcg_at_5", 0.0)
        )
        metrics_manager._metrics["retrieval_ndcg_at_10"].set(
            evaluation.get("ndcg_at_10", 0.0)
        )

        # Record query expansion metrics
        metrics_manager._metrics["query_expansion_recall_delta"].observe(
            evaluation.get("recall_delta", 0.0)
        )
        metrics_manager._metrics["query_expansion_mrr_improvement"].observe(
            evaluation.get("mrr_improvement", 0.0)
        )

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """Get summary of evaluation history."""
        if not self.evaluation_history:
            return {"total_evaluations": 0}

        recent_evaluations = self.evaluation_history[-100:]  # Last 100 evaluations

        avg_recall_delta = np.mean(
            [e["evaluation"]["recall_delta"] for e in recent_evaluations]
        )
        avg_mrr_improvement = np.mean(
            [e["evaluation"]["mrr_improvement"] for e in recent_evaluations]
        )
        avg_ndcg_improvement = np.mean(
            [e["evaluation"]["ndcg_improvement"] for e in recent_evaluations]
        )

        return {
            "total_evaluations": len(self.evaluation_history),
            "recent_evaluations": len(recent_evaluations),
            "avg_recall_delta": avg_recall_delta,
            "avg_mrr_improvement": avg_mrr_improvement,
            "avg_ndcg_improvement": avg_ndcg_improvement,
            "improvement_rate": len(
                [e for e in recent_evaluations if e["evaluation"]["recall_delta"] > 0]
            )
            / len(recent_evaluations),
        }


# Global metrics manager instance
metrics_manager = MetricsManager()

# Global retrieval evaluator instance
retrieval_evaluator = RetrievalEvaluator()


class RerankerEvaluator:
    """
    Advanced reranker evaluation metrics calculator.

    This class provides comprehensive evaluation metrics for reranker performance
    including latency, quality scores, timeout rates, and throughput analysis.
    """

    def __init__(self):
        """Initialize reranker evaluator."""
        self.performance_history: List[Dict[str, Any]] = []
        self.model_performance: Dict[str, List[Dict[str, Any]]] = {}
        self.cache_stats = {"hits": 0, "misses": 0}

    def record_reranking_performance(
        self,
        model_name: str,
        latency: float,
        batch_size: int,
        quality_scores: List[float],
        cache_hit: bool = False,
        timeout: bool = False,
        fallback: bool = False,
    ) -> None:
        """
        Record reranking performance metrics.

        Args:
            model_name: Name of the reranker model
            latency: Processing latency in seconds
            batch_size: Number of documents processed
            quality_scores: List of quality scores for documents
            cache_hit: Whether result was from cache
            timeout: Whether operation timed out
            fallback: Whether fallback method was used
        """
        performance_data = {
            "timestamp": time.time(),
            "model_name": model_name,
            "latency": latency,
            "batch_size": batch_size,
            "quality_scores": quality_scores,
            "avg_quality": np.mean(quality_scores) if quality_scores else 0.0,
            "max_quality": np.max(quality_scores) if quality_scores else 0.0,
            "min_quality": np.min(quality_scores) if quality_scores else 0.0,
            "cache_hit": cache_hit,
            "timeout": timeout,
            "fallback": fallback,
            "throughput": batch_size / latency if latency > 0 else 0.0,
        }

        # Store performance history
        self.performance_history.append(performance_data)

        # Store model-specific performance
        if model_name not in self.model_performance:
            self.model_performance[model_name] = []
        self.model_performance[model_name].append(performance_data)

        # Update cache stats
        if cache_hit:
            self.cache_stats["hits"] += 1
        else:
            self.cache_stats["misses"] += 1

        logger.debug(
            "Reranker performance recorded",
            model_name=model_name,
            latency=latency,
            batch_size=batch_size,
            avg_quality=performance_data["avg_quality"],
            throughput=performance_data["throughput"],
        )

    def record_model_loading_time(self, model_name: str, loading_time: float) -> None:
        """
        Record model loading time.

        Args:
            model_name: Name of the model
            loading_time: Time taken to load the model in seconds
        """
        logger.info(
            "Model loading time recorded",
            model_name=model_name,
            loading_time=loading_time,
        )

    def calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        return self.cache_stats["hits"] / total if total > 0 else 0.0

    def calculate_average_throughput(self, model_name: Optional[str] = None) -> float:
        """
        Calculate average throughput.

        Args:
            model_name: Specific model name, or None for all models

        Returns:
            Average throughput in documents per second
        """
        if model_name:
            performances = self.model_performance.get(model_name, [])
        else:
            performances = self.performance_history

        if not performances:
            return 0.0

        throughputs = [p["throughput"] for p in performances if p["throughput"] > 0]
        return np.mean(throughputs) if throughputs else 0.0

    def calculate_average_latency(self, model_name: Optional[str] = None) -> float:
        """
        Calculate average latency.

        Args:
            model_name: Specific model name, or None for all models

        Returns:
            Average latency in seconds
        """
        if model_name:
            performances = self.model_performance.get(model_name, [])
        else:
            performances = self.performance_history

        if not performances:
            return 0.0

        latencies = [p["latency"] for p in performances]
        return np.mean(latencies)

    def calculate_average_quality(self, model_name: Optional[str] = None) -> float:
        """
        Calculate average quality score.

        Args:
            model_name: Specific model name, or None for all models

        Returns:
            Average quality score
        """
        if model_name:
            performances = self.model_performance.get(model_name, [])
        else:
            performances = self.performance_history

        if not performances:
            return 0.0

        qualities = [p["avg_quality"] for p in performances]
        return np.mean(qualities)

    def calculate_timeout_rate(self, model_name: Optional[str] = None) -> float:
        """
        Calculate timeout rate.

        Args:
            model_name: Specific model name, or None for all models

        Returns:
            Timeout rate (0.0 to 1.0)
        """
        if model_name:
            performances = self.model_performance.get(model_name, [])
        else:
            performances = self.performance_history

        if not performances:
            return 0.0

        timeouts = sum(1 for p in performances if p["timeout"])
        return timeouts / len(performances)

    def calculate_fallback_rate(self, model_name: Optional[str] = None) -> float:
        """
        Calculate fallback rate.

        Args:
            model_name: Specific model name, or None for all models

        Returns:
            Fallback rate (0.0 to 1.0)
        """
        if model_name:
            performances = self.model_performance.get(model_name, [])
        else:
            performances = self.performance_history

        if not performances:
            return 0.0

        fallbacks = sum(1 for p in performances if p["fallback"])
        return fallbacks / len(performances)

    def record_evaluation_metrics(
        self, metrics_manager: "MetricsManager", performance_data: Dict[str, Any]
    ) -> None:
        """
        Record evaluation metrics to Prometheus.

        Args:
            metrics_manager: MetricsManager instance
            performance_data: Performance data dictionary
        """
        if not metrics_manager.enabled:
            return

        model_name = performance_data.get("model_name", "unknown")
        latency = performance_data.get("latency", 0.0)
        batch_size = performance_data.get("batch_size", 0)
        avg_quality = performance_data.get("avg_quality", 0.0)
        timeout = performance_data.get("timeout", False)
        fallback = performance_data.get("fallback", False)

        # Record latency metrics
        metrics_manager._metrics["reranker_latency"].observe(latency)
        metrics_manager._metrics["reranker_latency_by_model"].labels(
            model_name=model_name
        ).observe(latency)

        # Record batch size
        metrics_manager._metrics["reranker_batch_size"].observe(batch_size)

        # Record quality metrics
        metrics_manager._metrics["reranker_quality_score"].observe(avg_quality)
        metrics_manager._metrics["reranker_quality_by_model"].labels(
            model_name=model_name
        ).observe(avg_quality)

        # Record timeout and fallback rates
        if timeout:
            metrics_manager._metrics["reranker_timeout_rate"].inc()
        if fallback:
            metrics_manager._metrics["reranker_fallback_rate"].inc()

        # Record cache hit rate
        cache_hit_rate = self.calculate_cache_hit_rate()
        metrics_manager._metrics["reranker_cache_hit_rate"].set(cache_hit_rate)

        # Record throughput
        throughput = batch_size / latency if latency > 0 else 0.0
        metrics_manager._metrics["reranker_throughput"].set(throughput)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.performance_history:
            return {
                "total_operations": 0,
                "models_used": [],
                "cache_hit_rate": 0.0,
                "average_throughput": 0.0,
                "average_latency": 0.0,
                "average_quality": 0.0,
                "timeout_rate": 0.0,
                "fallback_rate": 0.0,
            }

        recent_performances = self.performance_history[-100:]  # Last 100 operations

        return {
            "total_operations": len(self.performance_history),
            "recent_operations": len(recent_performances),
            "models_used": list(self.model_performance.keys()),
            "cache_hit_rate": self.calculate_cache_hit_rate(),
            "average_throughput": self.calculate_average_throughput(),
            "average_latency": self.calculate_average_latency(),
            "average_quality": self.calculate_average_quality(),
            "timeout_rate": self.calculate_timeout_rate(),
            "fallback_rate": self.calculate_fallback_rate(),
            "model_performance": {
                model: {
                    "operations": len(perfs),
                    "avg_latency": self.calculate_average_latency(model),
                    "avg_quality": self.calculate_average_quality(model),
                    "avg_throughput": self.calculate_average_throughput(model),
                    "timeout_rate": self.calculate_timeout_rate(model),
                    "fallback_rate": self.calculate_fallback_rate(model),
                }
                for model, perfs in self.model_performance.items()
            },
        }


# Global reranker evaluator instance
reranker_evaluator = RerankerEvaluator()


class CacheAnalytics:
    """
    Advanced cache analytics and metrics calculator.

    This class provides comprehensive analytics for cache performance
    including hit rates, deduplication ratios, memory usage, and efficiency metrics.
    """

    def __init__(self):
        """Initialize cache analytics."""
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "ttl_expired": 0,
            "total_accesses": 0,
            "embedding_generations": 0,
            "similarity_computations": 0,
        }
        self.cache_history: List[Dict[str, Any]] = []
        self.access_patterns: Dict[str, int] = {}
        self.confidence_scores: List[float] = []
        self.similarity_scores: List[float] = []
        self.memory_usage_history: List[Dict[str, Any]] = []

    def record_cache_hit(
        self, query: str, similarity_score: float, confidence_score: float
    ) -> None:
        """
        Record cache hit event.

        Args:
            query: Query that resulted in cache hit
            similarity_score: Similarity score of the match
            confidence_score: Confidence score of the cached answer
        """
        self.cache_stats["hits"] += 1
        self.cache_stats["total_accesses"] += 1

        # Record access pattern
        self.access_patterns[query] = self.access_patterns.get(query, 0) + 1

        # Record scores
        self.similarity_scores.append(similarity_score)
        self.confidence_scores.append(confidence_score)

        # Record history
        self.cache_history.append(
            {
                "timestamp": time.time(),
                "event": "hit",
                "query": query,
                "similarity_score": similarity_score,
                "confidence_score": confidence_score,
            }
        )

        logger.debug(
            "Cache hit recorded",
            query=query,
            similarity_score=similarity_score,
            confidence_score=confidence_score,
        )

    def record_cache_miss(self, query: str) -> None:
        """
        Record cache miss event.

        Args:
            query: Query that resulted in cache miss
        """
        self.cache_stats["misses"] += 1
        self.cache_stats["total_accesses"] += 1

        # Record history
        self.cache_history.append(
            {"timestamp": time.time(), "event": "miss", "query": query}
        )

        logger.debug("Cache miss recorded", query=query)

    def record_cache_eviction(
        self, evicted_query: str, reason: str = "size_limit"
    ) -> None:
        """
        Record cache eviction event.

        Args:
            evicted_query: Query that was evicted
            reason: Reason for eviction
        """
        self.cache_stats["evictions"] += 1

        # Record history
        self.cache_history.append(
            {
                "timestamp": time.time(),
                "event": "eviction",
                "query": evicted_query,
                "reason": reason,
            }
        )

        logger.debug("Cache eviction recorded", query=evicted_query, reason=reason)

    def record_ttl_expiration(self, expired_query: str) -> None:
        """
        Record TTL expiration event.

        Args:
            expired_query: Query that expired due to TTL
        """
        self.cache_stats["ttl_expired"] += 1

        # Record history
        self.cache_history.append(
            {"timestamp": time.time(), "event": "ttl_expired", "query": expired_query}
        )

        logger.debug("TTL expiration recorded", query=expired_query)

    def record_embedding_generation_time(self, generation_time: float) -> None:
        """
        Record embedding generation time.

        Args:
            generation_time: Time spent generating embedding in seconds
        """
        self.cache_stats["embedding_generations"] += 1

        logger.debug(
            "Embedding generation time recorded", generation_time=generation_time
        )

    def record_similarity_computation_time(self, computation_time: float) -> None:
        """
        Record similarity computation time.

        Args:
            computation_time: Time spent computing similarity in seconds
        """
        self.cache_stats["similarity_computations"] += 1

        logger.debug(
            "Similarity computation time recorded", computation_time=computation_time
        )

    def record_cache_size(self, size: int) -> None:
        """
        Record current cache size.

        Args:
            size: Current number of entries in cache
        """
        self.memory_usage_history.append(
            {
                "timestamp": time.time(),
                "cache_size": size,
                "hit_rate": self.calculate_hit_rate(),
                "miss_rate": self.calculate_miss_rate(),
            }
        )

        # Keep only recent history (last 1000 entries)
        if len(self.memory_usage_history) > 1000:
            self.memory_usage_history = self.memory_usage_history[-1000:]

    def calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        return self.cache_stats["hits"] / total if total > 0 else 0.0

    def calculate_miss_rate(self) -> float:
        """Calculate cache miss rate."""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        return self.cache_stats["misses"] / total if total > 0 else 0.0

    def calculate_eviction_rate(self) -> float:
        """Calculate cache eviction rate."""
        total_accesses = self.cache_stats["total_accesses"]
        return (
            self.cache_stats["evictions"] / total_accesses
            if total_accesses > 0
            else 0.0
        )

    def calculate_ttl_expiration_rate(self) -> float:
        """Calculate TTL expiration rate."""
        total_accesses = self.cache_stats["total_accesses"]
        return (
            self.cache_stats["ttl_expired"] / total_accesses
            if total_accesses > 0
            else 0.0
        )

    def calculate_average_confidence_score(self) -> float:
        """Calculate average confidence score."""
        return np.mean(self.confidence_scores) if self.confidence_scores else 0.0

    def calculate_average_similarity_score(self) -> float:
        """Calculate average similarity score."""
        return np.mean(self.similarity_scores) if self.similarity_scores else 0.0

    def calculate_deduplication_ratio(self) -> float:
        """
        Calculate deduplication ratio based on access patterns.

        Returns:
            Ratio of unique queries to total queries
        """
        total_queries = len(self.access_patterns)
        total_accesses = sum(self.access_patterns.values())
        return total_queries / total_accesses if total_accesses > 0 else 0.0

    def calculate_memory_efficiency(self) -> float:
        """
        Calculate memory efficiency based on hit rate and memory usage.

        Returns:
            Efficiency score (0.0 to 1.0)
        """
        hit_rate = self.calculate_hit_rate()
        eviction_rate = self.calculate_eviction_rate()

        # Higher hit rate and lower eviction rate = better efficiency
        efficiency = hit_rate * (1.0 - eviction_rate)
        return max(0.0, min(1.0, efficiency))

    def record_evaluation_metrics(
        self, metrics_manager: "MetricsManager", cache_data: Dict[str, Any]
    ) -> None:
        """
        Record evaluation metrics to Prometheus.

        Args:
            metrics_manager: MetricsManager instance
            cache_data: Cache data dictionary
        """
        if not metrics_manager.enabled:
            return

        # Record hit/miss rates
        hit_rate = self.calculate_hit_rate()
        miss_rate = self.calculate_miss_rate()
        metrics_manager._metrics["cache_hit_rate"].set(hit_rate)
        metrics_manager._metrics["cache_miss_rate"].set(miss_rate)

        # Record cache size
        cache_size = cache_data.get("size", 0)
        metrics_manager._metrics["cache_size"].set(cache_size)

        # Record memory usage
        memory_usage = cache_data.get("memory_usage", 0)
        metrics_manager._metrics["cache_memory_usage"].set(memory_usage)

        # Record eviction rate
        eviction_rate = self.calculate_eviction_rate()
        if eviction_rate > 0:
            metrics_manager._metrics["cache_eviction_rate"].inc()

        # Record TTL expiration
        ttl_expired = cache_data.get("ttl_expired", 0)
        if ttl_expired > 0:
            metrics_manager._metrics["cache_ttl_expired"].inc()

        # Record access frequency
        access_frequency = cache_data.get("access_frequency", 0)
        if access_frequency > 0:
            metrics_manager._metrics["cache_access_frequency"].observe(access_frequency)

        # Record confidence scores
        avg_confidence = self.calculate_average_confidence_score()
        if avg_confidence > 0:
            metrics_manager._metrics["cache_confidence_score"].observe(avg_confidence)

        # Record deduplication ratio
        dedup_ratio = self.calculate_deduplication_ratio()
        metrics_manager._metrics["cache_deduplication_ratio"].set(dedup_ratio)

        # Record similarity threshold
        similarity_threshold = cache_data.get("similarity_threshold", 0.8)
        metrics_manager._metrics["cache_similarity_threshold"].set(similarity_threshold)

        # Record timing metrics
        embedding_time = cache_data.get("embedding_generation_time", 0.0)
        if embedding_time > 0:
            metrics_manager._metrics["cache_embedding_generation_time"].observe(
                embedding_time
            )

        similarity_time = cache_data.get("similarity_computation_time", 0.0)
        if similarity_time > 0:
            metrics_manager._metrics["cache_similarity_computation_time"].observe(
                similarity_time
            )

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive cache analytics summary."""
        return {
            "cache_stats": self.cache_stats.copy(),
            "hit_rate": self.calculate_hit_rate(),
            "miss_rate": self.calculate_miss_rate(),
            "eviction_rate": self.calculate_eviction_rate(),
            "ttl_expiration_rate": self.calculate_ttl_expiration_rate(),
            "average_confidence_score": self.calculate_average_confidence_score(),
            "average_similarity_score": self.calculate_average_similarity_score(),
            "deduplication_ratio": self.calculate_deduplication_ratio(),
            "memory_efficiency": self.calculate_memory_efficiency(),
            "total_queries": len(self.access_patterns),
            "unique_queries": len(self.access_patterns),
            "total_accesses": self.cache_stats["total_accesses"],
            "recent_history": self.cache_history[-100:] if self.cache_history else [],
            "memory_usage_trend": self.memory_usage_history[-50:]
            if self.memory_usage_history
            else [],
        }


# Global cache analytics instance
cache_analytics = CacheAnalytics()


class QualityEvaluator:
    """
    Advanced quality and confidence evaluation metrics calculator.

    This class provides comprehensive evaluation metrics for response quality,
    confidence scores, user satisfaction, and content assessment.
    """

    def __init__(self):
        """Initialize quality evaluator."""
        self.quality_history: List[Dict[str, Any]] = []
        self.confidence_scores: List[float] = []
        self.user_feedback: List[Dict[str, Any]] = []
        self.response_metrics: Dict[str, List[float]] = {
            "accuracy": [],
            "relevance": [],
            "completeness": [],
            "coherence": [],
            "factual_accuracy": [],
        }
        self.model_performance: Dict[str, List[Dict[str, Any]]] = {}
        self.quality_stats = {
            "total_responses": 0,
            "high_quality_responses": 0,
            "low_confidence_responses": 0,
            "user_satisfaction_count": 0,
            "average_confidence": 0.0,
            "average_quality": 0.0,
        }

    def record_response_quality(
        self,
        query: str,
        response: str,
        confidence_score: float,
        model_name: str,
        context_used: List[str],
        quality_scores: Dict[str, float],
        user_satisfaction: Optional[int] = None,
    ) -> None:
        """
        Record response quality metrics.

        Args:
            query: Original user query
            response: Generated response
            confidence_score: Confidence score (0.0 to 1.0)
            model_name: Name of the LLM model used
            context_used: List of context chunks used
            quality_scores: Dictionary of quality scores
            user_satisfaction: User satisfaction rating (1-5)
        """
        # Calculate additional metrics
        response_length = len(response.split())
        context_utilization = len(context_used) / max(len(context_used), 1)

        # Record quality data
        quality_data = {
            "timestamp": time.time(),
            "query": query,
            "response": response,
            "confidence_score": confidence_score,
            "model_name": model_name,
            "response_length": response_length,
            "context_utilization": context_utilization,
            "quality_scores": quality_scores,
            "user_satisfaction": user_satisfaction,
            "is_high_quality": self._is_high_quality(confidence_score, quality_scores),
            "is_low_confidence": confidence_score < 0.7,
        }

        # Store in history
        self.quality_history.append(quality_data)

        # Store confidence score
        self.confidence_scores.append(confidence_score)

        # Store user satisfaction if provided
        if user_satisfaction is not None:
            feedback_data = {
                "timestamp": time.time(),
                "query": query,
                "response": response,
                "satisfaction_score": user_satisfaction,
                "feedback_text": None,
            }
            self.user_feedback.append(feedback_data)
            self.quality_stats["user_satisfaction_count"] += 1

        # Store quality scores
        for metric, score in quality_scores.items():
            if metric in self.response_metrics:
                self.response_metrics[metric].append(score)

        # Store model-specific performance
        if model_name not in self.model_performance:
            self.model_performance[model_name] = []
        self.model_performance[model_name].append(quality_data)

        # Update statistics
        self.quality_stats["total_responses"] += 1
        if quality_data["is_high_quality"]:
            self.quality_stats["high_quality_responses"] += 1
        if quality_data["is_low_confidence"]:
            self.quality_stats["low_confidence_responses"] += 1
        if user_satisfaction is not None:
            self.quality_stats["user_satisfaction_count"] += 1
            self.user_feedback.append(
                {
                    "timestamp": time.time(),
                    "query": query,
                    "satisfaction_score": user_satisfaction,
                    "response": response,
                }
            )

        # Update averages
        self._update_averages()

        logger.debug(
            "Response quality recorded",
            query=query[:50] + "..." if len(query) > 50 else query,
            confidence_score=confidence_score,
            model_name=model_name,
            response_length=response_length,
            is_high_quality=quality_data["is_high_quality"],
        )

    def record_user_feedback(
        self,
        query: str,
        response: str,
        satisfaction_score: int,
        feedback_text: Optional[str] = None,
    ) -> None:
        """
        Record user feedback and satisfaction.

        Args:
            query: Original query
            response: Response that was rated
            satisfaction_score: User satisfaction score (1-5)
            feedback_text: Optional feedback text
        """
        feedback_data = {
            "timestamp": time.time(),
            "query": query,
            "response": response,
            "satisfaction_score": satisfaction_score,
            "feedback_text": feedback_text,
        }

        self.user_feedback.append(feedback_data)
        self.quality_stats["user_satisfaction_count"] += 1

        logger.debug(
            "User feedback recorded",
            satisfaction_score=satisfaction_score,
            has_feedback_text=feedback_text is not None,
        )

    def _is_high_quality(
        self, confidence_score: float, quality_scores: Dict[str, float]
    ) -> bool:
        """Determine if response is high quality."""
        # High quality if confidence > 0.8 and average quality > 0.7
        avg_quality = np.mean(list(quality_scores.values())) if quality_scores else 0.0
        return confidence_score > 0.8 and avg_quality > 0.7

    def _update_averages(self) -> None:
        """Update average statistics."""
        if self.confidence_scores:
            self.quality_stats["average_confidence"] = np.mean(self.confidence_scores)

        all_quality_scores = []
        for scores in self.response_metrics.values():
            all_quality_scores.extend(scores)

        if all_quality_scores:
            self.quality_stats["average_quality"] = np.mean(all_quality_scores)

    def calculate_confidence_distribution(self) -> Dict[str, float]:
        """Calculate confidence score distribution."""
        if not self.confidence_scores:
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}

        return {
            "mean": np.mean(self.confidence_scores),
            "std": np.std(self.confidence_scores),
            "min": np.min(self.confidence_scores),
            "max": np.max(self.confidence_scores),
            "median": np.median(self.confidence_scores),
        }

    def calculate_quality_metrics(self) -> Dict[str, float]:
        """Calculate overall quality metrics."""
        metrics = {}

        for metric_name, scores in self.response_metrics.items():
            if scores:
                metrics[f"{metric_name}_mean"] = np.mean(scores)
                metrics[f"{metric_name}_std"] = np.std(scores)
                metrics[f"{metric_name}_min"] = np.min(scores)
                metrics[f"{metric_name}_max"] = np.max(scores)
            else:
                metrics[f"{metric_name}_mean"] = 0.0
                metrics[f"{metric_name}_std"] = 0.0
                metrics[f"{metric_name}_min"] = 0.0
                metrics[f"{metric_name}_max"] = 0.0

        return metrics

    def calculate_user_satisfaction_metrics(self) -> Dict[str, Any]:
        """Calculate user satisfaction metrics."""
        if not self.user_feedback:
            return {
                "average_satisfaction": 0.0,
                "satisfaction_distribution": {},
                "total_feedback": 0,
            }

        satisfaction_scores = [f["satisfaction_score"] for f in self.user_feedback]

        # Calculate distribution
        distribution = {}
        for score in range(1, 6):
            distribution[score] = satisfaction_scores.count(score)

        return {
            "average_satisfaction": np.mean(satisfaction_scores),
            "satisfaction_distribution": distribution,
            "total_feedback": len(self.user_feedback),
            "recent_feedback": self.user_feedback[-10:]
            if len(self.user_feedback) > 10
            else self.user_feedback,
        }

    def calculate_model_performance(self) -> Dict[str, Dict[str, float]]:
        """Calculate performance metrics by model."""
        model_metrics = {}

        for model_name, performances in self.model_performance.items():
            if not performances:
                continue

            confidences = [p["confidence_score"] for p in performances]
            qualities = []
            for p in performances:
                if p["quality_scores"]:
                    qualities.append(np.mean(list(p["quality_scores"].values())))

            model_metrics[model_name] = {
                "total_responses": len(performances),
                "average_confidence": np.mean(confidences) if confidences else 0.0,
                "average_quality": np.mean(qualities) if qualities else 0.0,
                "high_quality_rate": sum(
                    1 for p in performances if p["is_high_quality"]
                )
                / len(performances),
                "low_confidence_rate": sum(
                    1 for p in performances if p["is_low_confidence"]
                )
                / len(performances),
            }

        return model_metrics

    def record_evaluation_metrics(
        self, metrics_manager: "MetricsManager", quality_data: Dict[str, Any]
    ) -> None:
        """
        Record evaluation metrics to Prometheus.

        Args:
            metrics_manager: MetricsManager instance
            quality_data: Quality data dictionary
        """
        if not metrics_manager.enabled:
            return

        confidence_score = quality_data.get("confidence_score", 0.0)
        model_name = quality_data.get("model_name", "unknown")
        quality_scores = quality_data.get("quality_scores", {})
        response_length = quality_data.get("response_length", 0)
        context_utilization = quality_data.get("context_utilization", 0.0)
        user_satisfaction = quality_data.get("user_satisfaction")

        # Record confidence metrics
        metrics_manager._metrics["answer_confidence_score"].observe(confidence_score)
        metrics_manager._metrics["answer_confidence_by_model"].labels(
            model_name=model_name
        ).observe(confidence_score)

        # Record quality metrics
        if quality_scores:
            avg_quality = np.mean(list(quality_scores.values()))
            metrics_manager._metrics["response_quality_score"].observe(avg_quality)

            # Record individual quality scores
            for metric, score in quality_scores.items():
                if metric == "accuracy":
                    metrics_manager._metrics["response_accuracy"].observe(score)
                elif metric == "relevance":
                    metrics_manager._metrics["content_relevance_score"].observe(score)
                elif metric == "completeness":
                    metrics_manager._metrics["answer_completeness_score"].observe(score)
                elif metric == "factual_accuracy":
                    metrics_manager._metrics["factual_accuracy_score"].observe(score)
                elif metric == "coherence":
                    metrics_manager._metrics["response_coherence_score"].observe(score)

        # Record response metrics
        metrics_manager._metrics["response_length_distribution"].observe(
            response_length
        )
        metrics_manager._metrics["context_utilization_ratio"].observe(
            context_utilization
        )

        # Record user satisfaction
        if user_satisfaction is not None:
            metrics_manager._metrics["user_satisfaction_score"].observe(
                user_satisfaction
            )

        # Record quality indicators
        if quality_data.get("is_high_quality", False):
            metrics_manager._metrics["high_quality_responses"].inc()

        if quality_data.get("is_low_confidence", False):
            metrics_manager._metrics["low_confidence_responses"].inc()

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get comprehensive quality evaluation summary."""
        return {
            "quality_stats": self.quality_stats.copy(),
            "confidence_distribution": self.calculate_confidence_distribution(),
            "quality_metrics": self.calculate_quality_metrics(),
            "user_satisfaction": self.calculate_user_satisfaction_metrics(),
            "model_performance": self.calculate_model_performance(),
            "total_responses": len(self.quality_history),
            "recent_responses": self.quality_history[-50:]
            if self.quality_history
            else [],
            "quality_trends": self._calculate_quality_trends(),
        }

    def _calculate_quality_trends(self) -> Dict[str, List[float]]:
        """Calculate quality trends over time."""
        if len(self.quality_history) < 10:
            return {"confidence": [], "quality": []}

        # Group by time windows (last 10 responses)
        recent_responses = self.quality_history[-10:]

        confidence_trend = [r["confidence_score"] for r in recent_responses]
        quality_trend = []

        for r in recent_responses:
            if r["quality_scores"]:
                quality_trend.append(np.mean(list(r["quality_scores"].values())))
            else:
                quality_trend.append(0.0)

        return {"confidence": confidence_trend, "quality": quality_trend}


class SystemPerformanceMonitor:
    """
    System performance and resource monitoring.

    This class provides comprehensive monitoring of system resources,
    performance metrics, and bottleneck detection.
    """

    def __init__(self):
        """Initialize system performance monitor."""
        self.cpu_history: List[float] = []
        self.memory_history: List[float] = []
        self.disk_history: List[float] = []
        self.network_history: List[float] = []
        self.response_time_history: List[float] = []
        self.error_count = 0
        self.request_count = 0
        self.concurrent_users = 0
        self.queue_length = 0

        # Performance thresholds
        self.thresholds = {
            "cpu_warning": 70.0,
            "cpu_critical": 90.0,
            "memory_warning": 80.0,
            "memory_critical": 95.0,
            "disk_warning": 85.0,
            "disk_critical": 95.0,
            "response_time_warning": 5.0,
            "response_time_critical": 10.0,
            "error_rate_warning": 5.0,
            "error_rate_critical": 10.0,
        }

    def record_cpu_usage(self, cpu_percent: float) -> None:
        """Record CPU usage percentage."""
        self.cpu_history.append(cpu_percent)
        # Keep only last 100 measurements
        if len(self.cpu_history) > 100:
            self.cpu_history = self.cpu_history[-100:]

    def record_memory_usage(self, memory_bytes: int, memory_percent: float) -> None:
        """Record memory usage."""
        self.memory_history.append(memory_percent)
        # Keep only last 100 measurements
        if len(self.memory_history) > 100:
            self.memory_history = self.memory_history[-100:]

    def record_disk_usage(self, disk_bytes: int, disk_percent: float) -> None:
        """Record disk usage."""
        self.disk_history.append(disk_percent)
        # Keep only last 100 measurements
        if len(self.disk_history) > 100:
            self.disk_history = self.disk_history[-100:]

    def record_network_latency(self, latency_seconds: float) -> None:
        """Record network latency."""
        self.network_history.append(latency_seconds)
        # Keep only last 100 measurements
        if len(self.network_history) > 100:
            self.network_history = self.network_history[-100:]

    def record_response_time(self, response_time_seconds: float) -> None:
        """Record system response time."""
        self.response_time_history.append(response_time_seconds)
        # Keep only last 100 measurements
        if len(self.response_time_history) > 100:
            self.response_time_history = self.response_time_history[-100:]

    def record_request(self, success: bool = True) -> None:
        """Record a request (success or failure)."""
        self.request_count += 1
        if not success:
            self.error_count += 1

    def update_concurrent_users(self, count: int) -> None:
        """Update concurrent user count."""
        self.concurrent_users = count

    def update_queue_length(self, length: int) -> None:
        """Update queue length."""
        self.queue_length = length

    def get_cpu_metrics(self) -> Dict[str, float]:
        """Get CPU usage metrics."""
        if not self.cpu_history:
            return {"current": 0.0, "average": 0.0, "max": 0.0, "min": 0.0}

        return {
            "current": self.cpu_history[-1] if self.cpu_history else 0.0,
            "average": np.mean(self.cpu_history),
            "max": np.max(self.cpu_history),
            "min": np.min(self.cpu_history),
        }

    def get_memory_metrics(self) -> Dict[str, float]:
        """Get memory usage metrics."""
        if not self.memory_history:
            return {"current": 0.0, "average": 0.0, "max": 0.0, "min": 0.0}

        return {
            "current": self.memory_history[-1] if self.memory_history else 0.0,
            "average": np.mean(self.memory_history),
            "max": np.max(self.memory_history),
            "min": np.min(self.memory_history),
        }

    def get_disk_metrics(self) -> Dict[str, float]:
        """Get disk usage metrics."""
        if not self.disk_history:
            return {"current": 0.0, "average": 0.0, "max": 0.0, "min": 0.0}

        return {
            "current": self.disk_history[-1] if self.disk_history else 0.0,
            "average": np.mean(self.disk_history),
            "max": np.max(self.disk_history),
            "min": np.min(self.disk_history),
        }

    def get_network_metrics(self) -> Dict[str, float]:
        """Get network latency metrics."""
        if not self.network_history:
            return {"current": 0.0, "average": 0.0, "max": 0.0, "min": 0.0}

        return {
            "current": self.network_history[-1] if self.network_history else 0.0,
            "average": np.mean(self.network_history),
            "max": np.max(self.network_history),
            "min": np.min(self.network_history),
        }

    def get_response_time_metrics(self) -> Dict[str, float]:
        """Get response time metrics."""
        if not self.response_time_history:
            return {"current": 0.0, "average": 0.0, "max": 0.0, "min": 0.0}

        return {
            "current": self.response_time_history[-1]
            if self.response_time_history
            else 0.0,
            "average": np.mean(self.response_time_history),
            "max": np.max(self.response_time_history),
            "min": np.min(self.response_time_history),
        }

    def get_error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100.0

    def get_throughput(self) -> float:
        """Calculate throughput (requests per second)."""
        if not self.response_time_history:
            return 0.0

        # Simple calculation: average requests per second based on response time
        avg_response_time = np.mean(self.response_time_history)
        if avg_response_time == 0:
            return 0.0
        return 1.0 / avg_response_time

    def detect_bottlenecks(self) -> List[str]:
        """Detect performance bottlenecks."""
        bottlenecks = []

        cpu_metrics = self.get_cpu_metrics()
        memory_metrics = self.get_memory_metrics()
        disk_metrics = self.get_disk_metrics()
        response_metrics = self.get_response_time_metrics()
        error_rate = self.get_error_rate()

        # CPU bottleneck
        if cpu_metrics["current"] > self.thresholds["cpu_critical"]:
            bottlenecks.append(f"Critical CPU usage: {cpu_metrics['current']:.1f}%")
        elif cpu_metrics["current"] > self.thresholds["cpu_warning"]:
            bottlenecks.append(f"High CPU usage: {cpu_metrics['current']:.1f}%")

        # Memory bottleneck
        if memory_metrics["current"] > self.thresholds["memory_critical"]:
            bottlenecks.append(
                f"Critical memory usage: {memory_metrics['current']:.1f}%"
            )
        elif memory_metrics["current"] > self.thresholds["memory_warning"]:
            bottlenecks.append(f"High memory usage: {memory_metrics['current']:.1f}%")

        # Disk bottleneck
        if disk_metrics["current"] > self.thresholds["disk_critical"]:
            bottlenecks.append(f"Critical disk usage: {disk_metrics['current']:.1f}%")
        elif disk_metrics["current"] > self.thresholds["disk_warning"]:
            bottlenecks.append(f"High disk usage: {disk_metrics['current']:.1f}%")

        # Response time bottleneck
        if response_metrics["current"] > self.thresholds["response_time_critical"]:
            bottlenecks.append(
                f"Critical response time: {response_metrics['current']:.2f}s"
            )
        elif response_metrics["current"] > self.thresholds["response_time_warning"]:
            bottlenecks.append(
                f"Slow response time: {response_metrics['current']:.2f}s"
            )

        # Error rate bottleneck
        if error_rate > self.thresholds["error_rate_critical"]:
            bottlenecks.append(f"Critical error rate: {error_rate:.1f}%")
        elif error_rate > self.thresholds["error_rate_warning"]:
            bottlenecks.append(f"High error rate: {error_rate:.1f}%")

        return bottlenecks

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        return {
            "cpu_metrics": self.get_cpu_metrics(),
            "memory_metrics": self.get_memory_metrics(),
            "disk_metrics": self.get_disk_metrics(),
            "network_metrics": self.get_network_metrics(),
            "response_time_metrics": self.get_response_time_metrics(),
            "error_rate": self.get_error_rate(),
            "throughput": self.get_throughput(),
            "concurrent_users": self.concurrent_users,
            "queue_length": self.queue_length,
            "bottlenecks": self.detect_bottlenecks(),
            "total_requests": self.request_count,
            "total_errors": self.error_count,
        }

    def record_evaluation_metrics(
        self, metrics_manager: "MetricsManager", performance_data: Dict[str, Any]
    ) -> None:
        """
        Record performance metrics to Prometheus.

        Args:
            metrics_manager: MetricsManager instance
            performance_data: Performance data dictionary
        """
        if not metrics_manager.enabled:
            return

        # Record system metrics
        cpu_percent = performance_data.get("cpu_percent", 0.0)
        memory_bytes = performance_data.get("memory_bytes", 0)
        memory_percent = performance_data.get("memory_percent", 0.0)
        disk_bytes = performance_data.get("disk_bytes", 0)
        disk_percent = performance_data.get("disk_percent", 0.0)
        network_latency = performance_data.get("network_latency", 0.0)
        response_time = performance_data.get("response_time", 0.0)
        throughput = performance_data.get("throughput", 0.0)
        concurrent_users = performance_data.get("concurrent_users", 0)
        queue_length = performance_data.get("queue_length", 0)
        error_rate = performance_data.get("error_rate", 0.0)
        gpu_percent = performance_data.get("gpu_percent", 0.0)
        gpu_memory = performance_data.get("gpu_memory", 0)

        # Record metrics
        metrics_manager._metrics["system_cpu_usage"].set(cpu_percent)
        metrics_manager._metrics["system_memory_usage"].set(memory_bytes)
        metrics_manager._metrics["system_memory_percent"].set(memory_percent)
        metrics_manager._metrics["system_disk_usage"].set(disk_bytes)
        metrics_manager._metrics["system_disk_percent"].set(disk_percent)
        metrics_manager._metrics["system_network_latency"].observe(network_latency)
        metrics_manager._metrics["system_response_time"].observe(response_time)
        metrics_manager._metrics["system_throughput"].set(throughput)
        metrics_manager._metrics["system_concurrent_users"].set(concurrent_users)
        metrics_manager._metrics["system_queue_length"].set(queue_length)
        metrics_manager._metrics["system_error_rate"].set(error_rate)
        metrics_manager._metrics["system_gpu_usage"].set(gpu_percent)
        metrics_manager._metrics["system_gpu_memory"].set(gpu_memory)


# Global instances
metrics_manager = MetricsManager()
retrieval_evaluator = RetrievalEvaluator()
reranker_evaluator = RerankerEvaluator()
cache_analytics = CacheAnalytics()
quality_evaluator = QualityEvaluator()
system_performance_monitor = SystemPerformanceMonitor()
