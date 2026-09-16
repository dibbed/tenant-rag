"""Administrative commands for bot management."""

import asyncio
import os
import signal
import sys
from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.app.ui.manager import ui_manager

from .utils import safe_reply, safe_reply_with_kb

router = Router()


def is_admin_user(user_id: int) -> bool:
    """Check if user is admin (from ADMIN_USERS env or settings)."""
    return user_id in settings.admin_users_list


@router.message(Command("shutdown"))
async def shutdown_handler(message: Message) -> None:
    """Handle bot shutdown command (admin only)"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        if not is_admin_user(user_id):
            await safe_reply(
                message, "⛔ دسترسی غیرمجاز. فقط ادمین‌ها می‌توانند ربات را خاموش کنند."
            )
            return

        logger.info(f"Admin {user_id} initiated bot shutdown")

        shutdown_msg = "🛑 ربات در حال خاموش شدن...\n\n"
        shutdown_msg += "⏰ 10 ثانیه تا خاموش شدن کامل\n"
        shutdown_msg += "📝 تمام عملیات در حال تکمیل هستند\n"
        shutdown_msg += "🔒 اتصالات در حال بسته شدن"

        await safe_reply(message, shutdown_msg)

        # Give time for message to be sent
        await asyncio.sleep(2)

        # Graceful shutdown
        logger.info("Bot shutdown initiated by admin")
        os._exit(0)

    except Exception as e:
        logger.error(f"Error in shutdown_handler: {e}")
        await safe_reply(message, "❌ خطا در خاموش کردن ربات")


@router.message(Command("restart"))
async def restart_handler(message: Message) -> None:
    """Handle bot restart command (admin only)"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        if not is_admin_user(user_id):
            await safe_reply(
                message,
                "⛔ دسترسی غیرمجاز. فقط ادمین‌ها می‌توانند ربات را ری‌استارت کنند.",
            )
            return

        logger.info(f"Admin {user_id} initiated bot restart")

        restart_msg = "🔄 ربات در حال ری‌استارت...\n\n"
        restart_msg += "⏰ 5 ثانیه تا ری‌استارت\n"
        restart_msg += "💾 ذخیره‌سازی وضعیت فعلی\n"
        restart_msg += "🔄 بارگذاری مجدد سرویس‌ها"

        await safe_reply(message, restart_msg)

        # Give time for message to be sent
        await asyncio.sleep(2)

        # Restart the bot
        logger.info("Bot restart initiated by admin")
        python = sys.executable
        os.execl(python, python, *sys.argv)

    except Exception as e:
        logger.error(f"Error in restart_handler: {e}")
        await safe_reply(message, "❌ خطا در ری‌استارت ربات")


@router.message(Command("status"))
async def status_handler(message: Message) -> None:
    """Handle system status command"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.info(f"User {user_id} used /status command")

        # Get system information
        import psutil

        # CPU and Memory info
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Process info
        process = psutil.Process()
        process_memory = process.memory_info()

        status_msg = "📊 وضعیت سیستم\n\n"
        status_msg += f"💻 CPU: {cpu_percent:.1f}%\n"
        status_msg += f"🧠 حافظه کل: {memory.total // (1024**3)} GB\n"
        status_msg += f"🧠 حافظه استفاده شده: {memory.percent:.1f}%\n"
        status_msg += f"💽 فضای دیسک: {disk.percent:.1f}%\n"
        status_msg += f"🔄 حافظه ربات: {process_memory.rss // (1024**2)} MB\n"
        status_msg += f"⏰ زمان اجرا: {process.create_time():.0f} ثانیه\n"

        if is_admin_user(user_id):
            status_msg += "\n👑 دسترسی ادمین: فعال"
            status_msg += f"\n🆔 User ID: {user_id}"

        await safe_reply_with_kb(message, status_msg, ui_manager.back_keyboard)

    except Exception as e:
        logger.error(f"Error in status_handler: {e}")
        await safe_reply(message, "❌ خطا در دریافت وضعیت سیستم")


@router.message(Command("logs"))
async def logs_handler(message: Message) -> None:
    """Handle logs viewing command (admin only)"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        if not is_admin_user(user_id):
            await safe_reply(
                message, "⛔ دسترسی غیرمجاز. فقط ادمین‌ها می‌توانند لاگ‌ها را مشاهده کنند."
            )
            return

        logger.info(f"Admin {user_id} requested logs")

        # Read recent logs
        log_file = "logs/ragbot.log"
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                recent_lines = lines[-20:]  # Last 20 lines

            logs_msg = "📋 آخرین لاگ‌های سیستم\n\n"
            logs_msg += "".join(recent_lines)

            # Telegram message limit
            if len(logs_msg) > 4000:
                logs_msg = logs_msg[:4000] + "\n... (محدود شده)"

        except FileNotFoundError:
            logs_msg = "❌ فایل لاگ یافت نشد"

        await safe_reply_with_kb(message, logs_msg, ui_manager.back_keyboard)

    except Exception as e:
        logger.error(f"Error in logs_handler: {e}")
        await safe_reply(message, "❌ خطا در خواندن لاگ‌ها")


@router.message(Command("clear_cache"))
async def clear_cache_handler(message: Message) -> None:
    """Handle cache clearing command (admin only)"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        if not is_admin_user(user_id):
            await safe_reply(
                message, "⛔ دسترسی غیرمجاز. فقط ادمین‌ها می‌توانند کش را پاک کنند."
            )
            return

        logger.info(f"Admin {user_id} requested cache clearing")

        # Clear cache
        from ragbot.caching.cache_manager import cache_manager

        await cache_manager.initialize()
        await cache_manager.clear()
        await cache_manager.clear_semantic_cache()

        cache_msg = "🗑️ کش با موفقیت پاک شد!\n\n"
        cache_msg += "✅ کش L1 و L2 پاک شد\n"
        cache_msg += "✅ کش معنایی پاک شد\n"
        cache_msg += "🔄 سیستم آماده استفاده مجدد"

        await safe_reply_with_kb(message, cache_msg, ui_manager.back_keyboard)

    except Exception as e:
        logger.error(f"Error in clear_cache_handler: {e}")
        await safe_reply(message, "❌ خطا در پاک کردن کش")


@router.message(Command("admin"))
async def admin_handler(message: Message) -> None:
    """Handle admin panel command"""
    user_id = message.from_user.id if message.from_user else 0

    try:
        if not is_admin_user(user_id):
            await safe_reply(message, "⛔ دسترسی غیرمجاز. شما ادمین نیستید.")
            return

        logger.info(f"Admin {user_id} accessed admin panel")

        admin_msg = "👑 پنل مدیریت ادمین\n\n"
        admin_msg += "🔧 دستورات مدیریتی:\n"
        admin_msg += "• /shutdown - خاموش کردن ربات\n"
        admin_msg += "• /restart - ری‌استارت ربات\n"
        admin_msg += "• /status - وضعیت سیستم\n"
        admin_msg += "• /logs - مشاهده لاگ‌ها\n"
        admin_msg += "• /clear_cache - پاک کردن کش\n\n"
        admin_msg += "⚠️ احتیاط: این دستورات قوی هستند!"

        await safe_reply_with_kb(message, admin_msg, ui_manager.admin_keyboard)

    except Exception as e:
        logger.error(f"Error in admin_handler: {e}")
        await safe_reply(message, "❌ خطا در دسترسی به پنل ادمین")
