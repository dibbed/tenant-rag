"""Plugins callback handlers."""

from aiogram import Router
from aiogram.types import CallbackQuery

from ragbot.app.ui.manager import ui_manager

router = Router()


@router.callback_query(lambda c: c.data == "plugins_menu")
async def plugins_menu_callback(query: CallbackQuery) -> None:
    """Handle plugins menu callback"""
    try:
        msg = "📦 منوی مدیریت پلاگین‌ها\n\n"
        msg += "از دکمه‌های زیر برای مدیریت پلاگین‌ها استفاده کنید:"

        await query.message.edit_text(msg, reply_markup=ui_manager.plugins_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش منوی پلاگین‌ها", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "plugins_load")
async def plugins_load_callback(query: CallbackQuery) -> None:
    """Handle plugins load callback"""
    try:
        msg = "📦 بارگذاری پلاگین\n\n"
        msg += "برای بارگذاری پلاگین از دستور زیر استفاده کنید:\n"
        msg += "<code>/load_plugin [مسیر فایل]</code>\n\n"
        msg += "مثال: <code>/load_plugin plugins/my_plugin.py</code>"

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای بارگذاری پلاگین", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "plugins_unload")
async def plugins_unload_callback(query: CallbackQuery) -> None:
    """Handle plugins unload callback"""
    try:
        msg = "🗑️ حذف پلاگین\n\n"
        msg += "برای حذف پلاگین از دستور زیر استفاده کنید:\n"
        msg += "<code>/unload_plugin [شناسه پلاگین]</code>\n\n"
        msg += "مثال: <code>/unload_plugin my_plugin</code>"

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای حذف پلاگین", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "plugins_list")
async def plugins_list_callback(query: CallbackQuery) -> None:
    """Handle plugins list callback"""
    try:
        msg = "📋 لیست پلاگین‌ها\n\n"
        msg += "برای مشاهده پلاگین‌های نصب شده از دستور زیر استفاده کنید:\n"
        msg += "<code>/list_plugins</code>\n\n"
        msg += "این دستور تمام پلاگین‌های فعال و غیرفعال را نمایش می‌دهد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای لیست پلاگین‌ها", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "plugins_status")
async def plugins_status_callback(query: CallbackQuery) -> None:
    """Handle plugins status callback"""
    try:
        msg = "🔍 وضعیت پلاگین\n\n"
        msg += "برای بررسی وضعیت پلاگین از دستور زیر استفاده کنید:\n"
        msg += "<code>/plugin_status [شناسه پلاگین]</code>\n\n"
        msg += "مثال: <code>/plugin_status my_plugin</code>"

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای وضعیت پلاگین", show_alert=False)
        except Exception:
            pass
