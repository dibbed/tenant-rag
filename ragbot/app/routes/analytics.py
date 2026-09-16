"""Analytics command handler."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.app.ui.manager import ui_manager

from .utils import get_integration_service, safe_reply, safe_reply_with_kb

router = Router()


@router.message(Command("analytics"))
async def analytics_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /analytics command")

        integration_service = await get_integration_service()
        user_analytics = await integration_service.get_user_analytics(str(user_id))

        # Use UI manager to create analytics message
        analytics_msg = ui_manager.create_analytics_message(user_analytics)

        await safe_reply_with_kb(message, analytics_msg, ui_manager.back_keyboard)
    except Exception:
        error_msg = (
            "خطا در نمایش تحلیل کاربر."
            if settings.default_lang == "fa"
            else "Error showing user analytics."
        )
        await safe_reply(message, error_msg)


@router.message(Command("ml_insights"))
async def ml_insights_handler(message: Message) -> None:
    """Handler for ML insights command"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /ml_insights command")

        integration_service = await get_integration_service()
        rag_service = integration_service.rag_service
        insights = await rag_service.get_ml_insights()

        if settings.default_lang == "fa":
            msg = "🤖 بینش‌های یادگیری ماشین\n\n"
            if "error" in insights:
                msg += f"❌ {insights['error']}\n"
            else:
                query_patterns = insights.get("query_patterns", {})
                if query_patterns:
                    msg += f"📊 الگوهای پرسش: {query_patterns.get('most_common_queries', [])[:3]}\n"

                popular_topics = insights.get("popular_topics", [])
                if popular_topics:
                    msg += "\n🔥 موضوعات محبوب:\n"
                    for topic in popular_topics[:5]:
                        if hasattr(topic, "name"):
                            msg += f"• {topic.name} (تعداد: {topic.frequency})\n"
        else:
            msg = "🤖 ML Insights\n\n"
            if "error" in insights:
                msg += f"❌ {insights['error']}\n"
            else:
                msg += "ML insights generated successfully\n"

        await safe_reply(message, msg)
    except Exception as e:
        logger.error(f"Error in ML insights: {e}")
        error_msg = (
            "خطا در دریافت بینش‌های ML."
            if settings.default_lang == "fa"
            else "Error getting ML insights."
        )
        await safe_reply(message, error_msg)


@router.message(Command("predictive"))
async def predictive_analytics_handler(message: Message) -> None:
    """Handler for predictive analytics command"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /predictive command")

        integration_service = await get_integration_service()
        rag_service = integration_service.rag_service
        analytics = await rag_service.get_predictive_analytics()

        if settings.default_lang == "fa":
            msg = "🔮 تحلیل‌های پیش‌بینانه\n\n"
            if "error" in analytics:
                msg += f"❌ {analytics['error']}\n"
            else:
                load_pred = analytics.get("load_prediction", {})
                if load_pred:
                    msg += f"📈 پیش‌بینی بار: {load_pred.get('predicted_load', 0):.2f}\n"
                    msg += f"🔒 اطمینان: {load_pred.get('confidence', 0):.2f}\n"

                storage_pred = analytics.get("storage_prediction", {})
                if storage_pred:
                    msg += "\n💾 ذخیره‌سازی:\n"
                    msg += f"• فعلی: {storage_pred.get('current_usage', 0):.1f} GB\n"
                    msg += (
                        f"• پیش‌بینی: {storage_pred.get('predicted_usage', 0):.1f} GB\n"
                    )
                    msg += f"• زمان تا ظرفیت: {storage_pred.get('time_to_capacity', 0)} روز\n"

                anomalies = analytics.get("anomalies", [])
                if anomalies:
                    msg += f"\n⚠️ ناهنجاری‌ها: {len(anomalies)} مورد\n"
        else:
            msg = "🔮 Predictive Analytics\n\n"
            if "error" in analytics:
                msg += f"❌ {analytics['error']}\n"
            else:
                msg += "Predictive analytics generated successfully\n"

        await safe_reply(message, msg)
    except Exception as e:
        logger.error(f"Error in predictive analytics: {e}")
        error_msg = (
            "خطا در دریافت تحلیل‌های پیش‌بینانه."
            if settings.default_lang == "fa"
            else "Error getting predictive analytics."
        )
        await safe_reply(message, error_msg)


@router.message(Command("comprehensive_analytics"))
async def comprehensive_analytics_handler(message: Message) -> None:
    """Handler for comprehensive analytics report command"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /comprehensive_analytics command")

        integration_service = await get_integration_service()
        rag_service = integration_service.rag_service
        report = await rag_service.get_comprehensive_analytics_report(30)

        if settings.default_lang == "fa":
            msg = "📊 گزارش جامع تحلیل (30 روز)\n\n"
            if "error" in report:
                msg += f"❌ {report['error']}\n"
            else:
                summary = report.get("summary", {})
                msg += f"👥 کاربران: {summary.get('total_users', 0)}\n"
                msg += f"📝 بخش‌ها: {summary.get('user_segments_count', 0)}\n"
                msg += f"⚠️ کاربران پرخطر: {summary.get('high_risk_users', 0)}\n\n"

                features = summary.get("features_enabled", {})
                msg += "✅ قابلیت‌های فعال:\n"
                if features.get("ml_insights"):
                    msg += "• بینش‌های ML\n"
                if features.get("predictive_analytics"):
                    msg += "• تحلیل پیش‌بینانه\n"
                if features.get("user_segmentation"):
                    msg += "• بخش‌بندی کاربران\n"
                if features.get("churn_prediction"):
                    msg += "• پیش‌بینی ترک\n"
        else:
            msg = "📊 Comprehensive Analytics Report (30 days)\n\n"
            if "error" in report:
                msg += f"❌ {report['error']}\n"
            else:
                msg += "Comprehensive report generated successfully\n"

        await safe_reply(message, msg)
    except Exception as e:
        logger.error(f"Error in comprehensive analytics: {e}")
        error_msg = (
            "خطا در دریافت گزارش جامع."
            if settings.default_lang == "fa"
            else "Error getting comprehensive report."
        )
        await safe_reply(message, error_msg)
