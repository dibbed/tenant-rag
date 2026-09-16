"""Security features handler."""

import asyncio

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


@router.message(Command("backup"))
async def backup_handler(message: Message) -> None:
    """Handle secure backup creation."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="backup_start")
        logger.info("backup_handler invoked", user_id=user_id)

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

        # Parse backup name from message
        backup_name = (
            message.text.replace("/backup", "").strip() if message.text else None
        )
        if backup_name:
            backup_name = backup_name.replace(" ", "_")

        processing_msg = (
            "🔐 در حال ایجاد backup امن..."
            if settings.default_lang == "fa"
            else "🔐 Creating secure backup..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService backup functionality
        if hasattr(rag_service, "create_secure_backup"):
            try:
                result = await rag_service.create_secure_backup(backup_name=backup_name)

                if result.get("success"):
                    response_msg = (
                        f"✅ Backup امن با موفقیت ایجاد شد!\n"
                        f"شناسه Backup: {result.get('backup_id', 'N/A')}\n"
                        f"مسیر فایل: {result.get('backup_path', 'N/A')}\n"
                        f"اندازه فایل: {result.get('file_size', 0)} bytes\n"
                        f"نسبت فشرده‌سازی: {result.get('compression_ratio', 0):.2f}"
                        if settings.default_lang == "fa"
                        else f"✅ Secure backup created successfully!\n"
                        f"Backup ID: {result.get('backup_id', 'N/A')}\n"
                        f"File path: {result.get('backup_path', 'N/A')}\n"
                        f"File size: {result.get('file_size', 0)} bytes\n"
                        f"Compression ratio: {result.get('compression_ratio', 0):.2f}"
                    )
                else:
                    response_msg = (
                        f"❌ خطا در ایجاد backup: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Backup creation error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Backup creation failed: {e}")
                error_msg = (
                    f"❌ خطا در ایجاد backup: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Backup creation error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت secure backup فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Secure backup feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "backup_handler")


@router.message(Command("restore"))
async def restore_handler(message: Message) -> None:
    """Handle backup restoration."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="restore_start")
        logger.info("restore_handler invoked", user_id=user_id)

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

        # Parse backup path from message
        backup_path = (
            message.text.replace("/restore", "").strip() if message.text else ""
        )
        if not backup_path:
            error_msg = (
                "❓ لطفاً مسیر backup را بعد از دستور /restore بنویسید.\n"
                "مثال: /restore /path/to/backup.tar.gz"
                if settings.default_lang == "fa"
                else "❓ Please write backup path after /restore command.\n"
                "Example: /restore /path/to/backup.tar.gz"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🔄 در حال بازگردانی از backup..."
            if settings.default_lang == "fa"
            else "🔄 Restoring from backup..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService restore functionality
        if hasattr(rag_service, "restore_from_backup"):
            try:
                result = await rag_service.restore_from_backup(backup_path=backup_path)

                if result.get("success"):
                    response_msg = (
                        f"✅ بازگردانی با موفقیت انجام شد!\n"
                        f"شناسه Restore: {result.get('restore_id', 'N/A')}\n"
                        f"تعداد اسناد بازگردانی شده: {result.get('restored_documents', 0)}\n"
                        f"زمان بازگردانی: {result.get('restore_time', 0):.2f}s\n"
                        f"Store های بازگردانی شده: {', '.join(result.get('restored_stores', []))}"
                        if settings.default_lang == "fa"
                        else f"✅ Restore completed successfully!\n"
                        f"Restore ID: {result.get('restore_id', 'N/A')}\n"
                        f"Documents restored: {result.get('restored_documents', 0)}\n"
                        f"Restore time: {result.get('restore_time', 0):.2f}s\n"
                        f"Stores restored: {', '.join(result.get('restored_stores', []))}"
                    )
                else:
                    response_msg = (
                        f"❌ خطا در بازگردانی: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Restore error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Restore failed: {e}")
                error_msg = (
                    f"❌ خطا در بازگردانی: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Restore error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت restore فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Restore feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "restore_handler")


@router.message(Command("rotate_keys"))
async def rotate_keys_handler(message: Message) -> None:
    """Handle encryption key rotation."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="rotate_keys_start")
        logger.info("rotate_keys_handler invoked", user_id=user_id)

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
            "🔑 در حال چرخش کلیدهای رمزنگاری..."
            if settings.default_lang == "fa"
            else "🔑 Rotating encryption keys..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use RAGService key rotation functionality
        if hasattr(rag_service, "rotate_encryption_keys"):
            try:
                result = await rag_service.rotate_encryption_keys()

                if result.get("success"):
                    response_msg = (
                        f"✅ چرخش کلیدها با موفقیت انجام شد!\n"
                        f"کلید قدیمی: {result.get('old_key_id', 'N/A')}\n"
                        f"کلید جدید: {result.get('new_key_id', 'N/A')}\n"
                        f"تعداد اسناد چرخش شده: {result.get('documents_rotated', 0)}\n"
                        f"زمان چرخش: {result.get('rotation_time', 0):.2f}s"
                        if settings.default_lang == "fa"
                        else f"✅ Key rotation completed successfully!\n"
                        f"Old key: {result.get('old_key_id', 'N/A')}\n"
                        f"New key: {result.get('new_key_id', 'N/A')}\n"
                        f"Documents rotated: {result.get('documents_rotated', 0)}\n"
                        f"Rotation time: {result.get('rotation_time', 0):.2f}s"
                    )
                else:
                    response_msg = (
                        f"❌ خطا در چرخش کلیدها: {result.get('error', 'Unknown error')}"
                        if settings.default_lang == "fa"
                        else f"❌ Key rotation error: {result.get('error', 'Unknown error')}"
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Key rotation failed: {e}")
                error_msg = (
                    f"❌ خطا در چرخش کلیدها: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Key rotation error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت key rotation فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Key rotation feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "rotate_keys_handler")


@router.message(Command("list_keys"))
async def list_keys_handler(message: Message) -> None:
    """Handle encryption key listing."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="list_keys_start")
        logger.info("list_keys_handler invoked", user_id=user_id)

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
            "🔑 در حال دریافت لیست کلیدها..."
            if settings.default_lang == "fa"
            else "🔑 Retrieving key list..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use KeyManager for key listing
        if hasattr(rag_service, "key_manager"):
            try:
                keys = rag_service.key_manager.list_keys()

                if keys:
                    response_msg = (
                        f"🔑 لیست کلیدهای رمزنگاری:\n\n"
                        if settings.default_lang == "fa"
                        else f"🔑 Encryption Keys List:\n\n"
                    )

                    for i, key in enumerate(keys[:5], 1):  # Show max 5 keys
                        response_msg += (
                            f"{i}. ID: {key.get('key_id', 'N/A')}\n"
                            f"   الگوریتم: {key.get('algorithm', 'N/A')}\n"
                            f"   وضعیت: {'فعال' if key.get('is_active') else 'غیرفعال'}\n"
                            f"   تاریخ ایجاد: {key.get('created_at', 'N/A')}\n\n"
                            if settings.default_lang == "fa"
                            else f"{i}. ID: {key.get('key_id', 'N/A')}\n"
                            f"   Algorithm: {key.get('algorithm', 'N/A')}\n"
                            f"   Status: {'Active' if key.get('is_active') else 'Inactive'}\n"
                            f"   Created: {key.get('created_at', 'N/A')}\n\n"
                        )

                    if len(keys) > 5:
                        response_msg += (
                            f"... و {len(keys) - 5} کلید دیگر"
                            if settings.default_lang == "fa"
                            else f"... and {len(keys) - 5} more keys"
                        )
                else:
                    response_msg = (
                        "❌ هیچ کلیدی یافت نشد."
                        if settings.default_lang == "fa"
                        else "❌ No keys found."
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Key listing failed: {e}")
                error_msg = (
                    f"❌ خطا در دریافت لیست کلیدها: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Key listing error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت key management فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Key management feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "list_keys_handler")
