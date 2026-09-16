"""
مثال استفاده از Performance Monitoring
"""

import asyncio
import time

from ragbot.configs.settings import Settings
from ragbot.outputs.performance_dashboard import PerformanceDashboard
from ragbot.utils.async_processor import AsyncProcessor


async def simulate_work():
    """شبیه‌سازی کار برای تست performance monitoring"""
    await asyncio.sleep(0.1)
    return "work completed"


async def main():
    """مثال اصلی"""
    print("🚀 شروع مثال Performance Monitoring")

    # ایجاد تنظیمات
    settings = Settings(
        bot_token="test_token",
        performance={
            "enable_performance_monitoring": True,
            "enable_resource_monitoring": True,
            "enable_memory_optimization": True,
            "monitoring_interval": 2,
            "resource_check_interval": 2,
            "optimization_interval": 5,
            "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
        },
    )

    # ایجاد Performance Dashboard
    dashboard = PerformanceDashboard(settings)
    await dashboard.initialize()

    # ایجاد Async Processor
    processor = AsyncProcessor(max_workers=2)

    try:
        print("📊 شروع نظارت بر عملکرد...")

        # شبیه‌سازی درخواست‌ها
        for i in range(5):
            start_time = time.time()

            # انجام کار
            await simulate_work()

            # ثبت درخواست
            processing_time = time.time() - start_time
            await dashboard.record_request(processing_time, success=True)

            print(f"✅ درخواست {i + 1} تکمیل شد ({processing_time:.3f}s)")

            # انتظار کوتاه
            await asyncio.sleep(0.5)

        # پردازش ناهمزمان
        print("\n🔄 شروع پردازش ناهمزمان...")

        async def process_item(item):
            await asyncio.sleep(0.1)
            return item * 2

        items = list(range(1, 11))
        results = await processor.process_documents_async(items, process_item)

        print(f"✅ پردازش {len(items)} آیتم تکمیل شد: {results}")

        # انتظار برای جمع‌آوری متریک‌ها
        print("\n⏳ انتظار برای جمع‌آوری متریک‌ها...")
        await asyncio.sleep(3)

        # دریافت خلاصه عملکرد
        print("\n📈 خلاصه عملکرد:")
        perf_summary = await dashboard.get_performance_summary()

        if "no_data" in perf_summary:
            print("❌ داده‌ای برای نمایش وجود ندارد")
        else:
            print(
                f"⏱️  میانگین زمان پاسخ: {perf_summary.get('average_response_time', 0):.3f}s"
            )
            print(f"📊 تعداد کل درخواست‌ها: {perf_summary.get('total_requests', 0)}")
            print(f"❌ نرخ خطا: {perf_summary.get('error_rate', 0):.2%}")
            print(f"💻 استفاده از CPU: {perf_summary.get('cpu_usage', 0):.1f}%")
            print(f"🧠 استفاده از حافظه: {perf_summary.get('memory_usage', 0):.1f}%")
            print(f"🔗 اتصالات فعال: {perf_summary.get('active_connections', 0)}")

        # دریافت خلاصه منابع
        print("\n💾 خلاصه منابع:")
        resource_summary = await dashboard.get_resource_summary()

        if "no_data" in resource_summary:
            print("❌ داده‌ای برای نمایش وجود ندارد")
        else:
            current = resource_summary.get("current", {})
            averages = resource_summary.get("averages", {})

            print(f"💻 CPU فعلی: {current.get('cpu_percent', 0):.1f}%")
            print(f"🧠 حافظه فعلی: {current.get('memory_percent', 0):.1f}%")
            print(f"💽 دیسک فعلی: {current.get('disk_usage', 0):.1f}%")
            print(f"📊 میانگین CPU: {averages.get('cpu_percent', 0):.1f}%")
            print(f"📊 میانگین حافظه: {averages.get('memory_percent', 0):.1f}%")

            # نمایش هشدارها
            alerts = resource_summary.get("alerts", [])
            if alerts:
                print(f"\n⚠️  هشدارهای فعال ({len(alerts)}):")
                for alert in alerts[-3:]:  # آخرین 3 هشدار
                    severity = alert.get("severity", "unknown")
                    message = alert.get("message", "بدون پیام")
                    print(f"  - {severity}: {message}")
            else:
                print("\n✅ هیچ هشدار فعالی وجود ندارد")

        # دریافت وضعیت سلامت
        print("\n🏥 وضعیت سلامت سیستم:")
        health = await dashboard.get_health_status()

        status = health.get("overall_status", "unknown")
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🚨",
            "unhealthy": "❌",
        }.get(status, "❓")

        print(f"{status_emoji} وضعیت کلی: {status}")

        components = health.get("components", {})
        for component, status in components.items():
            if isinstance(status, dict):
                comp_status = status.get("status", "unknown")
                comp_emoji = {
                    "healthy": "✅",
                    "warning": "⚠️",
                    "critical": "🚨",
                    "unhealthy": "❌",
                }.get(comp_status, "❓")
                print(f"  {comp_emoji} {component}: {comp_status}")
            else:
                print(f"  ❓ {component}: {status}")

        print("\n🎉 مثال Performance Monitoring با موفقیت تکمیل شد!")

    except Exception as e:
        print(f"❌ خطا در اجرای مثال: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # پاک‌سازی
        print("\n🧹 پاک‌سازی منابع...")
        await dashboard.shutdown()
        await processor.shutdown()
        print("✅ پاک‌سازی تکمیل شد")


if __name__ == "__main__":
    asyncio.run(main())
