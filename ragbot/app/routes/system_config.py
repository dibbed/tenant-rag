"""System status and configuration related handlers."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

from .utils import (
    get_rag_service,
    is_user_authorized,
    safe_log_error,
    safe_reply,
)

router = Router()


@router.message(Command("status"))
async def status_handler(message: Message) -> None:
    try:
        user_id = message.from_user.id if message.from_user else 0

        logger.info(f"User {user_id} used /status command")

        rag_service = await get_rag_service()
        health_status = await rag_service.get_health_status()

        if settings.default_lang == "fa":
            status_msg = "📊 وضعیت سیستم\n\n"
            status_msg += f"🔋 وضعیت کلی: {health_status.overall_status}\n"
            status_msg += f"⏰ زمان بررسی: {health_status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_msg += f"🕐 مدت فعالیت: {health_status.uptime:.1f} ثانیه\n\n"
            status_msg += "🔧 وضعیت اجزا:\n"
            for component, health in health_status.components.items():
                status_emoji = "✅" if health.status == "healthy" else "❌"
                status_msg += f"{status_emoji} {component}: {health.status}\n"
                if health.response_time:
                    status_msg += f"   ⚡ زمان پاسخ: {health.response_time:.2f}ms\n"
        else:
            status_msg = "📊 System Status\n\n"
            status_msg += f"🔋 Overall Status: {health_status.overall_status}\n"
            status_msg += f"⏰ Check Time: {health_status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_msg += f"🕐 Uptime: {health_status.uptime:.1f} seconds\n\n"
            status_msg += "🔧 Component Status:\n"
            for component, health in health_status.components.items():
                status_emoji = "✅" if health.status == "healthy" else "❌"
                status_msg += f"{status_emoji} {component}: {health.status}\n"
                if health.response_time:
                    status_msg += f"   ⚡ Response Time: {health.response_time:.2f}ms\n"

        await safe_reply(message, status_msg)
    except Exception as e:
        logger.error(f"Error in status_handler for user {user_id}: {e}")
        error_msg = (
            "خطا در نمایش وضعیت."
            if settings.default_lang == "fa"
            else "Error showing status."
        )
        await safe_reply(message, error_msg)


@router.message(Command("config"))
async def config_handler(message: Message) -> None:
    try:
        if settings.default_lang == "fa":
            msg = (
                "⚙️ تنظیمات فعلی ربات:\n\n"
                f"🌐 زبان پیش‌فرض: {settings.default_lang}\n"
                f"🔎 OCR فعال: {'بله' if settings.rag.ocr_enabled else 'خیر'}\n"
                f"🧠 موتور OCR: {settings.rag.ocr_engine}\n"
                f"🗣️ زبان OCR: {settings.rag.ocr_lang}"
            )
        else:
            msg = (
                "⚙️ Current Bot Configuration:\n\n"
                f"🌐 Default language: {settings.default_lang}\n"
                f"🔎 OCR enabled: {bool(settings.rag.ocr_enabled)}\n"
                f"🧠 OCR engine: {settings.rag.ocr_engine}\n"
                f"🗣️ OCR language: {settings.rag.ocr_lang}"
            )
        await safe_reply(message, msg)
    except Exception as e:
        error_msg = (
            "خطا در نمایش تنظیمات."
            if settings.default_lang == "fa"
            else "Error showing config."
        )
        await safe_reply(message, error_msg)
        await safe_log_error(error=e, context="config_handler")


@router.message(Command("ocron"))
async def ocr_on_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        if not is_user_authorized(user_id):
            return await safe_reply(message, "⛔ Unauthorized.")
        settings.rag.ocr_enabled = True  # type: ignore[attr-defined]
        msg = "🔎 OCR enabled." if settings.default_lang != "fa" else "🔎 OCR فعال شد."
        await safe_reply(message, msg)
    except Exception as e:
        await safe_reply(message, "Error toggling OCR.")
        await safe_log_error(error=e, context="ocr_on_handler", user_id=user_id)


@router.message(Command("ocroff"))
async def ocr_off_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        if not is_user_authorized(user_id):
            return await safe_reply(message, "⛔ Unauthorized.")
        settings.rag.ocr_enabled = False  # type: ignore[attr-defined]
        msg = (
            "🔎 OCR disabled."
            if settings.default_lang != "fa"
            else "🔎 OCR غیرفعال شد."
        )
        await safe_reply(message, msg)
    except Exception as e:
        await safe_reply(message, "Error toggling OCR.")
        await safe_log_error(error=e, context="ocr_off_handler", user_id=user_id)


@router.message(Command("setocr"))
async def set_ocr_engine_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        if not is_user_authorized(user_id):
            return await safe_reply(message, "⛔ Unauthorized.")
        text = message.text or ""
        parts = text.strip().split()
        if len(parts) < 2:
            return await safe_reply(
                message, "Usage: /setocr <none|pytesseract|easyocr|google>"
            )
        engine = parts[1].lower()
        if engine not in {"none", "pytesseract", "easyocr", "google"}:
            return await safe_reply(message, "Invalid engine.")
        settings.rag.ocr_engine = engine  # type: ignore[attr-defined]
        msg = (
            f"🧠 OCR engine set to: {engine}"
            if settings.default_lang != "fa"
            else f"🧠 موتور OCR تنظیم شد: {engine}"
        )
        await safe_reply(message, msg)
    except Exception as e:
        await safe_reply(message, "Error setting OCR engine.")
        await safe_log_error(error=e, context="set_ocr_engine_handler", user_id=user_id)
