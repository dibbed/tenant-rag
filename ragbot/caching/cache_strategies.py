"""
استراتژی‌های مختلف کش

این ماژول شامل پیاده‌سازی استراتژی‌های مختلف کش است.
"""

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional


class CacheStrategy(Enum):
    """استراتژی‌های کش.

    Attributes:
        SEMANTIC: کش معنایی
        EXACT: کش دقیق
        FUZZY: کش فازی
        HYBRID: کش ترکیبی
    """

    SEMANTIC = "semantic"
    EXACT = "exact"
    FUZZY = "fuzzy"
    HYBRID = "hybrid"


class CacheStrategyBase(ABC):
    """کلاس پایه استراتژی کش.

    این کلاس پایه برای تمام استراتژی‌های کش است.
    """

    @abstractmethod
    async def should_cache(
        self, query: str, answer: str, confidence_score: float
    ) -> bool:
        """تعیین نیاز به کش کردن.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            confidence_score: امتیاز اطمینان پاسخ

        Returns:
            True اگر باید کش شود، False در غیر این صورت
        """
        pass

    @abstractmethod
    async def find_match(
        self, query: str, cache_entries: Dict[str, Any]
    ) -> Optional[Any]:
        """یافتن تطبیق در کش.

        Args:
            query: پرسش کاربر
            cache_entries: ورودی‌های کش

        Returns:
            ورودی کش تطبیق یا None
        """
        pass

    @abstractmethod
    async def calculate_priority(self, entry: Any) -> float:
        """محاسبه اولویت ورودی.

        Args:
            entry: ورودی کش

        Returns:
            امتیاز اولویت
        """
        pass


class SemanticCacheStrategy(CacheStrategyBase):
    """استراتژی کش معنایی.

    این کلاس استراتژی کش معنایی را پیاده‌سازی می‌کند.
    """

    def __init__(self, similarity_threshold: float = 0.8):
        """مقداردهی اولیه استراتژی کش معنایی.

        Args:
            similarity_threshold: آستانه شباهت برای تطبیق
        """
        self.similarity_threshold = similarity_threshold

    async def should_cache(
        self, query: str, answer: str, confidence_score: float
    ) -> bool:
        """تعیین نیاز به کش کردن معنایی.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            confidence_score: امتیاز اطمینان پاسخ

        Returns:
            True اگر باید کش شود، False در غیر این صورت
        """
        # کش کردن اگر اطمینان بالا باشد
        return confidence_score >= 0.7

    async def find_match(
        self, query: str, cache_entries: Dict[str, Any]
    ) -> Optional[Any]:
        """یافتن تطبیق معنایی.

        Args:
            query: پرسش کاربر
            cache_entries: ورودی‌های کش

        Returns:
            ورودی کش تطبیق یا None
        """
        # پیاده‌سازی جستجوی معنایی
        # اینجا باید از embedder استفاده شود
        return None

    async def calculate_priority(self, entry: Any) -> float:
        """محاسبه اولویت بر اساس معنا.

        Args:
            entry: ورودی کش

        Returns:
            امتیاز اولویت
        """
        # اولویت بر اساس کیفیت و مرتبط بودن
        return entry.confidence_score * 0.7 + entry.access_count * 0.3


class ExactCacheStrategy(CacheStrategyBase):
    """استراتژی کش دقیق.

    این کلاس استراتژی کش دقیق را پیاده‌سازی می‌کند.
    """

    async def should_cache(
        self, query: str, answer: str, confidence_score: float
    ) -> bool:
        """تعیین نیاز به کش کردن دقیق.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            confidence_score: امتیاز اطمینان پاسخ

        Returns:
            True اگر باید کش شود، False در غیر این صورت
        """
        # همیشه کش کردن
        return True

    async def find_match(
        self, query: str, cache_entries: Dict[str, Any]
    ) -> Optional[Any]:
        """یافتن تطبیق دقیق.

        Args:
            query: پرسش کاربر
            cache_entries: ورودی‌های کش

        Returns:
            ورودی کش تطبیق یا None
        """
        # جستجوی دقیق
        for key, entry in cache_entries.items():
            if entry.query == query:
                return entry
        return None

    async def calculate_priority(self, entry: Any) -> float:
        """محاسبه اولویت بر اساس دسترسی.

        Args:
            entry: ورودی کش

        Returns:
            امتیاز اولویت
        """
        return entry.access_count


class FuzzyCacheStrategy(CacheStrategyBase):
    """استراتژی کش فازی.

    این کلاس استراتژی کش فازی را پیاده‌سازی می‌کند.
    """

    def __init__(self, fuzzy_threshold: float = 0.85):
        """مقداردهی اولیه استراتژی کش فازی.

        Args:
            fuzzy_threshold: آستانه فازی برای تطبیق
        """
        self.fuzzy_threshold = fuzzy_threshold

    async def should_cache(
        self, query: str, answer: str, confidence_score: float
    ) -> bool:
        """تعیین نیاز به کش کردن فازی.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            confidence_score: امتیاز اطمینان پاسخ

        Returns:
            True اگر باید کش شود، False در غیر این صورت
        """
        # کش کردن اگر طول پاسخ مناسب باشد
        return len(answer) > 10 and confidence_score >= 0.6

    async def find_match(
        self, query: str, cache_entries: Dict[str, Any]
    ) -> Optional[Any]:
        """یافتن تطبیق فازی.

        Args:
            query: پرسش کاربر
            cache_entries: ورودی‌های کش

        Returns:
            ورودی کش تطبیق یا None
        """
        # پیاده‌سازی جستجوی فازی
        # استفاده از الگوریتم‌های فازی
        return None

    async def calculate_priority(self, entry: Any) -> float:
        """محاسبه اولویت فازی.

        Args:
            entry: ورودی کش

        Returns:
            امتیاز اولویت
        """
        # اولویت بر اساس کیفیت و زمان
        time_factor = 1.0 / (time.time() - entry.timestamp + 1)
        return (
            entry.confidence_score * 0.5 + entry.access_count * 0.3 + time_factor * 0.2
        )


class HybridCacheStrategy(CacheStrategyBase):
    """استراتژی کش ترکیبی.

    این کلاس استراتژی کش ترکیبی را پیاده‌سازی می‌کند.
    """

    def __init__(self, strategies: List[CacheStrategyBase]):
        """مقداردهی اولیه استراتژی کش ترکیبی.

        Args:
            strategies: لیست استراتژی‌های کش
        """
        self.strategies = strategies

    async def should_cache(
        self, query: str, answer: str, confidence_score: float
    ) -> bool:
        """تعیین نیاز به کش کردن ترکیبی.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            confidence_score: امتیاز اطمینان پاسخ

        Returns:
            True اگر باید کش شود، False در غیر این صورت
        """
        # استفاده از تمام استراتژی‌ها
        results = []
        for strategy in self.strategies:
            result = await strategy.should_cache(query, answer, confidence_score)
            results.append(result)

        # کش کردن اگر اکثریت موافق باشند
        return sum(results) > len(results) / 2

    async def find_match(
        self, query: str, cache_entries: Dict[str, Any]
    ) -> Optional[Any]:
        """یافتن تطبیق ترکیبی.

        Args:
            query: پرسش کاربر
            cache_entries: ورودی‌های کش

        Returns:
            ورودی کش تطبیق یا None
        """
        # امتحان تمام استراتژی‌ها
        for strategy in self.strategies:
            match = await strategy.find_match(query, cache_entries)
            if match:
                return match
        return None

    async def calculate_priority(self, entry: Any) -> float:
        """محاسبه اولویت ترکیبی.

        Args:
            entry: ورودی کش

        Returns:
            امتیاز اولویت
        """
        # میانگین اولویت‌های تمام استراتژی‌ها
        priorities = []
        for strategy in self.strategies:
            priority = await strategy.calculate_priority(entry)
            priorities.append(priority)

        return sum(priorities) / len(priorities)


class CacheStrategyFactory:
    """کارخانه استراتژی‌های کش.

    این کلاس استراتژی‌های کش را ایجاد می‌کند.
    """

    @staticmethod
    def create_strategy(strategy_type: CacheStrategy, **kwargs) -> CacheStrategyBase:
        """ایجاد استراتژی کش.

        Args:
            strategy_type: نوع استراتژی کش
            **kwargs: پارامترهای اضافی

        Returns:
            نمونه استراتژی کش

        Raises:
            ValueError: اگر نوع استراتژی ناشناخته باشد
        """
        if strategy_type == CacheStrategy.SEMANTIC:
            return SemanticCacheStrategy(**kwargs)
        elif strategy_type == CacheStrategy.EXACT:
            return ExactCacheStrategy(**kwargs)
        elif strategy_type == CacheStrategy.FUZZY:
            return FuzzyCacheStrategy(**kwargs)
        elif strategy_type == CacheStrategy.HYBRID:
            strategies = kwargs.get("strategies", [])
            return HybridCacheStrategy(strategies)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

    @staticmethod
    def create_default_strategy() -> CacheStrategyBase:
        """ایجاد استراتژی پیش‌فرض.

        Returns:
            استراتژی کش پیش‌فرض
        """
        return SemanticCacheStrategy(similarity_threshold=0.8)

    @staticmethod
    def create_hybrid_strategy() -> CacheStrategyBase:
        """ایجاد استراتژی ترکیبی.

        Returns:
            استراتژی کش ترکیبی
        """
        strategies = [
            SemanticCacheStrategy(similarity_threshold=0.8),
            ExactCacheStrategy(),
            FuzzyCacheStrategy(fuzzy_threshold=0.85),
        ]
        return HybridCacheStrategy(strategies)


class CacheStrategyManager:
    """مدیر استراتژی‌های کش.

    این کلاس استراتژی‌های کش را مدیریت می‌کند.
    """

    def __init__(self):
        """مقداردهی اولیه مدیر استراتژی‌ها."""
        self.strategies: Dict[str, CacheStrategyBase] = {}
        self.active_strategy: Optional[CacheStrategyBase] = None

    def add_strategy(self, name: str, strategy: CacheStrategyBase):
        """اضافه کردن استراتژی.

        Args:
            name: نام استراتژی
            strategy: استراتژی کش
        """
        self.strategies[name] = strategy

    def set_active_strategy(self, name: str):
        """تنظیم استراتژی فعال.

        Args:
            name: نام استراتژی فعال

        Raises:
            KeyError: اگر استراتژی وجود نداشته باشد
        """
        if name not in self.strategies:
            raise KeyError(f"Strategy '{name}' not found")
        self.active_strategy = self.strategies[name]

    def get_active_strategy(self) -> Optional[CacheStrategyBase]:
        """دریافت استراتژی فعال.

        Returns:
            استراتژی فعال یا None
        """
        return self.active_strategy

    def get_strategy(self, name: str) -> Optional[CacheStrategyBase]:
        """دریافت استراتژی با نام.

        Args:
            name: نام استراتژی

        Returns:
            استراتژی یا None
        """
        return self.strategies.get(name)

    def list_strategies(self) -> List[str]:
        """لیست نام استراتژی‌ها.

        Returns:
            لیست نام استراتژی‌ها
        """
        return list(self.strategies.keys())

    async def evaluate_strategy_performance(self, name: str) -> Dict[str, Any]:
        """ارزیابی عملکرد استراتژی.

        Args:
            name: نام استراتژی

        Returns:
            دیکشنری شامل عملکرد استراتژی
        """
        if name not in self.strategies:
            raise KeyError(f"Strategy '{name}' not found")

        strategy = self.strategies[name]

        # اینجا می‌توانید منطق ارزیابی عملکرد را اضافه کنید
        return {
            "strategy_name": name,
            "performance_score": 0.8,  # نمونه
            "evaluation_time": time.time(),
        }
