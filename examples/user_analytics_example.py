#!/usr/bin/env python3
"""
مثال استفاده از سیستم تحلیل کاربران
"""

import asyncio

from ragbot.analytics.analytics_dashboard import AnalyticsDashboard
from ragbot.configs.settings import Settings


async def main():
    """مثال کامل استفاده از سیستم تحلیل کاربران"""

    print("🚀 شروع مثال تحلیل کاربران...")

    # ایجاد تنظیمات
    settings = Settings()

    # ایجاد داشبورد تحلیل
    dashboard = AnalyticsDashboard(settings)
    await dashboard.initialize()

    print("✅ داشبورد تحلیل راه‌اندازی شد")

    # شبیه‌سازی فعالیت کاربران
    print("\n📊 شبیه‌سازی فعالیت کاربران...")

    # کاربر 1: کاربر فعال
    user1_id = "user_123"
    print(f"\n👤 شبیه‌سازی کاربر {user1_id}...")

    # اضافه کردن اسناد
    await dashboard.track_user_action(
        user1_id, "add_document", {"source": "ai_guide.pdf", "source_type": "pdf"}
    )
    await dashboard.record_document_type("pdf")

    await dashboard.track_user_action(
        user1_id, "add_document", {"source": "ml_tutorial.docx", "source_type": "docx"}
    )
    await dashboard.record_document_type("docx")

    # پرسش‌ها
    queries = [
        "What is artificial intelligence?",
        "How does machine learning work?",
        "What are neural networks?",
        "Explain deep learning",
        "What is natural language processing?",
    ]

    for i, query in enumerate(queries):
        await dashboard.track_user_action(
            user1_id,
            "query",
            {
                "query": query,
                "processing_time": 2.5 + i * 0.1,
                "confidence_score": 0.8 + i * 0.02,
            },
        )

        # ثبت مدت جلسه
        await dashboard.record_session_length(300 + i * 60)  # 5-9 minutes

        # بازخورد رضایت (هر چند پرسش یکبار)
        if i % 2 == 0:
            rating = 4 + (i % 2)  # 4 یا 5
            await dashboard.record_satisfaction_feedback(
                user1_id,
                query,
                f"Answer to: {query}",
                rating,
                f"Great answer! Rating: {rating}",
            )

    # کاربر 2: کاربر معمولی
    user2_id = "user_456"
    print(f"\n👤 شبیه‌سازی کاربر {user2_id}...")

    await dashboard.track_user_action(
        user2_id,
        "add_document",
        {"source": "business_report.pdf", "source_type": "pdf"},
    )
    await dashboard.record_document_type("pdf")

    queries2 = ["What are the key findings?", "How can we improve sales?"]

    for i, query in enumerate(queries2):
        await dashboard.track_user_action(
            user2_id,
            "query",
            {
                "query": query,
                "processing_time": 1.8 + i * 0.2,
                "confidence_score": 0.7 + i * 0.05,
            },
        )

        await dashboard.record_session_length(180 + i * 30)  # 3-3.5 minutes

        if i == 1:  # فقط یک بازخورد
            await dashboard.record_satisfaction_feedback(
                user2_id, query, f"Answer to: {query}", 3, "Average answer"
            )

    # کاربر 3: کاربر کم‌استفاده
    user3_id = "user_789"
    print(f"\n👤 شبیه‌سازی کاربر {user3_id}...")

    await dashboard.track_user_action(
        user3_id, "add_document", {"source": "quick_guide.txt", "source_type": "text"}
    )
    await dashboard.record_document_type("text")

    await dashboard.track_user_action(
        user3_id,
        "query",
        {
            "query": "What is this about?",
            "processing_time": 1.2,
            "confidence_score": 0.6,
        },
    )

    await dashboard.record_session_length(120)  # 2 minutes

    print("\n📈 دریافت تحلیل‌ها...")

    # تحلیل کاربر خاص
    print("\n🔍 تحلیل کاربر 1:")
    user1_analytics = await dashboard.get_user_analytics(user1_id)

    if "error" not in user1_analytics:
        profile = user1_analytics["behavior_insights"]["profile"]
        print(f"  📊 تعداد جلسات: {profile.total_sessions}")
        print(f"  ❓ تعداد پرسش‌ها: {profile.total_queries}")
        print(f"  📈 الگوی استفاده: {profile.usage_pattern}")
        print(f"  ⭐ میانگین رضایت: {profile.satisfaction_avg:.1f}")

        satisfaction = user1_analytics["satisfaction_profile"]
        if not satisfaction.get("no_data"):
            print(f"  😊 امتیاز رضایت: {satisfaction['average_rating']:.1f}/5")

    # گزارش جامع
    print("\n📋 گزارش جامع:")
    report = await dashboard.get_analytics_report(days=7)

    if "error" not in report:
        summary = report["summary"]
        print(f"  👥 کل کاربران: {summary['total_users']}")
        print(f"  ❓ کل پرسش‌ها: {summary['total_queries']}")
        print(f"  ⭐ رضایت کلی: {summary['overall_satisfaction']:.1f}")
        print(f"  🔄 کل فعالیت‌ها: {summary['total_activities']}")

        health = report["health_assessment"]
        print(f"  🏥 سلامت سیستم: {health['status']} ({health['score']}/100)")

        recommendations = report["recommendations"]
        if recommendations:
            print("  💡 توصیه‌ها:")
            for rec in recommendations[:3]:
                print(f"    • {rec}")

    # داشبورد جامع
    print("\n🎯 داشبورد جامع:")
    comprehensive = await dashboard.get_comprehensive_dashboard()

    if "error" not in comprehensive:
        user_behavior = comprehensive["user_behavior"]
        print(f"  📊 کاربران فعال: {user_behavior['total_users']}")
        print(f"  📈 الگوهای استفاده: {user_behavior['usage_patterns']}")

        usage_patterns = comprehensive["usage_patterns"]
        peak_hours = usage_patterns.get("peak_hours", {})
        if not peak_hours.get("no_data"):
            print(f"  🕐 ساعات پیک: {peak_hours.get('most_active_hour', 'نامشخص')}")

        satisfaction = comprehensive["satisfaction"]
        metrics = satisfaction.get("metrics", {})
        if not metrics.get("no_data"):
            print(f"  😊 رضایت کلی: {metrics.get('overall_satisfaction', 0):.1f}")
            print(f"  📊 تعداد بازخورد: {metrics.get('total_feedback', 0)}")

    # صادرات داده‌ها
    print("\n💾 صادرات داده‌ها...")
    exported_data = await dashboard.export_analytics_data("json")
    print(f"  ✅ داده‌ها صادر شدند (حجم: {len(str(exported_data))} کاراکتر)")

    # خاموش کردن داشبورد
    await dashboard.shutdown()
    print("\n✅ مثال با موفقیت تکمیل شد!")


if __name__ == "__main__":
    asyncio.run(main())
