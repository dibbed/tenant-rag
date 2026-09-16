"""
داشبورد تحلیل کاربران
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from .satisfaction_tracker import SatisfactionTracker
from .usage_patterns import UsagePatternsAnalyzer
from .user_behavior import UserBehaviorAnalyzer
from .ml_insights import MLInsightsEngine
from .predictive import PredictiveAnalyzer


class AnalyticsDashboard:
    """داشبورد تحلیل کاربران"""

    def __init__(self, settings=None):
        """Initialize analytics dashboard"""
        self.settings = settings
        self.user_behavior = UserBehaviorAnalyzer()
        self.usage_patterns = UsagePatternsAnalyzer()
        self.satisfaction_tracker = SatisfactionTracker()

        # Initialize advanced analytics based on settings
        if self.settings and getattr(self.settings, "enable_ml_insights", True):
            self.ml_insights = MLInsightsEngine(self.user_behavior, self.usage_patterns)
        else:
            self.ml_insights = None

        if self.settings and getattr(
            self.settings, "enable_predictive_analytics", True
        ):
            self.predictive_analyzer = PredictiveAnalyzer(
                self.user_behavior, self.usage_patterns
            )
        else:
            self.predictive_analyzer = None

        self._initialized = False

    async def initialize(self):
        """Initialize analytics dashboard"""
        try:
            if not self._initialized:
                logger.info("Initializing analytics dashboard...")
                self._initialized = True
                logger.success("Analytics dashboard initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing analytics dashboard: {e}")
            raise

    async def track_user_action(
        self, user_id: str, action: str, metadata: Dict[str, Any] = None
    ):
        """ردیابی عمل کاربر در تمام سیستم‌ها"""
        try:
            # ردیابی در تحلیلگر رفتار
            await self.user_behavior.track_user_action(user_id, action, metadata)

            # ردیابی در تحلیلگر الگوهای استفاده
            await self.usage_patterns.record_activity(user_id, action, metadata)

            logger.debug(
                f"Tracked action {action} for user {user_id} across all analytics systems"
            )
        except Exception as e:
            logger.error(f"Error tracking user action: {e}")

    async def record_satisfaction_feedback(
        self,
        user_id: str,
        query: str,
        answer: str,
        rating: int,
        feedback_text: str = None,
    ):
        """ثبت بازخورد رضایت"""
        try:
            await self.satisfaction_tracker.record_feedback(
                user_id, query, answer, rating, feedback_text
            )

            # همچنین به عنوان عمل کاربر ثبت کن
            await self.track_user_action(
                user_id,
                "satisfaction",
                {"score": rating, "query": query, "feedback": feedback_text},
            )
        except Exception as e:
            logger.error(f"Error recording satisfaction feedback: {e}")

    async def record_session_length(self, duration: float):
        """ثبت مدت جلسه"""
        try:
            await self.usage_patterns.record_session_length(duration)
        except Exception as e:
            logger.error(f"Error recording session length: {e}")

    async def record_document_type(self, doc_type: str):
        """ثبت نوع سند"""
        try:
            await self.usage_patterns.record_document_type(doc_type)
        except Exception as e:
            logger.error(f"Error recording document type: {e}")

    async def get_comprehensive_dashboard(self) -> Dict[str, Any]:
        """دریافت داشبورد جامع"""
        try:
            dashboard_data = {
                "timestamp": datetime.now(),
                "user_behavior": await self._get_user_behavior_summary(),
                "usage_patterns": await self._get_usage_patterns_summary(),
                "satisfaction": await self._get_satisfaction_summary(),
                "overall_insights": await self._generate_overall_insights(),
            }

            return dashboard_data
        except Exception as e:
            logger.error(f"Error getting comprehensive dashboard: {e}")
            return {"error": str(e)}

    async def _get_user_behavior_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه رفتار کاربران"""
        try:
            all_users_summary = await self.user_behavior.get_all_users_summary()

            return {
                "total_users": all_users_summary.get("total_users", 0),
                "total_sessions": all_users_summary.get("total_sessions", 0),
                "total_queries": all_users_summary.get("total_queries", 0),
                "usage_patterns": all_users_summary.get("usage_patterns", {}),
                "average_queries_per_user": all_users_summary.get(
                    "average_queries_per_user", 0
                ),
            }
        except Exception as e:
            logger.error(f"Error getting user behavior summary: {e}")
            return {"error": str(e)}

    async def _get_usage_patterns_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه الگوهای استفاده"""
        try:
            patterns = await self.usage_patterns.analyze_usage_patterns()
            summary = await self.usage_patterns.get_usage_summary()

            return {
                "peak_hours": patterns.get("peak_hours", {}),
                "usage_distribution": patterns.get("usage_distribution", {}),
                "query_patterns": patterns.get("query_patterns", {}),
                "document_preferences": patterns.get("document_preferences", {}),
                "session_characteristics": patterns.get("session_characteristics", {}),
                "user_engagement": patterns.get("user_engagement", {}),
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"Error getting usage patterns summary: {e}")
            return {"error": str(e)}

    async def _get_satisfaction_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه رضایت"""
        try:
            metrics = await self.satisfaction_tracker.get_satisfaction_metrics()
            insights = await self.satisfaction_tracker.get_satisfaction_insights()
            summary = await self.satisfaction_tracker.get_satisfaction_summary()

            return {"metrics": metrics, "insights": insights, "summary": summary}
        except Exception as e:
            logger.error(f"Error getting satisfaction summary: {e}")
            return {"error": str(e)}

    async def _generate_overall_insights(self) -> Dict[str, Any]:
        """تولید بینش‌های کلی"""
        try:
            insights = {
                "system_health": await self._assess_system_health(),
                "key_metrics": await self._get_key_metrics(),
                "recommendations": await self._generate_recommendations(),
                "trends": await self._analyze_trends(),
            }

            return insights
        except Exception as e:
            logger.error(f"Error generating overall insights: {e}")
            return {"error": str(e)}

    async def _assess_system_health(self) -> Dict[str, Any]:
        """ارزیابی سلامت سیستم"""
        try:
            # دریافت آمار کلی
            user_summary = await self.user_behavior.get_all_users_summary()
            satisfaction_metrics = (
                await self.satisfaction_tracker.get_satisfaction_metrics()
            )
            usage_summary = await self.usage_patterns.get_usage_summary()

            # محاسبه امتیاز سلامت
            health_score = 0
            health_factors = []

            # عامل کاربران فعال
            total_users = user_summary.get("total_users", 0)
            if total_users > 0:
                health_score += 25
                health_factors.append(f"Active users: {total_users}")
            else:
                health_factors.append("No active users")

            # عامل رضایت
            overall_satisfaction = satisfaction_metrics.get("overall_satisfaction", 0)
            if overall_satisfaction >= 4.0:
                health_score += 30
                health_factors.append(f"High satisfaction: {overall_satisfaction}")
            elif overall_satisfaction >= 3.0:
                health_score += 20
                health_factors.append(f"Moderate satisfaction: {overall_satisfaction}")
            else:
                health_factors.append(f"Low satisfaction: {overall_satisfaction}")

            # عامل استفاده
            total_activities = usage_summary.get("total_activities", 0)
            if total_activities > 100:
                health_score += 25
                health_factors.append(f"High usage: {total_activities} activities")
            elif total_activities > 10:
                health_score += 15
                health_factors.append(f"Moderate usage: {total_activities} activities")
            else:
                health_factors.append(f"Low usage: {total_activities} activities")

            # عامل تنوع کاربران
            unique_users = usage_summary.get("unique_users", 0)
            if unique_users > 5:
                health_score += 20
                health_factors.append(f"Good user diversity: {unique_users} users")
            elif unique_users > 1:
                health_score += 10
                health_factors.append(f"Limited user diversity: {unique_users} users")
            else:
                health_factors.append(f"Single user: {unique_users} users")

            # تعیین وضعیت سلامت
            if health_score >= 80:
                health_status = "excellent"
            elif health_score >= 60:
                health_status = "good"
            elif health_score >= 40:
                health_status = "fair"
            else:
                health_status = "poor"

            return {
                "status": health_status,
                "score": health_score,
                "factors": health_factors,
                "description": f"System health is {health_status} with a score of {health_score}/100",
            }
        except Exception as e:
            logger.error(f"Error assessing system health: {e}")
            return {"error": str(e)}

    async def _get_key_metrics(self) -> Dict[str, Any]:
        """دریافت متریک‌های کلیدی"""
        try:
            user_summary = await self.user_behavior.get_all_users_summary()
            satisfaction_metrics = (
                await self.satisfaction_tracker.get_satisfaction_metrics()
            )
            usage_summary = await self.usage_patterns.get_usage_summary()

            return {
                "total_users": user_summary.get("total_users", 0),
                "total_queries": user_summary.get("total_queries", 0),
                "overall_satisfaction": satisfaction_metrics.get(
                    "overall_satisfaction", 0
                ),
                "total_activities": usage_summary.get("total_activities", 0),
                "total_sessions": usage_summary.get("total_sessions", 0),
                "unique_users": usage_summary.get("unique_users", 0),
            }
        except Exception as e:
            logger.error(f"Error getting key metrics: {e}")
            return {"error": str(e)}

    async def _generate_recommendations(self) -> List[str]:
        """تولید توصیه‌ها"""
        try:
            recommendations = []

            # دریافت آمار
            user_summary = await self.user_behavior.get_all_users_summary()
            satisfaction_metrics = (
                await self.satisfaction_tracker.get_satisfaction_metrics()
            )
            usage_summary = await self.usage_patterns.get_usage_summary()

            # توصیه بر اساس تعداد کاربران
            total_users = user_summary.get("total_users", 0)
            if total_users == 0:
                recommendations.append("Focus on user acquisition and engagement")
            elif total_users < 5:
                recommendations.append(
                    "Consider marketing strategies to attract more users"
                )

            # توصیه بر اساس رضایت
            overall_satisfaction = satisfaction_metrics.get("overall_satisfaction", 0)
            if overall_satisfaction < 3.0:
                recommendations.append("Improve response quality and accuracy")
                recommendations.append("Add more relevant documents to knowledge base")
            elif overall_satisfaction < 4.0:
                recommendations.append("Continue improving response relevance")

            # توصیه بر اساس استفاده
            total_activities = usage_summary.get("total_activities", 0)
            if total_activities < 50:
                recommendations.append(
                    "Encourage more frequent usage through notifications"
                )

            # توصیه بر اساس الگوهای استفاده
            usage_patterns = await self.usage_patterns.analyze_usage_patterns()
            peak_hours = usage_patterns.get("peak_hours", {})
            if peak_hours.get("most_active_hour") is not None:
                peak_hour = peak_hours["most_active_hour"]
                recommendations.append(
                    f"Optimize performance during peak hours (hour {peak_hour})"
                )

            return recommendations
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    async def _analyze_trends(self) -> Dict[str, Any]:
        """تحلیل روندها"""
        try:
            trends = {}

            # روند استفاده
            usage_trend = await self.usage_patterns.get_trend_analysis(days=7)
            trends["usage_trend"] = usage_trend

            # روند رضایت
            satisfaction_trend = (
                await self.satisfaction_tracker._calculate_satisfaction_trend()
            )
            trends["satisfaction_trend"] = satisfaction_trend

            return trends
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {"error": str(e)}

    async def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """دریافت تحلیل کاربر خاص"""
        try:
            user_insights = await self.user_behavior.get_user_insights(user_id)
            satisfaction_profile = (
                await self.satisfaction_tracker.get_user_satisfaction_profile(user_id)
            )

            return {
                "user_id": user_id,
                "behavior_insights": user_insights,
                "satisfaction_profile": satisfaction_profile,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {"error": str(e)}

    async def get_analytics_report(self, days: int = 30) -> Dict[str, Any]:
        """دریافت گزارش تحلیل"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            report = {
                "period": f"Last {days} days",
                "generated_at": datetime.now(),
                "summary": await self._get_key_metrics(),
                "user_behavior": await self._get_user_behavior_summary(),
                "usage_patterns": await self._get_usage_patterns_summary(),
                "satisfaction": await self._get_satisfaction_summary(),
                "health_assessment": await self._assess_system_health(),
                "recommendations": await self._generate_recommendations(),
                "trends": await self._analyze_trends(),
            }

            return report
        except Exception as e:
            logger.error(f"Error getting analytics report: {e}")
            return {"error": str(e)}

    async def export_analytics_data(self, format: str = "json") -> Dict[str, Any]:
        """صادرات داده‌های تحلیل"""
        try:
            if format.lower() == "json":
                return await self.get_comprehensive_dashboard()
            else:
                return {"error": f"Unsupported format: {format}"}
        except Exception as e:
            logger.error(f"Error exporting analytics data: {e}")
            return {"error": str(e)}

    async def shutdown(self):
        """خاموش کردن داشبورد"""
        try:
            logger.info("Shutting down analytics dashboard...")
            self._initialized = False
            logger.success("Analytics dashboard shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down analytics dashboard: {e}")

    async def get_ml_insights(self) -> Dict[str, Any]:
        """دریافت بینش‌های ML"""
        try:
            if not self.ml_insights:
                return {"error": "ML insights disabled in settings"}

            logger.info("Generating ML insights...")

            # تحلیل الگوهای پرسش
            query_patterns = await self.ml_insights.analyze_query_patterns()

            # شناسایی موضوعات محبوب
            popular_topics = await self.ml_insights.identify_popular_topics()

            # پیشنهادات بهبود محتوا
            content_suggestions = await self.ml_insights.suggest_content_improvements()

            # بهینه‌سازی embedding
            embedding_optimization = (
                await self.ml_insights.optimize_embedding_strategy()
            )

            insights = {
                "query_patterns": query_patterns,
                "popular_topics": popular_topics,
                "content_suggestions": content_suggestions,
                "embedding_optimization": embedding_optimization,
                "generated_at": datetime.now(),
            }

            logger.success("ML insights generated successfully")
            return insights

        except Exception as e:
            logger.error(f"Error generating ML insights: {e}")
            return {"error": str(e)}

    async def get_predictive_analytics(self) -> Dict[str, Any]:
        """دریافت تحلیل‌های پیش‌بینانه"""
        try:
            if not self.predictive_analyzer:
                return {"error": "Predictive analytics disabled in settings"}

            logger.info("Generating predictive analytics...")

            # پیش‌بینی بار سیستم
            load_prediction = await self.predictive_analyzer.predict_system_load()

            # پیش‌بینی نیازهای ذخیره‌سازی
            storage_prediction = await self.predictive_analyzer.predict_storage_needs()

            # تشخیص ناهنجاری‌ها
            # شبیه‌سازی متریک‌های سیستم
            from .predictive import SystemMetrics

            sample_metrics = [
                SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_usage=75.0,
                    memory_usage=80.0,
                    disk_usage=45.0,
                    query_count=150,
                    response_time=1.2,
                    error_rate=0.02,
                    active_users=25,
                )
            ]
            anomalies = await self.predictive_analyzer.detect_anomalies(sample_metrics)

            # توصیه‌های بهینه‌سازی
            recommendations = await self.predictive_analyzer.recommend_optimizations()

            analytics = {
                "load_prediction": load_prediction,
                "storage_prediction": storage_prediction,
                "anomalies": anomalies,
                "recommendations": recommendations,
                "generated_at": datetime.now(),
            }

            logger.success("Predictive analytics generated successfully")
            return analytics

        except Exception as e:
            logger.error(f"Error generating predictive analytics: {e}")
            return {"error": str(e)}

    async def get_advanced_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """دریافت تحلیل‌های پیشرفته کاربر"""
        try:
            logger.info(f"Generating advanced analytics for user {user_id}")

            # تحلیل الگوهای جستجو
            search_patterns = await self.user_behavior.analyze_search_patterns()

            # شناسایی بخش‌بندی کاربران (فقط اگر فعال باشد)
            user_segments = []
            if self.settings and getattr(
                self.settings, "enable_user_segmentation", True
            ):
                user_segments = await self.user_behavior.identify_user_segments()

            # پیش‌بینی ترک کاربران (فقط اگر فعال باشد)
            churn_prediction = {}
            if self.settings and getattr(
                self.settings, "enable_churn_prediction", True
            ):
                churn_prediction = await self.user_behavior.predict_user_churn()

            # توصیه‌های شخصی‌سازی (فقط اگر فعال باشد)
            personalization = {}
            if self.settings and getattr(self.settings, "enable_personalization", True):
                personalization = await self.user_behavior.recommend_personalization(
                    user_id
                )

            # پیش‌بینی رفتار کاربر (فقط اگر ML Insights فعال باشد)
            behavior_prediction = {}
            if self.ml_insights:
                behavior_prediction = await self.ml_insights.predict_user_behavior(
                    user_id
                )

            analytics = {
                "user_id": user_id,
                "search_patterns": search_patterns,
                "user_segments": user_segments,
                "churn_prediction": churn_prediction,
                "personalization": personalization,
                "behavior_prediction": behavior_prediction,
                "generated_at": datetime.now(),
            }

            logger.success(f"Advanced user analytics generated for user {user_id}")
            return analytics

        except Exception as e:
            logger.error(f"Error generating advanced user analytics: {e}")
            return {"error": str(e)}

    async def get_comprehensive_analytics_report(
        self, days: int = 30
    ) -> Dict[str, Any]:
        """دریافت گزارش جامع تحلیل"""
        try:
            logger.info("Generating comprehensive analytics report...")

            # گزارش پایه
            base_report = await self.get_analytics_report(days)

            # بینش‌های ML (فقط اگر فعال باشد)
            ml_insights = {}
            if self.ml_insights:
                ml_insights = await self.get_ml_insights()

            # تحلیل‌های پیش‌بینانه (فقط اگر فعال باشد)
            predictive_analytics = {}
            if self.predictive_analyzer:
                predictive_analytics = await self.get_predictive_analytics()

            # تحلیل‌های پیشرفته کاربران (فقط اگر فعال باشد)
            user_segments = []
            churn_prediction = {}
            if self.settings and getattr(
                self.settings, "enable_user_segmentation", True
            ):
                user_segments = await self.user_behavior.identify_user_segments()
            if self.settings and getattr(
                self.settings, "enable_churn_prediction", True
            ):
                churn_prediction = await self.user_behavior.predict_user_churn()

            comprehensive_report = {
                "report_type": "comprehensive",
                "period_days": days,
                "generated_at": datetime.now(),
                "base_analytics": base_report,
                "ml_insights": ml_insights,
                "predictive_analytics": predictive_analytics,
                "user_segments": user_segments,
                "churn_prediction": churn_prediction,
                "summary": {
                    "total_users": len(self.user_behavior.user_sessions),
                    "ml_insights_available": self.ml_insights is not None,
                    "predictive_analytics_available": self.predictive_analyzer
                    is not None,
                    "user_segments_count": len(user_segments),
                    "high_risk_users": churn_prediction.get("high_risk_users", 0),
                    "features_enabled": {
                        "ml_insights": self.ml_insights is not None,
                        "predictive_analytics": self.predictive_analyzer is not None,
                        "user_segmentation": self.settings
                        and getattr(self.settings, "enable_user_segmentation", True),
                        "churn_prediction": self.settings
                        and getattr(self.settings, "enable_churn_prediction", True),
                        "personalization": self.settings
                        and getattr(self.settings, "enable_personalization", True),
                        "anomaly_detection": self.settings
                        and getattr(self.settings, "enable_anomaly_detection", True),
                    },
                },
            }

            logger.success("Comprehensive analytics report generated successfully")
            return comprehensive_report

        except Exception as e:
            logger.error(f"Error generating comprehensive analytics report: {e}")
            return {"error": str(e)}


# Global dashboard instance
_dashboard: Optional[AnalyticsDashboard] = None


async def get_analytics_dashboard(settings=None) -> AnalyticsDashboard:
    """Get or create the global analytics dashboard instance"""
    global _dashboard

    if _dashboard is None:
        _dashboard = AnalyticsDashboard(settings)
        await _dashboard.initialize()

    return _dashboard


async def shutdown_analytics_dashboard():
    """Shutdown the global analytics dashboard"""
    global _dashboard

    if _dashboard is not None:
        await _dashboard.shutdown()
        _dashboard = None
