"""Monitoring callback handlers."""

from aiogram import Router
from aiogram.types import CallbackQuery

from ragbot.app.ui.manager import ui_manager
from .utils import get_integration_service

router = Router()


@router.callback_query(lambda c: c.data == "monitoring_menu")
async def monitoring_menu_callback(query: CallbackQuery) -> None:
    """Handle monitoring menu callback"""
    try:
        msg = "📊 منوی مانیتورینگ سیستم\n\n"
        msg += "از دکمه‌های زیر برای مانیتورینگ سیستم استفاده کنید:"

        await query.message.edit_text(msg, reply_markup=ui_manager.monitoring_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش منوی مانیتورینگ", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "monitoring_health")
async def monitoring_health_callback(query: CallbackQuery) -> None:
    """Handle monitoring health callback"""
    try:
        msg = "🩺 وضعیت سلامت سیستم\n\n"
        msg += "برای بررسی سلامت سیستم از دستور زیر استفاده کنید:\n"
        msg += "<code>/health</code>\n\n"
        msg += "این دستور وضعیت تمام سرویس‌ها و Graceful Degradation را بررسی می‌کند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای سلامت", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "monitoring_realtime")
async def monitoring_realtime_callback(query: CallbackQuery) -> None:
    """Handle monitoring realtime callback"""
    try:
        msg = "📊 مانیتورینگ لحظه‌ای\n\n"
        msg += "برای مانیتورینگ لحظه‌ای از دستور زیر استفاده کنید:\n"
        msg += "<code>/monitoring</code>\n\n"
        msg += "این دستور وضعیت CPU، حافظه، دیسک و نرخ خطا را نمایش می‌دهد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای مانیتورینگ", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "monitoring_performance")
async def monitoring_performance_callback(query: CallbackQuery) -> None:
    """Handle monitoring performance callback"""
    try:
        integration_service = await get_integration_service()
        perf_summary = await integration_service.get_performance_summary()
        status_msg = ui_manager.create_performance_status(perf_summary)

        await query.message.edit_text(status_msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش وضعیت عملکرد", show_alert=False)
        except Exception:
            pass
