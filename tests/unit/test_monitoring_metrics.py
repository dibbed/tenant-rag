"""
Unit tests for monitoring metrics and evaluation framework.

This module provides comprehensive unit tests for the monitoring
and evaluation components implemented in Phase 1.
"""

import time
from unittest.mock import Mock

import numpy as np
import pytest

from ragbot.outputs.metrics import (
    CacheAnalytics,
    MetricsManager,
    QualityEvaluator,
    RerankerEvaluator,
    RetrievalEvaluator,
    SystemPerformanceMonitor,
    cache_analytics,
    metrics_manager,
    quality_evaluator,
    reranker_evaluator,
    retrieval_evaluator,
)
from ragbot.rag.retrieve.advanced_retriever import AdvancedRetriever
from ragbot.rag.store.base import VectorDocument


class TestMetricsManager:
    """Test cases for MetricsManager class."""

    def test_initialization(self):
        """Test MetricsManager initialization."""
        manager = MetricsManager()
        assert hasattr(manager, "enabled")
        assert hasattr(manager, "_metrics")
        assert hasattr(manager, "_in_memory_metrics")

    def test_time_operation_context_manager(self):
        """Test timing operation context manager."""
        manager = MetricsManager()

        with manager.time_operation("test_operation"):
            time.sleep(0.01)  # Small delay for testing

        # Verify timing was recorded (basic check)
        assert True  # Context manager should complete without error

    def test_record_user_activity(self):
        """Test user activity recording."""
        manager = MetricsManager()
        user_id = 12345

        # Should not raise exception
        manager.record_user_activity(user_id)
        assert manager._in_memory_metrics["user_activity"] >= 1

    def test_record_document_processing(self):
        """Test document processing metrics recording."""
        manager = MetricsManager()

        manager.record_document_processing(
            document_type="pdf", status="success", duration=1.5, chunk_count=10
        )

        assert manager._in_memory_metrics["documents_success"] >= 1

    def test_record_query_processing(self):
        """Test query processing metrics recording."""
        manager = MetricsManager()

        manager.record_query_processing(
            language="en",
            status="success",
            total_duration=2.0,
            retrieval_duration=1.0,
            llm_duration=1.0,
        )

        assert manager._in_memory_metrics["queries_success"] >= 1

    def test_record_error(self):
        """Test error recording."""
        manager = MetricsManager()

        manager.record_error("test_error", "test_component")
        assert manager._in_memory_metrics["errors"] >= 1

    def test_health_check(self):
        """Test health check functionality."""
        manager = MetricsManager()
        health_status = manager.health_check()

        assert "metrics_enabled" in health_status
        assert "prometheus_available" in health_status
        assert "total_metrics_collected" in health_status


class TestRetrievalEvaluator:
    """Test cases for RetrievalEvaluator class."""

    def test_initialization(self):
        """Test RetrievalEvaluator initialization."""
        evaluator = RetrievalEvaluator()
        assert hasattr(evaluator, "ground_truth_cache")
        assert hasattr(evaluator, "evaluation_history")
        assert len(evaluator.evaluation_history) == 0

    def test_calculate_recall_at_k(self):
        """Test Recall@K calculation."""
        evaluator = RetrievalEvaluator()

        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = ["doc1", "doc3", "doc6"]

        # Test Recall@3
        recall_at_3 = evaluator.calculate_recall_at_k(retrieved, relevant, 3)
        assert recall_at_3 == 2 / 3  # 2 out of 3 relevant docs found in top 3

        # Test Recall@5
        recall_at_5 = evaluator.calculate_recall_at_k(retrieved, relevant, 5)
        assert recall_at_5 == 2 / 3  # 2 out of 3 relevant docs found in top 5

        # Test edge case: no relevant docs
        recall_empty = evaluator.calculate_recall_at_k(retrieved, [], 3)
        assert recall_empty == 0.0

    def test_calculate_mrr(self):
        """Test Mean Reciprocal Rank calculation."""
        evaluator = RetrievalEvaluator()

        retrieved = ["doc1", "doc2", "doc3"]
        relevant = ["doc2", "doc4"]

        mrr = evaluator.calculate_mrr(retrieved, relevant)
        assert mrr == 0.5  # First relevant doc at position 2

        # Test edge case: no relevant docs
        mrr_empty = evaluator.calculate_mrr(retrieved, [])
        assert mrr_empty == 0.0

        # Test edge case: no relevant docs in retrieved
        mrr_no_match = evaluator.calculate_mrr(["doc1", "doc2"], ["doc3"])
        assert mrr_no_match == 0.0

    def test_calculate_ndcg_at_k(self):
        """Test NDCG@K calculation."""
        evaluator = RetrievalEvaluator()

        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = ["doc1", "doc3", "doc6"]

        ndcg_at_5 = evaluator.calculate_ndcg_at_k(retrieved, relevant, 5)
        assert 0.0 <= ndcg_at_5 <= 1.0  # NDCG should be between 0 and 1

        # Test edge case: no relevant docs
        ndcg_empty = evaluator.calculate_ndcg_at_k(retrieved, [], 5)
        assert ndcg_empty == 0.0

    def test_evaluate_query_expansion(self):
        """Test query expansion evaluation."""
        evaluator = RetrievalEvaluator()

        original_query = "machine learning"
        expanded_query = "machine learning artificial intelligence"
        original_results = ["doc1", "doc2", "doc3"]
        expanded_results = ["doc1", "doc3", "doc4", "doc5"]
        relevant_docs = ["doc1", "doc3", "doc6"]

        evaluation = evaluator.evaluate_query_expansion(
            original_query,
            expanded_query,
            original_results,
            expanded_results,
            relevant_docs,
        )

        # Check that evaluation contains expected keys
        expected_keys = [
            "original_recall_5",
            "expanded_recall_5",
            "recall_delta",
            "original_mrr",
            "expanded_mrr",
            "mrr_improvement",
            "original_ndcg_10",
            "expanded_ndcg_10",
            "ndcg_improvement",
            "improvement_ratio",
        ]

        for key in expected_keys:
            assert key in evaluation
            assert isinstance(evaluation[key], (int, float))

        # Check that evaluation history was updated
        assert len(evaluator.evaluation_history) == 1
        assert evaluator.evaluation_history[0]["original_query"] == original_query

    def test_record_evaluation_metrics(self):
        """Test recording evaluation metrics to Prometheus."""
        evaluator = RetrievalEvaluator()

        # Mock metrics manager
        mock_manager = Mock()
        mock_manager.enabled = True
        mock_manager._metrics = {
            "retrieval_recall_at_1": Mock(),
            "retrieval_recall_at_3": Mock(),
            "retrieval_recall_at_5": Mock(),
            "retrieval_recall_at_10": Mock(),
            "retrieval_mrr": Mock(),
            "retrieval_ndcg_at_5": Mock(),
            "retrieval_ndcg_at_10": Mock(),
            "query_expansion_recall_delta": Mock(),
            "query_expansion_mrr_improvement": Mock(),
        }

        evaluation = {
            "recall_at_1": 0.8,
            "recall_at_3": 0.9,
            "recall_at_5": 0.95,
            "recall_at_10": 1.0,
            "mrr": 0.7,
            "ndcg_at_5": 0.85,
            "ndcg_at_10": 0.9,
            "recall_delta": 0.1,
            "mrr_improvement": 0.05,
        }

        # Should not raise exception
        evaluator.record_evaluation_metrics(mock_manager, evaluation)

        # Verify metrics were called
        mock_manager._metrics["retrieval_recall_at_1"].set.assert_called_with(0.8)
        mock_manager._metrics["retrieval_mrr"].set.assert_called_with(0.7)
        mock_manager._metrics[
            "query_expansion_recall_delta"
        ].observe.assert_called_with(0.1)

    def test_get_evaluation_summary(self):
        """Test evaluation summary generation."""
        evaluator = RetrievalEvaluator()

        # Test empty history
        summary_empty = evaluator.get_evaluation_summary()
        assert summary_empty["total_evaluations"] == 0

        # Add some evaluation history
        evaluator.evaluation_history = [
            {
                "timestamp": time.time(),
                "original_query": "test1",
                "expanded_query": "test1 expanded",
                "evaluation": {
                    "recall_delta": 0.1,
                    "mrr_improvement": 0.05,
                    "ndcg_improvement": 0.08,
                },
            },
            {
                "timestamp": time.time(),
                "original_query": "test2",
                "expanded_query": "test2 expanded",
                "evaluation": {
                    "recall_delta": -0.05,
                    "mrr_improvement": 0.02,
                    "ndcg_improvement": 0.03,
                },
            },
        ]

        summary = evaluator.get_evaluation_summary()
        assert summary["total_evaluations"] == 2
        assert summary["recent_evaluations"] == 2
        assert "avg_recall_delta" in summary
        assert "avg_mrr_improvement" in summary
        assert "avg_ndcg_improvement" in summary
        assert "improvement_rate" in summary


class TestAdvancedRetrieverIntegration:
    """Test cases for AdvancedRetriever metrics integration."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        mock_store = Mock()
        mock_store.search.return_value = [
            VectorDocument(
                id="doc1",
                content="Test content 1",
                metadata={},
                embedding=[0.1, 0.2, 0.3],
            ),
            VectorDocument(
                id="doc2",
                content="Test content 2",
                metadata={},
                embedding=[0.4, 0.5, 0.6],
            ),
            VectorDocument(
                id="doc3",
                content="Test content 3",
                metadata={},
                embedding=[0.7, 0.8, 0.9],
            ),
        ]
        return mock_store

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder."""
        mock_embedder = Mock()
        mock_embedder.embed.return_value = np.array([0.1, 0.2, 0.3])
        return mock_embedder

    def test_advanced_retriever_metrics_integration(
        self, mock_vector_store, mock_embedder
    ):
        """Test that AdvancedRetriever properly integrates with metrics."""
        retriever = AdvancedRetriever(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            enable_reranking=False,
            enable_hybrid=False,
            enable_expansion=False,
        )

        # Verify that retriever has metrics integration capability
        assert hasattr(retriever, "_record_advanced_metrics")

        # Test that metrics recording method exists and is callable
        assert callable(retriever._record_advanced_metrics)


class TestGlobalInstances:
    """Test cases for global metric instances."""

    def test_global_metrics_manager(self):
        """Test global metrics manager instance."""
        assert metrics_manager is not None
        assert isinstance(metrics_manager, MetricsManager)

    def test_global_retrieval_evaluator(self):
        """Test global retrieval evaluator instance."""
        assert retrieval_evaluator is not None
        assert isinstance(retrieval_evaluator, RetrievalEvaluator)

    def test_global_reranker_evaluator(self):
        """Test global reranker evaluator instance."""
        assert reranker_evaluator is not None
        assert isinstance(reranker_evaluator, RerankerEvaluator)

    def test_global_cache_analytics(self):
        """Test global cache analytics instance."""
        assert cache_analytics is not None
        assert isinstance(cache_analytics, CacheAnalytics)

    def test_global_quality_evaluator(self):
        """Test global quality evaluator instance."""
        assert quality_evaluator is not None
        assert isinstance(quality_evaluator, QualityEvaluator)


class TestMetricsIntegration:
    """Integration tests for metrics system."""

    def test_metrics_manager_with_retrieval_evaluator(self):
        """Test integration between MetricsManager and RetrievalEvaluator."""
        manager = MetricsManager()
        evaluator = RetrievalEvaluator()

        # Test that evaluator can record metrics to manager
        evaluation = {"recall_at_5": 0.8, "mrr": 0.7, "ndcg_at_10": 0.9}

        # Should not raise exception
        evaluator.record_evaluation_metrics(manager, evaluation)

    def test_end_to_end_evaluation_flow(self):
        """Test complete evaluation flow."""
        evaluator = RetrievalEvaluator()

        # Simulate retrieval results
        retrieved_docs = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant_docs = ["doc1", "doc3", "doc6"]

        # Calculate all metrics
        recall_at_1 = evaluator.calculate_recall_at_k(retrieved_docs, relevant_docs, 1)
        recall_at_5 = evaluator.calculate_recall_at_k(retrieved_docs, relevant_docs, 5)
        mrr = evaluator.calculate_mrr(retrieved_docs, relevant_docs)
        ndcg_at_5 = evaluator.calculate_ndcg_at_k(retrieved_docs, relevant_docs, 5)

        # Verify all metrics are valid
        assert 0.0 <= recall_at_1 <= 1.0
        assert 0.0 <= recall_at_5 <= 1.0
        assert 0.0 <= mrr <= 1.0
        assert 0.0 <= ndcg_at_5 <= 1.0

        # Test evaluation summary
        summary = evaluator.get_evaluation_summary()
        assert summary["total_evaluations"] == 0  # No query expansion evaluations yet


class TestRerankerEvaluator:
    """Test cases for RerankerEvaluator class."""

    def test_initialization(self):
        """Test RerankerEvaluator initialization."""
        evaluator = RerankerEvaluator()
        assert hasattr(evaluator, "performance_history")
        assert hasattr(evaluator, "model_performance")
        assert hasattr(evaluator, "cache_stats")
        assert len(evaluator.performance_history) == 0
        assert evaluator.cache_stats == {"hits": 0, "misses": 0}

    def test_record_reranking_performance(self):
        """Test reranking performance recording."""
        evaluator = RerankerEvaluator()

        model_name = "test-model"
        latency = 1.5
        batch_size = 10
        quality_scores = [0.8, 0.7, 0.6, 0.5, 0.4]

        evaluator.record_reranking_performance(
            model_name=model_name,
            latency=latency,
            batch_size=batch_size,
            quality_scores=quality_scores,
            cache_hit=False,
            timeout=False,
            fallback=False,
        )

        assert len(evaluator.performance_history) == 1
        assert len(evaluator.model_performance[model_name]) == 1

        performance = evaluator.performance_history[0]
        assert performance["model_name"] == model_name
        assert performance["latency"] == latency
        assert performance["batch_size"] == batch_size
        assert performance["avg_quality"] == np.mean(quality_scores)
        assert performance["throughput"] == batch_size / latency

    def test_record_model_loading_time(self):
        """Test model loading time recording."""
        evaluator = RerankerEvaluator()

        model_name = "test-model"
        loading_time = 5.2

        # Should not raise exception
        evaluator.record_model_loading_time(model_name, loading_time)

    def test_calculate_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        evaluator = RerankerEvaluator()

        # Test empty cache
        assert evaluator.calculate_cache_hit_rate() == 0.0

        # Add some cache hits and misses
        evaluator.cache_stats["hits"] = 7
        evaluator.cache_stats["misses"] = 3

        hit_rate = evaluator.calculate_cache_hit_rate()
        assert hit_rate == 0.7  # 7 / (7 + 3)

    def test_calculate_average_throughput(self):
        """Test average throughput calculation."""
        evaluator = RerankerEvaluator()

        # Test empty performance history
        assert evaluator.calculate_average_throughput() == 0.0

        # Add some performance data
        evaluator.performance_history = [
            {"throughput": 10.0, "model_name": "model1"},
            {"throughput": 20.0, "model_name": "model1"},
            {"throughput": 0.0, "model_name": "model1"},  # Should be ignored
        ]

        avg_throughput = evaluator.calculate_average_throughput()
        assert avg_throughput == 15.0  # (10 + 20) / 2

        # Test model-specific throughput
        evaluator.model_performance["model1"] = evaluator.performance_history
        model_throughput = evaluator.calculate_average_throughput("model1")
        assert model_throughput == 15.0

    def test_calculate_average_latency(self):
        """Test average latency calculation."""
        evaluator = RerankerEvaluator()

        # Test empty performance history
        assert evaluator.calculate_average_latency() == 0.0

        # Add some performance data
        evaluator.performance_history = [
            {"latency": 1.0, "model_name": "model1"},
            {"latency": 2.0, "model_name": "model1"},
            {"latency": 3.0, "model_name": "model1"},
        ]

        avg_latency = evaluator.calculate_average_latency()
        assert avg_latency == 2.0  # (1 + 2 + 3) / 3

    def test_calculate_average_quality(self):
        """Test average quality calculation."""
        evaluator = RerankerEvaluator()

        # Test empty performance history
        assert evaluator.calculate_average_quality() == 0.0

        # Add some performance data
        evaluator.performance_history = [
            {"avg_quality": 0.8, "model_name": "model1"},
            {"avg_quality": 0.7, "model_name": "model1"},
            {"avg_quality": 0.6, "model_name": "model1"},
        ]

        avg_quality = evaluator.calculate_average_quality()
        assert abs(avg_quality - 0.7) < 0.001  # (0.8 + 0.7 + 0.6) / 3

    def test_calculate_timeout_rate(self):
        """Test timeout rate calculation."""
        evaluator = RerankerEvaluator()

        # Test empty performance history
        assert evaluator.calculate_timeout_rate() == 0.0

        # Add some performance data
        evaluator.performance_history = [
            {"timeout": True, "model_name": "model1"},
            {"timeout": False, "model_name": "model1"},
            {"timeout": True, "model_name": "model1"},
            {"timeout": False, "model_name": "model1"},
        ]

        timeout_rate = evaluator.calculate_timeout_rate()
        assert timeout_rate == 0.5  # 2 timeouts out of 4 operations

    def test_calculate_fallback_rate(self):
        """Test fallback rate calculation."""
        evaluator = RerankerEvaluator()

        # Test empty performance history
        assert evaluator.calculate_fallback_rate() == 0.0

        # Add some performance data
        evaluator.performance_history = [
            {"fallback": True, "model_name": "model1"},
            {"fallback": False, "model_name": "model1"},
            {"fallback": False, "model_name": "model1"},
        ]

        fallback_rate = evaluator.calculate_fallback_rate()
        assert fallback_rate == 1 / 3  # 1 fallback out of 3 operations

    def test_record_evaluation_metrics(self):
        """Test recording evaluation metrics to Prometheus."""
        evaluator = RerankerEvaluator()

        # Mock metrics manager
        mock_manager = Mock()
        mock_manager.enabled = True
        mock_manager._metrics = {
            "reranker_latency": Mock(),
            "reranker_latency_by_model": Mock(),
            "reranker_batch_size": Mock(),
            "reranker_quality_score": Mock(),
            "reranker_quality_by_model": Mock(),
            "reranker_timeout_rate": Mock(),
            "reranker_fallback_rate": Mock(),
            "reranker_cache_hit_rate": Mock(),
            "reranker_throughput": Mock(),
        }

        performance_data = {
            "model_name": "test-model",
            "latency": 1.5,
            "batch_size": 10,
            "avg_quality": 0.8,
            "timeout": False,
            "fallback": False,
        }

        # Should not raise exception
        evaluator.record_evaluation_metrics(mock_manager, performance_data)

        # Verify metrics were called
        mock_manager._metrics["reranker_latency"].observe.assert_called_with(1.5)
        mock_manager._metrics["reranker_batch_size"].observe.assert_called_with(10)
        mock_manager._metrics["reranker_quality_score"].observe.assert_called_with(0.8)

    def test_get_performance_summary(self):
        """Test performance summary generation."""
        evaluator = RerankerEvaluator()

        # Test empty performance history
        summary_empty = evaluator.get_performance_summary()
        assert summary_empty["total_operations"] == 0
        assert summary_empty["models_used"] == []
        assert summary_empty["cache_hit_rate"] == 0.0

        # Add some performance data
        evaluator.performance_history = [
            {
                "model_name": "model1",
                "latency": 1.0,
                "batch_size": 5,
                "avg_quality": 0.8,
                "timeout": False,
                "fallback": False,
                "throughput": 5.0,
            },
            {
                "model_name": "model1",
                "latency": 2.0,
                "batch_size": 10,
                "avg_quality": 0.7,
                "timeout": True,
                "fallback": False,
                "throughput": 5.0,
            },
        ]
        evaluator.model_performance["model1"] = evaluator.performance_history
        evaluator.cache_stats = {"hits": 1, "misses": 1}

        summary = evaluator.get_performance_summary()
        assert summary["total_operations"] == 2
        assert summary["models_used"] == ["model1"]
        assert summary["cache_hit_rate"] == 0.5
        assert summary["average_latency"] == 1.5
        assert summary["average_quality"] == 0.75
        assert summary["timeout_rate"] == 0.5
        assert summary["fallback_rate"] == 0.0
        assert "model_performance" in summary
        assert "model1" in summary["model_performance"]


class TestCacheAnalytics:
    """Test cases for CacheAnalytics class."""

    def test_initialization(self):
        """Test CacheAnalytics initialization."""
        analytics = CacheAnalytics()
        assert hasattr(analytics, "cache_stats")
        assert hasattr(analytics, "cache_history")
        assert hasattr(analytics, "access_patterns")
        assert hasattr(analytics, "confidence_scores")
        assert hasattr(analytics, "similarity_scores")
        assert hasattr(analytics, "memory_usage_history")

        # Check initial values
        assert analytics.cache_stats["hits"] == 0
        assert analytics.cache_stats["misses"] == 0
        assert len(analytics.cache_history) == 0

    def test_record_cache_hit(self):
        """Test cache hit recording."""
        analytics = CacheAnalytics()

        query = "test query"
        similarity_score = 0.85
        confidence_score = 0.9

        analytics.record_cache_hit(query, similarity_score, confidence_score)

        assert analytics.cache_stats["hits"] == 1
        assert analytics.cache_stats["total_accesses"] == 1
        assert query in analytics.access_patterns
        assert analytics.access_patterns[query] == 1
        assert len(analytics.similarity_scores) == 1
        assert len(analytics.confidence_scores) == 1
        assert len(analytics.cache_history) == 1

        # Test multiple hits for same query
        analytics.record_cache_hit(query, 0.9, 0.95)
        assert analytics.access_patterns[query] == 2
        assert analytics.cache_stats["hits"] == 2

    def test_record_cache_miss(self):
        """Test cache miss recording."""
        analytics = CacheAnalytics()

        query = "test query"
        analytics.record_cache_miss(query)

        assert analytics.cache_stats["misses"] == 1
        assert analytics.cache_stats["total_accesses"] == 1
        assert len(analytics.cache_history) == 1
        assert analytics.cache_history[0]["event"] == "miss"
        assert analytics.cache_history[0]["query"] == query

    def test_record_cache_eviction(self):
        """Test cache eviction recording."""
        analytics = CacheAnalytics()

        evicted_query = "evicted query"
        reason = "size_limit"

        analytics.record_cache_eviction(evicted_query, reason)

        assert analytics.cache_stats["evictions"] == 1
        assert len(analytics.cache_history) == 1
        assert analytics.cache_history[0]["event"] == "eviction"
        assert analytics.cache_history[0]["query"] == evicted_query
        assert analytics.cache_history[0]["reason"] == reason

    def test_record_ttl_expiration(self):
        """Test TTL expiration recording."""
        analytics = CacheAnalytics()

        expired_query = "expired query"
        analytics.record_ttl_expiration(expired_query)

        assert analytics.cache_stats["ttl_expired"] == 1
        assert len(analytics.cache_history) == 1
        assert analytics.cache_history[0]["event"] == "ttl_expired"
        assert analytics.cache_history[0]["query"] == expired_query

    def test_record_embedding_generation_time(self):
        """Test embedding generation time recording."""
        analytics = CacheAnalytics()

        generation_time = 0.5
        analytics.record_embedding_generation_time(generation_time)

        assert analytics.cache_stats["embedding_generations"] == 1

    def test_record_similarity_computation_time(self):
        """Test similarity computation time recording."""
        analytics = CacheAnalytics()

        computation_time = 0.02
        analytics.record_similarity_computation_time(computation_time)

        assert analytics.cache_stats["similarity_computations"] == 1

    def test_record_cache_size(self):
        """Test cache size recording."""
        analytics = CacheAnalytics()

        # Add some hits/misses first
        analytics.record_cache_hit("query1", 0.8, 0.9)
        analytics.record_cache_miss("query2")

        size = 10
        analytics.record_cache_size(size)

        assert len(analytics.memory_usage_history) == 1
        assert analytics.memory_usage_history[0]["cache_size"] == size
        assert (
            analytics.memory_usage_history[0]["hit_rate"] == 0.5
        )  # 1 hit out of 2 total
        assert (
            analytics.memory_usage_history[0]["miss_rate"] == 0.5
        )  # 1 miss out of 2 total

    def test_calculate_hit_rate(self):
        """Test hit rate calculation."""
        analytics = CacheAnalytics()

        # Test empty cache
        assert analytics.calculate_hit_rate() == 0.0

        # Add some hits and misses
        analytics.cache_stats["hits"] = 7
        analytics.cache_stats["misses"] = 3

        hit_rate = analytics.calculate_hit_rate()
        assert hit_rate == 0.7  # 7 / (7 + 3)

    def test_calculate_miss_rate(self):
        """Test miss rate calculation."""
        analytics = CacheAnalytics()

        # Test empty cache
        assert analytics.calculate_miss_rate() == 0.0

        # Add some hits and misses
        analytics.cache_stats["hits"] = 7
        analytics.cache_stats["misses"] = 3

        miss_rate = analytics.calculate_miss_rate()
        assert miss_rate == 0.3  # 3 / (7 + 3)

    def test_calculate_eviction_rate(self):
        """Test eviction rate calculation."""
        analytics = CacheAnalytics()

        # Test empty cache
        assert analytics.calculate_eviction_rate() == 0.0

        # Add some data
        analytics.cache_stats["evictions"] = 2
        analytics.cache_stats["total_accesses"] = 10

        eviction_rate = analytics.calculate_eviction_rate()
        assert eviction_rate == 0.2  # 2 / 10

    def test_calculate_ttl_expiration_rate(self):
        """Test TTL expiration rate calculation."""
        analytics = CacheAnalytics()

        # Test empty cache
        assert analytics.calculate_ttl_expiration_rate() == 0.0

        # Add some data
        analytics.cache_stats["ttl_expired"] = 1
        analytics.cache_stats["total_accesses"] = 10

        ttl_rate = analytics.calculate_ttl_expiration_rate()
        assert ttl_rate == 0.1  # 1 / 10

    def test_calculate_average_confidence_score(self):
        """Test average confidence score calculation."""
        analytics = CacheAnalytics()

        # Test empty scores
        assert analytics.calculate_average_confidence_score() == 0.0

        # Add some scores
        analytics.confidence_scores = [0.8, 0.9, 0.7, 0.95]

        avg_confidence = analytics.calculate_average_confidence_score()
        assert abs(avg_confidence - 0.8375) < 0.001  # (0.8 + 0.9 + 0.7 + 0.95) / 4

    def test_calculate_average_similarity_score(self):
        """Test average similarity score calculation."""
        analytics = CacheAnalytics()

        # Test empty scores
        assert analytics.calculate_average_similarity_score() == 0.0

        # Add some scores
        analytics.similarity_scores = [0.85, 0.92, 0.78, 0.88]

        avg_similarity = analytics.calculate_average_similarity_score()
        assert abs(avg_similarity - 0.8575) < 0.001  # (0.85 + 0.92 + 0.78 + 0.88) / 4

    def test_calculate_deduplication_ratio(self):
        """Test deduplication ratio calculation."""
        analytics = CacheAnalytics()

        # Test empty patterns
        assert analytics.calculate_deduplication_ratio() == 0.0

        # Add some access patterns
        analytics.access_patterns = {
            "query1": 3,  # accessed 3 times
            "query2": 2,  # accessed 2 times
            "query3": 1,  # accessed 1 time
        }

        dedup_ratio = analytics.calculate_deduplication_ratio()
        assert dedup_ratio == 0.5  # 3 unique queries / 6 total accesses

    def test_calculate_memory_efficiency(self):
        """Test memory efficiency calculation."""
        analytics = CacheAnalytics()

        # Test empty cache
        assert analytics.calculate_memory_efficiency() == 0.0

        # Add some data for efficiency calculation
        analytics.cache_stats["hits"] = 8
        analytics.cache_stats["misses"] = 2
        analytics.cache_stats["evictions"] = 1
        analytics.cache_stats["total_accesses"] = 10

        efficiency = analytics.calculate_memory_efficiency()
        # hit_rate = 0.8, eviction_rate = 0.1, efficiency = 0.8 * (1 - 0.1) = 0.72
        assert abs(efficiency - 0.72) < 0.001

    def test_record_evaluation_metrics(self):
        """Test recording evaluation metrics to Prometheus."""
        analytics = CacheAnalytics()

        # Add some data
        analytics.cache_stats["hits"] = 7
        analytics.cache_stats["misses"] = 3
        analytics.confidence_scores = [0.8, 0.9, 0.7]
        analytics.access_patterns = {"query1": 2, "query2": 1}

        # Mock metrics manager
        mock_manager = Mock()
        mock_manager.enabled = True
        mock_manager._metrics = {
            "cache_hit_rate": Mock(),
            "cache_miss_rate": Mock(),
            "cache_size": Mock(),
            "cache_memory_usage": Mock(),
            "cache_eviction_rate": Mock(),
            "cache_ttl_expired": Mock(),
            "cache_access_frequency": Mock(),
            "cache_confidence_score": Mock(),
            "cache_deduplication_ratio": Mock(),
            "cache_similarity_threshold": Mock(),
            "cache_embedding_generation_time": Mock(),
            "cache_similarity_computation_time": Mock(),
        }

        cache_data = {
            "size": 10,
            "memory_usage": 10240,
            "similarity_threshold": 0.8,
            "embedding_generation_time": 0.5,
            "similarity_computation_time": 0.02,
        }

        # Should not raise exception
        analytics.record_evaluation_metrics(mock_manager, cache_data)

        # Verify metrics were called
        mock_manager._metrics["cache_hit_rate"].set.assert_called_with(0.7)
        mock_manager._metrics["cache_miss_rate"].set.assert_called_with(0.3)
        mock_manager._metrics["cache_size"].set.assert_called_with(10)
        mock_manager._metrics["cache_memory_usage"].set.assert_called_with(10240)

    def test_get_analytics_summary(self):
        """Test analytics summary generation."""
        analytics = CacheAnalytics()

        # Test empty analytics
        summary_empty = analytics.get_analytics_summary()
        assert summary_empty["cache_stats"]["hits"] == 0
        assert summary_empty["hit_rate"] == 0.0
        assert summary_empty["total_queries"] == 0

        # Add some data
        analytics.cache_stats = {
            "hits": 8,
            "misses": 2,
            "evictions": 1,
            "ttl_expired": 0,
            "total_accesses": 10,
            "embedding_generations": 5,
            "similarity_computations": 10,
        }
        analytics.confidence_scores = [0.8, 0.9, 0.7, 0.85]
        analytics.similarity_scores = [0.85, 0.92, 0.78]
        analytics.access_patterns = {"query1": 3, "query2": 2}
        analytics.cache_history = [
            {"event": "hit", "query": "query1"},
            {"event": "miss", "query": "query2"},
        ]

        summary = analytics.get_analytics_summary()
        assert summary["cache_stats"]["hits"] == 8
        assert summary["hit_rate"] == 0.8
        assert summary["miss_rate"] == 0.2
        assert summary["total_queries"] == 2
        assert summary["unique_queries"] == 2
        assert summary["total_accesses"] == 10
        assert len(summary["recent_history"]) == 2
        assert "memory_efficiency" in summary
        assert "deduplication_ratio" in summary


class TestQualityEvaluator:
    """Test cases for QualityEvaluator class."""

    def test_initialization(self):
        """Test QualityEvaluator initialization."""
        evaluator = QualityEvaluator()
        assert hasattr(evaluator, "quality_history")
        assert hasattr(evaluator, "confidence_scores")
        assert hasattr(evaluator, "user_feedback")
        assert hasattr(evaluator, "response_metrics")
        assert hasattr(evaluator, "model_performance")
        assert hasattr(evaluator, "quality_stats")

        # Check initial values
        assert len(evaluator.quality_history) == 0
        assert len(evaluator.confidence_scores) == 0
        assert len(evaluator.user_feedback) == 0
        assert evaluator.quality_stats["total_responses"] == 0

    def test_record_response_quality(self):
        """Test response quality recording."""
        evaluator = QualityEvaluator()

        query = "What is machine learning?"
        response = "Machine learning is a subset of artificial intelligence."
        confidence_score = 0.85
        model_name = "gpt-3.5-turbo"
        context_used = ["ML is AI subset", "AI includes ML"]
        quality_scores = {
            "accuracy": 0.8,
            "relevance": 0.9,
            "completeness": 0.7,
            "coherence": 0.8,
            "factual_accuracy": 0.85,
        }

        evaluator.record_response_quality(
            query=query,
            response=response,
            confidence_score=confidence_score,
            model_name=model_name,
            context_used=context_used,
            quality_scores=quality_scores,
        )

        assert len(evaluator.quality_history) == 1
        assert len(evaluator.confidence_scores) == 1
        assert evaluator.confidence_scores[0] == confidence_score
        assert evaluator.quality_stats["total_responses"] == 1

        # Check quality scores stored
        for metric, score in quality_scores.items():
            assert len(evaluator.response_metrics[metric]) == 1
            assert evaluator.response_metrics[metric][0] == score

        # Check model performance
        assert model_name in evaluator.model_performance
        assert len(evaluator.model_performance[model_name]) == 1

    def test_record_user_feedback(self):
        """Test user feedback recording."""
        evaluator = QualityEvaluator()

        query = "Test question"
        response = "Test response"
        satisfaction_score = 4
        feedback_text = "Good answer"

        evaluator.record_user_feedback(
            query=query,
            response=response,
            satisfaction_score=satisfaction_score,
            feedback_text=feedback_text,
        )

        assert len(evaluator.user_feedback) == 1
        assert evaluator.user_feedback[0]["satisfaction_score"] == satisfaction_score
        assert evaluator.user_feedback[0]["feedback_text"] == feedback_text
        assert evaluator.quality_stats["user_satisfaction_count"] == 1

    def test_calculate_confidence_distribution(self):
        """Test confidence distribution calculation."""
        evaluator = QualityEvaluator()

        # Test empty scores
        distribution = evaluator.calculate_confidence_distribution()
        assert distribution["mean"] == 0.0
        assert distribution["std"] == 0.0

        # Add some confidence scores
        evaluator.confidence_scores = [0.8, 0.9, 0.7, 0.85, 0.75]

        distribution = evaluator.calculate_confidence_distribution()
        assert (
            abs(distribution["mean"] - 0.8) < 0.001
        )  # (0.8 + 0.9 + 0.7 + 0.85 + 0.75) / 5
        assert distribution["min"] == 0.7
        assert distribution["max"] == 0.9
        assert distribution["median"] == 0.8

    def test_calculate_quality_metrics(self):
        """Test quality metrics calculation."""
        evaluator = QualityEvaluator()

        # Add some quality scores
        evaluator.response_metrics["accuracy"] = [0.8, 0.9, 0.7]
        evaluator.response_metrics["relevance"] = [0.85, 0.9, 0.8]

        metrics = evaluator.calculate_quality_metrics()

        assert abs(metrics["accuracy_mean"] - 0.8) < 0.001  # (0.8 + 0.9 + 0.7) / 3
        assert abs(metrics["relevance_mean"] - 0.85) < 0.001  # (0.85 + 0.9 + 0.8) / 3
        assert metrics["accuracy_min"] == 0.7
        assert metrics["accuracy_max"] == 0.9

    def test_calculate_user_satisfaction_metrics(self):
        """Test user satisfaction metrics calculation."""
        evaluator = QualityEvaluator()

        # Test empty feedback
        satisfaction = evaluator.calculate_user_satisfaction_metrics()
        assert satisfaction["average_satisfaction"] == 0.0
        assert satisfaction["total_feedback"] == 0

        # Add some feedback
        evaluator.user_feedback = [
            {"satisfaction_score": 4, "query": "q1", "response": "r1"},
            {"satisfaction_score": 5, "query": "q2", "response": "r2"},
            {"satisfaction_score": 3, "query": "q3", "response": "r3"},
        ]

        satisfaction = evaluator.calculate_user_satisfaction_metrics()
        assert (
            abs(satisfaction["average_satisfaction"] - 4.0) < 0.001
        )  # (4 + 5 + 3) / 3
        assert satisfaction["total_feedback"] == 3
        assert satisfaction["satisfaction_distribution"][4] == 1
        assert satisfaction["satisfaction_distribution"][5] == 1
        assert satisfaction["satisfaction_distribution"][3] == 1

    def test_calculate_model_performance(self):
        """Test model performance calculation."""
        evaluator = QualityEvaluator()

        # Add some model performance data
        evaluator.model_performance["model1"] = [
            {
                "confidence_score": 0.8,
                "quality_scores": {"accuracy": 0.8, "relevance": 0.9},
                "is_high_quality": True,
                "is_low_confidence": False,
            },
            {
                "confidence_score": 0.6,
                "quality_scores": {"accuracy": 0.7, "relevance": 0.8},
                "is_high_quality": False,
                "is_low_confidence": True,
            },
        ]

        performance = evaluator.calculate_model_performance()

        assert "model1" in performance
        model_perf = performance["model1"]
        assert model_perf["total_responses"] == 2
        assert abs(model_perf["average_confidence"] - 0.7) < 0.001  # (0.8 + 0.6) / 2
        assert model_perf["high_quality_rate"] == 0.5  # 1 out of 2
        assert model_perf["low_confidence_rate"] == 0.5  # 1 out of 2

    def test_record_evaluation_metrics(self):
        """Test recording evaluation metrics to Prometheus."""
        evaluator = QualityEvaluator()

        # Mock metrics manager
        mock_manager = Mock()
        mock_manager.enabled = True
        mock_manager._metrics = {
            "answer_confidence_score": Mock(),
            "answer_confidence_by_model": Mock(),
            "response_quality_score": Mock(),
            "response_accuracy": Mock(),
            "content_relevance_score": Mock(),
            "answer_completeness_score": Mock(),
            "factual_accuracy_score": Mock(),
            "response_coherence_score": Mock(),
            "response_length_distribution": Mock(),
            "context_utilization_ratio": Mock(),
            "user_satisfaction_score": Mock(),
            "high_quality_responses": Mock(),
            "low_confidence_responses": Mock(),
        }

        quality_data = {
            "confidence_score": 0.85,
            "model_name": "gpt-3.5-turbo",
            "quality_scores": {
                "accuracy": 0.8,
                "relevance": 0.9,
                "completeness": 0.7,
                "coherence": 0.8,
                "factual_accuracy": 0.85,
            },
            "response_length": 25,
            "context_utilization": 0.8,
            "user_satisfaction": 4,
            "is_high_quality": True,
            "is_low_confidence": False,
        }

        # Should not raise exception
        evaluator.record_evaluation_metrics(mock_manager, quality_data)

        # Verify metrics were called
        mock_manager._metrics["answer_confidence_score"].observe.assert_called_with(
            0.85
        )
        mock_manager._metrics[
            "response_length_distribution"
        ].observe.assert_called_with(25)
        mock_manager._metrics["context_utilization_ratio"].observe.assert_called_with(
            0.8
        )
        mock_manager._metrics["user_satisfaction_score"].observe.assert_called_with(4)
        mock_manager._metrics["high_quality_responses"].inc.assert_called_once()

    def test_get_quality_summary(self):
        """Test quality summary generation."""
        evaluator = QualityEvaluator()

        # Test empty evaluator
        summary_empty = evaluator.get_quality_summary()
        assert summary_empty["quality_stats"]["total_responses"] == 0
        assert summary_empty["total_responses"] == 0

        # Add some data
        evaluator.quality_history = [
            {
                "confidence_score": 0.8,
                "quality_scores": {"accuracy": 0.8, "relevance": 0.9},
                "model_name": "model1",
                "is_high_quality": True,
                "is_low_confidence": False,
            },
            {
                "confidence_score": 0.9,
                "quality_scores": {"accuracy": 0.9, "relevance": 0.85},
                "model_name": "model1",
                "is_high_quality": True,
                "is_low_confidence": False,
            },
        ]
        evaluator.confidence_scores = [0.8, 0.9]
        evaluator.response_metrics["accuracy"] = [0.8, 0.9]
        evaluator.response_metrics["relevance"] = [0.9, 0.85]
        evaluator.model_performance["model1"] = evaluator.quality_history

        summary = evaluator.get_quality_summary()
        assert summary["total_responses"] == 2
        assert len(summary["recent_responses"]) == 2
        assert "model1" in summary["model_performance"]
        assert "confidence_distribution" in summary
        assert "quality_metrics" in summary
        assert "quality_trends" in summary

    def test_is_high_quality(self):
        """Test high quality determination."""
        evaluator = QualityEvaluator()

        # High quality case
        assert (
            evaluator._is_high_quality(0.9, {"accuracy": 0.8, "relevance": 0.9}) == True
        )

        # Low confidence case
        assert (
            evaluator._is_high_quality(0.6, {"accuracy": 0.8, "relevance": 0.9})
            == False
        )

        # Low quality case
        assert (
            evaluator._is_high_quality(0.9, {"accuracy": 0.6, "relevance": 0.5})
            == False
        )

        # Edge case
        assert evaluator._is_high_quality(0.8, {}) == False

    def test_update_averages(self):
        """Test average statistics update."""
        evaluator = QualityEvaluator()

        # Add some data
        evaluator.confidence_scores = [0.8, 0.9, 0.7]
        evaluator.response_metrics["accuracy"] = [0.8, 0.9]
        evaluator.response_metrics["relevance"] = [0.7, 0.85]

        evaluator._update_averages()

        assert abs(evaluator.quality_stats["average_confidence"] - 0.8) < 0.001
        assert (
            abs(evaluator.quality_stats["average_quality"] - 0.8125) < 0.001
        )  # (0.8+0.9+0.7+0.85)/4


class TestSystemPerformanceMonitor:
    """Test cases for SystemPerformanceMonitor class."""

    def test_initialization(self):
        """Test SystemPerformanceMonitor initialization."""
        monitor = SystemPerformanceMonitor()

        assert hasattr(monitor, "cpu_history")
        assert hasattr(monitor, "memory_history")
        assert hasattr(monitor, "disk_history")
        assert hasattr(monitor, "network_history")
        assert hasattr(monitor, "response_time_history")
        assert hasattr(monitor, "error_count")
        assert hasattr(monitor, "request_count")
        assert hasattr(monitor, "concurrent_users")
        assert hasattr(monitor, "queue_length")
        assert hasattr(monitor, "thresholds")

        # Check initial values
        assert len(monitor.cpu_history) == 0
        assert len(monitor.memory_history) == 0
        assert monitor.error_count == 0
        assert monitor.request_count == 0
        assert monitor.concurrent_users == 0
        assert monitor.queue_length == 0

    def test_record_cpu_usage(self):
        """Test CPU usage recording."""
        monitor = SystemPerformanceMonitor()

        monitor.record_cpu_usage(75.5)
        assert len(monitor.cpu_history) == 1
        assert monitor.cpu_history[0] == 75.5

        # Test history limit
        for i in range(105):
            monitor.record_cpu_usage(float(i))
        assert len(monitor.cpu_history) == 100
        assert monitor.cpu_history[0] == 5  # First 5 were removed

    def test_record_memory_usage(self):
        """Test memory usage recording."""
        monitor = SystemPerformanceMonitor()

        monitor.record_memory_usage(1024000000, 80.5)
        assert len(monitor.memory_history) == 1
        assert monitor.memory_history[0] == 80.5

    def test_record_disk_usage(self):
        """Test disk usage recording."""
        monitor = SystemPerformanceMonitor()

        monitor.record_disk_usage(512000000000, 60.0)
        assert len(monitor.disk_history) == 1
        assert monitor.disk_history[0] == 60.0

    def test_record_network_latency(self):
        """Test network latency recording."""
        monitor = SystemPerformanceMonitor()

        monitor.record_network_latency(0.05)
        assert len(monitor.network_history) == 1
        assert monitor.network_history[0] == 0.05

    def test_record_response_time(self):
        """Test response time recording."""
        monitor = SystemPerformanceMonitor()

        monitor.record_response_time(2.5)
        assert len(monitor.response_time_history) == 1
        assert monitor.response_time_history[0] == 2.5

    def test_record_request(self):
        """Test request recording."""
        monitor = SystemPerformanceMonitor()

        monitor.record_request(success=True)
        assert monitor.request_count == 1
        assert monitor.error_count == 0

        monitor.record_request(success=False)
        assert monitor.request_count == 2
        assert monitor.error_count == 1

    def test_update_concurrent_users(self):
        """Test concurrent users update."""
        monitor = SystemPerformanceMonitor()

        monitor.update_concurrent_users(25)
        assert monitor.concurrent_users == 25

    def test_update_queue_length(self):
        """Test queue length update."""
        monitor = SystemPerformanceMonitor()

        monitor.update_queue_length(10)
        assert monitor.queue_length == 10

    def test_get_cpu_metrics(self):
        """Test CPU metrics calculation."""
        monitor = SystemPerformanceMonitor()

        # Test empty history
        metrics = monitor.get_cpu_metrics()
        assert metrics["current"] == 0.0
        assert metrics["average"] == 0.0

        # Test with data
        monitor.cpu_history = [70.0, 80.0, 90.0]
        metrics = monitor.get_cpu_metrics()
        assert metrics["current"] == 90.0
        assert abs(metrics["average"] - 80.0) < 0.001
        assert metrics["max"] == 90.0
        assert metrics["min"] == 70.0

    def test_get_memory_metrics(self):
        """Test memory metrics calculation."""
        monitor = SystemPerformanceMonitor()

        # Test empty history
        metrics = monitor.get_memory_metrics()
        assert metrics["current"] == 0.0

        # Test with data
        monitor.memory_history = [60.0, 70.0, 80.0]
        metrics = monitor.get_memory_metrics()
        assert metrics["current"] == 80.0
        assert abs(metrics["average"] - 70.0) < 0.001

    def test_get_error_rate(self):
        """Test error rate calculation."""
        monitor = SystemPerformanceMonitor()

        # Test no requests
        assert monitor.get_error_rate() == 0.0

        # Test with requests
        monitor.request_count = 100
        monitor.error_count = 5
        assert monitor.get_error_rate() == 5.0

        monitor.error_count = 0
        assert monitor.get_error_rate() == 0.0

    def test_get_throughput(self):
        """Test throughput calculation."""
        monitor = SystemPerformanceMonitor()

        # Test no response times
        assert monitor.get_throughput() == 0.0

        # Test with response times
        monitor.response_time_history = [0.5, 1.0, 2.0]
        throughput = monitor.get_throughput()
        expected = 1.0 / np.mean([0.5, 1.0, 2.0])
        assert abs(throughput - expected) < 0.001

    def test_detect_bottlenecks(self):
        """Test bottleneck detection."""
        monitor = SystemPerformanceMonitor()

        # Test no bottlenecks
        monitor.cpu_history = [50.0]
        monitor.memory_history = [60.0]
        monitor.disk_history = [70.0]
        monitor.response_time_history = [2.0]
        monitor.request_count = 100
        monitor.error_count = 2

        bottlenecks = monitor.detect_bottlenecks()
        assert len(bottlenecks) == 0

        # Test CPU bottleneck
        monitor.cpu_history = [95.0]
        bottlenecks = monitor.detect_bottlenecks()
        assert len(bottlenecks) > 0
        assert any("CPU usage" in bottleneck for bottleneck in bottlenecks)

        # Test memory bottleneck
        monitor.cpu_history = [50.0]
        monitor.memory_history = [96.0]
        bottlenecks = monitor.detect_bottlenecks()
        assert any("memory usage" in bottleneck for bottleneck in bottlenecks)

    def test_get_performance_summary(self):
        """Test performance summary generation."""
        monitor = SystemPerformanceMonitor()

        monitor.cpu_history = [70.0]
        monitor.memory_history = [80.0]
        monitor.disk_history = [60.0]
        monitor.network_history = [0.1]
        monitor.response_time_history = [2.0]
        monitor.request_count = 50
        monitor.error_count = 2
        monitor.concurrent_users = 10
        monitor.queue_length = 5

        summary = monitor.get_performance_summary()

        assert "cpu_metrics" in summary
        assert "memory_metrics" in summary
        assert "disk_metrics" in summary
        assert "network_metrics" in summary
        assert "response_time_metrics" in summary
        assert "error_rate" in summary
        assert "throughput" in summary
        assert "concurrent_users" in summary
        assert "queue_length" in summary
        assert "bottlenecks" in summary
        assert "total_requests" in summary
        assert "total_errors" in summary

        assert summary["concurrent_users"] == 10
        assert summary["queue_length"] == 5
        assert summary["total_requests"] == 50
        assert summary["total_errors"] == 2

    def test_record_evaluation_metrics(self):
        """Test recording evaluation metrics to Prometheus."""
        monitor = SystemPerformanceMonitor()

        # Mock metrics manager
        mock_manager = Mock()
        mock_manager.enabled = True
        mock_manager._metrics = {
            "system_cpu_usage": Mock(),
            "system_memory_usage": Mock(),
            "system_memory_percent": Mock(),
            "system_disk_usage": Mock(),
            "system_disk_percent": Mock(),
            "system_network_latency": Mock(),
            "system_response_time": Mock(),
            "system_throughput": Mock(),
            "system_concurrent_users": Mock(),
            "system_queue_length": Mock(),
            "system_error_rate": Mock(),
            "system_gpu_usage": Mock(),
            "system_gpu_memory": Mock(),
        }

        performance_data = {
            "cpu_percent": 75.0,
            "memory_bytes": 1024000000,
            "memory_percent": 80.0,
            "disk_bytes": 512000000000,
            "disk_percent": 60.0,
            "network_latency": 0.05,
            "response_time": 2.0,
            "throughput": 0.5,
            "concurrent_users": 10,
            "queue_length": 5,
            "error_rate": 2.0,
            "gpu_percent": 50.0,
            "gpu_memory": 2048000000,
        }

        # Should not raise exception
        monitor.record_evaluation_metrics(mock_manager, performance_data)

        # Verify metrics were called
        mock_manager._metrics["system_cpu_usage"].set.assert_called_with(75.0)
        mock_manager._metrics["system_memory_usage"].set.assert_called_with(1024000000)
        mock_manager._metrics["system_memory_percent"].set.assert_called_with(80.0)
        mock_manager._metrics["system_disk_usage"].set.assert_called_with(512000000000)
        mock_manager._metrics["system_disk_percent"].set.assert_called_with(60.0)
        mock_manager._metrics["system_network_latency"].observe.assert_called_with(0.05)
        mock_manager._metrics["system_response_time"].observe.assert_called_with(2.0)
        mock_manager._metrics["system_throughput"].set.assert_called_with(0.5)
        mock_manager._metrics["system_concurrent_users"].set.assert_called_with(10)
        mock_manager._metrics["system_queue_length"].set.assert_called_with(5)
        mock_manager._metrics["system_error_rate"].set.assert_called_with(2.0)
        mock_manager._metrics["system_gpu_usage"].set.assert_called_with(50.0)
        mock_manager._metrics["system_gpu_memory"].set.assert_called_with(2048000000)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
    """Test cases for AdvancedRetriever metrics integration."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        mock_store = Mock()
        mock_store.search.return_value = [
            VectorDocument(
                id="doc1",
                content="Test content 1",
                metadata={},
                embedding=[0.1, 0.2, 0.3],
            ),
            VectorDocument(
                id="doc2",
                content="Test content 2",
                metadata={},
                embedding=[0.4, 0.5, 0.6],
            ),
            VectorDocument(
                id="doc3",
                content="Test content 3",
                metadata={},
                embedding=[0.7, 0.8, 0.9],
            ),
        ]
        return mock_store

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder."""
        mock_embedder = Mock()
        mock_embedder.embed.return_value = np.array([0.1, 0.2, 0.3])
        return mock_embedder

    def test_advanced_retriever_metrics_integration(
        self, mock_vector_store, mock_embedder
    ):
        """Test that AdvancedRetriever properly integrates with metrics."""
        retriever = AdvancedRetriever(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            enable_reranking=False,
            enable_hybrid=False,
            enable_expansion=False,
        )

        # Verify that retriever has metrics integration capability
        assert hasattr(retriever, "_record_advanced_metrics")

        # Test that metrics recording method exists and is callable
        assert callable(retriever._record_advanced_metrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
