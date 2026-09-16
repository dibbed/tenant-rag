"""Plugin management handlers."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

from .utils import (
    check_rate_limit,
    get_rag_service,
    is_user_authorized,
    safe_log_error,
    safe_reply,
)

router = Router()


@router.message(Command("load_plugin"))
async def load_plugin_handler(message: Message) -> None:
    """Handle plugin loading requests."""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.log_user_action(user_id=user_id, action="load_plugin_start")
        logger.info("load_plugin_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse plugin path from message
        command_text = (
            message.text.replace("/load_plugin", "").strip() if message.text else ""
        )
        if not command_text:
            error_msg = (
                "❓ لطفاً مسیر فایل plugin را بعد از دستور /load_plugin بنویسید.\n"
                "مثال: /load_plugin plugins/my_plugin.py"
                if settings.default_lang == "fa"
                else "❓ Please write plugin file path after /load_plugin command.\n"
                "Example: /load_plugin plugins/my_plugin.py"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🔌 در حال بارگذاری plugin..."
            if settings.default_lang == "fa"
            else "🔌 Loading plugin..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService plugin loading functionality
        if hasattr(rag_service, "load_plugin"):
            try:
                result = await rag_service.load_plugin(command_text)

                if result.get("success"):
                    response_msg = (
                        f"✅ Plugin با موفقیت بارگذاری شد!\n"
                        f"شناسه Plugin: {result.get('plugin_id', 'N/A')}\n"
                        f"وضعیت: {result.get('status', 'N/A')}\n"
                        f"مسیر: {command_text}"
                        if settings.default_lang == "fa"
                        else f"✅ Plugin loaded successfully!\n"
                        f"Plugin ID: {result.get('plugin_id', 'N/A')}\n"
                        f"Status: {result.get('status', 'N/A')}\n"
                        f"Path: {command_text}"
                    )
                else:
                    response_msg = (
                        f"❌ خطا در بارگذاری plugin: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Plugin loading error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Plugin loading failed: {e}")
                error_msg = (
                    f"❌ خطا در بارگذاری plugin: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Plugin loading error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت plugin loading فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Plugin loading feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "load_plugin_handler")


@router.message(Command("unload_plugin"))
async def unload_plugin_handler(message: Message) -> None:
    """Handle plugin unloading requests."""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.log_user_action(user_id=user_id, action="unload_plugin_start")
        logger.info("unload_plugin_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse plugin ID from message
        command_text = (
            message.text.replace("/unload_plugin", "").strip() if message.text else ""
        )
        if not command_text:
            error_msg = (
                "❓ لطفاً شناسه plugin را بعد از دستور /unload_plugin بنویسید.\n"
                "مثال: /unload_plugin my_plugin"
                if settings.default_lang == "fa"
                else "❓ Please write plugin ID after /unload_plugin command.\n"
                "Example: /unload_plugin my_plugin"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🔌 در حال برداشتن plugin..."
            if settings.default_lang == "fa"
            else "🔌 Unloading plugin..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService plugin unloading functionality
        if hasattr(rag_service, "unload_plugin"):
            try:
                result = await rag_service.unload_plugin(command_text)

                if result.get("success"):
                    response_msg = (
                        f"✅ Plugin با موفقیت برداشته شد!\n"
                        f"شناسه Plugin: {result.get('plugin_id', 'N/A')}\n"
                        f"وضعیت: {result.get('status', 'N/A')}"
                        if settings.default_lang == "fa"
                        else f"✅ Plugin unloaded successfully!\n"
                        f"Plugin ID: {result.get('plugin_id', 'N/A')}\n"
                        f"Status: {result.get('status', 'N/A')}"
                    )
                else:
                    response_msg = (
                        f"❌ خطا در برداشتن plugin: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Plugin unloading error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Plugin unloading failed: {e}")
                error_msg = (
                    f"❌ خطا در برداشتن plugin: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Plugin unloading error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت plugin unloading فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Plugin unloading feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "unload_plugin_handler")


@router.message(Command("list_plugins"))
async def list_plugins_handler(message: Message) -> None:
    """Handle plugin listing requests."""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.log_user_action(user_id=user_id, action="list_plugins_start")
        logger.info("list_plugins_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        processing_msg = (
            "📋 در حال دریافت لیست plugins..."
            if settings.default_lang == "fa"
            else "📋 Retrieving plugin list..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService plugin listing functionality
        if hasattr(rag_service, "list_plugins"):
            try:
                result = await rag_service.list_plugins()

                if result.get("success"):
                    plugins = result.get("plugins", {})
                    plugin_count = result.get("count", 0)

                    if plugin_count > 0:
                        response_msg = (
                            f"📋 لیست Plugins ({plugin_count} مورد):\n\n"
                            if settings.default_lang == "fa"
                            else f"📋 Plugin List ({plugin_count} items):\n\n"
                        )

                        # Show first few plugins (limit to avoid message length issues)
                        for i, (plugin_id, plugin_info) in enumerate(
                            list(plugins.items())[:5]
                        ):
                            status = plugin_info.get("status", "unknown")
                            name = plugin_info.get("metadata", {}).get(
                                "name", plugin_id
                            )

                            response_msg += (
                                f"{i + 1}. {name} ({plugin_id})\n"
                                f"   وضعیت: {status}\n"
                                f"   نوع: {plugin_info.get('metadata', {}).get('type', 'N/A')}\n\n"
                                if settings.default_lang == "fa"
                                else f"{i + 1}. {name} ({plugin_id})\n"
                                f"   Status: {status}\n"
                                f"   Type: {plugin_info.get('metadata', {}).get('type', 'N/A')}\n\n"
                            )

                        if plugin_count > 5:
                            response_msg += (
                                f"... و {plugin_count - 5} plugin دیگر"
                                if settings.default_lang == "fa"
                                else f"... and {plugin_count - 5} more plugins"
                            )
                    else:
                        response_msg = (
                            "📋 هیچ plugin نصب شده ای پیدا نشد."
                            if settings.default_lang == "fa"
                            else "📋 No installed plugins found."
                        )
                else:
                    response_msg = (
                        f"❌ خطا در دریافت لیست plugins: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Plugin listing error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Plugin listing failed: {e}")
                error_msg = (
                    f"❌ خطا در دریافت لیست plugins: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Plugin listing error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت plugin listing فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Plugin listing feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "list_plugins_handler")


@router.message(Command("plugin_status"))
async def plugin_status_handler(message: Message) -> None:
    """Handle plugin status requests."""
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.log_user_action(user_id=user_id, action="plugin_status_start")
        logger.info("plugin_status_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse plugin ID from message
        command_text = (
            message.text.replace("/plugin_status", "").strip() if message.text else ""
        )
        if not command_text:
            error_msg = (
                "❓ لطفاً شناسه plugin را بعد از دستور /plugin_status بنویسید.\n"
                "مثال: /plugin_status my_plugin"
                if settings.default_lang == "fa"
                else "❓ Please write plugin ID after /plugin_status command.\n"
                "Example: /plugin_status my_plugin"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🔍 در حال بررسی وضعیت plugin..."
            if settings.default_lang == "fa"
            else "🔍 Checking plugin status..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService plugin status functionality
        if hasattr(rag_service, "get_plugin_status"):
            try:
                result = await rag_service.get_plugin_status(command_text)

                if result.get("success"):
                    status = result.get("status", "unknown")
                    response_msg = (
                        f"🔍 وضعیت Plugin:\n"
                        f"شناسه: {result.get('plugin_id', 'N/A')}\n"
                        f"وضعیت: {status}"
                        if settings.default_lang == "fa"
                        else f"🔍 Plugin Status:\n"
                        f"ID: {result.get('plugin_id', 'N/A')}\n"
                        f"Status: {status}"
                    )
                else:
                    response_msg = (
                        f"❌ خطا در دریافت وضعیت plugin: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Plugin status error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Plugin status check failed: {e}")
                error_msg = (
                    f"❌ خطا در بررسی وضعیت plugin: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Plugin status check error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت plugin status فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Plugin status feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "plugin_status_handler")
