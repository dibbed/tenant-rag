"""
Advanced Query Features Example

This example demonstrates the usage of advanced query features including:
- Complex aggregation operations
- Advanced filtering systems
- Custom scoring algorithms
- Query optimization
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock

from ragbot.rag.query import (
    QueryAggregator,
    AggregationType,
    AdvancedFilter,
    FilterOperator,
    FilterCondition,
    CustomScorer,
    QueryOptimizer,
)


async def main():
    """Main example function"""
    print("🚀 Advanced Query Features Example")
    print("=" * 50)

    # Create mock vector store
    mock_store = Mock()

    # Create sample documents
    sample_docs = []
    for i in range(20):
        doc = Mock()
        doc.id = f"doc_{i}"
        doc.score = 0.3 + (i * 0.03)
        doc.content = f"Document content {i}" * 50
        doc.metadata = {
            "category": f"cat_{i % 4}",
            "score": 10 + i,
            "view_count": 100 + i * 10,
            "like_count": 5 + i,
            "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
            "location": {"lat": 35.0 + i * 0.01, "lon": 51.0 + i * 0.01},
            "tags": [f"tag_{i}", f"category_{i % 3}"],
        }
        sample_docs.append(doc)

    # Mock async methods
    async def mock_get_documents_by_metadata(filters=None):
        return sample_docs

    async def mock_get_all_documents():
        return sample_docs

    mock_store.get_documents_by_metadata = mock_get_documents_by_metadata
    mock_store.get_all_documents = mock_get_all_documents

    print(f"📄 Created {len(sample_docs)} sample documents")

    # 1. Query Aggregation Example
    print("\n📊 1. Query Aggregation Example")
    print("-" * 30)

    aggregator = QueryAggregator(mock_store)

    # Group by category with count
    category_counts = await aggregator.group_by_metadata(
        "category", aggregation=AggregationType.COUNT
    )
    print(f"Category counts: {category_counts}")

    # Statistical summary
    score_summary = await aggregator.statistical_summary("score")
    print(f"Score summary: {score_summary}")

    # Percentile analysis
    percentiles = await aggregator.percentile_analysis("score", [25, 50, 75, 90])
    print(f"Score percentiles: {percentiles}")

    # 2. Advanced Filtering Example
    print("\n🔍 2. Advanced Filtering Example")
    print("-" * 30)

    filter_system = AdvancedFilter(mock_store)

    # Range filter
    range_results = await filter_system.range_filter("score", 15, 25)
    print(f"Documents with score 15-25: {len(range_results)}")

    # Regex filter
    regex_results = await filter_system.regex_filter("category", r"cat_[0-2]")
    print(f"Documents matching regex: {len(regex_results)}")

    # Composite filter
    conditions = [
        FilterCondition("score", FilterOperator.GT, 15),
        FilterCondition("category", FilterOperator.EQ, "cat_0"),
    ]
    composite_results = await filter_system.composite_filter(conditions, logic="AND")
    print(f"Composite filter results: {len(composite_results)}")

    # Geographic filter
    geo_results = await filter_system.geo_filter(35.0, 51.0, 0.5)
    print(f"Documents within 0.5km: {len(geo_results)}")

    # 3. Custom Scoring Example
    print("\n⭐ 3. Custom Scoring Example")
    print("-" * 30)

    scorer = CustomScorer(mock_store)

    # Weighted scoring
    weights = {
        "semantic_similarity": 0.5,
        "content_length": 0.2,
        "metadata_quality": 0.2,
        "recency": 0.1,
    }
    weighted_results = await scorer.weighted_scoring(sample_docs[:5], weights)
    print(f"Weighted scoring results: {len(weighted_results)}")
    print(
        f"Top scored document: {weighted_results[0].document_id} (score: {weighted_results[0].final_score:.3f})"
    )

    # Time decay scoring
    time_decay_results = await scorer.time_decay_scoring(
        sample_docs[:5], decay_factor=0.1
    )
    print(f"Time decay scoring results: {len(time_decay_results)}")

    # Popularity scoring
    popularity_results = await scorer.popularity_scoring(sample_docs[:5])
    print(f"Popularity scoring results: {len(popularity_results)}")

    # Hybrid scoring
    hybrid_results = await scorer.hybrid_scoring(sample_docs[:5])
    print(f"Hybrid scoring results: {len(hybrid_results)}")

    # 4. Query Optimization Example
    print("\n⚡ 4. Query Optimization Example")
    print("-" * 30)

    optimizer = QueryOptimizer(mock_store)

    # Simple query optimization
    simple_query = "test query"
    simple_result = await optimizer.optimize_query(simple_query)
    print(
        f"Simple query optimization: {simple_result.improvement_percentage:.1f}% improvement"
    )
    print(
        f"Applied optimizations: {[opt.value for opt in simple_result.optimized_plan.optimization_applied]}"
    )

    # Complex query optimization
    complex_query = (
        "very long query with many words that should trigger optimization strategies"
    )
    complex_filters = {
        "category": "test",
        "score": {"$gte": 10, "$lte": 100},
        "tags": ["tag1", "tag2", "tag3"],
    }
    complex_result = await optimizer.optimize_query(complex_query, complex_filters)
    print(
        f"Complex query optimization: {complex_result.improvement_percentage:.1f}% improvement"
    )
    print(
        f"Applied optimizations: {[opt.value for opt in complex_result.optimized_plan.optimization_applied]}"
    )

    # 5. Integration Example
    print("\n🔄 5. Integration Example")
    print("-" * 30)

    # Complete pipeline: Optimize -> Filter -> Score -> Aggregate
    query = "integration test query"

    # Step 1: Optimize query
    optimization_result = await optimizer.optimize_query(query)
    print(
        f"Step 1 - Query optimized: {optimization_result.improvement_percentage:.1f}% improvement"
    )

    # Step 2: Apply filters
    filtered_ids = await filter_system.range_filter("score", 12, 20)
    print(f"Step 2 - Filtered documents: {len(filtered_ids)}")

    # Step 3: Score documents
    scored_docs = await scorer.weighted_scoring(sample_docs, weights)
    print(f"Step 3 - Scored documents: {len(scored_docs)}")

    # Step 4: Aggregate results
    aggregation_result = await aggregator.group_by_metadata(
        "category", aggregation=AggregationType.COUNT
    )
    print(f"Step 4 - Aggregated by category: {aggregation_result}")

    print("\n✅ Advanced Query Features Example Completed Successfully!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
