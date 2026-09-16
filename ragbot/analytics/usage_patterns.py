"""
تحلیل الگوهای استفاده
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict

from loguru import logger


class UsagePatternsAnalyzer:
    """تحلیلگر الگوهای استفاده"""

    def __init__(self):
        """Initialize usage patterns analyzer"""
        self.hourly_usage = defaultdict(int)
        self.daily_usage = defaultdict(int)
        self.query_types = Counter()
        self.document_types = Counter()
        self.session_lengths = []
        self.user_activity = defaultdict(list)

    async def record_activity(
        self, user_id: str, activity_type: str, metadata: Dict[str, Any] = None
    ):
        """ثبت فعالیت کاربر"""
        try:
            current_time = datetime.now()

            # ثبت در آمار ساعتی
            hour_key = current_time.hour
            self.hourly_usage[hour_key] += 1

            # ثبت در آمار روزانه
            day_key = current_time.strftime("%Y-%m-%d")
            self.daily_usage[day_key] += 1

            # ثبت نوع فعالیت
            self.query_types[activity_type] += 1

            # ثبت فعالیت کاربر
            self.user_activity[user_id].append(
                {
                    "type": activity_type,
                    "timestamp": current_time,
                    "metadata": metadata or {},
                }
            )

            logger.debug(f"Recorded activity {activity_type} for user {user_id}")
        except Exception as e:
            logger.error(f"Error recording activity: {e}")

    async def record_session_length(self, duration: float):
        """ثبت مدت جلسه"""
        try:
            self.session_lengths.append(duration)

            # محدود کردن تاریخچه
            if len(self.session_lengths) > 1000:
                self.session_lengths = self.session_lengths[-500:]
        except Exception as e:
            logger.error(f"Error recording session length: {e}")

    async def record_document_type(self, doc_type: str):
        """ثبت نوع سند"""
        try:
            self.document_types[doc_type] += 1
        except Exception as e:
            logger.error(f"Error recording document type: {e}")

    async def analyze_usage_patterns(
        self, user_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """تحلیل الگوهای استفاده"""
        try:
            patterns = {
                "peak_hours": await self._find_peak_hours(),
                "usage_distribution": await self._analyze_usage_distribution(),
                "query_patterns": await self._analyze_query_patterns(),
                "document_preferences": await self._analyze_document_preferences(),
                "session_characteristics": await self._analyze_session_characteristics(),
                "user_engagement": await self._analyze_user_engagement(),
            }

            return patterns
        except Exception as e:
            logger.error(f"Error analyzing usage patterns: {e}")
            return {"error": str(e)}

    async def _find_peak_hours(self) -> Dict[str, Any]:
        """یافتن ساعات پیک استفاده"""
        try:
            if not self.hourly_usage:
                return {"no_data": True}

            # یافتن ساعات پیک
            peak_hours = sorted(
                self.hourly_usage.items(), key=lambda x: x[1], reverse=True
            )[:3]

            return {
                "peak_hours": [hour for hour, count in peak_hours],
                "usage_by_hour": dict(self.hourly_usage),
                "most_active_hour": peak_hours[0][0] if peak_hours else None,
                "total_hourly_usage": sum(self.hourly_usage.values()),
            }
        except Exception as e:
            logger.error(f"Error finding peak hours: {e}")
            return {"error": str(e)}

    async def _analyze_usage_distribution(self) -> Dict[str, Any]:
        """تحلیل توزیع استفاده"""
        try:
            total_usage = sum(self.daily_usage.values())

            if total_usage == 0:
                return {"no_data": True}

            # محاسبه میانگین روزانه
            avg_daily = total_usage / len(self.daily_usage) if self.daily_usage else 0

            # یافتن روزهای پیک
            peak_days = sorted(
                self.daily_usage.items(), key=lambda x: x[1], reverse=True
            )[:3]

            # محاسبه واریانس
            variance = (
                sum((count - avg_daily) ** 2 for count in self.daily_usage.values())
                / len(self.daily_usage)
                if self.daily_usage
                else 0
            )

            return {
                "total_usage": total_usage,
                "average_daily": round(avg_daily, 2),
                "peak_days": [day for day, count in peak_days],
                "usage_by_day": dict(self.daily_usage),
                "usage_variance": round(variance, 2),
                "consistency_score": round(
                    1 - (variance / avg_daily) if avg_daily > 0 else 0, 2
                ),
            }
        except Exception as e:
            logger.error(f"Error analyzing usage distribution: {e}")
            return {"error": str(e)}

    async def _analyze_query_patterns(self) -> Dict[str, Any]:
        """تحلیل الگوهای پرسش"""
        try:
            if not self.query_types:
                return {"no_data": True}

            total_queries = sum(self.query_types.values())

            return {
                "total_queries": total_queries,
                "query_types": dict(self.query_types.most_common()),
                "most_common_query_type": self.query_types.most_common(1)[0][0]
                if self.query_types
                else None,
                "query_diversity": len(self.query_types),
                "query_distribution": {
                    query_type: round(count / total_queries * 100, 2)
                    for query_type, count in self.query_types.items()
                },
            }
        except Exception as e:
            logger.error(f"Error analyzing query patterns: {e}")
            return {"error": str(e)}

    async def _analyze_document_preferences(self) -> Dict[str, Any]:
        """تحلیل ترجیحات اسناد"""
        try:
            if not self.document_types:
                return {"no_data": True}

            total_documents = sum(self.document_types.values())

            return {
                "total_documents": total_documents,
                "document_types": dict(self.document_types.most_common()),
                "most_common_document_type": self.document_types.most_common(1)[0][0]
                if self.document_types
                else None,
                "document_diversity": len(self.document_types),
                "document_distribution": {
                    doc_type: round(count / total_documents * 100, 2)
                    for doc_type, count in self.document_types.items()
                },
            }
        except Exception as e:
            logger.error(f"Error analyzing document preferences: {e}")
            return {"error": str(e)}

    async def _analyze_session_characteristics(self) -> Dict[str, Any]:
        """تحلیل ویژگی‌های جلسه"""
        try:
            if not self.session_lengths:
                return {"no_data": True}

            avg_length = sum(self.session_lengths) / len(self.session_lengths)
            sorted_lengths = sorted(self.session_lengths)

            # محاسبه میانه
            n = len(sorted_lengths)
            median = (
                sorted_lengths[n // 2]
                if n % 2 == 1
                else (sorted_lengths[n // 2 - 1] + sorted_lengths[n // 2]) / 2
            )

            # محاسبه انحراف معیار
            variance = sum((x - avg_length) ** 2 for x in self.session_lengths) / len(
                self.session_lengths
            )
            std_dev = variance**0.5

            return {
                "total_sessions": len(self.session_lengths),
                "average_length": round(avg_length, 2),
                "median_length": round(median, 2),
                "shortest_session": min(self.session_lengths),
                "longest_session": max(self.session_lengths),
                "standard_deviation": round(std_dev, 2),
                "session_length_distribution": await self._get_session_distribution(),
            }
        except Exception as e:
            logger.error(f"Error analyzing session characteristics: {e}")
            return {"error": str(e)}

    async def _get_session_distribution(self) -> Dict[str, int]:
        """توزیع مدت جلسات"""
        try:
            distribution = {
                "short": 0,  # کمتر از 5 دقیقه
                "medium": 0,  # 5-30 دقیقه
                "long": 0,  # بیشتر از 30 دقیقه
            }

            for length in self.session_lengths:
                if length < 300:  # 5 minutes
                    distribution["short"] += 1
                elif length < 1800:  # 30 minutes
                    distribution["medium"] += 1
                else:
                    distribution["long"] += 1

            return distribution
        except Exception as e:
            logger.error(f"Error getting session distribution: {e}")
            return {}

    async def _analyze_user_engagement(self) -> Dict[str, Any]:
        """تحلیل درگیری کاربران"""
        try:
            if not self.user_activity:
                return {"no_data": True}

            # تحلیل فعالیت کاربران
            user_stats = {}
            for user_id, activities in self.user_activity.items():
                if not activities:
                    continue

                # محاسبه آمار کاربر
                total_activities = len(activities)
                unique_days = len(
                    set(activity["timestamp"].date() for activity in activities)
                )
                avg_activities_per_day = (
                    total_activities / unique_days if unique_days > 0 else 0
                )

                user_stats[user_id] = {
                    "total_activities": total_activities,
                    "active_days": unique_days,
                    "avg_activities_per_day": round(avg_activities_per_day, 2),
                    "last_activity": max(
                        activity["timestamp"] for activity in activities
                    ),
                }

            # طبقه‌بندی کاربران بر اساس درگیری
            engagement_levels = {
                "high": 0,  # بیش از 10 فعالیت در روز
                "medium": 0,  # 3-10 فعالیت در روز
                "low": 0,  # کمتر از 3 فعالیت در روز
            }

            for user_id, stats in user_stats.items():
                avg_daily = stats["avg_activities_per_day"]
                if avg_daily > 10:
                    engagement_levels["high"] += 1
                elif avg_daily >= 3:
                    engagement_levels["medium"] += 1
                else:
                    engagement_levels["low"] += 1

            return {
                "total_active_users": len(user_stats),
                "engagement_levels": engagement_levels,
                "average_activities_per_user": round(
                    sum(stats["total_activities"] for stats in user_stats.values())
                    / len(user_stats)
                    if user_stats
                    else 0,
                    2,
                ),
                "most_active_users": sorted(
                    user_stats.items(),
                    key=lambda x: x[1]["total_activities"],
                    reverse=True,
                )[:5],
            }
        except Exception as e:
            logger.error(f"Error analyzing user engagement: {e}")
            return {"error": str(e)}

    async def get_trend_analysis(self, days: int = 7) -> Dict[str, Any]:
        """تحلیل روند استفاده"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # فیلتر کردن داده‌های اخیر
            recent_daily_usage = {
                day: count
                for day, count in self.daily_usage.items()
                if datetime.strptime(day, "%Y-%m-%d") >= cutoff_date
            }

            if not recent_daily_usage:
                return {"no_data": True}

            # محاسبه روند
            days_list = sorted(recent_daily_usage.keys())
            usage_values = [recent_daily_usage[day] for day in days_list]

            # محاسبه شیب خط روند (ساده)
            if len(usage_values) >= 2:
                trend_slope = (usage_values[-1] - usage_values[0]) / len(usage_values)
                trend_direction = (
                    "increasing"
                    if trend_slope > 0
                    else "decreasing"
                    if trend_slope < 0
                    else "stable"
                )
            else:
                trend_slope = 0
                trend_direction = "stable"

            return {
                "period_days": days,
                "trend_direction": trend_direction,
                "trend_slope": round(trend_slope, 2),
                "average_usage": round(sum(usage_values) / len(usage_values), 2),
                "usage_values": usage_values,
                "days": days_list,
            }
        except Exception as e:
            logger.error(f"Error getting trend analysis: {e}")
            return {"error": str(e)}

    async def get_usage_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه استفاده"""
        try:
            return {
                "total_activities": sum(self.hourly_usage.values()),
                "unique_users": len(self.user_activity),
                "total_sessions": len(self.session_lengths),
                "document_types_count": len(self.document_types),
                "query_types_count": len(self.query_types),
                "data_collection_period": {
                    "start": min(self.daily_usage.keys()) if self.daily_usage else None,
                    "end": max(self.daily_usage.keys()) if self.daily_usage else None,
                },
            }
        except Exception as e:
            logger.error(f"Error getting usage summary: {e}")
            return {"error": str(e)}
