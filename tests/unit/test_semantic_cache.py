"""
تست‌های واحد برای کش معنایی

این ماژول شامل تست‌های واحد برای سیستم کش معنایی است.
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from ragbot.caching.adaptive_cache import AdaptiveCache
from ragbot.caching.cache_metrics import CacheMetricsCollector, CachePerformanceAnalyzer
from ragbot.caching.semantic_cache import SemanticCache


class TestSemanticCache:
    """تست‌های کش معنایی."""

    @pytest.fixture
    async def semantic_cache(self):
        """فیکسچر برای ایجاد کش معنایی."""
        cache = SemanticCache(similarity_threshold=0.8, max_size=10, ttl_seconds=3600)
        yield cache
        # Cleanup
        await cache.clear_cache()

    @pytest.mark.asyncio
    async def test_cache_initialization(self, semantic_cache):
        """تست مقداردهی اولیه کش."""
        assert semantic_cache.similarity_threshold == 0.8
        assert semantic_cache.max_size == 10
        assert semantic_cache.ttl_seconds == 3600
        assert len(semantic_cache.cache) == 0
        assert semantic_cache.hit_count == 0
        assert semantic_cache.miss_count == 0

    @pytest.mark.asyncio
    async def test_cache_answer(self, semantic_cache):
        """تست ذخیره پاسخ در کش."""
        query = "What is machine learning?"
        answer = "Machine learning is a subset of artificial intelligence"
        context = ["ML is a subset of AI", "It involves learning from data"]
        metadata = {"language": "en", "timestamp": time.time()}
        confidence_score = 0.9

        # Mock the embedding method
        with patch.object(semantic_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            await semantic_cache.cache_answer(
                query=query,
                answer=answer,
                context=context,
                metadata=metadata,
                confidence_score=confidence_score,
            )

        assert len(semantic_cache.cache) == 1
        mock_embed.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_cache_hit(self, semantic_cache):
        """تست cache hit."""
        query = "What is machine learning?"
        answer = "Machine learning is a subset of AI"
        context = ["ML is AI subset"]
        metadata = {}
        confidence_score = 0.9

        # Mock embedding methods
        with patch.object(semantic_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            # Cache the answer
            await semantic_cache.cache_answer(
                query=query,
                answer=answer,
                context=context,
                metadata=metadata,
                confidence_score=confidence_score,
            )

            # Search for similar query
            similar_query = "What is ML?"
            result = await semantic_cache.get_similar_answer(similar_query)

        # Verify hit
        assert result is not None
        assert result.answer == answer
        assert result.confidence_score == confidence_score
        assert semantic_cache.hit_count == 1

    @pytest.mark.asyncio
    async def test_cache_miss(self, semantic_cache):
        """تست cache miss."""
        query = "What is machine learning?"
        answer = "Machine learning is a subset of AI"
        context = ["ML is AI subset"]
        metadata = {}
        confidence_score = 0.9

        # Mock embedding methods
        with patch.object(semantic_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            # Cache the answer
            await semantic_cache.cache_answer(
                query=query,
                answer=answer,
                context=context,
                metadata=metadata,
                confidence_score=confidence_score,
            )

            # Mock different embedding for unrelated query (completely different vector)
            mock_embed.return_value = [-0.9, -0.8, -0.7, -0.6, -0.5]

            # Search for unrelated query
            unrelated_query = "How to cook pasta?"
            result = await semantic_cache.get_similar_answer(unrelated_query)

        # Verify miss
        assert result is None
        assert semantic_cache.miss_count == 1

    @pytest.mark.asyncio
    async def test_cache_eviction(self, semantic_cache):
        """تست حذف ورودی‌های کش."""
        # Fill cache to max capacity
        for i in range(semantic_cache.max_size + 1):
            query = f"Question {i}"
            answer = f"Answer {i}"

            with patch.object(semantic_cache, "_get_query_embedding") as mock_embed:
                mock_embed.return_value = [float(i)] * 5

                await semantic_cache.cache_answer(
                    query=query,
                    answer=answer,
                    context=[f"Context {i}"],
                    metadata={},
                    confidence_score=0.8,
                )

        # Verify eviction occurred
        assert len(semantic_cache.cache) == semantic_cache.max_size
        assert semantic_cache.eviction_count == 1

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self, semantic_cache):
        """تست انقضای TTL."""
        # Create cache with short TTL
        short_ttl_cache = SemanticCache(ttl_seconds=1)

        query = "Test query"
        answer = "Test answer"

        with patch.object(short_ttl_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            # Cache answer
            await short_ttl_cache.cache_answer(
                query=query,
                answer=answer,
                context=["Test context"],
                metadata={},
                confidence_score=0.8,
            )

        assert len(short_ttl_cache.cache) == 1

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Trigger cleanup
        await short_ttl_cache._cleanup_expired()

        assert len(short_ttl_cache.cache) == 0

    @pytest.mark.asyncio
    async def test_cosine_similarity(self, semantic_cache):
        """تست محاسبه شباهت کسینوسی."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]

        # Test identical vectors
        similarity = semantic_cache._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-6

        # Test orthogonal vectors
        similarity = semantic_cache._cosine_similarity(vec1, vec3)
        assert abs(similarity - 0.0) < 1e-6

    @pytest.mark.asyncio
    async def test_cache_stats(self, semantic_cache):
        """تست آمار کش."""
        # Initially empty stats
        stats = await semantic_cache.get_cache_stats()
        assert stats["cache_size"] == 0
        assert stats["hit_rate"] == 0

        # Add some data and stats
        with patch.object(semantic_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            await semantic_cache.cache_answer(
                query="Test query",
                answer="Test answer",
                context=["Test context"],
                metadata={},
                confidence_score=0.8,
            )

            # Simulate hit and miss
            await semantic_cache.get_similar_answer("Test query")

            # Mock different embedding for completely different query
            mock_embed.return_value = [-0.1, -0.2, -0.3, -0.4, -0.5]
            await semantic_cache.get_similar_answer("Completely different query")

        stats = await semantic_cache.get_cache_stats()
        assert stats["cache_size"] == 1
        assert stats["hit_count"] == 1
        assert stats["miss_count"] == 1
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_cache_export_import(self, semantic_cache):
        """تست صادرات و واردات کش."""
        query = "Test query"
        answer = "Test answer"

        with patch.object(semantic_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            # Cache some data
            await semantic_cache.cache_answer(
                query=query,
                answer=answer,
                context=["Test context"],
                metadata={"test": "data"},
                confidence_score=0.8,
            )

        # Export cache
        exported_data = await semantic_cache.export_cache()
        assert "cache_entries" in exported_data
        assert "stats" in exported_data
        assert len(exported_data["cache_entries"]) == 1

        # Clear and import
        await semantic_cache.clear_cache()
        assert len(semantic_cache.cache) == 0

        await semantic_cache.import_cache(exported_data)
        assert len(semantic_cache.cache) == 1


class TestAdaptiveCache:
    """تست‌های کش تطبیقی."""

    @pytest.fixture
    async def adaptive_cache(self):
        """فیکسچر برای ایجاد کش تطبیقی."""
        cache = AdaptiveCache(
            similarity_threshold=0.8,
            max_size=5,
            ttl_seconds=3600,
            eviction_strategy="adaptive",
        )
        yield cache
        await cache.clear_cache()

    @pytest.mark.asyncio
    async def test_adaptive_eviction(self, adaptive_cache):
        """تست حذف تطبیقی."""
        # Fill cache with different quality scores
        queries = [
            ("High quality query", 0.9),
            ("Medium quality query", 0.7),
            ("Low quality query", 0.4),
            ("Very high quality query", 0.95),
            ("Very low quality query", 0.2),
        ]

        with patch.object(adaptive_cache, "_get_query_embedding") as mock_embed:
            for i, (query, quality) in enumerate(queries):
                mock_embed.return_value = [float(i)] * 5

                await adaptive_cache.cache_answer(
                    query=query,
                    answer=f"Answer for {query}",
                    context=[f"Context for {query}"],
                    metadata={},
                    confidence_score=quality,
                )

        assert len(adaptive_cache.cache) == 5

        # Add one more to trigger eviction
        with patch.object(adaptive_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [6.0] * 5

            await adaptive_cache.cache_answer(
                query="Trigger eviction",
                answer="Eviction answer",
                context=["Eviction context"],
                metadata={},
                confidence_score=0.8,
            )

        # Should evict the lowest quality entry
        assert len(adaptive_cache.cache) == 5
        assert adaptive_cache.eviction_count == 1

    @pytest.mark.asyncio
    async def test_access_pattern_analysis(self, adaptive_cache):
        """تست تحلیل الگوی دسترسی."""
        query = "Test query"

        with patch.object(adaptive_cache, "_get_query_embedding") as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

            # Cache answer
            await adaptive_cache.cache_answer(
                query=query,
                answer="Test answer",
                context=["Test context"],
                metadata={},
                confidence_score=0.8,
            )

            # Access multiple times
            for _ in range(3):
                await adaptive_cache.get_similar_answer(query)

        # Check access patterns
        patterns = await adaptive_cache.get_access_patterns()
        assert query in patterns
        assert patterns[query]["access_frequency"] > 0

    @pytest.mark.asyncio
    async def test_cache_optimization(self, adaptive_cache):
        """تست بهینه‌سازی کش."""
        initial_size = adaptive_cache.max_size

        # Simulate high hit rate
        adaptive_cache.hit_count = 80
        adaptive_cache.miss_count = 20

        await adaptive_cache.optimize_cache_size()

        # Should increase cache size due to high hit rate
        assert adaptive_cache.max_size >= initial_size

    @pytest.mark.asyncio
    async def test_performance_prediction(self, adaptive_cache):
        """تست پیش‌بینی عملکرد."""
        # Add some test data
        adaptive_cache.hit_count = 70
        adaptive_cache.miss_count = 30

        prediction = await adaptive_cache.predict_cache_performance()

        assert "current_hit_rate" in prediction
        assert "hit_rate_trend" in prediction
        assert "optimal_cache_size" in prediction
        assert "recommended_strategy" in prediction
        assert prediction["current_hit_rate"] == 0.7


class TestCacheMetrics:
    """تست‌های متریک‌های کش."""

    @pytest.fixture
    def metrics_collector(self):
        """فیکسچر برای جمع‌آورنده متریک‌ها."""
        return CacheMetricsCollector()

    def test_metrics_recording(self, metrics_collector):
        """تست ثبت متریک‌ها."""
        # Record some metrics
        metrics_collector.record_cache_hit()
        metrics_collector.record_cache_miss()
        metrics_collector.update_cache_size(100)
        metrics_collector.update_hit_rate(0.8)

        # Get summary
        summary = metrics_collector.get_metrics_summary()

        assert summary["cache_hits"] == 1
        assert summary["cache_misses"] == 1
        assert summary["cache_size"] == 100
        assert summary["hit_rate"] == 0.8

    @pytest.mark.asyncio
    async def test_performance_analyzer(self):
        """تست تحلیلگر عملکرد."""
        analyzer = CachePerformanceAnalyzer()

        test_stats = {
            "hit_rate": 0.7,
            "cache_size": 500,
            "max_size": 1000,
            "eviction_count": 10,
        }

        analysis = await analyzer.analyze_performance(test_stats)

        assert "current_performance" in analysis
        assert "trends" in analysis
        assert "alerts" in analysis
        assert "recommendations" in analysis

    @pytest.mark.asyncio
    async def test_alert_generation(self):
        """تست تولید هشدارها."""
        analyzer = CachePerformanceAnalyzer()

        # Low hit rate scenario
        low_hit_stats = {"hit_rate": 0.4, "cache_size": 900, "max_size": 1000}

        alerts = await analyzer._check_alerts(low_hit_stats)

        assert len(alerts) > 0
        assert any(alert["type"] == "low_hit_rate" for alert in alerts)

    @pytest.mark.asyncio
    async def test_recommendations(self):
        """تست تولید توصیه‌ها."""
        analyzer = CachePerformanceAnalyzer()

        # Low utilization scenario
        low_util_stats = {"hit_rate": 0.5, "cache_size": 200, "max_size": 1000}

        recommendations = await analyzer._generate_recommendations(low_util_stats)

        assert len(recommendations) > 0
        assert any("low" in rec.lower() for rec in recommendations)


@pytest.mark.asyncio
async def test_integration_scenario():
    """تست سناریوی یکپارچه."""
    # Create cache with metrics
    cache = AdaptiveCache(max_size=3, eviction_strategy="adaptive")
    metrics = CacheMetricsCollector()

    try:
        # Simulate real usage
        queries_and_answers = [
            ("What is Python?", "Python is a programming language", 0.9),
            ("How to use Python?", "You can use Python for various tasks", 0.8),
            ("Python vs Java", "Python and Java are different languages", 0.7),
            ("Machine learning with Python", "Python is great for ML", 0.85),
        ]

        with patch.object(cache, "_get_query_embedding") as mock_embed:
            for i, (query, answer, confidence) in enumerate(queries_and_answers):
                mock_embed.return_value = [float(i)] * 5

                # Try to get from cache first
                result = await cache.get_similar_answer(query)
                if result:
                    metrics.record_cache_hit()
                else:
                    metrics.record_cache_miss()

                    # Cache the answer
                    await cache.cache_answer(
                        query=query,
                        answer=answer,
                        context=[f"Context for {query}"],
                        metadata={"source": "test"},
                        confidence_score=confidence,
                    )

        # Verify final state
        cache_stats = await cache.get_cache_stats()
        metrics_summary = metrics.get_metrics_summary()

        assert cache_stats["cache_size"] <= cache.max_size
        assert metrics_summary["cache_misses"] > 0

    finally:
        await cache.clear_cache()
