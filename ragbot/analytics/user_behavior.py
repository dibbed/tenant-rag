"""
تحلیل رفتار کاربران
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class UserSession:
    """جلسه کاربر"""

    user_id: str
    start_time: datetime
    end_time: Optional[datetime]
    queries: List[str]
    documents_added: List[str]
    satisfaction_score: float


@dataclass
class UserProfile:
    """پروفایل کاربر"""

    user_id: str
    total_sessions: int
    total_queries: int
    favorite_topics: List[str]
    usage_pattern: str
    satisfaction_avg: float
    last_active: datetime


class UserBehaviorAnalyzer:
    """تحلیلگر رفتار کاربران"""

    def __init__(self):
        """Initialize user behavior analyzer"""
        self.user_sessions = defaultdict(list)
        self.user_profiles = {}
        self.query_patterns = defaultdict(list)
        self.topic_preferences = defaultdict(Counter)

    async def track_user_action(
        self, user_id: str, action: str, metadata: Dict[str, Any] = None
    ):
        """ردیابی عمل کاربر"""
        try:
            current_time = datetime.now()

            # اضافه کردن به جلسه فعلی
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []

            # ایجاد جلسه جدید اگر لازم باشد
            if not self.user_sessions[user_id] or current_time - self.user_sessions[
                user_id
            ][-1].start_time > timedelta(hours=1):
                new_session = UserSession(
                    user_id=user_id,
                    start_time=current_time,
                    end_time=None,
                    queries=[],
                    documents_added=[],
                    satisfaction_score=0.0,
                )
                self.user_sessions[user_id].append(new_session)

            # ثبت عمل
            current_session = self.user_sessions[user_id][-1]

            if action == "query":
                query_text = metadata.get("query", "") if metadata else ""
                current_session.queries.append(query_text)
                await self._analyze_query_pattern(user_id, query_text)

            elif action == "add_document":
                doc_source = metadata.get("source", "") if metadata else ""
                current_session.documents_added.append(doc_source)

            elif action == "satisfaction":
                score = metadata.get("score", 0.0) if metadata else 0.0
                current_session.satisfaction_score = score

            logger.debug(f"Tracked action {action} for user {user_id}")
        except Exception as e:
            logger.error(f"Error tracking user action: {e}")

    async def _analyze_query_pattern(self, user_id: str, query: str):
        """تحلیل الگوی پرسش"""
        try:
            # استخراج کلمات کلیدی
            keywords = await self._extract_keywords(query)

            # ثبت در الگوهای پرسش
            self.query_patterns[user_id].append(
                {"query": query, "keywords": keywords, "timestamp": datetime.now()}
            )

            # به‌روزرسانی ترجیحات موضوعی
            for keyword in keywords:
                self.topic_preferences[user_id][keyword] += 1
        except Exception as e:
            logger.error(f"Error analyzing query pattern: {e}")

    async def _extract_keywords(self, query: str) -> List[str]:
        """استخراج کلمات کلیدی از پرسش"""
        try:
            # حذف کلمات توقف
            stop_words = {
                "چیست",
                "چطور",
                "چرا",
                "کجا",
                "کی",
                "چی",
                "کدوم",
                "و",
                "در",
                "از",
                "به",
                "the",
                "is",
                "are",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "what",
                "how",
                "does",
                "do",
                "can",
                "could",
                "would",
                "should",
                "will",
                "shall",
                "may",
                "might",
                "must",
                "have",
                "has",
                "had",
                "been",
                "being",
                "was",
                "were",
                "be",
                "am",
                "an",
                "a",
                "as",
                "if",
                "so",
                "than",
                "that",
                "this",
                "these",
                "those",
                "there",
                "here",
                "where",
                "when",
                "why",
                "who",
                "which",
                "whom",
                "whose",
            }

            words = query.lower().split()
            keywords = [
                word for word in words if word not in stop_words and len(word) > 2
            ]

            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []

    async def generate_user_profile(self, user_id: str) -> UserProfile:
        """تولید پروفایل کاربر"""
        try:
            sessions = self.user_sessions.get(user_id, [])

            if not sessions:
                return UserProfile(
                    user_id=user_id,
                    total_sessions=0,
                    total_queries=0,
                    favorite_topics=[],
                    usage_pattern="unknown",
                    satisfaction_avg=0.0,
                    last_active=datetime.now(),
                )

            # محاسبه آمار
            total_queries = sum(len(session.queries) for session in sessions)
            satisfaction_scores = [
                s.satisfaction_score for s in sessions if s.satisfaction_score > 0
            ]
            satisfaction_avg = (
                sum(satisfaction_scores) / len(satisfaction_scores)
                if satisfaction_scores
                else 0.0
            )

            # ترجیحات موضوعی
            topic_prefs = self.topic_preferences.get(user_id, Counter())
            favorite_topics = [topic for topic, count in topic_prefs.most_common(5)]

            # الگوی استفاده
            usage_pattern = await self._determine_usage_pattern(sessions)

            # آخرین فعالیت
            last_active = max(session.start_time for session in sessions)

            profile = UserProfile(
                user_id=user_id,
                total_sessions=len(sessions),
                total_queries=total_queries,
                favorite_topics=favorite_topics,
                usage_pattern=usage_pattern,
                satisfaction_avg=satisfaction_avg,
                last_active=last_active,
            )

            self.user_profiles[user_id] = profile
            return profile
        except Exception as e:
            logger.error(f"Error generating user profile: {e}")
            return UserProfile(
                user_id=user_id,
                total_sessions=0,
                total_queries=0,
                favorite_topics=[],
                usage_pattern="unknown",
                satisfaction_avg=0.0,
                last_active=datetime.now(),
            )

    async def _determine_usage_pattern(self, sessions: List[UserSession]) -> str:
        """تعیین الگوی استفاده"""
        try:
            if not sessions:
                return "unknown"

            # تحلیل فرکانس استفاده
            session_durations = []
            for session in sessions:
                if session.end_time:
                    duration = (session.end_time - session.start_time).total_seconds()
                    session_durations.append(duration)

            if not session_durations:
                return "casual"

            avg_duration = sum(session_durations) / len(session_durations)

            # تحلیل تعداد پرسش‌ها
            total_queries = sum(len(session.queries) for session in sessions)
            avg_queries_per_session = total_queries / len(sessions)

            # تعیین الگو
            if (
                avg_duration > 1800 and avg_queries_per_session > 10
            ):  # 30 دقیقه و 10 پرسش
                return "power_user"
            elif (
                avg_duration > 600 and avg_queries_per_session > 5
            ):  # 10 دقیقه و 5 پرسش
                return "regular_user"
            elif avg_queries_per_session > 2:
                return "casual_user"
            else:
                return "light_user"
        except Exception as e:
            logger.error(f"Error determining usage pattern: {e}")
            return "unknown"

    async def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """دریافت بینش‌های کاربر"""
        try:
            profile = await self.generate_user_profile(user_id)

            insights = {
                "profile": profile,
                "recent_activity": await self._get_recent_activity(user_id),
                "usage_trends": await self._get_usage_trends(user_id),
                "recommendations": await self._generate_recommendations(profile),
            }

            return insights
        except Exception as e:
            logger.error(f"Error getting user insights: {e}")
            return {"error": str(e)}

    async def _get_recent_activity(self, user_id: str) -> Dict[str, Any]:
        """دریافت فعالیت اخیر"""
        try:
            sessions = self.user_sessions.get(user_id, [])

            if not sessions:
                return {"no_activity": True}

            recent_session = sessions[-1]
            last_week_sessions = [
                s for s in sessions if s.start_time > datetime.now() - timedelta(days=7)
            ]

            return {
                "last_session": {
                    "start_time": recent_session.start_time,
                    "queries_count": len(recent_session.queries),
                    "documents_added": len(recent_session.documents_added),
                },
                "weekly_sessions": len(last_week_sessions),
                "weekly_queries": sum(len(s.queries) for s in last_week_sessions),
            }
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return {"error": str(e)}

    async def _get_usage_trends(self, user_id: str) -> Dict[str, Any]:
        """دریافت روندهای استفاده"""
        try:
            sessions = self.user_sessions.get(user_id, [])

            if len(sessions) < 2:
                return {"insufficient_data": True}

            # تحلیل روند هفتگی
            weekly_stats = defaultdict(int)
            for session in sessions:
                week_start = session.start_time - timedelta(
                    days=session.start_time.weekday()
                )
                week_key = week_start.strftime("%Y-%W")
                weekly_stats[week_key] += len(session.queries)

            return {
                "weekly_trend": dict(weekly_stats),
                "growth_rate": await self._calculate_growth_rate(sessions),
            }
        except Exception as e:
            logger.error(f"Error getting usage trends: {e}")
            return {"error": str(e)}

    async def _calculate_growth_rate(self, sessions: List[UserSession]) -> float:
        """محاسبه نرخ رشد"""
        try:
            if len(sessions) < 4:
                return 0.0

            # مقایسه دو هفته اخیر با دو هفته قبل
            recent_sessions = sessions[-4:]
            older_sessions = sessions[-8:-4] if len(sessions) >= 8 else sessions[:-4]

            recent_queries = sum(len(s.queries) for s in recent_sessions)
            older_queries = sum(len(s.queries) for s in older_sessions)

            if older_queries == 0:
                return 100.0 if recent_queries > 0 else 0.0

            growth_rate = ((recent_queries - older_queries) / older_queries) * 100
            return round(growth_rate, 2)
        except Exception as e:
            logger.error(f"Error calculating growth rate: {e}")
            return 0.0

    async def _generate_recommendations(self, profile: UserProfile) -> List[str]:
        """تولید توصیه‌ها"""
        try:
            recommendations = []

            # توصیه بر اساس الگوی استفاده
            if profile.usage_pattern == "light_user":
                recommendations.append(
                    "سعی کنید بیشتر از بات استفاده کنید تا پاسخ‌های بهتری دریافت کنید"
                )

            elif profile.usage_pattern == "power_user":
                recommendations.append(
                    "شما کاربر فعالی هستید! سعی کنید اسناد بیشتری اضافه کنید"
                )

            # توصیه بر اساس رضایت
            if profile.satisfaction_avg < 0.6:
                recommendations.append(
                    "کیفیت پاسخ‌ها را با اضافه کردن اسناد مرتبط بهبود دهید"
                )

            # توصیه بر اساس موضوعات محبوب
            if profile.favorite_topics:
                recommendations.append(
                    f"شما علاقه‌مند به موضوعات {', '.join(profile.favorite_topics[:3])} هستید"
                )

            return recommendations
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    async def analyze_search_patterns(self) -> Dict[str, Any]:
        """تحلیل الگوهای جستجو"""
        try:
            logger.info("Analyzing search patterns...")

            # جمع‌آوری تمام پرسش‌ها
            all_queries = []
            query_times = []

            for _, sessions in self.user_sessions.items():
                for session in sessions:
                    all_queries.extend(session.queries)
                    query_times.extend([session.start_time] * len(session.queries))

            if not all_queries:
                return {"error": "no_data"}

            # تحلیل الگوهای جستجو
            search_patterns = {
                "total_queries": len(all_queries),
                "unique_queries": len(set(all_queries)),
                "query_length_distribution": self._analyze_query_lengths(all_queries),
                "temporal_patterns": self._analyze_query_temporal_patterns(query_times),
                "query_complexity": self._analyze_query_complexity(all_queries),
                "popular_keywords": self._extract_popular_keywords(all_queries),
                "query_categories": self._categorize_queries(all_queries),
            }

            logger.success("Search pattern analysis completed")
            return search_patterns

        except Exception as e:
            logger.error(f"Error analyzing search patterns: {e}")
            return {"error": str(e)}

    async def identify_user_segments(self) -> List[Dict[str, Any]]:
        """شناسایی بخش‌بندی کاربران"""
        try:
            logger.info("Identifying user segments...")

            segments = []

            # تحلیل پروفایل‌های کاربران
            for user_id in self.user_sessions.keys():
                profile = await self.generate_user_profile(user_id)

                # تعیین بخش کاربر
                segment = self._determine_user_segment(profile)
                segments.append(
                    {
                        "user_id": user_id,
                        "segment": segment,
                        "profile": profile,
                        "characteristics": self._get_segment_characteristics(
                            profile, segment
                        ),
                    }
                )

            # گروه‌بندی بر اساس بخش
            segment_groups = {}
            for user_segment in segments:
                segment_name = user_segment["segment"]
                if segment_name not in segment_groups:
                    segment_groups[segment_name] = []
                segment_groups[segment_name].append(user_segment)

            # تولید خلاصه بخش‌ها
            segment_summary = []
            for segment_name, users in segment_groups.items():
                segment_summary.append(
                    {
                        "segment_name": segment_name,
                        "user_count": len(users),
                        "percentage": len(users) / len(segments) * 100,
                        "characteristics": self._get_segment_summary_characteristics(
                            users
                        ),
                        "recommendations": self._get_segment_recommendations(
                            segment_name
                        ),
                    }
                )

            logger.success(f"Identified {len(segment_summary)} user segments")
            return segment_summary

        except Exception as e:
            logger.error(f"Error identifying user segments: {e}")
            return []

    async def predict_user_churn(self) -> Dict[str, Any]:
        """پیش‌بینی ترک کاربران"""
        try:
            logger.info("Predicting user churn...")

            churn_predictions = []

            for user_id in self.user_sessions.keys():
                profile = await self.generate_user_profile(user_id)

                # محاسبه امتیاز ترک
                churn_score = self._calculate_churn_score(profile)

                # تعیین احتمال ترک
                churn_probability = self._calculate_churn_probability(churn_score)

                # تعیین وضعیت
                churn_status = self._determine_churn_status(churn_probability)

                churn_predictions.append(
                    {
                        "user_id": user_id,
                        "churn_score": churn_score,
                        "churn_probability": churn_probability,
                        "churn_status": churn_status,
                        "risk_factors": self._identify_churn_risk_factors(profile),
                        "retention_recommendations": self._get_retention_recommendations(
                            churn_status
                        ),
                    }
                )

            # خلاصه پیش‌بینی ترک
            churn_summary = {
                "total_users": len(churn_predictions),
                "high_risk_users": len(
                    [p for p in churn_predictions if p["churn_status"] == "high_risk"]
                ),
                "medium_risk_users": len(
                    [p for p in churn_predictions if p["churn_status"] == "medium_risk"]
                ),
                "low_risk_users": len(
                    [p for p in churn_predictions if p["churn_status"] == "low_risk"]
                ),
                "average_churn_probability": sum(
                    p["churn_probability"] for p in churn_predictions
                )
                / len(churn_predictions),
                "predictions": churn_predictions,
            }

            logger.success("User churn prediction completed")
            return churn_summary

        except Exception as e:
            logger.error(f"Error predicting user churn: {e}")
            return {"error": str(e)}

    async def recommend_personalization(self, user_id: str) -> Dict[str, Any]:
        """توصیه شخصی‌سازی برای کاربر"""
        try:
            logger.info(
                f"Generating personalization recommendations for user {user_id}"
            )

            profile = await self.generate_user_profile(user_id)

            # تحلیل رفتار کاربر
            behavior_analysis = await self._analyze_user_behavior_patterns(user_id)

            # تولید توصیه‌های شخصی‌سازی
            personalization_recommendations = {
                "user_id": user_id,
                "personalization_score": self._calculate_personalization_score(profile),
                "content_recommendations": self._generate_content_recommendations(
                    profile, behavior_analysis
                ),
                "interface_recommendations": self._generate_interface_recommendations(
                    profile
                ),
                "feature_recommendations": self._generate_feature_recommendations(
                    profile, behavior_analysis
                ),
                "timing_recommendations": self._generate_timing_recommendations(
                    behavior_analysis
                ),
                "priority_actions": self._get_priority_personalization_actions(profile),
            }

            logger.success(
                f"Personalization recommendations generated for user {user_id}"
            )
            return personalization_recommendations

        except Exception as e:
            logger.error(f"Error generating personalization recommendations: {e}")
            return {"error": str(e)}

    # Helper methods for advanced analytics
    def _analyze_query_lengths(self, queries: List[str]) -> Dict[str, int]:
        """تحلیل توزیع طول پرسش‌ها"""
        try:
            length_distribution = {
                "short": len([q for q in queries if len(q.split()) <= 3]),
                "medium": len([q for q in queries if 3 < len(q.split()) <= 8]),
                "long": len([q for q in queries if len(q.split()) > 8]),
            }
            return length_distribution
        except Exception:
            return {"short": 0, "medium": 0, "long": 0}

    def _analyze_query_temporal_patterns(
        self, query_times: List[datetime]
    ) -> Dict[str, Any]:
        """تحلیل الگوهای زمانی پرسش‌ها"""
        try:
            if not query_times:
                return {"error": "no_data"}

            # تحلیل ساعتی
            hourly_counts = {}
            for time in query_times:
                hour = time.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

            # تحلیل روزانه
            daily_counts = {}
            for time in query_times:
                day = time.weekday()
                daily_counts[day] = daily_counts.get(day, 0) + 1

            return {
                "hourly_distribution": hourly_counts,
                "daily_distribution": daily_counts,
                "peak_hour": max(hourly_counts.items(), key=lambda x: x[1])[0]
                if hourly_counts
                else 0,
                "peak_day": max(daily_counts.items(), key=lambda x: x[1])[0]
                if daily_counts
                else 0,
            }
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {e}")
            return {"error": str(e)}

    def _analyze_query_complexity(self, queries: List[str]) -> Dict[str, Any]:
        """تحلیل پیچیدگی پرسش‌ها"""
        try:
            complexity_scores = []
            for query in queries:
                # محاسبه پیچیدگی ساده
                word_count = len(query.split())
                char_count = len(query)
                question_marks = query.count("?")
                special_chars = sum(
                    1 for c in query if not c.isalnum() and c not in " ?"
                )

                complexity = (
                    min(word_count / 20, 1.0) * 0.3
                    + min(char_count / 200, 1.0) * 0.2
                    + min(question_marks / 3, 1.0) * 0.2
                    + min(special_chars / 10, 1.0) * 0.3
                )
                complexity_scores.append(complexity)

            if complexity_scores:
                return {
                    "average_complexity": sum(complexity_scores)
                    / len(complexity_scores),
                    "max_complexity": max(complexity_scores),
                    "min_complexity": min(complexity_scores),
                    "complexity_distribution": {
                        "simple": len([c for c in complexity_scores if c < 0.3]),
                        "medium": len([c for c in complexity_scores if 0.3 <= c < 0.7]),
                        "complex": len([c for c in complexity_scores if c >= 0.7]),
                    },
                }
            else:
                return {
                    "average_complexity": 0,
                    "max_complexity": 0,
                    "min_complexity": 0,
                }
        except Exception as e:
            logger.error(f"Error analyzing query complexity: {e}")
            return {"error": str(e)}

    def _extract_popular_keywords(self, queries: List[str]) -> List[Tuple[str, int]]:
        """استخراج کلمات کلیدی محبوب"""
        try:
            from collections import Counter

            # استخراج کلمات کلیدی
            keywords = []
            for query in queries:
                words = [
                    word.lower()
                    for word in query.split()
                    if len(word) > 2 and word.isalpha()
                ]
                keywords.extend(words)

            # شمارش و مرتب‌سازی
            keyword_counts = Counter(keywords)
            return keyword_counts.most_common(20)
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []

    def _categorize_queries(self, queries: List[str]) -> Dict[str, List[str]]:
        """دسته‌بندی پرسش‌ها"""
        try:
            categories = {"questions": [], "commands": [], "requests": [], "other": []}

            for query in queries:
                query_lower = query.lower()
                if query_lower.startswith(("چی", "چطور", "چرا", "کجا", "کی", "کدام")):
                    categories["questions"].append(query)
                elif query_lower.startswith(("بگو", "نشان", "بیاور", "پیدا")):
                    categories["commands"].append(query)
                elif query_lower.startswith(("لطفا", "می‌تونید", "میشه")):
                    categories["requests"].append(query)
                else:
                    categories["other"].append(query)

            return categories
        except Exception as e:
            logger.error(f"Error categorizing queries: {e}")
            return {"questions": [], "commands": [], "requests": [], "other": []}

    def _determine_user_segment(self, profile: UserProfile) -> str:
        """تعیین بخش کاربر"""
        try:
            # تحلیل بر اساس الگوی استفاده
            if profile.total_sessions > 20 and profile.total_queries > 100:
                return "power_user"
            elif profile.total_sessions > 10 and profile.total_queries > 50:
                return "regular_user"
            elif profile.total_sessions > 5 and profile.total_queries > 20:
                return "casual_user"
            elif profile.total_sessions > 0 and profile.total_queries > 0:
                return "new_user"
            else:
                return "inactive_user"
        except Exception:
            return "unknown"

    def _get_segment_characteristics(
        self, profile: UserProfile, segment: str
    ) -> Dict[str, Any]:
        """دریافت ویژگی‌های بخش"""
        try:
            characteristics = {
                "sessions": profile.total_sessions,
                "queries": profile.total_queries,
                "satisfaction": profile.satisfaction_avg,
                "topics": len(profile.favorite_topics),
                "last_active": profile.last_active,
            }

            # ویژگی‌های خاص بخش
            if segment == "power_user":
                characteristics["engagement_level"] = "high"
                characteristics["loyalty"] = "high"
            elif segment == "regular_user":
                characteristics["engagement_level"] = "medium"
                characteristics["loyalty"] = "medium"
            elif segment == "casual_user":
                characteristics["engagement_level"] = "low"
                characteristics["loyalty"] = "low"
            else:
                characteristics["engagement_level"] = "unknown"
                characteristics["loyalty"] = "unknown"

            return characteristics
        except Exception as e:
            logger.error(f"Error getting segment characteristics: {e}")
            return {}

    def _get_segment_summary_characteristics(
        self, users: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """دریافت ویژگی‌های خلاصه بخش"""
        try:
            if not users:
                return {}

            profiles = [user["profile"] for user in users]

            return {
                "avg_sessions": sum(p.total_sessions for p in profiles) / len(profiles),
                "avg_queries": sum(p.total_queries for p in profiles) / len(profiles),
                "avg_satisfaction": sum(p.satisfaction_avg for p in profiles)
                / len(profiles),
                "avg_topics": sum(len(p.favorite_topics) for p in profiles)
                / len(profiles),
            }
        except Exception as e:
            logger.error(f"Error getting segment summary: {e}")
            return {}

    def _get_segment_recommendations(self, segment: str) -> List[str]:
        """دریافت توصیه‌های بخش"""
        try:
            recommendations_map = {
                "power_user": [
                    "ارائه ویژگی‌های پیشرفته",
                    "دسترسی اولویت‌دار به قابلیت‌های جدید",
                    "پشتیبانی تخصصی",
                ],
                "regular_user": [
                    "ارائه آموزش‌های پیشرفته",
                    "تشویق به استفاده بیشتر",
                    "معرفی قابلیت‌های جدید",
                ],
                "casual_user": [
                    "بهبود تجربه کاربری",
                    "ارائه محتوای جذاب",
                    "کاهش پیچیدگی رابط کاربری",
                ],
                "new_user": ["راهنمایی کامل", "آموزش‌های پایه", "تجربه کاربری ساده"],
                "inactive_user": [
                    "بازگرداندن کاربر",
                    "ارائه انگیزه‌های جدید",
                    "بررسی علل عدم استفاده",
                ],
            }

            return recommendations_map.get(segment, ["تحلیل بیشتر نیاز است"])
        except Exception:
            return ["خطا در تولید توصیه"]

    def _calculate_churn_score(self, profile: UserProfile) -> float:
        """محاسبه امتیاز ترک کاربر"""
        try:
            score = 0.0

            # عوامل کاهش امتیاز ترک (عوامل مثبت)
            if profile.total_sessions > 10:
                score -= 0.2
            if profile.total_queries > 50:
                score -= 0.2
            if profile.satisfaction_avg > 0.7:
                score -= 0.3
            if len(profile.favorite_topics) > 3:
                score -= 0.1

            # عوامل افزایش امتیاز ترک (عوامل منفی)
            if profile.satisfaction_avg < 0.4:
                score += 0.4
            if profile.total_sessions < 3:
                score += 0.3

            # بررسی آخرین فعالیت
            days_since_last_active = (datetime.now() - profile.last_active).days
            if days_since_last_active > 30:
                score += 0.5
            elif days_since_last_active > 14:
                score += 0.3
            elif days_since_last_active > 7:
                score += 0.1

            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    def _calculate_churn_probability(self, churn_score: float) -> float:
        """محاسبه احتمال ترک"""
        try:
            # تبدیل امتیاز به احتمال
            if churn_score < 0.2:
                return 0.1  # احتمال کم
            elif churn_score < 0.4:
                return 0.3  # احتمال متوسط
            elif churn_score < 0.6:
                return 0.5  # احتمال متوسط-بالا
            elif churn_score < 0.8:
                return 0.7  # احتمال بالا
            else:
                return 0.9  # احتمال خیلی بالا
        except Exception:
            return 0.5

    def _determine_churn_status(self, churn_probability: float) -> str:
        """تعیین وضعیت ترک"""
        try:
            if churn_probability > 0.7:
                return "high_risk"
            elif churn_probability > 0.4:
                return "medium_risk"
            else:
                return "low_risk"
        except Exception:
            return "unknown"

    def _identify_churn_risk_factors(self, profile: UserProfile) -> List[str]:
        """شناسایی عوامل ریسک ترک"""
        try:
            risk_factors = []

            if profile.satisfaction_avg < 0.4:
                risk_factors.append("low_satisfaction")
            if profile.total_sessions < 3:
                risk_factors.append("low_engagement")
            if len(profile.favorite_topics) < 2:
                risk_factors.append("limited_interest")

            days_since_last_active = (datetime.now() - profile.last_active).days
            if days_since_last_active > 14:
                risk_factors.append("inactive_period")

            return risk_factors if risk_factors else ["no_significant_risks"]
        except Exception:
            return ["unknown_risks"]

    def _get_retention_recommendations(self, churn_status: str) -> List[str]:
        """دریافت توصیه‌های حفظ کاربر"""
        try:
            recommendations_map = {
                "high_risk": [
                    "ارسال پیام شخصی‌سازی شده",
                    "ارائه تخفیف یا پاداش",
                    "بررسی علل نارضایتی",
                    "ارائه پشتیبانی ویژه",
                ],
                "medium_risk": [
                    "ارسال یادآوری استفاده",
                    "معرفی قابلیت‌های جدید",
                    "ارائه محتوای جذاب",
                    "بهبود تجربه کاربری",
                ],
                "low_risk": [
                    "ادامه ارائه خدمات باکیفیت",
                    "معرفی قابلیت‌های پیشرفته",
                    "تشویق به معرفی به دیگران",
                ],
            }

            return recommendations_map.get(churn_status, ["تحلیل بیشتر نیاز است"])
        except Exception:
            return ["خطا در تولید توصیه"]

    async def _analyze_user_behavior_patterns(self, user_id: str) -> Dict[str, Any]:
        """تحلیل الگوهای رفتاری کاربر"""
        try:
            sessions = self.user_sessions.get(user_id, [])

            if not sessions:
                return {"error": "no_data"}

            # تحلیل الگوهای زمانی
            session_times = [session.start_time for session in sessions]
            hourly_patterns = {}
            for time in session_times:
                hour = time.hour
                hourly_patterns[hour] = hourly_patterns.get(hour, 0) + 1

            # تحلیل طول جلسات
            session_lengths = []
            for session in sessions:
                if session.end_time:
                    length = (
                        session.end_time - session.start_time
                    ).total_seconds() / 60
                    session_lengths.append(length)

            return {
                "total_sessions": len(sessions),
                "hourly_patterns": hourly_patterns,
                "avg_session_length": sum(session_lengths) / len(session_lengths)
                if session_lengths
                else 0,
                "preferred_hours": sorted(
                    hourly_patterns.items(), key=lambda x: x[1], reverse=True
                )[:3],
            }
        except Exception as e:
            logger.error(f"Error analyzing behavior patterns: {e}")
            return {"error": str(e)}

    def _calculate_personalization_score(self, profile: UserProfile) -> float:
        """محاسبه امتیاز شخصی‌سازی"""
        try:
            score = 0.0

            # عوامل شخصی‌سازی
            if profile.total_sessions > 5:
                score += 0.2
            if profile.total_queries > 20:
                score += 0.2
            if len(profile.favorite_topics) > 2:
                score += 0.3
            if profile.satisfaction_avg > 0.6:
                score += 0.3

            return min(score, 1.0)
        except Exception:
            return 0.0

    def _generate_content_recommendations(
        self, profile: UserProfile, behavior_analysis: Dict[str, Any]
    ) -> List[str]:
        """تولید توصیه‌های محتوا"""
        try:
            recommendations = []

            # توصیه بر اساس موضوعات محبوب
            if profile.favorite_topics:
                recommendations.append(
                    f"محتوای بیشتر در زمینه {', '.join(profile.favorite_topics[:3])}"
                )

            # توصیه بر اساس الگوی استفاده
            if behavior_analysis.get("avg_session_length", 0) > 30:
                recommendations.append("محتوای عمیق و تفصیلی")
            else:
                recommendations.append("محتوای مختصر و کاربردی")

            return recommendations
        except Exception:
            return ["محتوای عمومی"]

    def _generate_interface_recommendations(self, profile: UserProfile) -> List[str]:
        """تولید توصیه‌های رابط کاربری"""
        try:
            recommendations = []

            if profile.usage_pattern == "power_user":
                recommendations.extend(
                    ["رابط کاربری پیشرفته", "دسترسی سریع به قابلیت‌ها", "کلیدهای میانبر"]
                )
            elif profile.usage_pattern == "casual_user":
                recommendations.extend(
                    ["رابط کاربری ساده", "راهنمایی بصری", "کاهش پیچیدگی"]
                )
            else:
                recommendations.append("رابط کاربری متعادل")

            return recommendations
        except Exception:
            return ["رابط کاربری استاندارد"]

    def _generate_feature_recommendations(
        self, profile: UserProfile, behavior_analysis: Dict[str, Any]
    ) -> List[str]:
        """تولید توصیه‌های قابلیت"""
        try:
            recommendations = []

            if profile.total_queries > 50:
                recommendations.append("قابلیت جستجوی پیشرفته")

            if len(profile.favorite_topics) > 3:
                recommendations.append("دسته‌بندی موضوعی")

            if behavior_analysis.get("avg_session_length", 0) > 20:
                recommendations.append("ذخیره جلسات")

            return recommendations
        except Exception:
            return ["قابلیت‌های پایه"]

    def _generate_timing_recommendations(
        self, behavior_analysis: Dict[str, Any]
    ) -> List[str]:
        """تولید توصیه‌های زمان‌بندی"""
        try:
            recommendations = []

            preferred_hours = behavior_analysis.get("preferred_hours", [])
            if preferred_hours:
                hours = [str(hour) for hour, _ in preferred_hours]
                recommendations.append(f"ارسال یادآوری در ساعات {', '.join(hours)}")

            return recommendations
        except Exception:
            return ["زمان‌بندی عمومی"]

    def _get_priority_personalization_actions(self, profile: UserProfile) -> List[str]:
        """دریافت اقدامات اولویت‌دار شخصی‌سازی"""
        try:
            actions = []

            if profile.satisfaction_avg < 0.5:
                actions.append("بهبود کیفیت پاسخ‌ها")

            if profile.total_sessions < 3:
                actions.append("افزایش تعامل کاربر")

            if len(profile.favorite_topics) < 2:
                actions.append("شناسایی علایق کاربر")

            return actions if actions else ["ادامه نظارت"]
        except Exception:
            return ["تحلیل بیشتر"]

    async def get_all_users_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه تمام کاربران"""
        try:
            total_users = len(self.user_sessions)
            total_sessions = sum(
                len(sessions) for sessions in self.user_sessions.values()
            )
            total_queries = sum(
                sum(len(session.queries) for session in sessions)
                for sessions in self.user_sessions.values()
            )

            # الگوهای استفاده
            usage_patterns = Counter()
            for user_id in self.user_sessions.keys():
                profile = await self.generate_user_profile(user_id)
                usage_patterns[profile.usage_pattern] += 1

            return {
                "total_users": total_users,
                "total_sessions": total_sessions,
                "total_queries": total_queries,
                "usage_patterns": dict(usage_patterns),
                "average_queries_per_user": total_queries / total_users
                if total_users > 0
                else 0,
            }
        except Exception as e:
            logger.error(f"Error getting all users summary: {e}")
            return {"error": str(e)}
