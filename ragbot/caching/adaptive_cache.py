"""
کش تطبیقی با حذف هوشمند

این ماژول شامل پیاده‌سازی کش تطبیقی است که بر اساس الگوهای دسترسی
و کیفیت پاسخ‌ها، حذف هوشمندانه ورودی‌ها را انجام می‌دهد.
"""

import time
from collections import defaultdict
from typing import Any, Dict, List

from .semantic_cache import SemanticCache


class AdaptiveCache(SemanticCache):
    """کش با حذف تطبیقی.

    این کلاس کش تطبیقی را پیاده‌سازی می‌کند که بر اساس الگوهای دسترسی
    و کیفیت پاسخ‌ها، حذف هوشمندانه ورودی‌ها را انجام می‌دهد.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        embedder=None,
        eviction_strategy: str = "lru",
    ):
        """مقداردهی اولیه کش تطبیقی.

        Args:
            similarity_threshold: آستانه شباهت برای تطبیق
            max_size: حداکثر اندازه کش
            ttl_seconds: زمان انقضای ورودی‌ها
            embedder: مدل جاسازی
            eviction_strategy: استراتژی حذف (lru, lfu, adaptive)
        """
        super().__init__(similarity_threshold, max_size, ttl_seconds, embedder)
        self.eviction_strategy = eviction_strategy

        # Adaptive parameters
        self.access_patterns = defaultdict(int)
        self.temporal_patterns = defaultdict(list)
        self.quality_scores = {}

        # Performance tracking
        self.eviction_history = []
        self.performance_metrics = {}

    async def cache_answer(
        self,
        query: str,
        answer: str,
        context: List[str],
        metadata: Dict[str, Any],
        confidence_score: float = 1.0,
    ) -> None:
        """ذخیره پاسخ با تحلیل تطبیقی.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            context: زمینه استفاده شده
            metadata: متادیتای اضافی
            confidence_score: امتیاز اطمینان پاسخ
        """
        # تحلیل الگوی دسترسی
        await self._analyze_access_pattern(query)

        # ذخیره پاسخ
        await super().cache_answer(query, answer, context, metadata, confidence_score)

        # به‌روزرسانی کیفیت
        self.quality_scores[query] = confidence_score

    async def _evict_least_used(self) -> None:
        """حذف تطبیقی بر اساس استراتژی انتخاب شده."""
        if self.eviction_strategy == "lru":
            await self._evict_lru()
        elif self.eviction_strategy == "lfu":
            await self._evict_lfu()
        elif self.eviction_strategy == "adaptive":
            await self._evict_adaptive()
        else:
            await super()._evict_least_used()

    async def _evict_lru(self) -> None:
        """حذف کم‌استفاده‌ترین اخیر (Least Recently Used)."""
        if not self.cache:
            return

        # یافتن کم‌استفاده‌ترین اخیر
        least_recent_key = min(
            self.cache.keys(), key=lambda k: self.cache[k].last_access
        )

        del self.cache[least_recent_key]
        self.eviction_count += 1

    async def _evict_lfu(self) -> None:
        """حذف کم‌فراوان‌ترین (Least Frequently Used)."""
        if not self.cache:
            return

        # یافتن کم‌فراوان‌ترین
        least_frequent_key = min(
            self.cache.keys(), key=lambda k: self.cache[k].access_count
        )

        del self.cache[least_frequent_key]
        self.eviction_count += 1

    async def _evict_adaptive(self) -> None:
        """حذف تطبیقی بر اساس الگوها و کیفیت."""
        if not self.cache:
            return

        # محاسبه امتیاز تطبیقی
        adaptive_scores = {}
        current_time = time.time()

        for key, entry in self.cache.items():
            # امتیاز دسترسی
            access_score = entry.access_count

            # امتیاز زمان
            time_score = 1.0 / (current_time - entry.last_access + 1)

            # امتیاز کیفیت
            quality_score = self.quality_scores.get(entry.query, 0.5)

            # امتیاز الگو
            pattern_score = self.access_patterns.get(entry.query, 0)

            # ترکیب امتیازات
            adaptive_score = (
                0.4 * access_score
                + 0.3 * time_score
                + 0.2 * quality_score
                + 0.1 * pattern_score
            )

            adaptive_scores[key] = adaptive_score

        # حذف کم‌امتیازترین
        least_adaptive_key = min(
            adaptive_scores.keys(), key=lambda k: adaptive_scores[k]
        )
        del self.cache[least_adaptive_key]
        self.eviction_count += 1

        # ثبت تاریخچه حذف
        self.eviction_history.append(
            {
                "timestamp": current_time,
                "key": least_adaptive_key,
                "strategy": "adaptive",
                "score": adaptive_scores[least_adaptive_key],
            }
        )

    async def _analyze_access_pattern(self, query: str) -> None:
        """تحلیل الگوی دسترسی.

        Args:
            query: پرسش کاربر
        """
        current_time = time.time()

        # ثبت دسترسی
        self.access_patterns[query] += 1
        self.temporal_patterns[query].append(current_time)

        # محدود کردن تاریخچه زمانی
        cutoff_time = current_time - 3600  # آخرین ساعت
        self.temporal_patterns[query] = [
            t for t in self.temporal_patterns[query] if t > cutoff_time
        ]

    async def optimize_cache_size(self) -> None:
        """بهینه‌سازی اندازه کش بر اساس عملکرد."""
        # تحلیل عملکرد
        hit_rate = (
            self.hit_count / (self.hit_count + self.miss_count)
            if (self.hit_count + self.miss_count) > 0
            else 0
        )

        # تنظیم اندازه بر اساس نرخ hit
        if hit_rate > 0.8 and len(self.cache) < self.max_size * 0.9:
            # افزایش اندازه کش
            self.max_size = min(self.max_size * 1.2, 2000)
        elif hit_rate < 0.5 and len(self.cache) > self.max_size * 0.7:
            # کاهش اندازه کش
            self.max_size = max(self.max_size * 0.8, 500)

    async def get_adaptive_stats(self) -> Dict[str, Any]:
        """دریافت آمار تطبیقی کش.

        Returns:
            دیکشنری شامل آمار تطبیقی کش
        """
        base_stats = await self.get_cache_stats()

        # آمار تطبیقی
        adaptive_stats = {
            "eviction_strategy": self.eviction_strategy,
            "eviction_history_count": len(self.eviction_history),
            "access_patterns_count": len(self.access_patterns),
            "quality_scores_count": len(self.quality_scores),
            "average_quality_score": sum(self.quality_scores.values())
            / len(self.quality_scores)
            if self.quality_scores
            else 0,
        }

        return {**base_stats, **adaptive_stats}

    async def get_access_patterns(self) -> Dict[str, Any]:
        """دریافت الگوهای دسترسی.

        Returns:
            دیکشنری شامل الگوهای دسترسی
        """
        current_time = time.time()
        patterns = {}

        for query, accesses in self.temporal_patterns.items():
            if accesses:
                # محاسبه فاصله زمانی بین دسترسی‌ها
                intervals = []
                for i in range(1, len(accesses)):
                    intervals.append(accesses[i] - accesses[i - 1])

                patterns[query] = {
                    "total_accesses": len(accesses),
                    "access_frequency": self.access_patterns[query],
                    "average_interval": sum(intervals) / len(intervals)
                    if intervals
                    else 0,
                    "last_access": max(accesses),
                    "quality_score": self.quality_scores.get(query, 0.5),
                }

        return patterns

    async def predict_cache_performance(self) -> Dict[str, Any]:
        """پیش‌بینی عملکرد کش.

        Returns:
            دیکشنری شامل پیش‌بینی عملکرد
        """
        current_stats = await self.get_adaptive_stats()

        # تحلیل روندها
        hit_rate_trend = "stable"
        if len(self.eviction_history) > 5:
            recent_evictions = self.eviction_history[-5:]
            eviction_frequency = len(recent_evictions) / 5

            if eviction_frequency > 0.8:
                hit_rate_trend = "decreasing"
            elif eviction_frequency < 0.2:
                hit_rate_trend = "increasing"

        # پیش‌بینی اندازه بهینه
        optimal_size = self.max_size
        if current_stats["hit_rate"] > 0.8:
            optimal_size = min(self.max_size * 1.1, 2000)
        elif current_stats["hit_rate"] < 0.6:
            optimal_size = max(self.max_size * 0.9, 500)

        return {
            "current_hit_rate": current_stats["hit_rate"],
            "hit_rate_trend": hit_rate_trend,
            "optimal_cache_size": optimal_size,
            "recommended_strategy": self._recommend_strategy(),
            "performance_score": self._calculate_performance_score(current_stats),
        }

    def _recommend_strategy(self) -> str:
        """توصیه استراتژی حذف بر اساس الگوهای دسترسی.

        Returns:
            نام استراتژی توصیه شده
        """
        if len(self.access_patterns) < 10:
            return "lru"  # برای داده‌های کم، LRU بهتر است

        # تحلیل الگوهای دسترسی
        access_counts = list(self.access_patterns.values())
        avg_access = sum(access_counts) / len(access_counts)

        if avg_access > 5:
            return "lfu"  # اگر دسترسی‌ها زیاد است، LFU بهتر است
        else:
            return "adaptive"  # در غیر این صورت، adaptive بهتر است

    def _calculate_performance_score(self, stats: Dict[str, Any]) -> float:
        """محاسبه امتیاز عملکرد کش.

        Args:
            stats: آمار کش

        Returns:
            امتیاز عملکرد (0.0 تا 1.0)
        """
        hit_rate_score = stats["hit_rate"]
        size_efficiency = stats["cache_size"] / stats["max_size"]
        eviction_efficiency = 1.0 - (
            stats["eviction_count"] / max(stats["hit_count"] + stats["miss_count"], 1)
        )

        # ترکیب امتیازات
        performance_score = (
            0.5 * hit_rate_score + 0.3 * size_efficiency + 0.2 * eviction_efficiency
        )

        return min(max(performance_score, 0.0), 1.0)
