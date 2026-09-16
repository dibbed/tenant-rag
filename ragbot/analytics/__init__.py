"""
تحلیل رفتار کاربران و آمار استفاده
"""

from .analytics_dashboard import AnalyticsDashboard
from .satisfaction_tracker import SatisfactionFeedback, SatisfactionTracker
from .usage_patterns import UsagePatternsAnalyzer
from .user_behavior import UserBehaviorAnalyzer, UserProfile, UserSession
from .ml_insights import (
    MLInsightsEngine,
    QueryPatternAnalysis,
    Topic,
    ContentSuggestion,
    EmbeddingOptimization,
    BehaviorPrediction,
    AnomalyReport,
)
from .predictive import (
    PredictiveAnalyzer,
    LoadPrediction,
    StoragePrediction,
    Anomaly,
    Recommendation,
    SystemMetrics,
)

__all__ = [
    # Core analytics
    "UserBehaviorAnalyzer",
    "UserSession",
    "UserProfile",
    "UsagePatternsAnalyzer",
    "SatisfactionTracker",
    "SatisfactionFeedback",
    "AnalyticsDashboard",
    # ML Insights
    "MLInsightsEngine",
    "QueryPatternAnalysis",
    "Topic",
    "ContentSuggestion",
    "EmbeddingOptimization",
    "BehaviorPrediction",
    "AnomalyReport",
    # Predictive Analytics
    "PredictiveAnalyzer",
    "LoadPrediction",
    "StoragePrediction",
    "Anomaly",
    "Recommendation",
    "SystemMetrics",
]
