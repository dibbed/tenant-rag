"""Supported formats handler."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

from .utils import get_document_service, safe_log_error, safe_reply

router = Router()


@router.message(Command("formats"))
async def formats_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0

    try:
        doc_service = await get_document_service()
        supported_formats = await doc_service.get_supported_formats()

        if settings.default_lang == "fa":
            response = "📚 فرمت‌های پشتیبانی شده:\n\n"
        else:
            response = "📚 Supported File Formats:\n\n"

        for format_ext, description in supported_formats.items():
            if format_ext == "url":
                response += f"🌐 {format_ext}: {description}\n"
            elif format_ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                response += f"🖼️ {format_ext}: {description}\n"
            elif format_ext in [".pptx", ".xlsx"]:
                response += f"📊 {format_ext}: {description}\n"
            elif format_ext in [".html", ".htm"]:
                response += f"🌐 {format_ext}: {description}\n"
            elif format_ext == ".md":
                response += f"📝 {format_ext}: {description}\n"
            else:
                response += f"📄 {format_ext}: {description}\n"

        if settings.default_lang == "fa":
            response += "\n💡 می‌توانید فایل‌های خود را با این فرمت‌ها ارسال کنید."
        else:
            response += "\n💡 You can send files with these formats."

        await safe_reply(message, response)
        logger.log_user_action(user_id=user_id, action="formats_command")
    except Exception as e:
        error_msg = (
            "❌ خطا در دریافت لیست فرمت‌ها."
            if settings.default_lang == "fa"
            else "❌ Error getting supported formats."
        )
        await safe_reply(message, error_msg)
        await safe_log_error(error=e, context="formats_handler", user_id=user_id)
