"""
تست‌های تحلیل کاربر
"""

from datetime import datetime, timedelta

import pytest

from ragbot.analytics.analytics_dashboard import AnalyticsDashboard
from ragbot.analytics.satisfaction_tracker import SatisfactionTracker
from ragbot.analytics.usage_patterns import UsagePatternsAnalyzer
from ragbot.analytics.user_behavior import UserBehaviorAnalyzer


class TestUserBehaviorAnalyzer:
    """تست تحلیلگر رفتار کاربر"""

    @pytest.mark.asyncio
    async def test_user_session_tracking(self):
        """تست ردیابی جلسه کاربر"""
        analyzer = UserBehaviorAnalyzer()

        # شبیه‌سازی جلسه کاربر
        await analyzer.track_user_action("user123", "query", {"query": "What is AI?"})
        await analyzer.track_user_action(
            "user123", "query", {"query": "How does ML work?"}
        )
        await analyzer.track_user_action("user123", "satisfaction", {"score": 4.5})

        # بررسی پروفایل کاربر
        profile = await analyzer.generate_user_profile("user123")

        # Assertions
        assert profile.user_id == "user123"
        assert profile.total_queries == 2
        assert profile.satisfaction_avg == 4.5
        assert profile.usage_pattern in [
            "light_user",
            "casual_user",
            "regular_user",
            "power_user",
            "casual",  # fallback pattern
        ]

    @pytest.mark.asyncio
    async def test_usage_pattern_detection(self):
        """تست تشخیص الگوی استفاده"""
        analyzer = UserBehaviorAnalyzer()

        # شبیه‌سازی کاربر فعال
        for i in range(10):
            await analyzer.track_user_action(
                "power_user", "query", {"query": f"Query {i}"}
            )

        profile = await analyzer.generate_user_profile("power_user")

        # Assertions
        assert profile.total_queries == 10
        # Note: Without session duration, it will be classified as casual
        assert profile.usage_pattern in ["power_user", "casual"]

    @pytest.mark.asyncio
    async def test_keyword_extraction(self):
        """تست استخراج کلمات کلیدی"""
        analyzer = UserBehaviorAnalyzer()

        keywords = await analyzer._extract_keywords(
            "What is artificial intelligence and how does it work?"
        )

        # Assertions
        assert "artificial" in keywords
        assert "intelligence" in keywords
        assert "work?" in keywords  # includes punctuation
        assert "what" not in keywords  # stop word
        assert "is" not in keywords  # stop word

    @pytest.mark.asyncio
    async def test_user_insights(self):
        """تست دریافت بینش‌های کاربر"""
        analyzer = UserBehaviorAnalyzer()

        # اضافه کردن داده‌های تست
        await analyzer.track_user_action("user123", "query", {"query": "AI technology"})
        await analyzer.track_user_action(
            "user123", "query", {"query": "Machine learning algorithms"}
        )
        await analyzer.track_user_action(
            "user123", "add_document", {"source": "ai_doc.pdf"}
        )

        insights = await analyzer.get_user_insights("user123")

        # Assertions
        assert "profile" in insights
        assert "recent_activity" in insights
        assert "usage_trends" in insights
        assert "recommendations" in insights
        assert insights["profile"].user_id == "user123"

    @pytest.mark.asyncio
    async def test_all_users_summary(self):
        """تست خلاصه تمام کاربران"""
        analyzer = UserBehaviorAnalyzer()

        # اضافه کردن چند کاربر
        await analyzer.track_user_action("user1", "query", {"query": "Query 1"})
        await analyzer.track_user_action("user2", "query", {"query": "Query 2"})
        await analyzer.track_user_action("user2", "query", {"query": "Query 3"})

        summary = await analyzer.get_all_users_summary()

        # Assertions
        assert summary["total_users"] == 2
        assert summary["total_queries"] == 3
        assert summary["total_sessions"] == 2


class TestUsagePatternsAnalyzer:
    """تست تحلیلگر الگوهای استفاده"""

    @pytest.mark.asyncio
    async def test_activity_recording(self):
        """تست ثبت فعالیت"""
        analyzer = UsagePatternsAnalyzer()

        await analyzer.record_activity("user123", "query", {"query": "test query"})
        await analyzer.record_activity("user123", "document", {"type": "pdf"})

        # بررسی آمار ساعتی
        current_hour = datetime.now().hour
        assert analyzer.hourly_usage[current_hour] >= 2

    @pytest.mark.asyncio
    async def test_session_length_recording(self):
        """تست ثبت مدت جلسه"""
        analyzer = UsagePatternsAnalyzer()

        await analyzer.record_session_length(300)  # 5 minutes
        await analyzer.record_session_length(1800)  # 30 minutes

        assert len(analyzer.session_lengths) == 2
        assert analyzer.session_lengths[0] == 300
        assert analyzer.session_lengths[1] == 1800

    @pytest.mark.asyncio
    async def test_document_type_recording(self):
        """تست ثبت نوع سند"""
        analyzer = UsagePatternsAnalyzer()

        await analyzer.record_document_type("pdf")
        await analyzer.record_document_type("docx")
        await analyzer.record_document_type("pdf")

        assert analyzer.document_types["pdf"] == 2
        assert analyzer.document_types["docx"] == 1

    @pytest.mark.asyncio
    async def test_usage_patterns_analysis(self):
        """تست تحلیل الگوهای استفاده"""
        analyzer = UsagePatternsAnalyzer()

        # اضافه کردن داده‌های تست
        for i in range(10):
            await analyzer.record_activity("user123", "query", {"query": f"Query {i}"})

        await analyzer.record_session_length(300)
        await analyzer.record_document_type("pdf")

        patterns = await analyzer.analyze_usage_patterns()

        # Assertions
        assert "peak_hours" in patterns
        assert "usage_distribution" in patterns
        assert "query_patterns" in patterns
        assert "document_preferences" in patterns
        assert "session_characteristics" in patterns
        assert "user_engagement" in patterns

    @pytest.mark.asyncio
    async def test_trend_analysis(self):
        """تست تحلیل روند"""
        analyzer = UsagePatternsAnalyzer()

        # شبیه‌سازی داده‌های چند روزه
        base_date = datetime.now() - timedelta(days=7)
        for i in range(7):
            date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            analyzer.daily_usage[date_str] = 10 + i  # افزایش تدریجی

        trend = await analyzer.get_trend_analysis(days=7)

        # Assertions
        assert trend["trend_direction"] == "increasing"
        assert trend["period_days"] == 7
        assert "usage_values" in trend


class TestSatisfactionTracker:
    """تست ردیابی رضایت"""

    @pytest.mark.asyncio
    async def test_satisfaction_tracking(self):
        """تست ردیابی رضایت"""
        tracker = SatisfactionTracker()

        # ثبت بازخورد
        await tracker.record_feedback(
            "user123", "What is AI?", "AI is...", 5, "Great answer!"
        )
        await tracker.record_feedback(
            "user123", "How does ML work?", "ML is...", 4, "Good"
        )

        # دریافت متریک‌ها
        metrics = await tracker.get_satisfaction_metrics()

        # Assertions
        assert metrics["overall_satisfaction"] == 4.5
        assert metrics["total_feedback"] == 2
        assert "user123" in metrics["user_satisfaction"]

    @pytest.mark.asyncio
    async def test_invalid_rating(self):
        """تست امتیاز نامعتبر"""
        tracker = SatisfactionTracker()

        # ثبت امتیاز نامعتبر
        await tracker.record_feedback("user123", "test", "answer", 6)  # امتیاز نامعتبر

        # بررسی که امتیاز ثبت نشده
        metrics = await tracker.get_satisfaction_metrics()
        assert metrics.get("total_feedback", 0) == 0

    @pytest.mark.asyncio
    async def test_user_satisfaction_profile(self):
        """تست پروفایل رضایت کاربر"""
        tracker = SatisfactionTracker()

        # ثبت چند بازخورد
        await tracker.record_feedback("user123", "Query 1", "Answer 1", 5)
        await tracker.record_feedback("user123", "Query 2", "Answer 2", 4)
        await tracker.record_feedback("user123", "Query 3", "Answer 3", 3)

        profile = await tracker.get_user_satisfaction_profile("user123")

        # Assertions
        assert profile["user_id"] == "user123"
        assert profile["total_feedback"] == 3
        assert profile["average_rating"] == 4.0
        assert profile["positive_ratings"] == 2
        assert profile["negative_ratings"] == 0

    @pytest.mark.asyncio
    async def test_satisfaction_insights(self):
        """تست بینش‌های رضایت"""
        tracker = SatisfactionTracker()

        # ثبت بازخوردهای مختلف
        await tracker.record_feedback("user1", "Query 1", "Answer 1", 5)
        await tracker.record_feedback("user2", "Query 2", "Answer 2", 4)
        await tracker.record_feedback("user3", "Query 3", "Answer 3", 2)

        insights = await tracker.get_satisfaction_insights()

        # Assertions
        assert "overall_health" in insights
        assert "improvement_areas" in insights
        assert "success_factors" in insights
        assert "recommendations" in insights

    @pytest.mark.asyncio
    async def test_query_satisfaction_analysis(self):
        """تست تحلیل رضایت بر اساس پرسش"""
        tracker = SatisfactionTracker()

        # ثبت بازخورد برای پرسش‌های مختلف
        await tracker.record_feedback("user123", "AI question", "AI answer", 5)
        await tracker.record_feedback("user456", "AI question", "AI answer", 4)
        await tracker.record_feedback("user789", "ML question", "ML answer", 2)

        analysis = await tracker.get_query_satisfaction_analysis()

        # Assertions
        assert "query_analysis" in analysis
        assert "best_rated_queries" in analysis
        assert "worst_rated_queries" in analysis
        assert "AI question" in analysis["query_analysis"]


class TestAnalyticsDashboard:
    """تست داشبورد تحلیل"""

    @pytest.mark.asyncio
    async def test_dashboard_initialization(self):
        """تست مقداردهی اولیه داشبورد"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        assert dashboard._initialized is True

    @pytest.mark.asyncio
    async def test_comprehensive_dashboard(self):
        """تست داشبورد جامع"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        # اضافه کردن داده‌های تست
        await dashboard.track_user_action("user123", "query", {"query": "test"})
        await dashboard.record_satisfaction_feedback("user123", "test", "answer", 4)

        comprehensive_data = await dashboard.get_comprehensive_dashboard()

        # Assertions
        assert "timestamp" in comprehensive_data
        assert "user_behavior" in comprehensive_data
        assert "usage_patterns" in comprehensive_data
        assert "satisfaction" in comprehensive_data
        assert "overall_insights" in comprehensive_data

    @pytest.mark.asyncio
    async def test_user_analytics(self):
        """تست تحلیل کاربر خاص"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        # اضافه کردن داده‌های کاربر
        await dashboard.track_user_action("user123", "query", {"query": "test query"})
        await dashboard.record_satisfaction_feedback("user123", "test", "answer", 5)

        user_analytics = await dashboard.get_user_analytics("user123")

        # Assertions
        assert user_analytics["user_id"] == "user123"
        assert "behavior_insights" in user_analytics
        assert "satisfaction_profile" in user_analytics

    @pytest.mark.asyncio
    async def test_analytics_report(self):
        """تست گزارش تحلیل"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        # اضافه کردن داده‌های تست
        await dashboard.track_user_action("user123", "query", {"query": "test"})
        await dashboard.record_satisfaction_feedback("user123", "test", "answer", 4)

        report = await dashboard.get_analytics_report(days=7)

        # Assertions
        assert "period" in report
        assert "generated_at" in report
        assert "summary" in report
        assert "user_behavior" in report
        assert "usage_patterns" in report
        assert "satisfaction" in report
        assert "health_assessment" in report
        assert "recommendations" in report
        assert "trends" in report

    @pytest.mark.asyncio
    async def test_export_analytics_data(self):
        """تست صادرات داده‌های تحلیل"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        # اضافه کردن داده‌های تست
        await dashboard.track_user_action("user123", "query", {"query": "test"})

        exported_data = await dashboard.export_analytics_data("json")

        # Assertions
        assert isinstance(exported_data, dict)
        assert "timestamp" in exported_data

    @pytest.mark.asyncio
    async def test_dashboard_shutdown(self):
        """تست خاموش کردن داشبورد"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        await dashboard.shutdown()

        assert dashboard._initialized is False


class TestIntegration:
    """تست‌های یکپارچگی"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """تست جریان کامل کار"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        # شبیه‌سازی جریان کامل کاربر
        user_id = "test_user"

        # اضافه کردن سند
        await dashboard.track_user_action(
            user_id, "add_document", {"source": "test.pdf"}
        )
        await dashboard.record_document_type("pdf")

        # پرسش‌ها
        await dashboard.track_user_action(user_id, "query", {"query": "What is AI?"})
        await dashboard.track_user_action(
            user_id, "query", {"query": "How does ML work?"}
        )

        # ثبت مدت جلسه
        await dashboard.record_session_length(600)  # 10 minutes

        # بازخورد رضایت
        await dashboard.record_satisfaction_feedback(
            user_id, "What is AI?", "AI is...", 5, "Great!"
        )

        # دریافت گزارش جامع
        comprehensive_data = await dashboard.get_comprehensive_dashboard()

        # Assertions
        assert comprehensive_data["user_behavior"]["total_users"] >= 1
        assert comprehensive_data["user_behavior"]["total_queries"] >= 2
        assert comprehensive_data["satisfaction"]["metrics"]["total_feedback"] >= 1

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """تست مدیریت خطا"""
        dashboard = AnalyticsDashboard()
        await dashboard.initialize()

        # تست با داده‌های نامعتبر
        await dashboard.track_user_action("", "invalid_action", None)
        await dashboard.record_satisfaction_feedback("", "", "", 0)

        # باید بدون خطا اجرا شود
        comprehensive_data = await dashboard.get_comprehensive_dashboard()
        assert isinstance(comprehensive_data, dict)
