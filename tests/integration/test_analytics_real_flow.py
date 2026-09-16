import pytest

from ragbot.configs.settings import Settings
from ragbot.services.integration_service import (
    IntegrationService,
    shutdown_integration_service,
)


@pytest.mark.asyncio
async def test_analytics_real_flow_multi_user():
    settings = Settings()
    integration = IntegrationService(settings)
    await integration.initialize()

    # Users
    u1 = "u_real_1"
    u2 = "u_real_2"

    # User 1: add docs, ask queries, provide feedback
    await integration.track_user_action(
        u1, "add_document", {"source": "file1.pdf", "source_type": "pdf"}
    )
    await integration.track_user_action(
        u1, "add_document", {"source": "file2.docx", "source_type": "docx"}
    )
    await integration.track_user_action(
        u1,
        "query",
        {"query": "What is AI?", "processing_time": 1.9, "confidence_score": 0.85},
    )
    await integration.track_user_action(
        u1,
        "query",
        {"query": "Explain ML", "processing_time": 2.1, "confidence_score": 0.82},
    )
    await integration.record_satisfaction_feedback(u1, "What is AI?", "AI is...", 5)

    # User 2: fewer interactions
    await integration.track_user_action(
        u2, "add_document", {"source": "sales.xlsx", "source_type": "xlsx"}
    )
    await integration.track_user_action(
        u2,
        "query",
        {
            "query": "How to improve sales?",
            "processing_time": 2.6,
            "confidence_score": 0.7,
        },
    )

    # Fetch analytics per-user
    u1_analytics = await integration.get_user_analytics(u1)
    u2_analytics = await integration.get_user_analytics(u2)

    assert u1_analytics["user_id"] == u1
    assert u2_analytics["user_id"] == u2

    # Check profile presence and some expected keys
    assert "behavior_insights" in u1_analytics
    assert "satisfaction_profile" in u1_analytics

    # Comprehensive report
    report = await integration.get_analytics_report(days=7)
    assert "summary" in report
    assert "user_behavior" in report
    assert "usage_patterns" in report
    assert "satisfaction" in report
    assert "health_assessment" in report

    # Dashboard data indirectly via comprehensive dashboard from analytics
    dashboard = await integration.get_analytics_dashboard()
    data = await dashboard.get_comprehensive_dashboard()
    assert "user_behavior" in data
    assert "usage_patterns" in data

    await integration.shutdown()
    await shutdown_integration_service()
