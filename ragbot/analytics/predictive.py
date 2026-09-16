"""
تحلیل پیش‌بینانه و پیش‌بینی سیستم
"""

import asyncio
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from .user_behavior import UserBehaviorAnalyzer, UserProfile
from .usage_patterns import UsagePatternsAnalyzer


@dataclass
class LoadPrediction:
    """پیش‌بینی بار سیستم"""

    time_horizon_hours: int
    predicted_load: float
    confidence: float
    peak_times: List[int]
    low_times: List[int]
    factors: List[str]


@dataclass
class StoragePrediction:
    """پیش‌بینی نیازهای ذخیره‌سازی"""

    current_usage: float
    predicted_usage: float
    growth_rate: float
    time_to_capacity: int  # روزها
    recommended_action: str
    confidence: float


@dataclass
class Anomaly:
    """ناهنجاری"""

    anomaly_id: str
    anomaly_type: str
    severity: str
    detected_at: datetime
    affected_component: str
    description: str
    impact_score: float


@dataclass
class Recommendation:
    """توصیه"""

    recommendation_id: str
    category: str
    priority: str
    description: str
    expected_benefit: float
    implementation_effort: str
    risk_level: str


@dataclass
class SystemMetrics:
    """متریک‌های سیستم"""

    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    query_count: int
    response_time: float
    error_rate: float
    active_users: int


class PredictiveAnalyzer:
    """تحلیلگر پیش‌بینانه"""

    def __init__(
        self,
        user_behavior: UserBehaviorAnalyzer = None,
        usage_patterns: UsagePatternsAnalyzer = None,
    ):
        """Initialize predictive analyzer"""
        self.user_behavior = user_behavior or UserBehaviorAnalyzer()
        self.usage_patterns = usage_patterns or UsagePatternsAnalyzer()

        # Historical data storage
        self.metrics_history = []
        self.load_history = []
        self.storage_history = []

        # Prediction models cache
        self._load_model = None
        self._storage_model = None
        self._anomaly_model = None

    async def predict_system_load(self, time_horizon: int = 24) -> LoadPrediction:
        """پیش‌بینی بار سیستم"""
        try:
            logger.info(f"Predicting system load for {time_horizon} hours...")

            # جمع‌آوری داده‌های تاریخی بار
            historical_load = await self._collect_historical_load_data()

            if not historical_load:
                # پیش‌بینی پیش‌فرض
                return LoadPrediction(
                    time_horizon_hours=time_horizon,
                    predicted_load=0.5,
                    confidence=0.3,
                    peak_times=[9, 10, 11, 14, 15, 16],
                    low_times=[0, 1, 2, 3, 4, 5],
                    factors=["insufficient_data"],
                )

            # تحلیل الگوهای زمانی
            hourly_patterns = await self._analyze_hourly_load_patterns(historical_load)

            # پیش‌بینی بار آینده
            predicted_load = await self._calculate_future_load(
                hourly_patterns, time_horizon
            )

            # شناسایی زمان‌های پیک و کم
            peak_times, low_times = await self._identify_peak_low_times(hourly_patterns)

            # محاسبه اطمینان
            confidence = await self._calculate_load_prediction_confidence(
                historical_load
            )

            # شناسایی عوامل تاثیرگذار
            factors = await self._identify_load_factors(hourly_patterns)

            prediction = LoadPrediction(
                time_horizon_hours=time_horizon,
                predicted_load=predicted_load,
                confidence=confidence,
                peak_times=peak_times,
                low_times=low_times,
                factors=factors,
            )

            logger.success(f"System load prediction completed: {predicted_load:.2f}")
            return prediction

        except Exception as e:
            logger.error(f"Error predicting system load: {e}")
            raise

    async def predict_storage_needs(
        self, growth_rate: float = 0.1
    ) -> StoragePrediction:
        """پیش‌بینی نیازهای ذخیره‌سازی"""
        try:
            logger.info("Predicting storage needs...")

            # جمع‌آوری داده‌های ذخیره‌سازی فعلی
            current_usage = await self._get_current_storage_usage()

            # تحلیل روند رشد تاریخی
            historical_growth = await self._analyze_storage_growth()

            # محاسبه نرخ رشد واقعی
            actual_growth_rate = historical_growth.get("growth_rate", growth_rate)

            # پیش‌بینی استفاده آینده
            predicted_usage = await self._calculate_future_storage_usage(
                current_usage, actual_growth_rate
            )

            # محاسبه زمان تا ظرفیت کامل
            time_to_capacity = await self._calculate_time_to_capacity(
                current_usage, predicted_usage, actual_growth_rate
            )

            # تولید توصیه
            recommended_action = await self._generate_storage_recommendation(
                current_usage, predicted_usage, time_to_capacity
            )

            # محاسبه اطمینان
            confidence = await self._calculate_storage_prediction_confidence(
                historical_growth
            )

            prediction = StoragePrediction(
                current_usage=current_usage,
                predicted_usage=predicted_usage,
                growth_rate=actual_growth_rate,
                time_to_capacity=time_to_capacity,
                recommended_action=recommended_action,
                confidence=confidence,
            )

            logger.success(f"Storage prediction completed: {predicted_usage:.2f}GB")
            return prediction

        except Exception as e:
            logger.error(f"Error predicting storage needs: {e}")
            raise

    async def detect_anomalies(self, metrics: List[SystemMetrics]) -> List[Anomaly]:
        """تشخیص ناهنجاری‌ها"""
        try:
            logger.info("Detecting anomalies in system metrics...")

            if not metrics:
                return []

            anomalies = []

            # تحلیل هر متریک
            for metric in metrics:
                # بررسی CPU
                cpu_anomaly = await self._check_cpu_anomaly(metric)
                if cpu_anomaly:
                    anomalies.append(cpu_anomaly)

                # بررسی Memory
                memory_anomaly = await self._check_memory_anomaly(metric)
                if memory_anomaly:
                    anomalies.append(memory_anomaly)

                # بررسی Response Time
                response_anomaly = await self._check_response_time_anomaly(metric)
                if response_anomaly:
                    anomalies.append(response_anomaly)

                # بررسی Error Rate
                error_anomaly = await self._check_error_rate_anomaly(metric)
                if error_anomaly:
                    anomalies.append(error_anomaly)

            # مرتب‌سازی بر اساس شدت
            anomalies.sort(
                key=lambda a: self._get_severity_score(a.severity), reverse=True
            )

            logger.success(f"Detected {len(anomalies)} anomalies")
            return anomalies

        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            raise

    async def recommend_optimizations(self) -> List[Recommendation]:
        """توصیه بهینه‌سازی‌ها"""
        try:
            logger.info("Generating optimization recommendations...")

            recommendations = []

            # تحلیل عملکرد سیستم
            system_performance = await self._analyze_system_performance()

            # توصیه‌های CPU
            cpu_recs = await self._generate_cpu_recommendations(system_performance)
            recommendations.extend(cpu_recs)

            # توصیه‌های Memory
            memory_recs = await self._generate_memory_recommendations(
                system_performance
            )
            recommendations.extend(memory_recs)

            # توصیه‌های Storage
            storage_recs = await self._generate_storage_recommendations(
                system_performance
            )
            recommendations.extend(storage_recs)

            # توصیه‌های Query Optimization
            query_recs = await self._generate_query_recommendations(system_performance)
            recommendations.extend(query_recs)

            # مرتب‌سازی بر اساس اولویت
            recommendations.sort(
                key=lambda r: self._get_priority_score(r.priority), reverse=True
            )

            logger.success(
                f"Generated {len(recommendations)} optimization recommendations"
            )
            return recommendations

        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}")
            raise

    # Helper methods
    async def _collect_historical_load_data(self) -> List[Dict[str, Any]]:
        """جمع‌آوری داده‌های تاریخی بار"""
        try:
            # شبیه‌سازی داده‌های تاریخی
            historical_data = []

            # تولید داده‌های نمونه برای 7 روز گذشته
            base_time = datetime.now() - timedelta(days=7)

            for day in range(7):
                for hour in range(24):
                    # شبیه‌سازی الگوی بار روزانه
                    if 9 <= hour <= 17:  # ساعات کاری
                        load_factor = 0.8
                    elif 18 <= hour <= 22:  # عصر
                        load_factor = 0.6
                    else:  # شب و صبح زود
                        load_factor = 0.2

                    # اضافه کردن نویز تصادفی
                    noise = np.random.normal(0, 0.1)
                    load = max(0, min(1, load_factor + noise))

                    historical_data.append(
                        {
                            "timestamp": base_time + timedelta(days=day, hours=hour),
                            "load": load,
                            "active_users": int(load * 100),
                            "queries_per_minute": int(load * 50),
                        }
                    )

            return historical_data

        except Exception as e:
            logger.error(f"Error collecting historical load data: {e}")
            return []

    async def _analyze_hourly_load_patterns(
        self, historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """تحلیل الگوهای ساعتی بار"""
        try:
            if not historical_data:
                return {"error": "no_data"}

            # گروه‌بندی بر اساس ساعت
            hourly_loads = defaultdict(list)

            for data_point in historical_data:
                hour = data_point["timestamp"].hour
                hourly_loads[hour].append(data_point["load"])

            # محاسبه میانگین برای هر ساعت
            hourly_averages = {}
            for hour, loads in hourly_loads.items():
                hourly_averages[hour] = statistics.mean(loads)

            # شناسایی الگوها
            peak_hour = max(hourly_averages.items(), key=lambda x: x[1])[0]
            low_hour = min(hourly_averages.items(), key=lambda x: x[1])[0]

            return {
                "hourly_averages": hourly_averages,
                "peak_hour": peak_hour,
                "low_hour": low_hour,
                "peak_load": hourly_averages[peak_hour],
                "low_load": hourly_averages[low_hour],
                "load_variance": statistics.variance(list(hourly_averages.values())),
            }

        except Exception as e:
            logger.error(f"Error analyzing hourly load patterns: {e}")
            return {"error": str(e)}

    async def _calculate_future_load(
        self, patterns: Dict[str, Any], time_horizon: int
    ) -> float:
        """محاسبه بار آینده"""
        try:
            if "error" in patterns:
                return 0.5  # مقدار پیش‌فرض

            # استفاده از الگوهای تاریخی برای پیش‌بینی
            hourly_averages = patterns.get("hourly_averages", {})

            if not hourly_averages:
                return 0.5

            # محاسبه میانگین کلی
            overall_average = statistics.mean(hourly_averages.values())

            # اضافه کردن فاکتور روند
            trend_factor = 1.0
            if patterns.get("load_variance", 0) > 0.1:
                trend_factor = 1.05  # روند صعودی

            predicted_load = overall_average * trend_factor

            return min(predicted_load, 1.0)

        except Exception as e:
            logger.error(f"Error calculating future load: {e}")
            return 0.5

    async def _identify_peak_low_times(
        self, patterns: Dict[str, Any]
    ) -> Tuple[List[int], List[int]]:
        """شناسایی زمان‌های پیک و کم"""
        try:
            if "error" in patterns:
                return [9, 10, 11], [0, 1, 2]

            hourly_averages = patterns.get("hourly_averages", {})

            if not hourly_averages:
                return [9, 10, 11], [0, 1, 2]

            # مرتب‌سازی ساعات بر اساس بار
            sorted_hours = sorted(
                hourly_averages.items(), key=lambda x: x[1], reverse=True
            )

            # انتخاب 3 ساعت پیک و 3 ساعت کم
            peak_times = [hour for hour, _ in sorted_hours[:3]]
            low_times = [hour for hour, _ in sorted_hours[-3:]]

            return peak_times, low_times

        except Exception as e:
            logger.error(f"Error identifying peak/low times: {e}")
            return [9, 10, 11], [0, 1, 2]

    async def _calculate_load_prediction_confidence(
        self, historical_data: List[Dict[str, Any]]
    ) -> float:
        """محاسبه اطمینان پیش‌بینی بار"""
        try:
            if not historical_data:
                return 0.3

            # اطمینان بر اساس مقدار داده‌های تاریخی
            data_points = len(historical_data)
            confidence = min(data_points / 100, 1.0)  # حداکثر 100 نقطه داده

            return max(confidence, 0.3)  # حداقل 30% اطمینان

        except Exception as e:
            logger.error(f"Error calculating load prediction confidence: {e}")
            return 0.3

    async def _identify_load_factors(self, patterns: Dict[str, Any]) -> List[str]:
        """شناسایی عوامل تاثیرگذار بر بار"""
        try:
            factors = []

            if "error" in patterns:
                return ["insufficient_data"]

            # تحلیل الگوهای زمانی
            hourly_averages = patterns.get("hourly_averages", {})

            if hourly_averages:
                # بررسی الگوی کاری
                work_hours_load = statistics.mean(
                    [hourly_averages.get(hour, 0) for hour in range(9, 18)]
                )
                non_work_hours_load = statistics.mean(
                    [
                        hourly_averages.get(hour, 0)
                        for hour in list(range(0, 9)) + list(range(18, 24))
                    ]
                )

                if work_hours_load > non_work_hours_load * 1.5:
                    factors.append("business_hours_pattern")

                # بررسی واریانس
                if patterns.get("load_variance", 0) > 0.1:
                    factors.append("high_variance")
                else:
                    factors.append("stable_pattern")

            return factors if factors else ["unknown_pattern"]

        except Exception as e:
            logger.error(f"Error identifying load factors: {e}")
            return ["error"]

    async def _get_current_storage_usage(self) -> float:
        """دریافت استفاده فعلی ذخیره‌سازی"""
        try:
            # شبیه‌سازی استفاده فعلی (GB)
            return 45.7  # مقدار نمونه

        except Exception as e:
            logger.error(f"Error getting current storage usage: {e}")
            return 0.0

    async def _analyze_storage_growth(self) -> Dict[str, Any]:
        """تحلیل روند رشد ذخیره‌سازی"""
        try:
            # شبیه‌سازی تحلیل رشد
            return {
                "growth_rate": 0.15,  # 15% رشد ماهانه
                "data_points": 30,
                "trend": "increasing",
                "seasonality": "low",
            }

        except Exception as e:
            logger.error(f"Error analyzing storage growth: {e}")
            return {"growth_rate": 0.1}

    async def _calculate_future_storage_usage(
        self, current: float, growth_rate: float
    ) -> float:
        """محاسبه استفاده آینده ذخیره‌سازی"""
        try:
            # پیش‌بینی برای 30 روز آینده
            days = 30
            future_usage = current * (1 + growth_rate) ** (days / 30)

            return future_usage

        except Exception as e:
            logger.error(f"Error calculating future storage usage: {e}")
            return current * 1.1

    async def _calculate_time_to_capacity(
        self, current: float, predicted: float, growth_rate: float
    ) -> int:
        """محاسبه زمان تا ظرفیت کامل"""
        try:
            # فرض ظرفیت کل 100GB
            total_capacity = 100.0

            if growth_rate <= 0:
                return 365  # یک سال

            # محاسبه زمان تا 90% ظرفیت
            target_usage = total_capacity * 0.9

            if predicted >= target_usage:
                return 0  # فوری

            # محاسبه روزها
            days = 0
            usage = current

            while usage < target_usage and days < 365:
                usage *= 1 + growth_rate / 30  # رشد روزانه
                days += 1

            return days

        except Exception as e:
            logger.error(f"Error calculating time to capacity: {e}")
            return 90

    async def _generate_storage_recommendation(
        self, current: float, predicted: float, time_to_capacity: int
    ) -> str:
        """تولید توصیه ذخیره‌سازی"""
        try:
            if time_to_capacity <= 7:
                return "urgent_expansion_required"
            elif time_to_capacity <= 30:
                return "plan_expansion_soon"
            elif time_to_capacity <= 90:
                return "monitor_and_plan"
            else:
                return "current_capacity_sufficient"

        except Exception as e:
            logger.error(f"Error generating storage recommendation: {e}")
            return "monitor_and_plan"

    async def _calculate_storage_prediction_confidence(
        self, historical_growth: Dict[str, Any]
    ) -> float:
        """محاسبه اطمینان پیش‌بینی ذخیره‌سازی"""
        try:
            data_points = historical_growth.get("data_points", 0)
            confidence = min(data_points / 30, 1.0)  # حداکثر 30 نقطه داده

            return max(confidence, 0.4)  # حداقل 40% اطمینان

        except Exception as e:
            logger.error(f"Error calculating storage prediction confidence: {e}")
            return 0.4

    async def _check_cpu_anomaly(self, metric: SystemMetrics) -> Optional[Anomaly]:
        """بررسی ناهنجاری CPU"""
        try:
            if metric.cpu_usage > 90:
                return Anomaly(
                    anomaly_id=f"cpu_high_{metric.timestamp.isoformat()}",
                    anomaly_type="high_cpu_usage",
                    severity="high",
                    detected_at=metric.timestamp,
                    affected_component="cpu",
                    description=f"CPU usage is critically high: {metric.cpu_usage:.1f}%",
                    impact_score=0.9,
                )
            elif metric.cpu_usage > 80:
                return Anomaly(
                    anomaly_id=f"cpu_warning_{metric.timestamp.isoformat()}",
                    anomaly_type="high_cpu_usage",
                    severity="medium",
                    detected_at=metric.timestamp,
                    affected_component="cpu",
                    description=f"CPU usage is high: {metric.cpu_usage:.1f}%",
                    impact_score=0.6,
                )

            return None

        except Exception as e:
            logger.error(f"Error checking CPU anomaly: {e}")
            return None

    async def _check_memory_anomaly(self, metric: SystemMetrics) -> Optional[Anomaly]:
        """بررسی ناهنجاری Memory"""
        try:
            if metric.memory_usage > 95:
                return Anomaly(
                    anomaly_id=f"memory_critical_{metric.timestamp.isoformat()}",
                    anomaly_type="high_memory_usage",
                    severity="critical",
                    detected_at=metric.timestamp,
                    affected_component="memory",
                    description=f"Memory usage is critically high: {metric.memory_usage:.1f}%",
                    impact_score=1.0,
                )
            elif metric.memory_usage > 85:
                return Anomaly(
                    anomaly_id=f"memory_high_{metric.timestamp.isoformat()}",
                    anomaly_type="high_memory_usage",
                    severity="high",
                    detected_at=metric.timestamp,
                    affected_component="memory",
                    description=f"Memory usage is high: {metric.memory_usage:.1f}%",
                    impact_score=0.8,
                )

            return None

        except Exception as e:
            logger.error(f"Error checking memory anomaly: {e}")
            return None

    async def _check_response_time_anomaly(
        self, metric: SystemMetrics
    ) -> Optional[Anomaly]:
        """بررسی ناهنجاری Response Time"""
        try:
            if metric.response_time > 5.0:  # بیش از 5 ثانیه
                return Anomaly(
                    anomaly_id=f"response_slow_{metric.timestamp.isoformat()}",
                    anomaly_type="slow_response_time",
                    severity="high",
                    detected_at=metric.timestamp,
                    affected_component="response_time",
                    description=f"Response time is very slow: {metric.response_time:.2f}s",
                    impact_score=0.8,
                )
            elif metric.response_time > 2.0:  # بیش از 2 ثانیه
                return Anomaly(
                    anomaly_id=f"response_delayed_{metric.timestamp.isoformat()}",
                    anomaly_type="slow_response_time",
                    severity="medium",
                    detected_at=metric.timestamp,
                    affected_component="response_time",
                    description=f"Response time is slow: {metric.response_time:.2f}s",
                    impact_score=0.5,
                )

            return None

        except Exception as e:
            logger.error(f"Error checking response time anomaly: {e}")
            return None

    async def _check_error_rate_anomaly(
        self, metric: SystemMetrics
    ) -> Optional[Anomaly]:
        """بررسی ناهنجاری Error Rate"""
        try:
            if metric.error_rate > 0.1:  # بیش از 10%
                return Anomaly(
                    anomaly_id=f"error_high_{metric.timestamp.isoformat()}",
                    anomaly_type="high_error_rate",
                    severity="critical",
                    detected_at=metric.timestamp,
                    affected_component="error_rate",
                    description=f"Error rate is critically high: {metric.error_rate:.1%}",
                    impact_score=1.0,
                )
            elif metric.error_rate > 0.05:  # بیش از 5%
                return Anomaly(
                    anomaly_id=f"error_elevated_{metric.timestamp.isoformat()}",
                    anomaly_type="high_error_rate",
                    severity="high",
                    detected_at=metric.timestamp,
                    affected_component="error_rate",
                    description=f"Error rate is elevated: {metric.error_rate:.1%}",
                    impact_score=0.7,
                )

            return None

        except Exception as e:
            logger.error(f"Error checking error rate anomaly: {e}")
            return None

    async def _analyze_system_performance(self) -> Dict[str, Any]:
        """تحلیل عملکرد سیستم"""
        try:
            # شبیه‌سازی تحلیل عملکرد
            return {
                "cpu_avg": 65.0,
                "memory_avg": 70.0,
                "disk_avg": 45.0,
                "response_time_avg": 1.2,
                "error_rate_avg": 0.02,
                "throughput": 150.0,
                "bottlenecks": ["memory", "disk_io"],
            }

        except Exception as e:
            logger.error(f"Error analyzing system performance: {e}")
            return {}

    async def _generate_cpu_recommendations(
        self, performance: Dict[str, Any]
    ) -> List[Recommendation]:
        """تولید توصیه‌های CPU"""
        try:
            recommendations = []

            cpu_avg = performance.get("cpu_avg", 0)

            if cpu_avg > 80:
                recommendations.append(
                    Recommendation(
                        recommendation_id="cpu_scale_up",
                        category="performance",
                        priority="high",
                        description="CPU usage is consistently high. Consider scaling up or optimizing queries.",
                        expected_benefit=0.8,
                        implementation_effort="medium",
                        risk_level="low",
                    )
                )
            elif cpu_avg > 60:
                recommendations.append(
                    Recommendation(
                        recommendation_id="cpu_monitor",
                        category="monitoring",
                        priority="medium",
                        description="CPU usage is moderate. Monitor for trends and optimize if needed.",
                        expected_benefit=0.3,
                        implementation_effort="low",
                        risk_level="low",
                    )
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating CPU recommendations: {e}")
            return []

    async def _generate_memory_recommendations(
        self, performance: Dict[str, Any]
    ) -> List[Recommendation]:
        """تولید توصیه‌های Memory"""
        try:
            recommendations = []

            memory_avg = performance.get("memory_avg", 0)

            if memory_avg > 85:
                recommendations.append(
                    Recommendation(
                        recommendation_id="memory_scale_up",
                        category="performance",
                        priority="critical",
                        description="Memory usage is critically high. Immediate scaling required.",
                        expected_benefit=0.9,
                        implementation_effort="high",
                        risk_level="high",
                    )
                )
            elif memory_avg > 70:
                recommendations.append(
                    Recommendation(
                        recommendation_id="memory_optimize",
                        category="optimization",
                        priority="high",
                        description="Memory usage is high. Optimize caching and data structures.",
                        expected_benefit=0.6,
                        implementation_effort="medium",
                        risk_level="medium",
                    )
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating memory recommendations: {e}")
            return []

    async def _generate_storage_recommendations(
        self, performance: Dict[str, Any]
    ) -> List[Recommendation]:
        """تولید توصیه‌های Storage"""
        try:
            recommendations = []

            disk_avg = performance.get("disk_avg", 0)

            if disk_avg > 90:
                recommendations.append(
                    Recommendation(
                        recommendation_id="storage_expand",
                        category="capacity",
                        priority="critical",
                        description="Disk usage is critically high. Immediate expansion required.",
                        expected_benefit=1.0,
                        implementation_effort="high",
                        risk_level="high",
                    )
                )
            elif disk_avg > 75:
                recommendations.append(
                    Recommendation(
                        recommendation_id="storage_cleanup",
                        category="maintenance",
                        priority="medium",
                        description="Disk usage is high. Consider cleanup and archiving.",
                        expected_benefit=0.4,
                        implementation_effort="low",
                        risk_level="low",
                    )
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating storage recommendations: {e}")
            return []

    async def _generate_query_recommendations(
        self, performance: Dict[str, Any]
    ) -> List[Recommendation]:
        """تولید توصیه‌های Query Optimization"""
        try:
            recommendations = []

            response_time_avg = performance.get("response_time_avg", 0)

            if response_time_avg > 2.0:
                recommendations.append(
                    Recommendation(
                        recommendation_id="query_optimize",
                        category="performance",
                        priority="high",
                        description="Response time is slow. Optimize queries and add indexes.",
                        expected_benefit=0.7,
                        implementation_effort="medium",
                        risk_level="medium",
                    )
                )
            elif response_time_avg > 1.0:
                recommendations.append(
                    Recommendation(
                        recommendation_id="query_monitor",
                        category="monitoring",
                        priority="low",
                        description="Response time is acceptable but could be improved.",
                        expected_benefit=0.2,
                        implementation_effort="low",
                        risk_level="low",
                    )
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating query recommendations: {e}")
            return []

    def _get_severity_score(self, severity: str) -> int:
        """تبدیل شدت به امتیاز"""
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return severity_map.get(severity, 1)

    def _get_priority_score(self, priority: str) -> int:
        """تبدیل اولویت به امتیاز"""
        priority_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return priority_map.get(priority, 1)
