"""
Advanced Query Features Module

This module provides advanced query capabilities including:
- Complex aggregation operations
- Advanced filtering systems
- Custom scoring algorithms
- Query optimization
"""

from .aggregation import (
    AggregationQuery,
    AggregationResult,
    AggregationType,
    QueryAggregator,
)
from .filters import (
    AdvancedFilter,
    CompositeFilter,
    FilterCondition,
    FilterOperator,
    GeoFilter,
)
from .optimizer import (
    OptimizationResult,
    OptimizationStrategy,
    QueryOptimizer,
    QueryPlan,
)
from .scoring import CustomScorer, ScoredDocument, ScoringStrategy

__all__ = [
    # Filtering
    "AdvancedFilter",
    "AggregationQuery",
    "AggregationResult",
    "AggregationType",
    "CompositeFilter",
    # Scoring
    "CustomScorer",
    "FilterCondition",
    "FilterOperator",
    "GeoFilter",
    "OptimizationResult",
    "OptimizationStrategy",
    # Aggregation
    "QueryAggregator",
    # Optimization
    "QueryOptimizer",
    "QueryPlan",
    "ScoredDocument",
    "ScoringStrategy",
]
