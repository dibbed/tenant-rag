"""Telegram bot setup and dispatcher configuration."""

# Force reload settings to get latest environment variables
import sys
import os
import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from ..outputs.logger import logger
from ..security.content_filter import ContentFilter
from ..security import EncryptionManager, KeyManager, SecureBackupManager
from ..analytics import AnalyticsDashboard
from .middleware.auth import AuthMiddleware
from .middleware.content_middleware import ContentFilterMiddleware
from .routes import router

# Only reload settings if explicitly requested
if os.getenv("RAGBOT_RELOAD_SETTINGS", "false").lower() == "true":
    if "ragbot.configs.settings" in sys.modules:
        del sys.modules["ragbot.configs.settings"]

from ..configs.settings import settings

# Bot instance with token and properties
bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))

# Dispatcher for handling updates
dp = Dispatcher()

# Include router for handlers
dp.include_router(router)

# Add middleware for authentication
dp.message.middleware(AuthMiddleware())

# Optionally add content filter middleware based on settings
if settings.vector_store.enable_content_filtering:
    dp.message.middleware(ContentFilterMiddleware(ContentFilter()))
    dp.callback_query.middleware(ContentFilterMiddleware(ContentFilter()))

# Initialize analytics dashboard
analytics_dashboard = AnalyticsDashboard(settings)


# Add context to bot
@dp.startup()
async def startup_handler():
    """Initialize bot context with components"""
    # Security components
    dp["encryption_manager"] = EncryptionManager()
    dp["key_manager"] = KeyManager()
    dp["backup_manager"] = SecureBackupManager(dp["encryption_manager"])

    # Query components (will be initialized with vector store in routes)
    dp["query_aggregator"] = None  # Will be set in routes
    dp["advanced_filter"] = None  # Will be set in routes
    dp["custom_scorer"] = None  # Will be set in routes
    dp["query_optimizer"] = None  # Will be set in routes

    # Analytics dashboard
    dp["analytics_dashboard"] = analytics_dashboard

    logger.info("Bot context initialized with Advanced Analytics")


async def main(shutdown_manager: Optional[object] = None) -> None:
    """Main bot startup function with graceful shutdown support."""
    logger.info("Starting RAG Telegram Bot")

    try:
        # Start polling with proper shutdown handling
        if shutdown_manager:
            # Use asyncio.wait_for to make polling interruptible
            polling_task = asyncio.create_task(dp.start_polling(bot))

            # Monitor for shutdown requests
            while not polling_task.done():
                if shutdown_manager.is_shutdown_requested():
                    logger.info("Shutdown requested, stopping bot polling...")
                    try:
                        await dp.stop_polling()
                        polling_task.cancel()
                        try:
                            await polling_task
                        except asyncio.CancelledError:
                            pass
                    except Exception as e:
                        logger.warning(f"Error stopping polling: {e}")
                    break
                elif shutdown_manager.is_force_shutdown():
                    logger.warning(
                        "Force shutdown detected, cancelling polling immediately..."
                    )
                    polling_task.cancel()
                    try:
                        await polling_task
                    except asyncio.CancelledError:
                        pass
                    break
                await asyncio.sleep(0.1)
        else:
            # Fallback to regular polling if no shutdown manager
            await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise
    finally:
        logger.info("Bot polling stopped")
