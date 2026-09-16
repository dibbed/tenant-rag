#!/usr/bin/env python3
"""
Real-world style test script for Analytics (examples)
- Runs multi-user flows
- Prints concise outputs to verify behavior
"""

import asyncio
from pprint import pprint

from ragbot.analytics.analytics_dashboard import AnalyticsDashboard
from ragbot.configs.settings import Settings


async def main() -> None:
    print("🚀 Analytics real test starting...")

    settings = Settings()
    dashboard = AnalyticsDashboard(settings)
    await dashboard.initialize()

    # Users
    u1 = "real_user_a"
    u2 = "real_user_b"

    # User A interactions
    await dashboard.track_user_action(
        u1, "add_document", {"source": "alpha.pdf", "source_type": "pdf"}
    )
    await dashboard.record_document_type("pdf")
    await dashboard.track_user_action(
        u1,
        "query",
        {"query": "What is AI?", "processing_time": 1.8, "confidence_score": 0.86},
    )
    await dashboard.track_user_action(
        u1,
        "query",
        {"query": "Explain LLMs", "processing_time": 2.2, "confidence_score": 0.81},
    )
    await dashboard.record_satisfaction_feedback(
        u1, "What is AI?", "AI is...", 5, "Great!"
    )

    # User B interactions
    await dashboard.track_user_action(
        u2, "add_document", {"source": "sales.xlsx", "source_type": "xlsx"}
    )
    await dashboard.record_document_type("xlsx")
    await dashboard.track_user_action(
        u2,
        "query",
        {"query": "Improve sales", "processing_time": 2.6, "confidence_score": 0.72},
    )

    # Fetch per-user analytics
    u1_analytics = await dashboard.get_user_analytics(u1)
    u2_analytics = await dashboard.get_user_analytics(u2)

    print("\n👤 User A analytics:")
    pprint(
        {
            k: v
            for k, v in u1_analytics.items()
            if k in ("user_id", "behavior_insights", "satisfaction_profile")
        }
    )

    print("\n👤 User B analytics:")
    pprint(
        {
            k: v
            for k, v in u2_analytics.items()
            if k in ("user_id", "behavior_insights", "satisfaction_profile")
        }
    )

    # System-wide report
    print("\n📋 System report (7 days):")
    report = await dashboard.get_analytics_report(days=7)
    summary = report.get("summary", {})
    health = report.get("health_assessment", {})
    print("Summary:", summary)
    print("Health:", health)

    # Comprehensive dashboard
    comp = await dashboard.get_comprehensive_dashboard()
    print("\n🎯 Comprehensive dashboard keys:", list(comp.keys()))
    print("User behavior:", comp.get("user_behavior", {}))
    print(
        "Usage patterns - peak hours:", comp.get("usage_patterns", {}).get("peak_hours")
    )

    await dashboard.shutdown()
    print("\n✅ Analytics real test finished successfully")


if __name__ == "__main__":
    asyncio.run(main())
