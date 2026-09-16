"""Question Answering handler (/ask)."""

import asyncio

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag import EmbeddingError, VectorStoreError
from ragbot.utils.debug_helpers import log_pydantic_error

from .utils import (
    check_rate_limit,
    get_integration_service,
    get_rag_service,
    is_user_authorized,
    safe_log_error,
    safe_reply,
)

router = Router()


@router.message(Command("ask"))
async def ask_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="ask_question_start")
        logger.info("ask_handler invoked", user_id=user_id)

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

        question = message.text.replace("/ask", "").strip() if message.text else ""
        if not question:
            error_msg = (
                "❓ لطفاً سوال خود را بعد از دستور /ask بنویسید.\n"
                "مثال: /ask این سند در مورد چه موضوعی است؟"
                if settings.default_lang == "fa"
                else "❓ Please write your question after the /ask command.\n"
                "Example: /ask What is this document about?"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🤔 در حال جستجو و تولید پاسخ..."
            if settings.default_lang == "fa"
            else "🤔 Searching and generating answer..."
        )
        try:
            reply_res = message.reply(processing_msg)
            status_message = (
                await reply_res if hasattr(reply_res, "__await__") else reply_res
            )
        except Exception:

            class _Dummy:
                async def edit_text(self, *_a, **_k):
                    return None

            status_message = _Dummy()

        rag_service = await get_rag_service()
        result = await rag_service.query_documents(question, settings.default_lang)

        processing_time = asyncio.get_event_loop().time() - start_time

        # Track analytics (best-effort)
        try:
            integration_service = await get_integration_service()
            await integration_service.track_user_action(
                str(user_id),
                "query",
                {
                    "query": question,
                    "processing_time": processing_time,
                    "confidence_score": result.confidence_score,
                    "sources_count": len(result.sources),
                },
            )
        except Exception:
            pass

        if settings.default_lang == "fa":
            response_msg = f"💬 <b>پاسخ:</b>\n{result.answer}\n\n"
            if result.sources:
                response_msg += "📚 <b>منابع:</b>\n"
                for i, source in enumerate(result.sources[:3], 1):
                    response_msg += f"{i}. {source[:100]}...\n"
            response_msg += f"\n⚡ زمان پردازش: {result.processing_time:.2f} ثانیه"
            if result.confidence_score:
                response_msg += f"\n🎯 اعتماد: {result.confidence_score:.1%}"
        else:
            response_msg = f"💬 <b>Answer:</b>\n{result.answer}\n\n"
            if result.sources:
                response_msg += "📚 <b>Sources:</b>\n"
                for i, source in enumerate(result.sources[:3], 1):
                    response_msg += f"{i}. {source[:100]}...\n"
            response_msg += (
                f"\n⚡ Processing time: {result.processing_time:.2f} seconds"
            )
            if result.confidence_score:
                response_msg += f"\n🎯 Confidence: {result.confidence_score:.1%}"

        await status_message.edit_text(response_msg)

        logger.log_user_action(
            user_id=user_id,
            action="ask_question_success",
            question=question[:100],
            processing_time=processing_time,
            confidence_score=result.confidence_score,
            sources_count=len(result.sources),
        )
    except EmbeddingError as e:
        error_msg = (
            "❌ خطا در پردازش سوال. لطفاً دوباره تلاش کنید."
            if settings.default_lang == "fa"
            else "❌ Error processing question. Please try again."
        )
        await status_message.edit_text(error_msg)  # type: ignore[name-defined]
        await safe_log_error(error=e, context="ask_handler_embedding", user_id=user_id)
    except VectorStoreError as e:
        error_msg = (
            "❌ خطا در جستجو. ممکن است هیچ سندی اضافه نشده باشد."
            if settings.default_lang == "fa"
            else "❌ Search error. You may need to add documents first."
        )
        await status_message.edit_text(error_msg)  # type: ignore[name-defined]
        await safe_log_error(error=e, context="ask_handler_search", user_id=user_id)
    except Exception as e:
        error_msg = (
            "❌ خطای غیرمنتظره در تولید پاسخ. لطفاً دوباره تلاش کنید."
            if settings.default_lang == "fa"
            else "❌ Unexpected error generating answer. Please try again."
        )
        await status_message.edit_text(error_msg)  # type: ignore[name-defined]
        await safe_log_error(
            error=e,
            context="ask_handler_general",
            user_id=user_id,
            question=message.text[:100] if message.text else "",
        )
        if "pydantic" in str(e).lower() or "__pydantic" in str(e):
            log_pydantic_error(
                e,
                context="ask_handler_general",
                user_id=user_id,
                question=message.text[:100] if message.text else "",
            )
        else:
            logger.error_with_traceback(
                f"Unexpected error in ask_handler: {e}",
                exc_info=True,
                user_id=user_id,
                question=message.text[:100] if message.text else "",
                error_type=type(e).__name__,
                error_details=str(e),
            )
