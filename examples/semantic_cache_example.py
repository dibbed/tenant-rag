#!/usr/bin/env python3
"""
مثال استفاده از کش معنایی

این فایل نشان می‌دهد چگونه از سیستم کش معنایی استفاده کنید.
"""

import asyncio
import time

from ragbot.caching.adaptive_cache import AdaptiveCache
from ragbot.caching.cache_metrics import CacheMetricsCollector
from ragbot.caching.semantic_cache import SemanticCache


async def basic_semantic_cache_example():
    """مثال پایه استفاده از کش معنایی."""
    print("=== مثال پایه کش معنایی ===")

    # ایجاد کش معنایی
    cache = SemanticCache(similarity_threshold=0.8, max_size=100, ttl_seconds=3600)

    # ذخیره چند پاسخ
    await cache.cache_answer(
        query="What is machine learning?",
        answer="Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
        context=[
            "Machine learning is a method of data analysis",
            "It automates analytical model building",
            "Uses algorithms that iteratively learn from data",
        ],
        metadata={"language": "en", "topic": "AI"},
        confidence_score=0.9,
    )

    await cache.cache_answer(
        query="چگونه پایتون یاد بگیرم؟",
        answer="برای یادگیری پایتون، ابتدا با مفاهیم پایه شروع کنید، سپس پروژه‌های عملی انجام دهید.",
        context=[
            "پایتون زبان برنامه‌نویسی ساده است",
            "با کتاب‌ها و دوره‌های آنلاین شروع کنید",
            "تمرین منظم کلید موفقیت است",
        ],
        metadata={"language": "fa", "topic": "programming"},
        confidence_score=0.85,
    )

    # جستجوی پاسخ‌های مشابه
    print("\n--- جستجوی پاسخ‌های مشابه ---")

    # پرسش مشابه اول
    similar_result = await cache.get_similar_answer("What is ML?")
    if similar_result:
        print(f"✅ پیدا شد: {similar_result.answer[:100]}...")
        print(f"امتیاز اطمینان: {similar_result.confidence_score}")
    else:
        print("❌ پاسخ مشابهی پیدا نشد")

    # پرسش مشابه دوم
    similar_result = await cache.get_similar_answer("آموزش پایتون چطوری؟")
    if similar_result:
        print(f"✅ پیدا شد: {similar_result.answer[:100]}...")
        print(f"امتیاز اطمینان: {similar_result.confidence_score}")
    else:
        print("❌ پاسخ مشابهی پیدا نشد")

    # نمایش آمار کش
    stats = await cache.get_cache_stats()
    print("\n--- آمار کش ---")
    print(f"اندازه کش: {stats['cache_size']}")
    print(f"نرخ موفقیت: {stats['hit_rate']:.2f}")
    print(f"تعداد hit: {stats['hit_count']}")
    print(f"تعداد miss: {stats['miss_count']}")

    # پاک‌سازی
    await cache.clear_cache()


async def adaptive_cache_example():
    """مثال استفاده از کش تطبیقی."""
    print("\n=== مثال کش تطبیقی ===")

    # ایجاد کش تطبیقی
    cache = AdaptiveCache(
        similarity_threshold=0.8,
        max_size=5,
        ttl_seconds=3600,
        eviction_strategy="adaptive",
    )

    # ذخیره پاسخ‌های با کیفیت متفاوت
    queries_and_answers = [
        ("High quality question", "Very detailed and accurate answer", 0.95),
        ("Medium quality question", "Good answer with some details", 0.75),
        ("Low quality question", "Basic answer", 0.45),
        ("Another high quality question", "Excellent comprehensive answer", 0.92),
        ("Poor quality question", "Minimal answer", 0.3),
    ]

    for query, answer, confidence in queries_and_answers:
        await cache.cache_answer(
            query=query,
            answer=answer,
            context=[f"Context for {query}"],
            metadata={"quality": "test"},
            confidence_score=confidence,
        )

    print(f"کش پر شد. اندازه: {len(cache.cache)}")

    # اضافه کردن یک ورودی دیگر برای تست حذف
    await cache.cache_answer(
        query="Trigger eviction question",
        answer="This should trigger eviction",
        context=["Eviction context"],
        metadata={},
        confidence_score=0.8,
    )

    print(f"بعد از حذف. اندازه: {len(cache.cache)}")
    print(f"تعداد حذف‌ها: {cache.eviction_count}")

    # نمایش الگوهای دسترسی
    patterns = await cache.get_access_patterns()
    print(f"\nتعداد الگوهای دسترسی: {len(patterns)}")

    # پیش‌بینی عملکرد
    prediction = await cache.predict_cache_performance()
    print("\nپیش‌بینی عملکرد:")
    print(f"نرخ hit فعلی: {prediction['current_hit_rate']:.2f}")
    print(f"اندازه بهینه: {prediction['optimal_cache_size']}")
    print(f"استراتژی توصیه‌شده: {prediction['recommended_strategy']}")

    # پاک‌سازی
    await cache.clear_cache()


async def cache_metrics_example():
    """مثال استفاده از متریک‌های کش."""
    print("\n=== مثال متریک‌های کش ===")

    # ایجاد جمع‌آورنده متریک‌ها
    metrics = CacheMetricsCollector()
    cache = SemanticCache(max_size=3)

    # شبیه‌سازی استفاده از کش
    queries = [
        "First question",
        "Second question",
        "Third question",
        "First question",  # Hit
        "Fourth question",  # Miss + eviction
    ]

    for i, query in enumerate(queries):
        # بررسی کش
        result = await cache.get_similar_answer(query)

        if result:
            print(f"✅ Cache hit: {query}")
            metrics.record_cache_hit()
        else:
            print(f"❌ Cache miss: {query}")
            metrics.record_cache_miss()

            # ذخیره در کش
            await cache.cache_answer(
                query=query,
                answer=f"Answer for {query}",
                context=[f"Context for {query}"],
                metadata={},
                confidence_score=0.8,
            )

        # به‌روزرسانی متریک‌ها
        metrics.update_cache_size(len(cache.cache))

        if cache.eviction_count > 0:
            metrics.record_cache_eviction()

    # محاسبه نرخ hit
    total_requests = metrics.cache_hits._value.get() + metrics.cache_misses._value.get()
    hit_rate = (
        metrics.cache_hits._value.get() / total_requests if total_requests > 0 else 0
    )
    metrics.update_hit_rate(hit_rate)

    # نمایش خلاصه متریک‌ها
    summary = metrics.get_metrics_summary()
    print("\n--- خلاصه متریک‌ها ---")
    print(f"Cache hits: {summary['cache_hits']}")
    print(f"Cache misses: {summary['cache_misses']}")
    print(f"Cache evictions: {summary['cache_evictions']}")
    print(f"Cache size: {summary['cache_size']}")
    print(f"Hit rate: {summary['hit_rate']:.2f}")

    # پاک‌سازی
    await cache.clear_cache()


async def performance_comparison():
    """مقایسه عملکرد با و بدون کش."""
    print("\n=== مقایسه عملکرد ===")

    # تست بدون کش
    print("تست بدون کش...")
    start_time = time.time()

    for i in range(100):
        # شبیه‌سازی پردازش سنگین
        await asyncio.sleep(0.01)  # 10ms تأخیر

    no_cache_time = time.time() - start_time
    print(f"زمان بدون کش: {no_cache_time:.2f} ثانیه")

    # تست با کش
    print("تست با کش...")
    cache = SemanticCache(max_size=50)
    start_time = time.time()

    for i in range(100):
        query = f"Query {i % 10}"  # 10 پرسش منحصر به فرد

        # بررسی کش
        result = await cache.get_similar_answer(query)

        if not result:
            # شبیه‌سازی پردازش سنگین فقط برای miss
            await asyncio.sleep(0.01)

            # ذخیره در کش
            await cache.cache_answer(
                query=query,
                answer=f"Answer for {query}",
                context=[f"Context for {query}"],
                metadata={},
                confidence_score=0.8,
            )

    cache_time = time.time() - start_time
    print(f"زمان با کش: {cache_time:.2f} ثانیه")

    # محاسبه بهبود
    improvement = ((no_cache_time - cache_time) / no_cache_time) * 100
    print(f"بهبود عملکرد: {improvement:.1f}%")

    # آمار کش
    stats = await cache.get_cache_stats()
    print(f"نرخ موفقیت کش: {stats['hit_rate']:.2f}")

    # پاک‌سازی
    await cache.clear_cache()


async def main():
    """تابع اصلی."""
    print("🚀 شروع مثال‌های کش معنایی")

    try:
        await basic_semantic_cache_example()
        await adaptive_cache_example()
        await cache_metrics_example()
        await performance_comparison()

        print("\n✅ همه مثال‌ها با موفقیت اجرا شدند!")

    except Exception as e:
        print(f"❌ خطا در اجرای مثال‌ها: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
