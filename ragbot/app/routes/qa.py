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


def _get_active_logger():
    import sys
    routes_mod = sys.modules.get("ragbot.app.routes")
    return getattr(routes_mod, "logger", logger) if routes_mod else logger


@router.message(Command("ask"))
async def ask_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()
    active_logger = _get_active_logger()

    try:
        active_logger.log_user_action(user_id=user_id, action="ask_question_start")
        active_logger.info("ask_handler invoked", user_id=user_id)

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
            sources_len = len(result.sources) if hasattr(result, "sources") and hasattr(result.sources, "__len__") else 0
            await integration_service.track_user_action(
                str(user_id),
                "query",
                {
                    "query": question,
                    "processing_time": processing_time,
                    "confidence_score": getattr(result, "confidence_score", None),
                    "sources_count": sources_len,
                },
            )
        except Exception:
            pass

        # Robust string extraction for metrics
        proc_time_str = ""
        raw_proc = getattr(result, "processing_time", None)
        if raw_proc is not None:
            try:
                proc_time_str = f"{float(raw_proc):.2f}"
            except (ValueError, TypeError):
                proc_time_str = str(raw_proc)

        conf_str = ""
        raw_conf = getattr(result, "confidence_score", None)
        if raw_conf is not None:
            try:
                conf_str = f"{float(raw_conf):.1%}"
            except (ValueError, TypeError):
                conf_str = str(raw_conf)

        sources_list = getattr(result, "sources", None) or []
        answer_str = getattr(result, "answer", "")

        if settings.default_lang == "fa":
            response_msg = f"💬 <b>پاسخ:</b>\n{answer_str}\n\n"
            if sources_list and hasattr(sources_list, "__iter__"):
                response_msg += "📚 <b>منابع:</b>\n"
                for i, source in enumerate(sources_list[:3], 1):
                    response_msg += f"{i}. {str(source)[:100]}...\n"
            if proc_time_str:
                response_msg += f"\n⚡ زمان پردازش: {proc_time_str} ثانیه"
            if conf_str:
                response_msg += f"\n🎯 اعتماد: {conf_str}"
        else:
            response_msg = f"💬 <b>Answer:</b>\n{answer_str}\n\n"
            if sources_list and hasattr(sources_list, "__iter__"):
                response_msg += "📚 <b>Sources:</b>\n"
                for i, source in enumerate(sources_list[:3], 1):
                    response_msg += f"{i}. {str(source)[:100]}...\n"
            if proc_time_str:
                response_msg += (
                    f"\n⚡ Processing time: {proc_time_str} seconds"
                )
            if conf_str:
                response_msg += f"\n🎯 Confidence: {conf_str}"

        await status_message.edit_text(response_msg)

        sources_count = len(sources_list) if hasattr(sources_list, "__len__") else 0
        active_logger.log_user_action(
            user_id=user_id,
            action="ask_question_success",
            question=question[:100],
            processing_time=processing_time,
            confidence_score=raw_conf,
            sources_count=sources_count,
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
