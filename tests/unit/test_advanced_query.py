"""
Unit tests for Advanced Query Features

Tests for aggregation, filtering, scoring, and optimization capabilities.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from ragbot.rag.query import (
    QueryAggregator,
    AggregationType,
    AggregationQuery,
    AggregationResult,
    AdvancedFilter,
    FilterOperator,
    FilterCondition,
    CustomScorer,
    ScoredDocument,
    QueryOptimizer,
    QueryPlan,
    OptimizationResult,
)


class TestQueryAggregator:
    """Test QueryAggregator functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing"""
        store = Mock()
        store.get_documents_by_metadata = AsyncMock(return_value=[])
        store.get_all_documents = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        docs = []
        for i in range(10):
            doc = Mock()
            doc.id = f"doc_{i}"
            doc.score = 0.5 + (i * 0.1)
            doc.metadata = {
                "category": f"cat_{i % 3}",
                "score": 10 + i,
                "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
            }
            docs.append(doc)
        return docs

    @pytest.fixture
    def aggregator(self, mock_vector_store):
        """QueryAggregator instance for testing"""
        return QueryAggregator(mock_vector_store)

    @pytest.mark.asyncio
    async def test_group_by_metadata_count(self, aggregator, sample_documents):
        """Test grouping by metadata with count aggregation"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        result = await aggregator.group_by_metadata(
            "category", aggregation=AggregationType.COUNT
        )

        assert isinstance(result, dict)
        assert "cat_0" in result
        assert "cat_1" in result
        assert "cat_2" in result
        assert result["cat_0"] == 4  # 0, 3, 6, 9
        assert result["cat_1"] == 3  # 1, 4, 7
        assert result["cat_2"] == 3  # 2, 5, 8

    @pytest.mark.asyncio
    async def test_group_by_metadata_avg(self, aggregator, sample_documents):
        """Test grouping by metadata with average aggregation"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        result = await aggregator.group_by_metadata(
            "category", aggregation=AggregationType.AVG
        )

        assert isinstance(result, dict)
        assert all(isinstance(v, float) for v in result.values())

    @pytest.mark.asyncio
    async def test_count_by_date_range(self, aggregator, sample_documents):
        """Test counting documents by date range"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        count = await aggregator.count_by_date_range(start_date, end_date)

        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_aggregate_scores(self, aggregator, sample_documents):
        """Test score aggregation"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        result = await aggregator.aggregate_scores(AggregationType.SUM)

        assert isinstance(result, float)
        assert result > 0

    @pytest.mark.asyncio
    async def test_statistical_summary(self, aggregator, sample_documents):
        """Test statistical summary generation"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        summary = await aggregator.statistical_summary("score")

        assert isinstance(summary, dict)
        assert "count" in summary
        assert "mean" in summary
        assert "min" in summary
        assert "max" in summary
        assert "std_dev" in summary

    @pytest.mark.asyncio
    async def test_execute_aggregation_query(self, aggregator, sample_documents):
        """Test executing complex aggregation query"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        query = AggregationQuery(
            field="score", operation=AggregationType.AVG, group_by=["category"]
        )

        result = await aggregator.execute_aggregation_query(query)

        assert isinstance(result, AggregationResult)
        assert isinstance(result.data, dict)
        assert result.total_count == len(sample_documents)
        assert result.execution_time >= 0

    @pytest.mark.asyncio
    async def test_percentile_analysis(self, aggregator, sample_documents):
        """Test percentile analysis"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        percentiles = await aggregator.percentile_analysis("score", [25, 50, 75])

        assert isinstance(percentiles, dict)
        assert "p25" in percentiles
        assert "p50" in percentiles
        assert "p75" in percentiles

    @pytest.mark.asyncio
    async def test_mode_analysis(self, aggregator, sample_documents):
        """Test mode analysis"""
        aggregator.vector_store.get_documents_by_metadata.return_value = (
            sample_documents
        )

        mode_result = await aggregator.mode_analysis("category")

        assert isinstance(mode_result, dict)
        assert "mode" in mode_result
        assert "frequency" in mode_result


class TestAdvancedFilter:
    """Test AdvancedFilter functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing"""
        store = Mock()
        store.get_all_documents = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        docs = []
        for i in range(10):
            doc = Mock()
            doc.id = f"doc_{i}"
            doc.metadata = {
                "score": 10 + i,
                "category": f"cat_{i % 3}",
                "title": f"Title {i}",
                "location": {"lat": 35.0 + i * 0.1, "lon": 51.0 + i * 0.1},
            }
            docs.append(doc)
        return docs

    @pytest.fixture
    def advanced_filter(self, mock_vector_store):
        """AdvancedFilter instance for testing"""
        return AdvancedFilter(mock_vector_store)

    @pytest.mark.asyncio
    async def test_range_filter(self, advanced_filter, sample_documents):
        """Test range filtering"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        result = await advanced_filter.range_filter("score", 12, 15)

        assert isinstance(result, list)
        assert all(isinstance(doc_id, str) for doc_id in result)

    @pytest.mark.asyncio
    async def test_regex_filter(self, advanced_filter, sample_documents):
        """Test regex filtering"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        result = await advanced_filter.regex_filter("title", r"Title [0-5]")

        assert isinstance(result, list)
        assert len(result) <= len(sample_documents)

    @pytest.mark.asyncio
    async def test_composite_filter(self, advanced_filter, sample_documents):
        """Test composite filtering"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        conditions = [
            FilterCondition("score", FilterOperator.GT, 12),
            FilterCondition("category", FilterOperator.EQ, "cat_0"),
        ]

        result = await advanced_filter.composite_filter(conditions, logic="AND")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_geo_filter(self, advanced_filter, sample_documents):
        """Test geographic filtering"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        result = await advanced_filter.geo_filter(35.0, 51.0, 1.0)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_date_range_filter(self, advanced_filter, sample_documents):
        """Test date range filtering"""
        # Add date metadata to sample documents
        for i, doc in enumerate(sample_documents):
            doc.metadata["created_at"] = (
                datetime.now() - timedelta(days=i)
            ).isoformat()

        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        result = await advanced_filter.date_range_filter(
            "created_at", start_date, end_date
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_text_search_filter(self, advanced_filter, sample_documents):
        """Test text search filtering"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        result = await advanced_filter.text_search_filter(
            "title", "Title 1", "starts_with"
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_numeric_filter(self, advanced_filter, sample_documents):
        """Test numeric filtering"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        result = await advanced_filter.numeric_filter("score", FilterOperator.GT, 12)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_array_filter(self, advanced_filter, sample_documents):
        """Test array filtering"""
        # Add array metadata to sample documents
        for i, doc in enumerate(sample_documents):
            doc.metadata["tags"] = [f"tag_{i}", f"category_{i % 3}"]

        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        result = await advanced_filter.array_filter(
            "tags", FilterOperator.IN, ["tag_1", "tag_2"]
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_filter_statistics(self, advanced_filter, sample_documents):
        """Test filter statistics"""
        advanced_filter.vector_store.get_all_documents.return_value = sample_documents

        stats = await advanced_filter.get_filter_statistics()

        assert isinstance(stats, dict)
        assert "cached_patterns" in stats
        assert "total_documents" in stats
        assert "available_fields" in stats


class TestCustomScorer:
    """Test CustomScorer functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing"""
        return Mock()

    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        docs = []
        for i in range(10):
            doc = Mock()
            doc.id = f"doc_{i}"
            doc.score = 0.5 + (i * 0.05)
            doc.content = f"Content {i}" * 100  # Vary content length
            doc.metadata = {
                "view_count": 100 + i * 10,
                "like_count": 10 + i,
                "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
            }
            docs.append(doc)
        return docs

    @pytest.fixture
    def custom_scorer(self, mock_vector_store):
        """CustomScorer instance for testing"""
        return CustomScorer(mock_vector_store)

    @pytest.mark.asyncio
    async def test_weighted_scoring(self, custom_scorer, sample_documents):
        """Test weighted scoring"""
        weights = {
            "semantic_similarity": 0.5,
            "content_length": 0.2,
            "metadata_quality": 0.2,
            "recency": 0.1,
        }

        result = await custom_scorer.weighted_scoring(sample_documents, weights)

        assert isinstance(result, list)
        assert len(result) == len(sample_documents)
        assert all(isinstance(doc, ScoredDocument) for doc in result)
        assert all(0 <= doc.final_score <= 1 for doc in result)

    @pytest.mark.asyncio
    async def test_time_decay_scoring(self, custom_scorer, sample_documents):
        """Test time decay scoring"""
        result = await custom_scorer.time_decay_scoring(
            sample_documents, decay_factor=0.1
        )

        assert isinstance(result, list)
        assert len(result) == len(sample_documents)
        assert all(isinstance(doc, ScoredDocument) for doc in result)

    @pytest.mark.asyncio
    async def test_popularity_scoring(self, custom_scorer, sample_documents):
        """Test popularity scoring"""
        result = await custom_scorer.popularity_scoring(sample_documents)

        assert isinstance(result, list)
        assert len(result) == len(sample_documents)
        assert all(isinstance(doc, ScoredDocument) for doc in result)

    @pytest.mark.asyncio
    async def test_semantic_boost_scoring(self, custom_scorer, sample_documents):
        """Test semantic boost scoring"""
        result = await custom_scorer.semantic_boost_scoring(sample_documents)

        assert isinstance(result, list)
        assert len(result) == len(sample_documents)
        assert all(isinstance(doc, ScoredDocument) for doc in result)

    @pytest.mark.asyncio
    async def test_hybrid_scoring(self, custom_scorer, sample_documents):
        """Test hybrid scoring"""
        result = await custom_scorer.hybrid_scoring(sample_documents)

        assert isinstance(result, list)
        assert len(result) == len(sample_documents)
        assert all(isinstance(doc, ScoredDocument) for doc in result)

    @pytest.mark.asyncio
    async def test_custom_scoring(self, custom_scorer, sample_documents):
        """Test custom scoring function"""

        def custom_score_func(doc):
            return doc.score * 1.5

        result = await custom_scorer.custom_scoring(sample_documents, custom_score_func)

        assert isinstance(result, list)
        assert len(result) == len(sample_documents)
        assert all(isinstance(doc, ScoredDocument) for doc in result)

    @pytest.mark.asyncio
    async def test_get_scoring_statistics(self, custom_scorer):
        """Test scoring statistics"""
        stats = await custom_scorer.get_scoring_statistics()

        assert isinstance(stats, dict)
        assert "cached_scores" in stats
        assert "cache_ttl" in stats
        assert "available_strategies" in stats

    @pytest.mark.asyncio
    async def test_benchmark_scoring_strategies(self, custom_scorer, sample_documents):
        """Test scoring strategy benchmarking"""
        result = await custom_scorer.benchmark_scoring_strategies(
            sample_documents, sample_size=5
        )

        assert isinstance(result, dict)
        assert "weighted" in result
        assert "time_decay" in result
        assert "popularity" in result
        assert "hybrid" in result


class TestQueryOptimizer:
    """Test QueryOptimizer functionality"""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing"""
        return Mock()

    @pytest.fixture
    def query_optimizer(self, mock_vector_store):
        """QueryOptimizer instance for testing"""
        return QueryOptimizer(mock_vector_store)

    @pytest.mark.asyncio
    async def test_optimize_query_simple(self, query_optimizer):
        """Test simple query optimization"""
        query = "test query"
        filters = {"category": "test"}

        result = await query_optimizer.optimize_query(query, filters)

        assert isinstance(result, OptimizationResult)
        assert isinstance(result.original_plan, QueryPlan)
        assert isinstance(result.optimized_plan, QueryPlan)
        assert isinstance(result.improvement_percentage, float)
        assert isinstance(result.recommendations, list)
        assert isinstance(result.performance_metrics, dict)

    @pytest.mark.asyncio
    async def test_optimize_query_complex(self, query_optimizer):
        """Test complex query optimization"""
        query = "very long query with many words that should trigger optimization strategies"
        filters = {
            "category": "test",
            "score": {"$gte": 10, "$lte": 100},
            "tags": ["tag1", "tag2", "tag3"],
        }

        result = await query_optimizer.optimize_query(query, filters)

        assert isinstance(result, OptimizationResult)
        assert len(result.optimized_plan.optimization_applied) > 0

    @pytest.mark.asyncio
    async def test_query_analysis(self, query_optimizer):
        """Test query analysis"""
        query = "test query"
        filters = {"category": "test"}

        analysis = await query_optimizer._analyze_query(query, filters)

        assert isinstance(analysis, dict)
        assert "query_length" in analysis
        assert "has_filters" in analysis
        assert "filter_complexity" in analysis
        assert "estimated_result_size" in analysis
        assert "query_type" in analysis
        assert "performance_hints" in analysis
        assert "complexity_score" in analysis

    @pytest.mark.asyncio
    async def test_execution_plan_creation(self, query_optimizer):
        """Test execution plan creation"""
        analysis = {
            "query_length": 5,
            "has_filters": True,
            "filter_complexity": 2,
            "estimated_result_size": 100,
            "query_type": "search",
            "performance_hints": [],
            "complexity_score": 0.3,
        }

        plan = await query_optimizer._create_execution_plan(analysis)

        assert isinstance(plan, QueryPlan)
        assert isinstance(plan.steps, list)
        assert isinstance(plan.estimated_cost, float)
        assert isinstance(plan.estimated_result_size, int)

    @pytest.mark.asyncio
    async def test_optimization_application(self, query_optimizer):
        """Test optimization application"""
        analysis = {
            "query_length": 25,
            "has_filters": True,
            "filter_complexity": 8,
            "estimated_result_size": 15000,
            "query_type": "search",
            "performance_hints": ["long_query", "complex_filters", "large_result_set"],
            "complexity_score": 0.8,
        }

        original_plan = QueryPlan(
            steps=["parse_query", "apply_filters", "vector_search"],
            estimated_cost=10.0,
            execution_time=0.0,
            optimization_applied=[],
            estimated_result_size=15000,
        )

        optimized_plan = await query_optimizer._apply_optimizations(
            original_plan, analysis
        )

        assert isinstance(optimized_plan, QueryPlan)
        assert len(optimized_plan.optimization_applied) > 0
        assert optimized_plan.estimated_cost < original_plan.estimated_cost

    @pytest.mark.asyncio
    async def test_get_optimization_statistics(self, query_optimizer):
        """Test optimization statistics"""
        # Add some query history
        query_optimizer.query_history = [
            {
                "query": "test query",
                "timestamp": datetime.now().isoformat(),
                "analysis": {},
                "original_plan": {
                    "steps": ["parse_query", "vector_search"],
                    "estimated_cost": 10.0,
                    "estimated_result_size": 100,
                },
                "optimized_plan": {
                    "steps": ["parse_query", "check_cache", "vector_search"],
                    "estimated_cost": 8.0,
                    "optimizations_applied": ["cache_optimization"],
                },
                "improvement": 15.5,
            }
        ]

        stats = await query_optimizer.get_optimization_statistics()

        assert isinstance(stats, dict)
        assert "total_queries" in stats
        assert "avg_improvement" in stats
        assert "most_common_optimizations" in stats
        assert "performance_trends" in stats

    @pytest.mark.asyncio
    async def test_benchmark_optimization(self, query_optimizer):
        """Test optimization benchmarking"""
        sample_queries = [
            "simple query",
            "complex query with many filters and conditions",
            "another test query",
        ]

        result = await query_optimizer.benchmark_optimization(sample_queries)

        assert isinstance(result, dict)
        assert "queries_tested" in result
        assert "avg_improvement" in result
        assert "optimization_effectiveness" in result
        assert "performance_gains" in result


class TestIntegration:
    """Integration tests for advanced query features"""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for integration testing"""
        store = Mock()
        store.get_documents_by_metadata = AsyncMock(return_value=[])
        store.get_all_documents = AsyncMock(return_value=[])
        return store

    @pytest.mark.asyncio
    async def test_aggregation_with_filtering(self, mock_vector_store):
        """Test aggregation combined with filtering"""
        # Create sample documents
        docs = []
        for i in range(20):
            doc = Mock()
            doc.id = f"doc_{i}"
            doc.score = 0.5 + (i * 0.02)
            doc.metadata = {
                "category": f"cat_{i % 4}",
                "score": 10 + i,
                "status": "active" if i % 2 == 0 else "inactive",
            }
            docs.append(doc)

        mock_vector_store.get_documents_by_metadata.return_value = docs

        # Test aggregation with filtering
        aggregator = QueryAggregator(mock_vector_store)
        result = await aggregator.group_by_metadata(
            "category", filters={"status": "active"}, aggregation=AggregationType.COUNT
        )

        assert isinstance(result, dict)
        assert len(result) <= 4  # Max 4 categories

    @pytest.mark.asyncio
    async def test_scoring_with_optimization(self, mock_vector_store):
        """Test scoring combined with optimization"""
        # Create sample documents
        docs = []
        for i in range(10):
            doc = Mock()
            doc.id = f"doc_{i}"
            doc.score = 0.5 + (i * 0.05)
            doc.content = f"Content {i}" * 50
            doc.metadata = {
                "view_count": 100 + i * 10,
                "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
            }
            docs.append(doc)

        # Test optimization
        optimizer = QueryOptimizer(mock_vector_store)
        optimization_result = await optimizer.optimize_query("test query")

        # Test scoring
        scorer = CustomScorer(mock_vector_store)
        scored_docs = await scorer.hybrid_scoring(docs)

        assert isinstance(optimization_result, OptimizationResult)
        assert isinstance(scored_docs, list)
        assert len(scored_docs) == len(docs)

    @pytest.mark.asyncio
    async def test_complete_query_pipeline(self, mock_vector_store):
        """Test complete query pipeline"""
        # Create comprehensive sample documents
        docs = []
        for i in range(15):
            doc = Mock()
            doc.id = f"doc_{i}"
            doc.score = 0.3 + (i * 0.04)
            doc.content = f"Document content {i}" * 30
            doc.metadata = {
                "category": f"cat_{i % 3}",
                "score": 5 + i,
                "view_count": 50 + i * 5,
                "like_count": 5 + i,
                "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
                "location": {"lat": 35.0 + i * 0.01, "lon": 51.0 + i * 0.01},
            }
            docs.append(doc)

        mock_vector_store.get_documents_by_metadata.return_value = docs
        mock_vector_store.get_all_documents.return_value = docs

        # Initialize all components
        aggregator = QueryAggregator(mock_vector_store)
        filter_system = AdvancedFilter(mock_vector_store)
        scorer = CustomScorer(mock_vector_store)
        optimizer = QueryOptimizer(mock_vector_store)

        # Test complete pipeline
        query = "test query for pipeline"

        # 1. Optimize query
        optimization_result = await optimizer.optimize_query(query)

        # 2. Apply filters
        filtered_ids = await filter_system.range_filter("score", 10, 20)

        # 3. Score documents
        scored_docs = await scorer.weighted_scoring(
            docs,
            {
                "semantic_similarity": 0.6,
                "content_length": 0.2,
                "metadata_quality": 0.1,
                "recency": 0.1,
            },
        )

        # 4. Aggregate results
        aggregation_result = await aggregator.group_by_metadata(
            "category", aggregation=AggregationType.COUNT
        )

        # Verify all components worked
        assert isinstance(optimization_result, OptimizationResult)
        assert isinstance(filtered_ids, list)
        assert isinstance(scored_docs, list)
        assert isinstance(aggregation_result, dict)

        # Verify data consistency
        assert len(scored_docs) == len(docs)
        assert all(0 <= doc.final_score <= 1 for doc in scored_docs)
