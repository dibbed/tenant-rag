"""Document ingestion handlers: /add and implicit handlers for files and URLs."""

import asyncio
import tempfile
from pathlib import Path

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag import DocumentProcessingError, VectorStoreError

from .utils import (
    get_bot,
    get_integration_service,
    get_rag_service,
    maybe_await,
    safe_log_error,
)

router = Router()


@router.message(Command("add"))
async def add_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="add_document_start")

        processing_msg = (
            "🔄 در حال پردازش..."
            if settings.default_lang == "fa"
            else "🔄 Processing..."
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

        source = ""
        source_type = ""

        if message.document:
            # Size check first
            file_size_mb = (
                message.document.file_size / (1024 * 1024)
                if message.document.file_size
                else 0
            )
            if file_size_mb > settings.security.max_file_size_mb:
                error_msg = (
                    f"❌ فایل بیش از حد بزرگ است. حداکثر: {settings.security.max_file_size_mb}MB"
                    if settings.default_lang == "fa"
                    else f"❌ File too large. Maximum: {settings.security.max_file_size_mb}MB"
                )
                await status_message.edit_text(error_msg)
                return

            # Download the file to a temp path with the correct suffix inferred from filename
            bot = await maybe_await(get_bot())
            bot = bot or message.bot
            file_info = await bot.get_file(message.document.file_id)
            file_content = await bot.download_file(file_info.file_path)

            # Infer suffix from original file name (fallback to .pdf to be safe)
            orig_name = (message.document.file_name or "").lower()
            from pathlib import Path as _Path

            inferred_suffix = _Path(orig_name).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(
                suffix=inferred_suffix, delete=False
            ) as temp_file:
                temp_file.write(file_content.read())
                source = temp_file.name

            # Let RAG service auto-detect source type; improves multi-format support (md/html/txt/...)
            source_type = None
        elif message.text:
            text_content = message.text.replace("/add", "").strip()
            if text_content.startswith(("http://", "https://")):
                source_type = "url"
                source = text_content
            elif text_content:
                source_type = "text"
                source = text_content
            else:
                error_msg = (
                    "❌ لطفاً فایل PDF یا DOCX، لینک یا متن ارسال کنید."
                    if settings.default_lang == "fa"
                    else "❌ Please send a PDF or DOCX file, URL, or text."
                )
                await status_message.edit_text(error_msg)
                return
        else:
            error_msg = (
                "❌ لطفاً فایل PDF یا DOCX، لینک یا متن ارسال کنید."
                if settings.default_lang == "fa"
                else "❌ Please send a PDF or DOCX file, URL, or text."
            )
            await status_message.edit_text(error_msg)
            return

        rag_service = await maybe_await(get_rag_service())
        result = await rag_service.ingest_document(source, source_type)

        # Clean up temp file if created
        try:
            if source and Path(source).exists():
                Path(source).unlink()
        except Exception:
            pass

        processing_time = asyncio.get_event_loop().time() - start_time

        if result.success:
            if settings.default_lang == "fa":
                success_msg = (
                    f"✅ سند با موفقیت اضافه شد!\n\n"
                    f"📄 تعداد بخش‌ها: {result.chunks_created}\n"
                    f"⏱️ زمان پردازش: {result.processing_time:.2f} ثانیه\n"
                    f"🆔 شناسه سند: {result.document_id[:8]}..."
                )
            else:
                success_msg = (
                    f"✅ Document added successfully!\n\n"
                    f"📄 Chunks created: {result.chunks_created}\n"
                    f"⏱️ Processing time: {result.processing_time:.2f} seconds\n"
                    f"🆔 Document ID: {result.document_id[:8]}..."
                )
            await status_message.edit_text(success_msg)
            logger.log_user_action(
                user_id=user_id,
                action="add_document_success",
                document_id=result.document_id,
                chunks_created=result.chunks_created,
                processing_time=processing_time,
                source_type=source_type,
            )
        else:
            error_msg = (
                f"❌ خطا در پردازش سند:\n{result.error_message}"
                if settings.default_lang == "fa"
                else f"❌ Error processing document:\n{result.error_message}"
            )
            await status_message.edit_text(error_msg)
            await safe_log_error(
                error=Exception(result.error_message or "Unknown error"),
                context="add_document_processing",
                user_id=user_id,
                source_type=source_type,
            )

        # Track analytics for successful document addition (non-blocking best-effort)
        try:
            integration_service = await get_integration_service()
            await integration_service.track_user_action(
                str(user_id),
                "add_document",
                {
                    "source": source,
                    "source_type": source_type,
                    "processing_time": processing_time,
                },
            )
            await integration_service.record_document_type(source_type)
        except Exception:
            pass

    except DocumentProcessingError as e:
        error_msg = (
            f"❌ خطا در پردازش سند: {str(e)}"
            if settings.default_lang == "fa"
            else f"❌ Document processing error: {str(e)}"
        )
        await status_message.edit_text(error_msg)  # type: ignore[name-defined]
        await safe_log_error(error=e, context="add_handler_document", user_id=user_id)
    except VectorStoreError as e:
        error_msg = (
            "❌ خطا در ذخیره‌سازی. لطفاً دوباره تلاش کنید."
            if settings.default_lang == "fa"
            else "❌ Storage error. Please try again."
        )
        await status_message.edit_text(error_msg)  # type: ignore[name-defined]
        await safe_log_error(error=e, context="add_handler_storage", user_id=user_id)
    except Exception as e:
        error_msg = (
            "❌ خطای غیرمنتظره. لطفاً دوباره تلاش کنید."
            if settings.default_lang == "fa"
            else "❌ Unexpected error. Please try again."
        )
        await status_message.edit_text(error_msg)  # type: ignore[name-defined]
        await safe_log_error(error=e, context="add_handler_general", user_id=user_id)


@router.message(lambda message: message.document is not None)
async def document_handler(message: Message) -> None:
    await add_handler(message)


@router.message(
    lambda message: message.text and message.text.startswith(("http://", "https://"))
)
async def url_handler(message: Message) -> None:
    await add_handler(message)
