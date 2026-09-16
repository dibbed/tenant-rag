"""
ردیابی رضایت کاربران
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class SatisfactionFeedback:
    """بازخورد رضایت"""

    user_id: str
    query: str
    answer: str
    rating: int  # 1-5
    feedback_text: Optional[str]
    timestamp: datetime


class SatisfactionTracker:
    """ردیابی رضایت کاربران"""

    def __init__(self):
        """Initialize satisfaction tracker"""
        self.feedback_history = []
        self.user_satisfaction = defaultdict(list)
        self.query_satisfaction = defaultdict(list)
        self.rating_distribution = Counter()
        self.satisfaction_trends = []

    async def record_feedback(
        self,
        user_id: str,
        query: str,
        answer: str,
        rating: int,
        feedback_text: str = None,
    ):
        """ثبت بازخورد رضایت"""
        try:
            if not (1 <= rating <= 5):
                logger.warning(f"Invalid rating {rating} for user {user_id}")
                return

            feedback = SatisfactionFeedback(
                user_id=user_id,
                query=query,
                answer=answer,
                rating=rating,
                feedback_text=feedback_text,
                timestamp=datetime.now(),
            )

            self.feedback_history.append(feedback)
            self.user_satisfaction[user_id].append(rating)
            self.query_satisfaction[query].append(rating)
            self.rating_distribution[rating] += 1

            # محدود کردن تاریخچه
            if len(self.feedback_history) > 1000:
                self.feedback_history = self.feedback_history[-500:]

            logger.info(
                f"Recorded satisfaction feedback: {rating}/5 from user {user_id}"
            )
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")

    async def get_satisfaction_metrics(self) -> Dict[str, Any]:
        """دریافت متریک‌های رضایت"""
        try:
            if not self.feedback_history:
                return {"no_data": True}

            # محاسبه آمار کلی
            all_ratings = [f.rating for f in self.feedback_history]
            avg_satisfaction = sum(all_ratings) / len(all_ratings)

            # محاسبه میانه
            sorted_ratings = sorted(all_ratings)
            n = len(sorted_ratings)
            median = (
                sorted_ratings[n // 2]
                if n % 2 == 1
                else (sorted_ratings[n // 2 - 1] + sorted_ratings[n // 2]) / 2
            )

            # محاسبه انحراف معیار
            variance = sum(
                (rating - avg_satisfaction) ** 2 for rating in all_ratings
            ) / len(all_ratings)
            std_dev = variance**0.5

            # توزیع رتبه‌ها
            rating_distribution = Counter(all_ratings)

            # رضایت کاربران
            user_satisfaction = {}
            for user_id, ratings in self.user_satisfaction.items():
                if ratings:
                    user_satisfaction[user_id] = {
                        "average": round(sum(ratings) / len(ratings), 2),
                        "count": len(ratings),
                        "latest_rating": ratings[-1],
                        "rating_trend": await self._calculate_user_trend(ratings),
                    }

            return {
                "overall_satisfaction": round(avg_satisfaction, 2),
                "median_satisfaction": round(median, 2),
                "standard_deviation": round(std_dev, 2),
                "total_feedback": len(self.feedback_history),
                "rating_distribution": dict(rating_distribution),
                "user_satisfaction": user_satisfaction,
                "satisfaction_trend": await self._calculate_satisfaction_trend(),
                "satisfaction_levels": await self._categorize_satisfaction_levels(),
            }
        except Exception as e:
            logger.error(f"Error getting satisfaction metrics: {e}")
            return {"error": str(e)}

    async def _calculate_user_trend(self, ratings: List[int]) -> str:
        """محاسبه روند رضایت کاربر"""
        try:
            if len(ratings) < 3:
                return "insufficient_data"

            # مقایسه نیمه اول و دوم
            mid_point = len(ratings) // 2
            recent_avg = sum(ratings[mid_point:]) / len(ratings[mid_point:])
            older_avg = sum(ratings[:mid_point]) / len(ratings[:mid_point])

            if recent_avg > older_avg + 0.5:
                return "improving"
            elif recent_avg < older_avg - 0.5:
                return "declining"
            else:
                return "stable"
        except Exception as e:
            logger.error(f"Error calculating user trend: {e}")
            return "unknown"

    async def _calculate_satisfaction_trend(self) -> Dict[str, Any]:
        """محاسبه روند رضایت"""
        try:
            if len(self.feedback_history) < 10:
                return {"insufficient_data": True}

            # تقسیم به دو نیمه
            mid_point = len(self.feedback_history) // 2
            recent_feedback = self.feedback_history[mid_point:]
            older_feedback = self.feedback_history[:mid_point]

            recent_avg = sum(f.rating for f in recent_feedback) / len(recent_feedback)
            older_avg = sum(f.rating for f in older_feedback) / len(older_feedback)

            trend = (
                "improving"
                if recent_avg > older_avg
                else "declining"
                if recent_avg < older_avg
                else "stable"
            )

            return {
                "trend": trend,
                "recent_average": round(recent_avg, 2),
                "older_average": round(older_avg, 2),
                "change": round(recent_avg - older_avg, 2),
                "change_percentage": round(
                    ((recent_avg - older_avg) / older_avg * 100)
                    if older_avg > 0
                    else 0,
                    2,
                ),
            }
        except Exception as e:
            logger.error(f"Error calculating satisfaction trend: {e}")
            return {"error": str(e)}

    async def _categorize_satisfaction_levels(self) -> Dict[str, Any]:
        """طبقه‌بندی سطوح رضایت"""
        try:
            if not self.feedback_history:
                return {"no_data": True}

            # طبقه‌بندی بر اساس امتیاز
            levels = {
                "very_satisfied": 0,  # 5
                "satisfied": 0,  # 4
                "neutral": 0,  # 3
                "dissatisfied": 0,  # 2
                "very_dissatisfied": 0,  # 1
            }

            for feedback in self.feedback_history:
                if feedback.rating == 5:
                    levels["very_satisfied"] += 1
                elif feedback.rating == 4:
                    levels["satisfied"] += 1
                elif feedback.rating == 3:
                    levels["neutral"] += 1
                elif feedback.rating == 2:
                    levels["dissatisfied"] += 1
                else:
                    levels["very_dissatisfied"] += 1

            total = sum(levels.values())
            percentages = {
                level: round(count / total * 100, 2) for level, count in levels.items()
            }

            return {
                "counts": levels,
                "percentages": percentages,
                "satisfaction_score": round(
                    (
                        levels["very_satisfied"] * 5
                        + levels["satisfied"] * 4
                        + levels["neutral"] * 3
                        + levels["dissatisfied"] * 2
                        + levels["very_dissatisfied"] * 1
                    )
                    / total,
                    2,
                )
                if total > 0
                else 0,
            }
        except Exception as e:
            logger.error(f"Error categorizing satisfaction levels: {e}")
            return {"error": str(e)}

    async def get_user_satisfaction_profile(self, user_id: str) -> Dict[str, Any]:
        """دریافت پروفایل رضایت کاربر"""
        try:
            user_ratings = self.user_satisfaction.get(user_id, [])

            if not user_ratings:
                return {"no_data": True}

            avg_rating = sum(user_ratings) / len(user_ratings)

            # تحلیل روند
            trend = await self._calculate_user_trend(user_ratings)

            # تحلیل کیفی
            positive_ratings = sum(1 for rating in user_ratings if rating >= 4)
            negative_ratings = sum(1 for rating in user_ratings if rating <= 2)

            satisfaction_ratio = (
                positive_ratings / len(user_ratings) if user_ratings else 0
            )

            return {
                "user_id": user_id,
                "total_feedback": len(user_ratings),
                "average_rating": round(avg_rating, 2),
                "trend": trend,
                "satisfaction_ratio": round(satisfaction_ratio, 2),
                "positive_ratings": positive_ratings,
                "negative_ratings": negative_ratings,
                "rating_history": user_ratings,
                "satisfaction_category": await self._get_satisfaction_category(
                    avg_rating
                ),
            }
        except Exception as e:
            logger.error(f"Error getting user satisfaction profile: {e}")
            return {"error": str(e)}

    async def _get_satisfaction_category(self, avg_rating: float) -> str:
        """تعیین دسته‌بندی رضایت"""
        if avg_rating >= 4.5:
            return "very_satisfied"
        elif avg_rating >= 3.5:
            return "satisfied"
        elif avg_rating >= 2.5:
            return "neutral"
        elif avg_rating >= 1.5:
            return "dissatisfied"
        else:
            return "very_dissatisfied"

    async def get_query_satisfaction_analysis(self) -> Dict[str, Any]:
        """تحلیل رضایت بر اساس پرسش‌ها"""
        try:
            if not self.query_satisfaction:
                return {"no_data": True}

            query_analysis = {}
            for query, ratings in self.query_satisfaction.items():
                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    query_analysis[query] = {
                        "average_rating": round(avg_rating, 2),
                        "feedback_count": len(ratings),
                        "satisfaction_category": await self._get_satisfaction_category(
                            avg_rating
                        ),
                    }

            # مرتب‌سازی بر اساس رضایت
            sorted_queries = sorted(
                query_analysis.items(),
                key=lambda x: x[1]["average_rating"],
                reverse=True,
            )

            return {
                "query_analysis": dict(query_analysis),
                "best_rated_queries": sorted_queries[:5],
                "worst_rated_queries": sorted_queries[-5:],
                "total_unique_queries": len(query_analysis),
            }
        except Exception as e:
            logger.error(f"Error getting query satisfaction analysis: {e}")
            return {"error": str(e)}

    async def get_satisfaction_insights(self) -> Dict[str, Any]:
        """دریافت بینش‌های رضایت"""
        try:
            metrics = await self.get_satisfaction_metrics()

            if "error" in metrics or "no_data" in metrics:
                return metrics

            insights = {
                "overall_health": await self._assess_overall_health(metrics),
                "improvement_areas": await self._identify_improvement_areas(),
                "success_factors": await self._identify_success_factors(),
                "recommendations": await self._generate_satisfaction_recommendations(
                    metrics
                ),
            }

            return insights
        except Exception as e:
            logger.error(f"Error getting satisfaction insights: {e}")
            return {"error": str(e)}

    async def _assess_overall_health(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """ارزیابی سلامت کلی رضایت"""
        try:
            overall_satisfaction = metrics.get("overall_satisfaction", 0)

            if overall_satisfaction >= 4.0:
                health_status = "excellent"
            elif overall_satisfaction >= 3.5:
                health_status = "good"
            elif overall_satisfaction >= 3.0:
                health_status = "fair"
            else:
                health_status = "poor"

            return {
                "status": health_status,
                "score": overall_satisfaction,
                "description": f"Overall satisfaction is {health_status} with a score of {overall_satisfaction}",
            }
        except Exception as e:
            logger.error(f"Error assessing overall health: {e}")
            return {"error": str(e)}

    async def _identify_improvement_areas(self) -> List[str]:
        """شناسایی زمینه‌های بهبود"""
        try:
            areas = []

            # تحلیل پرسش‌های با رضایت پایین
            query_analysis = await self.get_query_satisfaction_analysis()
            if "worst_rated_queries" in query_analysis:
                worst_queries = query_analysis["worst_rated_queries"]
                if worst_queries:
                    areas.append(
                        f"Improve responses to queries like: {worst_queries[0][0][:50]}..."
                    )

            # تحلیل روند
            trend = await self._calculate_satisfaction_trend()
            if trend.get("trend") == "declining":
                areas.append("Address declining satisfaction trend")

            return areas
        except Exception as e:
            logger.error(f"Error identifying improvement areas: {e}")
            return []

    async def _identify_success_factors(self) -> List[str]:
        """شناسایی عوامل موفقیت"""
        try:
            factors = []

            # تحلیل پرسش‌های با رضایت بالا
            query_analysis = await self.get_query_satisfaction_analysis()
            if "best_rated_queries" in query_analysis:
                best_queries = query_analysis["best_rated_queries"]
                if best_queries:
                    factors.append(
                        f"Maintain quality for queries like: {best_queries[0][0][:50]}..."
                    )

            return factors
        except Exception as e:
            logger.error(f"Error identifying success factors: {e}")
            return []

    async def _generate_satisfaction_recommendations(
        self, metrics: Dict[str, Any]
    ) -> List[str]:
        """تولید توصیه‌های رضایت"""
        try:
            recommendations = []

            overall_satisfaction = metrics.get("overall_satisfaction", 0)

            if overall_satisfaction < 3.0:
                recommendations.append(
                    "Focus on improving response quality and accuracy"
                )
                recommendations.append(
                    "Consider adding more relevant documents to the knowledge base"
                )
            elif overall_satisfaction < 4.0:
                recommendations.append("Continue improving response relevance")
                recommendations.append("Monitor user feedback more closely")
            else:
                recommendations.append("Maintain current quality standards")
                recommendations.append(
                    "Consider expanding features based on positive feedback"
                )

            return recommendations
        except Exception as e:
            logger.error(f"Error generating satisfaction recommendations: {e}")
            return []

    async def get_satisfaction_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه رضایت"""
        try:
            return {
                "total_feedback": len(self.feedback_history),
                "unique_users": len(self.user_satisfaction),
                "unique_queries": len(self.query_satisfaction),
                "data_collection_period": {
                    "start": min(f.timestamp for f in self.feedback_history)
                    if self.feedback_history
                    else None,
                    "end": max(f.timestamp for f in self.feedback_history)
                    if self.feedback_history
                    else None,
                },
                "recent_feedback_count": len(
                    [
                        f
                        for f in self.feedback_history
                        if f.timestamp > datetime.now() - timedelta(days=7)
                    ]
                ),
            }
        except Exception as e:
            logger.error(f"Error getting satisfaction summary: {e}")
            return {"error": str(e)}
