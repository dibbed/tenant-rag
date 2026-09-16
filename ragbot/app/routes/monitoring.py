"""
Monitoring routes: on-demand health and monitoring status commands.
"""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.monitoring.health_checker import HealthChecker
from ragbot.monitoring.real_time_monitor import RealTimeMonitor
from ragbot.outputs.logger import logger
from ragbot.services.graceful_degradation import graceful_degradation
from ragbot.app.ui.manager import ui_manager

from .utils import safe_reply_with_kb

router = Router()


@router.message(Command("health"))
async def health_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        logger.info(f"User {user_id} used /health command")
        checker = HealthChecker()
        await checker._run_all_checks()  # run one round
        status = await checker.get_health_status()

        # Get graceful degradation metrics
        gd_metrics = graceful_degradation.get_performance_metrics()
        gd_status = graceful_degradation.get_system_status()

        if settings.default_lang == "fa":
            status_msg = "🩺 وضعیت سلامت سیستم\n\n"
            status_msg += f"وضعیت کلی: {status.get('overall_status', 'unknown')}\n"
            checks = status.get("checks", {})
            for name, info in checks.items():
                status_msg += f"- {name}: {info.get('status', 'unknown')}\n"

            # Add graceful degradation status
            status_msg += "\n🛡️ وضعیت Graceful Degradation:\n"
            status_msg += f"وضعیت کلی: {gd_status.get('overall_status', 'unknown')}\n"
            status_msg += f"سرویس‌های سالم: {gd_status.get('healthy_services', 0)}\n"
            status_msg += (
                f"سرویس‌های دچار افت: {gd_status.get('degraded_services', 0)}\n"
            )
            status_msg += f"سرویس‌های بحرانی: {gd_status.get('critical_services', 0)}\n"

            # Add fallback counts
            fallback_counts = gd_metrics.get("fallback_counts", {})
            if fallback_counts:
                status_msg += "\n🔄 تعداد Fallback‌ها:\n"
                for service, count in fallback_counts.items():
                    if count > 0:
                        status_msg += f"  - {service}: {count}\n"
        else:
            status_msg = "🩺 System Health Status\n\n"
            status_msg += f"Overall: {status.get('overall_status', 'unknown')}\n"
            checks = status.get("checks", {})
            for name, info in checks.items():
                status_msg += f"- {name}: {info.get('status', 'unknown')}\n"

            # Add graceful degradation status
            status_msg += "\n🛡️ Graceful Degradation Status:\n"
            status_msg += (
                f"Overall Status: {gd_status.get('overall_status', 'unknown')}\n"
            )
            status_msg += f"Healthy Services: {gd_status.get('healthy_services', 0)}\n"
            status_msg += (
                f"Degraded Services: {gd_status.get('degraded_services', 0)}\n"
            )
            status_msg += (
                f"Critical Services: {gd_status.get('critical_services', 0)}\n"
            )

            # Add fallback counts
            fallback_counts = gd_metrics.get("fallback_counts", {})
            if fallback_counts:
                status_msg += "\n🔄 Fallback Counts:\n"
                for service, count in fallback_counts.items():
                    if count > 0:
                        status_msg += f"  - {service}: {count}\n"

        await safe_reply_with_kb(message, status_msg, ui_manager.monitoring_keyboard)
    except Exception as e:
        logger.error(f"/health failed: {e}")
        await safe_reply_with_kb(
            message,
            "خطا در دریافت وضعیت سلامت"
            if settings.default_lang == "fa"
            else "Error getting health status",
            ui_manager.monitoring_keyboard,
        )


@router.message(Command("monitoring"))
async def monitoring_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        logger.info(f"User {user_id} used /monitoring command")
        monitor = RealTimeMonitor(check_interval=1)
        await monitor.start_monitoring()
        # allow a brief collection
        # avoid long sleep in handler to keep responsiveness
        import asyncio

        await asyncio.sleep(1)
        status = await monitor.get_current_status()
        await monitor.stop_monitoring()

        metrics = status.get("metrics", {}) if status else {}

        # Get graceful degradation metrics
        gd_metrics = graceful_degradation.get_performance_metrics()
        gd_status = graceful_degradation.get_system_status()
        if settings.default_lang == "fa":
            msg = "📊 وضعیت مانیتورینگ لحظه‌ای\n\n"
            if status.get("no_data"):
                msg += "داده‌ای در دسترس نیست"
            else:
                msg += f"سلامت سیستم: {status.get('system_health', 'unknown')}\n"
                msg += f"CPU: {metrics.get('cpu_usage', 0):.1f}%\n"
                msg += f"حافظه: {metrics.get('memory_usage', 0):.1f}%\n"
                msg += f"دیسک: {metrics.get('disk_usage', 0):.1f}%\n"
                msg += f"زمان پاسخ (ms): {metrics.get('response_time', 0):.1f}\n"
                msg += f"نرخ خطا (%): {metrics.get('error_rate', 0):.1f}\n"

                # Add graceful degradation status
                msg += "\n🛡️ وضعیت Graceful Degradation:\n"
                msg += f"وضعیت کلی: {gd_status.get('overall_status', 'unknown')}\n"
                msg += f"سرویس‌های سالم: {gd_status.get('healthy_services', 0)}\n"
                msg += f"سرویس‌های دچار افت: {gd_status.get('degraded_services', 0)}\n"
                msg += f"سرویس‌های بحرانی: {gd_status.get('critical_services', 0)}\n"

                # Add fallback counts
                fallback_counts = gd_metrics.get("fallback_counts", {})
                if fallback_counts:
                    msg += "\n🔄 تعداد Fallback‌ها:\n"
                    for service, count in fallback_counts.items():
                        if count > 0:
                            msg += f"  - {service}: {count}\n"
        else:
            msg = "📊 Real-time Monitoring Status\n\n"
            if status.get("no_data"):
                msg += "No data available"
            else:
                msg += f"System health: {status.get('system_health', 'unknown')}\n"
                msg += f"CPU: {metrics.get('cpu_usage', 0):.1f}%\n"
                msg += f"Memory: {metrics.get('memory_usage', 0):.1f}%\n"
                msg += f"Disk: {metrics.get('disk_usage', 0):.1f}%\n"
                msg += f"Response time (ms): {metrics.get('response_time', 0):.1f}\n"
                msg += f"Error rate (%): {metrics.get('error_rate', 0):.1f}\n"

                # Add graceful degradation status
                msg += "\n🛡️ Graceful Degradation Status:\n"
                msg += f"Overall Status: {gd_status.get('overall_status', 'unknown')}\n"
                msg += f"Healthy Services: {gd_status.get('healthy_services', 0)}\n"
                msg += f"Degraded Services: {gd_status.get('degraded_services', 0)}\n"
                msg += f"Critical Services: {gd_status.get('critical_services', 0)}\n"

                # Add fallback counts
                fallback_counts = gd_metrics.get("fallback_counts", {})
                if fallback_counts:
                    msg += "\n🔄 Fallback Counts:\n"
                    for service, count in fallback_counts.items():
                        if count > 0:
                            msg += f"  - {service}: {count}\n"

        await safe_reply_with_kb(message, msg, ui_manager.monitoring_keyboard)
    except Exception as e:
        logger.error(f"/monitoring failed: {e}")
        await safe_reply_with_kb(
            message,
            "خطا در دریافت وضعیت مانیتورینگ"
            if settings.default_lang == "fa"
            else "Error getting monitoring status",
            ui_manager.monitoring_keyboard,
        )
