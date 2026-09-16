"""Comprehensive analytics report handler."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

from .utils import get_integration_service, safe_reply

router = Router()


@router.message(Command("report"))
async def report_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /report command")
        integration_service = await get_integration_service()
        report = await integration_service.get_analytics_report(days=30)

        if settings.default_lang == "fa":
            report_msg = "📊 گزارش جامع تحلیل\n\n"
            if "error" in report:
                report_msg += f"❌ خطا در گزارش: {report['error']}\n"
            else:
                summary = report.get("summary", {})
                health_assessment = report.get("health_assessment", {})
                recommendations = report.get("recommendations", [])
                report_msg += "📈 خلاصه کلیدی:\n"
                report_msg += f"👥 کل کاربران: {summary.get('total_users', 0)}\n"
                report_msg += f"❓ کل پرسش‌ها: {summary.get('total_queries', 0)}\n"
                report_msg += (
                    f"⭐ رضایت کلی: {summary.get('overall_satisfaction', 0):.1f}\n"
                )
                report_msg += (
                    f"🔄 کل فعالیت‌ها: {summary.get('total_activities', 0)}\n\n"
                )
                if health_assessment:
                    report_msg += "🏥 سلامت سیستم:\n"
                    report_msg += (
                        f"📊 وضعیت: {health_assessment.get('status', 'نامشخص')}\n"
                    )
                    report_msg += (
                        f"🎯 امتیاز: {health_assessment.get('score', 0)}/100\n"
                    )
                    report_msg += (
                        f"📝 توضیح: {health_assessment.get('description', '')}\n\n"
                    )
                if recommendations:
                    report_msg += "💡 توصیه‌های بهبود:\n"
                    for rec in recommendations[:5]:
                        report_msg += f"• {rec}\n"
        else:
            report_msg = "📊 Comprehensive Analytics Report\n\n"
            if "error" in report:
                report_msg += f"❌ Report Error: {report['error']}\n"
            else:
                summary = report.get("summary", {})
                health_assessment = report.get("health_assessment", {})
                recommendations = report.get("recommendations", [])
                report_msg += "📈 Key Summary:\n"
                report_msg += f"👥 Total Users: {summary.get('total_users', 0)}\n"
                report_msg += f"❓ Total Queries: {summary.get('total_queries', 0)}\n"
                report_msg += f"⭐ Overall Satisfaction: {summary.get('overall_satisfaction', 0):.1f}\n"
                report_msg += (
                    f"🔄 Total Activities: {summary.get('total_activities', 0)}\n\n"
                )
                if health_assessment:
                    report_msg += "🏥 System Health:\n"
                    report_msg += (
                        f"📊 Status: {health_assessment.get('status', 'unknown')}\n"
                    )
                    report_msg += f"🎯 Score: {health_assessment.get('score', 0)}/100\n"
                    report_msg += f"📝 Description: {health_assessment.get('description', '')}\n\n"
                if recommendations:
                    report_msg += "💡 Improvement Recommendations:\n"
                    for rec in recommendations[:5]:
                        report_msg += f"• {rec}\n"

        await safe_reply(message, report_msg)
    except Exception:
        error_msg = (
            "خطا در نمایش گزارش تحلیل."
            if settings.default_lang == "fa"
            else "Error showing analytics report."
        )
        await safe_reply(message, error_msg)
