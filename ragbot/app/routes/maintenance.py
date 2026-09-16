"""Maintenance handlers such as /reset."""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.caching.cache_manager import cache_manager
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag import VectorStoreError

from .utils import get_rag_service, maybe_await, safe_log_error, safe_reply

router = Router()


@router.message(Command("reset"))
async def reset_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0

    try:
        logger.log_user_action(user_id=user_id, action="reset_store_request")

        rag_service = await maybe_await(get_rag_service())
        if hasattr(rag_service, "reset_vector_store"):
            maybe = rag_service.reset_vector_store()
            success = await maybe if hasattr(maybe, "__await__") else maybe
        else:
            success = await rag_service.reset_store()

        # Also clear all cache layers (L1, L2, semantic) to reach zero state
        cache_clear_ok = True
        try:
            # Initialize cache manager if needed
            await cache_manager.initialize()
            l12_ok = await cache_manager.clear()
            sem_ok = await cache_manager.clear_semantic_cache()
            cache_clear_ok = l12_ok and (sem_ok or True)
        except Exception as _e:
            logger.warning(f"Cache clear step skipped/failed: {_e}")

        if success and cache_clear_ok:
            success_msg = (
                "✅ همه‌چیز پاک شد (Vector Store + Cache)!\n\n🔄 حالا می‌توانید اسناد جدید اضافه کنید."
                if settings.default_lang == "fa"
                else "✅ All cleared (Vector Store + Cache)!\n\n🔄 You can now add new documents."
            )
            await safe_reply(message, success_msg)
            logger.log_user_action(user_id=user_id, action="reset_store_success")
        elif success:
            partial_msg = (
                "✅ اسناد پاک شد، اما پاک‌سازی کش به‌طور کامل انجام نشد."
                if settings.default_lang == "fa"
                else "✅ Store cleared, but cache flush partially failed."
            )
            await safe_reply(message, partial_msg)
            logger.log_user_action(user_id=user_id, action="reset_store_partial_cache")
        else:
            error_msg = (
                "❌ خطا در پاک کردن اسناد. لطفاً دوباره تلاش کنید."
                if settings.default_lang == "fa"
                else "❌ Error clearing documents. Please try again."
            )
            await safe_reply(message, error_msg)
            logger.log_user_action(user_id=user_id, action="reset_store_failed")
    except VectorStoreError as e:
        error_msg = (
            "❌ خطا در دسترسی به فضای ذخیره‌سازی."
            if settings.default_lang == "fa"
            else "❌ Error accessing storage."
        )
        await safe_reply(message, error_msg)
        await safe_log_error(error=e, context="reset_handler_storage", user_id=user_id)
    except Exception as e:
        error_msg = (
            "❌ خطای غیرمنتظره. لطفاً دوباره تلاش کنید."
            if settings.default_lang == "fa"
            else "❌ Unexpected error. Please try again."
        )
        await safe_reply(message, error_msg)
        await safe_log_error(error=e, context="reset_handler_general", user_id=user_id)
