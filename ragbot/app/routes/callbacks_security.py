"""Security callback handlers."""

from aiogram import Router
from aiogram.types import CallbackQuery

from ragbot.app.ui.manager import ui_manager

router = Router()


@router.callback_query(lambda c: c.data == "security_menu")
async def security_menu_callback(query: CallbackQuery) -> None:
    """Handle security menu callback"""
    try:
        msg = "🔐 منوی امنیت و پشتیبان‌گیری\n\n"
        msg += "از دکمه‌های زیر برای مدیریت امنیت استفاده کنید:"

        await query.message.edit_text(msg, reply_markup=ui_manager.security_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش منوی امنیت", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "security_backup")
async def security_backup_callback(query: CallbackQuery) -> None:
    """Handle security backup callback"""
    try:
        msg = "🔐 ایجاد پشتیبان امن\n\n"
        msg += "برای ایجاد پشتیبان از دستور زیر استفاده کنید:\n"
        msg += "<code>/backup [نام پشتیبان]</code>\n\n"
        msg += "مثال: <code>/backup backup_2024</code>"

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای پشتیبان", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "security_restore")
async def security_restore_callback(query: CallbackQuery) -> None:
    """Handle security restore callback"""
    try:
        msg = "🔄 بازگردانی از پشتیبان\n\n"
        msg += "برای بازگردانی از دستور زیر استفاده کنید:\n"
        msg += "<code>/restore [مسیر فایل پشتیبان]</code>\n\n"
        msg += "مثال: <code>/restore /path/to/backup.tar.gz</code>"

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای بازگردانی", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "security_rotate_keys")
async def security_rotate_keys_callback(query: CallbackQuery) -> None:
    """Handle security rotate keys callback"""
    try:
        msg = "🔑 چرخش کلیدهای رمزنگاری\n\n"
        msg += "برای چرخش کلیدها از دستور زیر استفاده کنید:\n"
        msg += "<code>/rotate_keys</code>\n\n"
        msg += "⚠️ این عملیات تمام اسناد را با کلید جدید رمزنگاری می‌کند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای چرخش کلیدها", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "security_list_keys")
async def security_list_keys_callback(query: CallbackQuery) -> None:
    """Handle security list keys callback"""
    try:
        msg = "📋 لیست کلیدهای رمزنگاری\n\n"
        msg += "برای مشاهده کلیدها از دستور زیر استفاده کنید:\n"
        msg += "<code>/list_keys</code>\n\n"
        msg += "این دستور تمام کلیدهای فعال و غیرفعال را نمایش می‌دهد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای لیست کلیدها", show_alert=False)
        except Exception:
            pass
