"""Performance screen message handler."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.app.ui.manager import ui_manager

from .utils import (
    build_performance_keyboard,
    get_integration_service,
    safe_reply_with_kb,
)

router = Router()


@router.message(Command("performance"))
async def performance_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /performance command")

        integration_service = await get_integration_service()
        perf_summary = await integration_service.get_performance_summary()
        resource_summary = await integration_service.get_resource_summary()
        gd_metrics = await integration_service.get_graceful_degradation_metrics()
        gd_status = await integration_service.get_degradation_system_status()

        # Use UI manager to create performance status message
        status_msg = ui_manager.create_performance_status(perf_summary)

        # Add resource summary
        if "error" not in resource_summary and "no_data" not in resource_summary:
            current = resource_summary.get("current", {})
            averages = resource_summary.get("averages", {})

            if ui_manager.default_language == "fa":
                status_msg += "\n💾 وضعیت منابع:\n"
                status_msg += f"💻 CPU فعلی: {current.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"🧠 حافظه فعلی: {current.get('memory_percent', 0):.1f}%\n"
                )
                status_msg += f"💽 دیسک فعلی: {current.get('disk_usage', 0):.1f}%\n"
                status_msg += f"📊 میانگین CPU: {averages.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"📊 میانگین حافظه: {averages.get('memory_percent', 0):.1f}%\n"
                )
            else:
                status_msg += "\n💾 Resource Status:\n"
                status_msg += f"💻 Current CPU: {current.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"🧠 Current Memory: {current.get('memory_percent', 0):.1f}%\n"
                )
                status_msg += f"💽 Current Disk: {current.get('disk_usage', 0):.1f}%\n"
                status_msg += f"📊 Average CPU: {averages.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"📊 Average Memory: {averages.get('memory_percent', 0):.1f}%\n"
                )

        await safe_reply_with_kb(message, status_msg, ui_manager.performance_keyboard)
    except Exception:
        error_msg = (
            "خطا در نمایش وضعیت عملکرد."
            if settings.default_lang == "fa"
            else "Error showing performance status."
        )
        await safe_reply_with_kb(message, error_msg, ui_manager.performance_keyboard)
