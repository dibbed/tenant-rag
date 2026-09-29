"""
تحلیل رفتار کاربران و آمار استفاده
"""

from .analytics_dashboard import AnalyticsDashboard
from .ml_insights import (
    AnomalyReport,
    BehaviorPrediction,
    ContentSuggestion,
    EmbeddingOptimization,
    MLInsightsEngine,
    QueryPatternAnalysis,
    Topic,
)
from .predictive import (
    Anomaly,
    LoadPrediction,
    PredictiveAnalyzer,
    Recommendation,
    StoragePrediction,
    SystemMetrics,
)
from .satisfaction_tracker import SatisfactionFeedback, SatisfactionTracker
from .usage_patterns import UsagePatternsAnalyzer
from .user_behavior import UserBehaviorAnalyzer, UserProfile, UserSession

__all__ = [
    "AnalyticsDashboard",
    "Anomaly",
    "AnomalyReport",
    "BehaviorPrediction",
    "ContentSuggestion",
    "EmbeddingOptimization",
    "LoadPrediction",
    # ML Insights
    "MLInsightsEngine",
    # Predictive Analytics
    "PredictiveAnalyzer",
    "QueryPatternAnalysis",
    "Recommendation",
    "SatisfactionFeedback",
    "SatisfactionTracker",
    "StoragePrediction",
    "SystemMetrics",
    "Topic",
    "UsagePatternsAnalyzer",
    # Core analytics
    "UserBehaviorAnalyzer",
    "UserProfile",
    "UserSession",
]
