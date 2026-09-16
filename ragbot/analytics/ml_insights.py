"""
موتور بینش‌های یادگیری ماشین
"""

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .user_behavior import UserBehaviorAnalyzer, UserProfile
from .usage_patterns import UsagePatternsAnalyzer


@dataclass
class QueryPatternAnalysis:
    """تحلیل الگوهای پرسش"""

    most_common_queries: List[Tuple[str, int]]
    query_complexity_distribution: Dict[str, int]
    temporal_patterns: Dict[str, Any]
    semantic_clusters: List[Dict[str, Any]]
    query_evolution: List[Dict[str, Any]]


@dataclass
class Topic:
    """موضوع"""

    name: str
    frequency: int
    relevance_score: float
    related_queries: List[str]
    user_engagement: float


@dataclass
class ContentSuggestion:
    """پیشنهاد محتوا"""

    suggestion_type: str
    content_id: str
    reason: str
    confidence: float
    impact_score: float


@dataclass
class EmbeddingOptimization:
    """بهینه‌سازی embedding"""

    current_strategy: str
    recommended_strategy: str
    expected_improvement: float
    implementation_effort: str
    risk_level: str


@dataclass
class BehaviorPrediction:
    """پیش‌بینی رفتار"""

    user_id: str
    predicted_actions: List[str]
    confidence_scores: Dict[str, float]
    time_horizon: int
    factors: List[str]


@dataclass
class AnomalyReport:
    """گزارش ناهنجاری"""

    anomaly_type: str
    severity: str
    detected_at: datetime
    affected_metrics: List[str]
    description: str
    recommended_actions: List[str]


class MLInsightsEngine:
    """موتور بینش‌های یادگیری ماشین"""

    def __init__(
        self,
        user_behavior: UserBehaviorAnalyzer = None,
        usage_patterns: UsagePatternsAnalyzer = None,
    ):
        """Initialize ML insights engine"""
        self.user_behavior = user_behavior or UserBehaviorAnalyzer()
        self.usage_patterns = usage_patterns or UsagePatternsAnalyzer()

        # ML models cache
        self._query_pattern_model = None
        self._topic_model = None
        self._anomaly_model = None

        # Data storage
        self.query_history = []
        self.topic_clusters = []
        self.anomaly_history = []

    async def analyze_query_patterns(self) -> QueryPatternAnalysis:
        """تحلیل الگوهای پرسش"""
        try:
            logger.info("Analyzing query patterns...")

            # جمع‌آوری داده‌های پرسش
            all_queries = []
            query_times = []
            query_complexity = []

            for sessions in self.user_behavior.user_sessions.values():
                for session in sessions:
                    all_queries.extend(session.queries)
                    query_times.extend([session.start_time] * len(session.queries))

                    # محاسبه پیچیدگی پرسش
                    for query in session.queries:
                        complexity = self._calculate_query_complexity(query)
                        query_complexity.append(complexity)

            # تحلیل الگوهای رایج
            query_counter = Counter(all_queries)
            most_common = query_counter.most_common(20)

            # توزیع پیچیدگی
            complexity_dist = {
                "simple": len([c for c in query_complexity if c < 0.3]),
                "medium": len([c for c in query_complexity if 0.3 <= c < 0.7]),
                "complex": len([c for c in query_complexity if c >= 0.7]),
            }

            # الگوهای زمانی
            temporal_patterns = await self._analyze_temporal_patterns(query_times)

            # خوشه‌بندی معنایی
            semantic_clusters = await self._cluster_semantic_queries(all_queries)

            # تکامل پرسش‌ها
            query_evolution = await self._analyze_query_evolution(all_queries)

            analysis = QueryPatternAnalysis(
                most_common_queries=most_common,
                query_complexity_distribution=complexity_dist,
                temporal_patterns=temporal_patterns,
                semantic_clusters=semantic_clusters,
                query_evolution=query_evolution,
            )

            logger.success("Query pattern analysis completed")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing query patterns: {e}")
            raise

    async def identify_popular_topics(self) -> List[Topic]:
        """شناسایی موضوعات محبوب"""
        try:
            logger.info("Identifying popular topics...")

            # جمع‌آوری موضوعات از پروفایل کاربران
            topic_frequency = Counter()
            topic_queries = defaultdict(list)
            topic_engagement = defaultdict(list)

            for user_id, profile in self.user_behavior.user_profiles.items():
                for topic in profile.favorite_topics:
                    topic_frequency[topic] += 1
                    topic_queries[topic].extend(
                        [
                            q
                            for session in self.user_behavior.user_sessions[user_id]
                            for q in session.queries
                        ]
                    )
                    topic_engagement[topic].append(profile.satisfaction_avg)

            topics = []
            for topic, frequency in topic_frequency.most_common(15):
                related_queries = topic_queries[topic][:10]  # محدود کردن
                engagement_scores = topic_engagement[topic]
                avg_engagement = (
                    statistics.mean(engagement_scores) if engagement_scores else 0.0
                )

                # محاسبه امتیاز ارتباط
                relevance_score = self._calculate_topic_relevance(
                    topic, related_queries
                )

                topic_obj = Topic(
                    name=topic,
                    frequency=frequency,
                    relevance_score=relevance_score,
                    related_queries=related_queries,
                    user_engagement=avg_engagement,
                )
                topics.append(topic_obj)

            # مرتب‌سازی بر اساس امتیاز ترکیبی
            topics.sort(
                key=lambda t: t.frequency * t.relevance_score * t.user_engagement,
                reverse=True,
            )

            logger.success(f"Identified {len(topics)} popular topics")
            return topics

        except Exception as e:
            logger.error(f"Error identifying popular topics: {e}")
            raise

    async def suggest_content_improvements(self) -> List[ContentSuggestion]:
        """پیشنهاد بهبود محتوا"""
        try:
            logger.info("Generating content improvement suggestions...")

            suggestions = []

            # تحلیل پرسش‌های بدون پاسخ
            unanswered_queries = await self._find_unanswered_queries()
            for query in unanswered_queries[:10]:  # محدود کردن
                suggestion = ContentSuggestion(
                    suggestion_type="missing_content",
                    content_id=f"query_{hash(query)}",
                    reason=f"پرسش '{query}' پاسخ مناسبی دریافت نکرده",
                    confidence=0.8,
                    impact_score=0.7,
                )
                suggestions.append(suggestion)

            # تحلیل موضوعات کم‌کاربرد
            underutilized_topics = await self._find_underutilized_topics()
            for topic in underutilized_topics[:5]:
                suggestion = ContentSuggestion(
                    suggestion_type="content_expansion",
                    content_id=f"topic_{topic}",
                    reason=f"موضوع '{topic}' نیاز به محتوای بیشتر دارد",
                    confidence=0.6,
                    impact_score=0.5,
                )
                suggestions.append(suggestion)

            # تحلیل کیفیت پاسخ‌ها
            low_quality_responses = await self._find_low_quality_responses()
            for response in low_quality_responses[:5]:
                suggestion = ContentSuggestion(
                    suggestion_type="quality_improvement",
                    content_id=f"response_{response['id']}",
                    reason=f"پاسخ با کیفیت پایین: {response['reason']}",
                    confidence=0.7,
                    impact_score=0.8,
                )
                suggestions.append(suggestion)

            # مرتب‌سازی بر اساس امتیاز تاثیر
            suggestions.sort(key=lambda s: s.impact_score * s.confidence, reverse=True)

            logger.success(f"Generated {len(suggestions)} content suggestions")
            return suggestions

        except Exception as e:
            logger.error(f"Error generating content suggestions: {e}")
            raise

    async def optimize_embedding_strategy(self) -> EmbeddingOptimization:
        """بهینه‌سازی استراتژی embedding"""
        try:
            logger.info("Analyzing embedding strategy...")

            # تحلیل عملکرد فعلی
            current_performance = await self._analyze_current_embedding_performance()

            # پیشنهاد استراتژی جدید
            recommended_strategy = await self._recommend_embedding_strategy(
                current_performance
            )

            # محاسبه بهبود مورد انتظار
            expected_improvement = await self._calculate_embedding_improvement(
                current_performance, recommended_strategy
            )

            # ارزیابی تلاش پیاده‌سازی
            implementation_effort = self._assess_implementation_effort(
                recommended_strategy
            )

            # ارزیابی ریسک
            risk_level = self._assess_embedding_risk(recommended_strategy)

            optimization = EmbeddingOptimization(
                current_strategy=current_performance.get("strategy", "unknown"),
                recommended_strategy=recommended_strategy,
                expected_improvement=expected_improvement,
                implementation_effort=implementation_effort,
                risk_level=risk_level,
            )

            logger.success("Embedding strategy optimization completed")
            return optimization

        except Exception as e:
            logger.error(f"Error optimizing embedding strategy: {e}")
            raise

    async def predict_user_behavior(self, user_id: str) -> BehaviorPrediction:
        """پیش‌بینی رفتار کاربر"""
        try:
            logger.info(f"Predicting behavior for user {user_id}")

            # جمع‌آوری داده‌های کاربر
            user_profile = self.user_behavior.user_profiles.get(user_id)
            if not user_profile:
                raise ValueError(f"User {user_id} not found")

            # تحلیل الگوهای تاریخی
            historical_patterns = await self._analyze_user_historical_patterns(user_id)

            # پیش‌بینی اقدامات آینده
            predicted_actions = await self._predict_future_actions(historical_patterns)

            # محاسبه امتیازهای اطمینان
            confidence_scores = await self._calculate_prediction_confidence(
                user_profile, historical_patterns
            )

            # شناسایی عوامل تاثیرگذار
            factors = await self._identify_behavioral_factors(
                user_profile, historical_patterns
            )

            prediction = BehaviorPrediction(
                user_id=user_id,
                predicted_actions=predicted_actions,
                confidence_scores=confidence_scores,
                time_horizon=7,  # 7 روز آینده
                factors=factors,
            )

            logger.success(f"Behavior prediction completed for user {user_id}")
            return prediction

        except Exception as e:
            logger.error(f"Error predicting user behavior: {e}")
            raise

    async def detect_anomalies(self, metrics: Dict[str, Any]) -> AnomalyReport:
        """تشخیص ناهنجاری‌ها"""
        try:
            logger.info("Detecting anomalies in metrics...")

            # تحلیل هر متریک
            anomalies = []

            for metric_name, metric_value in metrics.items():
                anomaly = await self._check_metric_anomaly(metric_name, metric_value)
                if anomaly:
                    anomalies.append(anomaly)

            if not anomalies:
                # گزارش عدم وجود ناهنجاری
                return AnomalyReport(
                    anomaly_type="none",
                    severity="low",
                    detected_at=datetime.now(),
                    affected_metrics=[],
                    description="هیچ ناهنجاری قابل توجهی تشخیص داده نشد",
                    recommended_actions=["ادامه نظارت"],
                )

            # انتخاب شدیدترین ناهنجاری
            primary_anomaly = max(
                anomalies, key=lambda a: self._get_severity_score(a["severity"])
            )

            # تولید گزارش
            report = AnomalyReport(
                anomaly_type=primary_anomaly["type"],
                severity=primary_anomaly["severity"],
                detected_at=datetime.now(),
                affected_metrics=[primary_anomaly["metric"]],
                description=primary_anomaly["description"],
                recommended_actions=primary_anomaly["actions"],
            )

            # ذخیره در تاریخچه
            self.anomaly_history.append(report)

            logger.success(f"Anomaly detection completed: {primary_anomaly['type']}")
            return report

        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            raise

    # Helper methods
    def _calculate_query_complexity(self, query: str) -> float:
        """محاسبه پیچیدگی پرسش"""
        try:
            # عوامل پیچیدگی
            word_count = len(query.split())
            char_count = len(query)
            question_marks = query.count("?")
            special_chars = sum(1 for c in query if not c.isalnum() and c not in " ?")

            # محاسبه امتیاز پیچیدگی (0-1)
            complexity = (
                min(word_count / 20, 1.0) * 0.3
                + min(char_count / 200, 1.0) * 0.2
                + min(question_marks / 3, 1.0) * 0.2
                + min(special_chars / 10, 1.0) * 0.3
            )

            return min(complexity, 1.0)
        except Exception:
            return 0.5  # مقدار پیش‌فرض

    async def _analyze_temporal_patterns(
        self, query_times: List[datetime]
    ) -> Dict[str, Any]:
        """تحلیل الگوهای زمانی"""
        try:
            if not query_times:
                return {"error": "no_data"}

            # تحلیل ساعتی
            hourly_counts = defaultdict(int)
            for time in query_times:
                hourly_counts[time.hour] += 1

            # تحلیل روزانه
            daily_counts = defaultdict(int)
            for time in query_times:
                daily_counts[time.weekday()] += 1

            # شناسایی پیک‌ها
            peak_hour = max(hourly_counts.items(), key=lambda x: x[1])[0]
            peak_day = max(daily_counts.items(), key=lambda x: x[1])[0]

            return {
                "hourly_distribution": dict(hourly_counts),
                "daily_distribution": dict(daily_counts),
                "peak_hour": peak_hour,
                "peak_day": peak_day,
                "total_queries": len(query_times),
            }
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {e}")
            return {"error": str(e)}

    async def _cluster_semantic_queries(
        self, queries: List[str]
    ) -> List[Dict[str, Any]]:
        """خوشه‌بندی معنایی پرسش‌ها"""
        try:
            if not queries:
                return []

            # خوشه‌بندی ساده بر اساس کلمات کلیدی
            clusters = defaultdict(list)

            for query in queries:
                # استخراج کلمات کلیدی ساده
                keywords = [
                    word.lower()
                    for word in query.split()
                    if len(word) > 3 and word.isalpha()
                ]

                if keywords:
                    # استفاده از اولین کلمه کلیدی به عنوان نماینده خوشه
                    cluster_key = keywords[0]
                    clusters[cluster_key].append(query)

            # تبدیل به لیست
            cluster_list = []
            for key, cluster_queries in clusters.items():
                if len(cluster_queries) > 1:  # فقط خوشه‌های با بیش از یک عضو
                    cluster_list.append(
                        {
                            "cluster_name": key,
                            "queries": cluster_queries[:10],  # محدود کردن
                            "size": len(cluster_queries),
                            "representative_query": cluster_queries[0],
                        }
                    )

            # مرتب‌سازی بر اساس اندازه
            cluster_list.sort(key=lambda x: x["size"], reverse=True)

            return cluster_list[:10]  # محدود کردن به 10 خوشه برتر

        except Exception as e:
            logger.error(f"Error clustering semantic queries: {e}")
            return []

    async def _analyze_query_evolution(
        self, queries: List[str]
    ) -> List[Dict[str, Any]]:
        """تحلیل تکامل پرسش‌ها"""
        try:
            if not queries:
                return []

            # تحلیل ساده بر اساس طول پرسش‌ها
            short_queries = [q for q in queries if len(q.split()) <= 3]
            long_queries = [q for q in queries if len(q.split()) > 8]

            evolution = [
                {
                    "period": "recent",
                    "query_length_trend": "increasing"
                    if len(long_queries) > len(short_queries)
                    else "decreasing",
                    "complexity_score": len(long_queries) / len(queries)
                    if queries
                    else 0,
                    "sample_queries": queries[-5:] if len(queries) >= 5 else queries,
                }
            ]

            return evolution

        except Exception as e:
            logger.error(f"Error analyzing query evolution: {e}")
            return []

    def _calculate_topic_relevance(self, topic: str, queries: List[str]) -> float:
        """محاسبه امتیاز ارتباط موضوع"""
        try:
            if not queries:
                return 0.0

            # محاسبه ساده بر اساس تکرار موضوع در پرسش‌ها
            topic_mentions = sum(
                1 for query in queries if topic.lower() in query.lower()
            )
            relevance = topic_mentions / len(queries)

            return min(relevance, 1.0)
        except Exception:
            return 0.0

    async def _find_unanswered_queries(self) -> List[str]:
        """یافتن پرسش‌های بدون پاسخ"""
        try:
            unanswered_queries = []

            # تحلیل پرسش‌های کاربران از user behavior analyzer
            for sessions in self.user_behavior.user_sessions.values():
                for session in sessions:
                    for query in session.queries:
                        # بررسی پرسش‌هایی که پاسخ کوتاه یا نامناسب دریافت کرده‌اند
                        if (
                            hasattr(query, "response_length")
                            and query.response_length < 50
                        ):
                            unanswered_queries.append(query.text)

                        # بررسی پرسش‌هایی که رضایت کاربر پایین بوده
                        if (
                            hasattr(query, "satisfaction_score")
                            and query.satisfaction_score < 0.3
                        ):
                            unanswered_queries.append(query.text)

                        # بررسی پرسش‌هایی که هیچ اسناد مرتبطی نداشته‌اند
                        if (
                            hasattr(query, "retrieved_documents")
                            and len(query.retrieved_documents) == 0
                        ):
                            unanswered_queries.append(query.text)

            # حذف تکرارها و محدود کردن تعداد
            unique_unanswered = list(set(unanswered_queries))[:10]

            logger.info(f"Found {len(unique_unanswered)} unanswered queries")
            return unique_unanswered

        except Exception as e:
            logger.error(f"Error finding unanswered queries: {e}")
            return []

    async def _find_underutilized_topics(self) -> List[str]:
        """یافتن موضوعات کم‌کاربرد"""
        try:
            # تحلیل موضوعات با فرکانس پایین
            all_topics = []
            for profile in self.user_behavior.user_profiles.values():
                all_topics.extend(profile.favorite_topics)

            topic_counts = Counter(all_topics)
            underutilized = [
                topic for topic, count in topic_counts.items() if count < 2
            ]  # کمتر از 2 بار استفاده

            return underutilized[:5]  # محدود کردن

        except Exception as e:
            logger.error(f"Error finding underutilized topics: {e}")
            return []

    async def _find_low_quality_responses(self) -> List[Dict[str, Any]]:
        """یافتن پاسخ‌های با کیفیت پایین"""
        try:
            low_quality_responses = []

            # تحلیل پاسخ‌ها از user behavior analyzer
            for user_id, sessions in self.user_behavior.user_sessions.items():
                for session in sessions:
                    for query in session.queries:
                        # بررسی پاسخ‌هایی که رضایت کاربر پایین بوده
                        if (
                            hasattr(query, "satisfaction_score")
                            and query.satisfaction_score < 0.4
                        ):
                            low_quality_responses.append(
                                {
                                    "id": f"resp_{user_id}_{session.session_id}_{query.query_id}",
                                    "reason": self._analyze_response_quality_issue(
                                        query
                                    ),
                                    "satisfaction_score": query.satisfaction_score,
                                    "user_id": user_id,
                                    "query_text": query.text,
                                    "response_length": getattr(
                                        query, "response_length", 0
                                    ),
                                    "timestamp": getattr(
                                        query, "timestamp", datetime.now()
                                    ),
                                }
                            )

                        # بررسی پاسخ‌هایی که خیلی کوتاه هستند
                        if (
                            hasattr(query, "response_length")
                            and query.response_length < 30
                        ):
                            low_quality_responses.append(
                                {
                                    "id": f"resp_{user_id}_{session.session_id}_{query.query_id}",
                                    "reason": "پاسخ خیلی کوتاه و ناکافی",
                                    "satisfaction_score": 0.2,
                                    "user_id": user_id,
                                    "query_text": query.text,
                                    "response_length": query.response_length,
                                    "timestamp": getattr(
                                        query, "timestamp", datetime.now()
                                    ),
                                }
                            )

            # مرتب‌سازی بر اساس امتیاز رضایت (پایین‌ترین اول)
            low_quality_responses.sort(key=lambda x: x["satisfaction_score"])

            logger.info(f"Found {len(low_quality_responses)} low quality responses")
            return low_quality_responses[:20]  # محدود کردن به 20 مورد

        except Exception as e:
            logger.error(f"Error finding low quality responses: {e}")
            return []

    def _analyze_response_quality_issue(self, query) -> str:
        """تحلیل مسائل کیفیت پاسخ"""
        try:
            issues = []

            # بررسی طول پاسخ
            response_length = getattr(query, "response_length", 0)
            if response_length < 50:
                issues.append("پاسخ کوتاه")
            elif response_length > 2000:
                issues.append("پاسخ خیلی طولانی")

            # بررسی امتیاز رضایت
            satisfaction_score = getattr(query, "satisfaction_score", 0.5)
            if satisfaction_score < 0.3:
                issues.append("رضایت بسیار پایین")
            elif satisfaction_score < 0.5:
                issues.append("رضایت پایین")

            # بررسی تعداد اسناد بازیابی شده
            retrieved_docs = getattr(query, "retrieved_documents", [])
            if len(retrieved_docs) == 0:
                issues.append("عدم وجود اسناد مرتبط")
            elif len(retrieved_docs) < 2:
                issues.append("اسناد مرتبط کم")

            # بررسی زمان پاسخ
            response_time = getattr(query, "response_time", 0)
            if response_time > 10:  # بیش از 10 ثانیه
                issues.append("زمان پاسخ طولانی")

            return "، ".join(issues) if issues else "کیفیت نامناسب"

        except Exception as e:
            logger.error(f"Error analyzing response quality issue: {e}")
            return "خطا در تحلیل کیفیت"

    async def _analyze_current_embedding_performance(self) -> Dict[str, Any]:
        """تحلیل عملکرد فعلی embedding"""
        try:
            # جمع‌آوری آمار عملکرد از user behavior analyzer
            total_queries = 0
            total_response_time = 0
            total_satisfaction = 0
            total_retrieved_docs = 0
            accuracy_scores = []

            for sessions in self.user_behavior.user_sessions.values():
                for session in sessions:
                    for query in session.queries:
                        total_queries += 1

                        # زمان پاسخ
                        response_time = getattr(query, "response_time", 0)
                        total_response_time += response_time

                        # رضایت کاربر
                        satisfaction = getattr(query, "satisfaction_score", 0.5)
                        total_satisfaction += satisfaction

                        # تعداد اسناد بازیابی شده
                        retrieved_docs = getattr(query, "retrieved_documents", [])
                        total_retrieved_docs += len(retrieved_docs)

                        # محاسبه دقت بر اساس رضایت و تعداد اسناد
                        accuracy = satisfaction * (
                            len(retrieved_docs) / 5.0
                        )  # نرمال‌سازی
                        accuracy_scores.append(min(accuracy, 1.0))

            if total_queries == 0:
                return {
                    "strategy": "no_data",
                    "accuracy": 0,
                    "speed": 0,
                    "memory_usage": 0,
                    "cost": 0,
                }

            # محاسبه میانگین‌ها
            avg_response_time = total_response_time / total_queries
            avg_satisfaction = total_satisfaction / total_queries
            avg_retrieved_docs = total_retrieved_docs / total_queries
            avg_accuracy = statistics.mean(accuracy_scores) if accuracy_scores else 0

            # نرمال‌سازی امتیازات (0-1)
            speed_score = max(0, 1 - (avg_response_time / 10.0))  # هرچه سریع‌تر بهتر
            memory_score = (
                0.7  # تخمینی - در پیاده‌سازی واقعی باید از سیستم مانیتورینگ دریافت شود
            )
            cost_score = (
                0.8  # تخمینی - در پیاده‌سازی واقعی باید از سیستم حسابداری دریافت شود
            )

            performance_data = {
                "strategy": "current_strategy",
                "accuracy": round(avg_accuracy, 3),
                "speed": round(speed_score, 3),
                "memory_usage": round(memory_score, 3),
                "cost": round(cost_score, 3),
                "avg_response_time": round(avg_response_time, 2),
                "avg_satisfaction": round(avg_satisfaction, 3),
                "avg_retrieved_docs": round(avg_retrieved_docs, 1),
                "total_queries_analyzed": total_queries,
            }

            logger.info(
                f"Embedding performance analysis completed for {total_queries} queries"
            )
            return performance_data

        except Exception as e:
            logger.error(f"Error analyzing embedding performance: {e}")
            return {
                "strategy": "error",
                "accuracy": 0,
                "speed": 0,
                "memory_usage": 0,
                "cost": 0,
            }

    async def _recommend_embedding_strategy(
        self, current_performance: Dict[str, Any]
    ) -> str:
        """پیشنهاد استراتژی embedding"""
        try:
            # تحلیل عملکرد فعلی
            accuracy = current_performance.get("accuracy", 0.5)
            speed = current_performance.get("speed", 0.5)
            memory_usage = current_performance.get("memory_usage", 0.5)
            cost = current_performance.get("cost", 0.5)
            avg_satisfaction = current_performance.get("avg_satisfaction", 0.5)
            avg_response_time = current_performance.get("avg_response_time", 5.0)

            # محاسبه امتیاز کلی
            overall_score = (accuracy + speed + avg_satisfaction) / 3

            # تعیین استراتژی بر اساس نقاط ضعف
            if accuracy < 0.6 and avg_satisfaction < 0.6:
                # دقت و رضایت پایین - نیاز به بهبود دقت
                return "improved_accuracy_strategy"

            elif speed < 0.4 or avg_response_time > 8.0:
                # سرعت پایین - نیاز به بهینه‌سازی سرعت
                return "optimized_speed_strategy"

            elif memory_usage > 0.8:
                # مصرف حافظه بالا - نیاز به بهینه‌سازی حافظه
                return "memory_optimized_strategy"

            elif cost > 0.8:
                # هزینه بالا - نیاز به بهینه‌سازی هزینه
                return "cost_optimized_strategy"

            elif overall_score < 0.7:
                # عملکرد کلی متوسط - استراتژی متعادل
                return "balanced_strategy"

            else:
                # عملکرد خوب - حفظ وضعیت فعلی با بهبودات جزئی
                return "incremental_improvement_strategy"

        except Exception as e:
            logger.error(f"Error recommending embedding strategy: {e}")
            return "default_strategy"

    async def _calculate_embedding_improvement(
        self, current: Dict[str, Any], recommended: str
    ) -> float:
        """محاسبه بهبود مورد انتظار"""
        try:
            # محاسبه بهبود بر اساس عملکرد فعلی و استراتژی پیشنهادی
            base_improvement = 0.05  # بهبود پایه 5%

            # تحلیل نقاط ضعف فعلی
            current_accuracy = current.get("accuracy", 0.5)
            current_speed = current.get("speed", 0.5)
            current_satisfaction = current.get("avg_satisfaction", 0.5)

            improvement_factors = []

            if recommended == "improved_accuracy_strategy":
                # بهبود دقت - اگر دقت فعلی پایین است
                if current_accuracy < 0.7:
                    accuracy_improvement = (0.7 - current_accuracy) * 0.3
                    improvement_factors.append(accuracy_improvement)

                # بهبود رضایت کاربر
                if current_satisfaction < 0.6:
                    satisfaction_improvement = (0.6 - current_satisfaction) * 0.2
                    improvement_factors.append(satisfaction_improvement)

            elif recommended == "optimized_speed_strategy":
                # بهبود سرعت - اگر سرعت فعلی پایین است
                if current_speed < 0.6:
                    speed_improvement = (0.6 - current_speed) * 0.4
                    improvement_factors.append(speed_improvement)

            elif recommended == "balanced_strategy":
                # استراتژی متعادل - بهبود کلی
                overall_score = (
                    current_accuracy + current_speed + current_satisfaction
                ) / 3
                if overall_score < 0.7:
                    balanced_improvement = (0.7 - overall_score) * 0.25
                    improvement_factors.append(balanced_improvement)

            elif recommended == "cost_optimized_strategy":
                # بهینه‌سازی هزینه - بهبود کارایی
                efficiency_improvement = 0.1
                improvement_factors.append(efficiency_improvement)

            # محاسبه بهبود کل
            total_improvement = base_improvement + sum(improvement_factors)

            # محدود کردن بهبود به حداکثر 50%
            final_improvement = min(total_improvement, 0.5)

            logger.info(
                f"Calculated improvement for {recommended}: {final_improvement:.3f}"
            )
            return round(final_improvement, 3)

        except Exception as e:
            logger.error(f"Error calculating embedding improvement: {e}")
            return 0.1  # بهبود پیش‌فرض 10%

    def _assess_implementation_effort(self, strategy: str) -> str:
        """ارزیابی تلاش پیاده‌سازی"""
        try:
            # ارزیابی تلاش بر اساس پیچیدگی استراتژی
            effort_assessment = {
                "improved_accuracy_strategy": "high",  # نیاز به تغییر مدل و تنظیمات
                "optimized_speed_strategy": "medium",  # نیاز به بهینه‌سازی کد
                "memory_optimized_strategy": "medium",  # نیاز به تغییر معماری
                "cost_optimized_strategy": "low",  # تغییرات ساده در تنظیمات
                "balanced_strategy": "low",  # تغییرات جزئی
                "incremental_improvement_strategy": "low",  # بهبودات تدریجی
                "default_strategy": "low",  # بدون تغییر
            }

            effort = effort_assessment.get(strategy, "medium")

            # اضافه کردن عوامل تأثیرگذار
            if strategy in ["improved_accuracy_strategy", "memory_optimized_strategy"]:
                # این استراتژی‌ها نیاز به تست گسترده دارند
                logger.info(f"Strategy {strategy} requires extensive testing")

            return effort

        except Exception as e:
            logger.error(f"Error assessing implementation effort: {e}")
            return "medium"

    def _assess_embedding_risk(self, strategy: str) -> str:
        """ارزیابی ریسک embedding"""
        try:
            # ارزیابی ریسک بر اساس تأثیر بر سیستم
            risk_assessment = {
                "improved_accuracy_strategy": "medium",  # ممکن است سرعت را کاهش دهد
                "optimized_speed_strategy": "low",  # ریسک کم، بهبود عملکرد
                "memory_optimized_strategy": "medium",  # ممکن است دقت را تحت تأثیر قرار دهد
                "cost_optimized_strategy": "low",  # ریسک کم، کاهش هزینه
                "balanced_strategy": "low",  # تغییرات متعادل
                "incremental_improvement_strategy": "low",  # ریسک بسیار کم
                "default_strategy": "low",  # بدون ریسک
            }

            risk = risk_assessment.get(strategy, "medium")

            # اضافه کردن عوامل ریسک
            if strategy in ["improved_accuracy_strategy", "memory_optimized_strategy"]:
                # این استراتژی‌ها ممکن است عملکرد سایر بخش‌ها را تحت تأثیر قرار دهند
                logger.info(f"Strategy {strategy} may impact other system components")

            return risk

        except Exception as e:
            logger.error(f"Error assessing embedding risk: {e}")
            return "medium"

    async def _analyze_user_historical_patterns(self, user_id: str) -> Dict[str, Any]:
        """تحلیل الگوهای تاریخی کاربر"""
        try:
            sessions = self.user_behavior.user_sessions.get(user_id, [])

            if not sessions:
                return {"error": "no_data"}

            # تحلیل الگوهای ساده
            total_queries = sum(len(session.queries) for session in sessions)
            avg_session_length = (
                statistics.mean(
                    [
                        (session.end_time - session.start_time).total_seconds() / 3600
                        for session in sessions
                        if session.end_time
                    ]
                )
                if sessions
                else 0
            )

            return {
                "total_sessions": len(sessions),
                "total_queries": total_queries,
                "avg_session_length_hours": avg_session_length,
                "last_activity": max(session.start_time for session in sessions),
            }

        except Exception as e:
            logger.error(f"Error analyzing user historical patterns: {e}")
            return {"error": str(e)}

    async def _predict_future_actions(self, patterns: Dict[str, Any]) -> List[str]:
        """پیش‌بینی اقدامات آینده"""
        try:
            if "error" in patterns:
                return ["unknown"]

            # پیش‌بینی ساده بر اساس الگوهای تاریخی
            predictions = []

            if patterns.get("total_queries", 0) > 10:
                predictions.append("continue_active_usage")

            if patterns.get("avg_session_length_hours", 0) > 1:
                predictions.append("long_session_usage")

            if patterns.get("total_sessions", 0) > 5:
                predictions.append("regular_user")

            return predictions if predictions else ["new_user"]

        except Exception as e:
            logger.error(f"Error predicting future actions: {e}")
            return ["unknown"]

    async def _calculate_prediction_confidence(
        self, profile: UserProfile, patterns: Dict[str, Any]
    ) -> Dict[str, float]:
        """محاسبه امتیازهای اطمینان پیش‌بینی"""
        try:
            confidence_scores = {}

            # محاسبه اطمینان بر اساس داده‌های موجود
            data_completeness = min(profile.total_sessions / 10, 1.0)

            confidence_scores["continue_active_usage"] = data_completeness * 0.8
            confidence_scores["long_session_usage"] = data_completeness * 0.7
            confidence_scores["regular_user"] = data_completeness * 0.9
            confidence_scores["new_user"] = (1 - data_completeness) * 0.6

            return confidence_scores

        except Exception as e:
            logger.error(f"Error calculating prediction confidence: {e}")
            return {"unknown": 0.5}

    async def _identify_behavioral_factors(
        self, profile: UserProfile, patterns: Dict[str, Any]
    ) -> List[str]:
        """شناسایی عوامل رفتاری"""
        try:
            factors = []

            if profile.total_sessions > 10:
                factors.append("experienced_user")

            if profile.satisfaction_avg > 0.7:
                factors.append("high_satisfaction")

            if len(profile.favorite_topics) > 3:
                factors.append("diverse_interests")

            if patterns.get("avg_session_length_hours", 0) > 0.5:
                factors.append("engaged_user")

            return factors if factors else ["new_user"]

        except Exception as e:
            logger.error(f"Error identifying behavioral factors: {e}")
            return ["unknown"]

    async def _check_metric_anomaly(
        self, metric_name: str, metric_value: Any
    ) -> Optional[Dict[str, Any]]:
        """بررسی ناهنجاری در متریک"""
        try:
            # جمع‌آوری داده‌های تاریخی برای مقایسه
            historical_values = []

            # جمع‌آوری مقادیر تاریخی از user behavior analyzer
            for sessions in self.user_behavior.user_sessions.values():
                for session in sessions:
                    for query in session.queries:
                        if hasattr(query, metric_name):
                            historical_values.append(getattr(query, metric_name))

            if not historical_values:
                return None

            # محاسبه آمار تاریخی
            mean_value = statistics.mean(historical_values)
            std_value = (
                statistics.stdev(historical_values) if len(historical_values) > 1 else 0
            )

            # تشخیص ناهنجاری بر اساس انحراف معیار
            if isinstance(metric_value, (int, float)):
                # ناهنجاری شدید (بیش از 3 انحراف معیار)
                if abs(metric_value - mean_value) > 3 * std_value:
                    severity = "critical"
                    anomaly_type = "statistical_outlier"
                    description = f"مقدار {metric_name} ({metric_value}) به طور قابل توجهی از میانگین ({mean_value:.2f}) انحراف دارد"

                # ناهنجاری متوسط (بیش از 2 انحراف معیار)
                elif abs(metric_value - mean_value) > 2 * std_value:
                    severity = "high"
                    anomaly_type = "statistical_outlier"
                    description = f"مقدار {metric_name} ({metric_value}) از میانگین ({mean_value:.2f}) انحراف دارد"

                # بررسی مقادیر خارج از محدوده منطقی
                elif metric_value < 0:
                    severity = "high"
                    anomaly_type = "negative_value"
                    description = f"مقدار {metric_name} منفی است ({metric_value})"

                elif metric_value > 1000:  # حد بالا برای اکثر متریک‌ها
                    severity = "medium"
                    anomaly_type = "unusually_high"
                    description = (
                        f"مقدار {metric_name} غیرعادی بالا است ({metric_value})"
                    )

                else:
                    return None  # ناهنجاری وجود ندارد

                # تعیین اقدامات پیشنهادی
                actions = self._get_anomaly_actions(anomaly_type, metric_name)

                anomaly_data = {
                    "type": anomaly_type,
                    "severity": severity,
                    "metric": metric_name,
                    "current_value": metric_value,
                    "historical_mean": round(mean_value, 3),
                    "historical_std": round(std_value, 3),
                    "deviation": round(abs(metric_value - mean_value), 3),
                    "description": description,
                    "actions": actions,
                    "timestamp": datetime.now(),
                }

                logger.warning(f"Anomaly detected in {metric_name}: {description}")
                return anomaly_data

            return None

        except Exception as e:
            logger.error(f"Error checking metric anomaly: {e}")
            return None

    def _get_anomaly_actions(self, anomaly_type: str, metric_name: str) -> List[str]:
        """تعیین اقدامات پیشنهادی برای ناهنجاری"""
        try:
            base_actions = [
                "بررسی منبع داده",
                "اعتبارسنجی محاسبات",
                "مشاهده لاگ‌های سیستم",
            ]

            specific_actions = []

            if anomaly_type == "statistical_outlier":
                specific_actions.extend(
                    [
                        "بررسی تغییرات اخیر در سیستم",
                        "تحلیل الگوهای زمانی",
                        "مقایسه با دوره‌های مشابه قبلی",
                    ]
                )

            elif anomaly_type == "negative_value":
                specific_actions.extend(
                    [
                        "بررسی منطق محاسبات",
                        "اعتبارسنجی ورودی‌ها",
                        "بررسی تنظیمات سیستم",
                    ]
                )

            elif anomaly_type == "unusually_high":
                specific_actions.extend(
                    [
                        "بررسی بار سیستم",
                        "تحلیل عملکرد منابع",
                        "بررسی تنظیمات محدودیت‌ها",
                    ]
                )

            # اقدامات خاص بر اساس نوع متریک
            if "response_time" in metric_name:
                specific_actions.extend(
                    [
                        "بررسی عملکرد شبکه",
                        "تحلیل بار سرور",
                        "بررسی کش سیستم",
                    ]
                )

            elif "satisfaction" in metric_name:
                specific_actions.extend(
                    [
                        "بررسی کیفیت پاسخ‌ها",
                        "تحلیل بازخورد کاربران",
                        "بررسی محتوای اسناد",
                    ]
                )

            elif "accuracy" in metric_name:
                specific_actions.extend(
                    [
                        "بررسی مدل embedding",
                        "تحلیل کیفیت اسناد",
                        "بررسی استراتژی بازیابی",
                    ]
                )

            return base_actions + specific_actions

        except Exception as e:
            logger.error(f"Error getting anomaly actions: {e}")
            return ["بررسی کلی سیستم"]

    def _get_severity_score(self, severity: str) -> int:
        """تبدیل شدت به امتیاز"""
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return severity_map.get(severity, 1)
