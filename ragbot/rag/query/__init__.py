"""
Advanced Query Features Module

This module provides advanced query capabilities including:
- Complex aggregation operations
- Advanced filtering systems
- Custom scoring algorithms
- Query optimization
"""

from .aggregation import (
    QueryAggregator,
    AggregationType,
    AggregationQuery,
    AggregationResult,
)

from .filters import (
    AdvancedFilter,
    FilterOperator,
    FilterCondition,
    CompositeFilter,
    GeoFilter,
)

from .scoring import CustomScorer, ScoringStrategy, ScoredDocument

from .optimizer import (
    QueryOptimizer,
    OptimizationStrategy,
    QueryPlan,
    OptimizationResult,
)

__all__ = [
    # Aggregation
    "QueryAggregator",
    "AggregationType",
    "AggregationQuery",
    "AggregationResult",
    # Filtering
    "AdvancedFilter",
    "FilterOperator",
    "FilterCondition",
    "CompositeFilter",
    "GeoFilter",
    # Scoring
    "CustomScorer",
    "ScoringStrategy",
    "ScoredDocument",
    # Optimization
    "QueryOptimizer",
    "OptimizationStrategy",
    "QueryPlan",
    "OptimizationResult",
]
