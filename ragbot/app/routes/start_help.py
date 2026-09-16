"""Start and Help command handlers."""

import time
from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.app.ui.manager import ui_manager
from ragbot.utils.timing import PerformanceTimer, log_timing_details

from .utils import safe_reply, safe_reply_with_kb

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    # Start timing
    timer = PerformanceTimer()
    timer.start()

    try:
        user_id = message.from_user.id if message.from_user else None
        username = message.from_user.username if message.from_user else "unknown"

        timer.checkpoint("message_received")
        logger.info(f"User {user_id} ({username}) used /start command")

        # Use UI manager to format welcome message
        timer.checkpoint("ui_format_start")
        welcome_msg = ui_manager.format_message("welcome")
        timer.checkpoint("ui_format_end")

        # Get appropriate keyboard based on user role
        timer.checkpoint("keyboard_generation_start")
        keyboard = ui_manager.get_main_keyboard_for_user(user_id)
        timer.checkpoint("keyboard_generation_end")

        # Send welcome message with appropriate keyboard
        timer.checkpoint("send_message_start")
        await safe_reply_with_kb(message, welcome_msg, keyboard)
        timer.checkpoint("send_message_end")

        # Log timing details
        duration = timer.end()
        log_timing_details("start_command", user_id, duration, timer.checkpoints)

    except Exception as e:
        timer.end()
        logger.error(f"Error in start_handler for user {user_id}: {e}")
        error_msg = (
            "خطا در شروع ربات."
            if settings.default_lang == "fa"
            else "Error starting bot."
        )
        await safe_reply(message, error_msg)


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    try:
        user_id = message.from_user.id if message.from_user else 0

        logger.info(f"User {user_id} used /help command")

        help_msg = ui_manager.format_message("help")
        await safe_reply_with_kb(message, help_msg, ui_manager.help_keyboard)
    except Exception as e:
        logger.error(f"Error in help_handler for user {user_id}: {e}")
        error_msg = (
            "خطا در نمایش راهنما."
            if settings.default_lang == "fa"
            else "Error showing help."
        )
        await safe_reply(message, error_msg)
