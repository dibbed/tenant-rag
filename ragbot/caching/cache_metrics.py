"""
متریک‌ها و نظارت بر کش

این ماژول شامل پیاده‌سازی متریک‌ها و نظارت بر عملکرد کش است.
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


@dataclass
class CacheMetrics:
    """متریک‌های کش.

    Attributes:
        hit_count: تعداد cache hit ها
        miss_count: تعداد cache miss ها
        eviction_count: تعداد حذف‌ها
        cache_size: اندازه فعلی کش
        hit_rate: نرخ موفقیت کش
        average_response_time: میانگین زمان پاسخ
        memory_usage: استفاده از حافظه
    """

    hit_count: int
    miss_count: int
    eviction_count: int
    cache_size: int
    hit_rate: float
    average_response_time: float
    memory_usage: float


class CacheMetricsCollector:
    """جمع‌آورنده متریک‌های کش.

    این کلاس متریک‌های کش را جمع‌آوری و مدیریت می‌کند.
    """

    def __init__(self, registry: CollectorRegistry = None):
        """مقداردهی اولیه جمع‌آورنده متریک‌ها.

        Args:
            registry: رجیستری Prometheus (اختیاری)
        """
        self.registry = registry or CollectorRegistry()

        # Prometheus metrics
        self.cache_hits = Counter(
            "rag_cache_hits_total", "Total cache hits", registry=self.registry
        )

        self.cache_misses = Counter(
            "rag_cache_misses_total", "Total cache misses", registry=self.registry
        )

        self.cache_evictions = Counter(
            "rag_cache_evictions_total", "Total cache evictions", registry=self.registry
        )

        self.cache_size = Gauge(
            "rag_cache_size", "Current cache size", registry=self.registry
        )

        self.cache_hit_rate = Gauge(
            "rag_cache_hit_rate", "Cache hit rate", registry=self.registry
        )

        self.cache_response_time = Histogram(
            "rag_cache_response_time_seconds",
            "Cache response time",
            registry=self.registry,
        )

        self.cache_memory_usage = Gauge(
            "rag_cache_memory_usage_bytes", "Cache memory usage", registry=self.registry
        )

    def record_cache_hit(self):
        """ثبت cache hit."""
        self.cache_hits.inc()

    def record_cache_miss(self):
        """ثبت cache miss."""
        self.cache_misses.inc()

    def record_cache_eviction(self):
        """ثبت cache eviction."""
        self.cache_evictions.inc()

    def update_cache_size(self, size: int):
        """به‌روزرسانی اندازه کش.

        Args:
            size: اندازه فعلی کش
        """
        self.cache_size.set(size)

    def update_hit_rate(self, hit_rate: float):
        """به‌روزرسانی نرخ hit.

        Args:
            hit_rate: نرخ موفقیت کش
        """
        self.cache_hit_rate.set(hit_rate)

    def record_response_time(self, duration: float):
        """ثبت زمان پاسخ.

        Args:
            duration: زمان پاسخ به ثانیه
        """
        self.cache_response_time.observe(duration)

    def update_memory_usage(self, usage: float):
        """به‌روزرسانی استفاده از حافظه.

        Args:
            usage: استفاده از حافظه به بایت
        """
        self.cache_memory_usage.set(usage)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه متریک‌ها.

        Returns:
            دیکشنری شامل خلاصه متریک‌ها
        """
        return {
            "cache_hits": self.cache_hits._value.get(),
            "cache_misses": self.cache_misses._value.get(),
            "cache_evictions": self.cache_evictions._value.get(),
            "cache_size": self.cache_size._value.get(),
            "hit_rate": self.cache_hit_rate._value.get(),
            "memory_usage": self.cache_memory_usage._value.get(),
        }


class CachePerformanceAnalyzer:
    """تحلیلگر عملکرد کش.

    این کلاس عملکرد کش را تحلیل و هشدارهای لازم را تولید می‌کند.
    """

    def __init__(self):
        """مقداردهی اولیه تحلیلگر عملکرد."""
        self.performance_history = []
        self.alert_thresholds = {
            "hit_rate_min": 0.6,
            "response_time_max": 0.1,
            "memory_usage_max": 0.8,
        }

    async def analyze_performance(self, cache_stats: Dict[str, Any]) -> Dict[str, Any]:
        """تحلیل عملکرد کش.

        Args:
            cache_stats: آمار کش

        Returns:
            دیکشنری شامل تحلیل عملکرد
        """
        current_time = time.time()

        # ثبت تاریخچه
        self.performance_history.append(
            {"timestamp": current_time, "stats": cache_stats}
        )

        # محدود کردن تاریخچه
        cutoff_time = current_time - 3600  # آخرین ساعت
        self.performance_history = [
            entry
            for entry in self.performance_history
            if entry["timestamp"] > cutoff_time
        ]

        # تحلیل روندها
        analysis = {
            "current_performance": cache_stats,
            "trends": await self._analyze_trends(),
            "alerts": await self._check_alerts(cache_stats),
            "recommendations": await self._generate_recommendations(cache_stats),
        }

        return analysis

    async def _analyze_trends(self) -> Dict[str, Any]:
        """تحلیل روندها.

        Returns:
            دیکشنری شامل تحلیل روندها
        """
        if len(self.performance_history) < 2:
            return {"insufficient_data": True}

        # محاسبه روندها
        hit_rates = [entry["stats"]["hit_rate"] for entry in self.performance_history]
        cache_sizes = [
            entry["stats"]["cache_size"] for entry in self.performance_history
        ]

        return {
            "hit_rate_trend": self._calculate_trend(hit_rates),
            "cache_size_trend": self._calculate_trend(cache_sizes),
            "performance_stability": self._calculate_stability(hit_rates),
        }

    async def _check_alerts(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """بررسی هشدارها.

        Args:
            stats: آمار کش

        Returns:
            لیست هشدارها
        """
        alerts = []

        # بررسی نرخ hit
        if stats["hit_rate"] < self.alert_thresholds["hit_rate_min"]:
            alerts.append(
                {
                    "type": "low_hit_rate",
                    "severity": "warning",
                    "message": f"Cache hit rate is low: {stats['hit_rate']:.2f}",
                    "recommendation": "Consider adjusting similarity threshold or cache size",
                }
            )

        # بررسی اندازه کش
        if stats["cache_size"] > stats["max_size"] * 0.9:
            alerts.append(
                {
                    "type": "cache_size_high",
                    "severity": "info",
                    "message": f"Cache size is high: {stats['cache_size']}/{stats['max_size']}",
                    "recommendation": "Consider increasing max_size or improving eviction strategy",
                }
            )

        return alerts

    async def _generate_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """تولید توصیه‌ها.

        Args:
            stats: آمار کش

        Returns:
            لیست توصیه‌ها
        """
        recommendations = []

        # توصیه بر اساس نرخ hit
        if stats["hit_rate"] < 0.7:
            recommendations.append(
                "Consider lowering similarity threshold for more cache hits"
            )

        if stats["hit_rate"] > 0.9:
            recommendations.append(
                "Consider raising similarity threshold for better answer quality"
            )

        # توصیه بر اساس اندازه کش
        if stats["cache_size"] < stats["max_size"] * 0.3:
            recommendations.append(
                "Cache utilization is low, consider reducing max_size"
            )

        if stats["cache_size"] > stats["max_size"] * 0.8:
            recommendations.append(
                "Cache utilization is high, consider increasing max_size"
            )

        return recommendations

    def _calculate_trend(self, values: List[float]) -> str:
        """محاسبه روند.

        Args:
            values: لیست مقادیر

        Returns:
            نوع روند (increasing, decreasing, stable)
        """
        if len(values) < 2:
            return "insufficient_data"

        # محاسبه شیب
        x = list(range(len(values)))
        y = values

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)

        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

    def _calculate_stability(self, values: List[float]) -> float:
        """محاسبه پایداری.

        Args:
            values: لیست مقادیر

        Returns:
            مقدار پایداری (0.0 تا 1.0)
        """
        if len(values) < 2:
            return 1.0

        mean_value = sum(values) / len(values)
        variance = sum((x - mean_value) ** 2 for x in values) / len(values)
        std_dev = variance**0.5

        # پایداری بر اساس انحراف معیار
        stability = 1.0 - min(std_dev / mean_value, 1.0) if mean_value > 0 else 0.0

        return stability


class CacheHealthChecker:
    """بررسی سلامت کش.

    این کلاس سلامت کش را بررسی و گزارش می‌دهد.
    """

    def __init__(self, metrics_collector: CacheMetricsCollector):
        """مقداردهی اولیه بررسی‌کننده سلامت.

        Args:
            metrics_collector: جمع‌آورنده متریک‌ها
        """
        self.metrics_collector = metrics_collector
        self.health_thresholds = {
            "min_hit_rate": 0.5,
            "max_response_time": 0.2,
            "max_memory_usage": 0.9,
            "max_eviction_rate": 0.1,
        }

    async def check_health(self) -> Dict[str, Any]:
        """بررسی سلامت کش.

        Returns:
            دیکشنری شامل وضعیت سلامت کش
        """
        metrics = self.metrics_collector.get_metrics_summary()

        health_status = "healthy"
        issues = []

        # بررسی نرخ hit
        if metrics["hit_rate"] < self.health_thresholds["min_hit_rate"]:
            health_status = "warning"
            issues.append(f"Low hit rate: {metrics['hit_rate']:.2f}")

        # بررسی اندازه کش
        if metrics["cache_size"] > 0:
            cache_utilization = metrics["cache_size"] / 1000  # فرض max_size = 1000
            if cache_utilization > self.health_thresholds["max_memory_usage"]:
                health_status = "warning"
                issues.append(f"High cache utilization: {cache_utilization:.2f}")

        # بررسی نرخ eviction
        total_requests = metrics["cache_hits"] + metrics["cache_misses"]
        if total_requests > 0:
            eviction_rate = metrics["cache_evictions"] / total_requests
            if eviction_rate > self.health_thresholds["max_eviction_rate"]:
                health_status = "warning"
                issues.append(f"High eviction rate: {eviction_rate:.2f}")

        return {
            "status": health_status,
            "issues": issues,
            "metrics": metrics,
            "timestamp": time.time(),
        }

    async def get_health_score(self) -> float:
        """دریافت امتیاز سلامت کش.

        Returns:
            امتیاز سلامت (0.0 تا 1.0)
        """
        health_check = await self.check_health()

        if health_check["status"] == "healthy":
            return 1.0
        elif health_check["status"] == "warning":
            return 0.7
        else:
            return 0.3
