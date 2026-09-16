"""Analytics callback handlers."""

from aiogram import Router
from aiogram.types import CallbackQuery

from ragbot.app.ui.manager import ui_manager
from .utils import get_integration_service

router = Router()


@router.callback_query(lambda c: c.data == "analytics_user")
async def analytics_user_callback(query: CallbackQuery) -> None:
    """Handle analytics user callback"""
    try:
        integration_service = await get_integration_service()
        user_analytics = await integration_service.get_user_analytics(
            str(query.from_user.id)
        )
        analytics_msg = ui_manager.create_analytics_message(user_analytics)

        await query.message.edit_text(
            analytics_msg, reply_markup=ui_manager.back_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش تحلیل کاربر", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "analytics_ml")
async def analytics_ml_callback(query: CallbackQuery) -> None:
    """Handle analytics ML callback"""
    try:
        msg = "🤖 بینش‌های یادگیری ماشین\n\n"
        msg += "برای دریافت بینش‌های ML از دستور زیر استفاده کنید:\n"
        msg += "<code>/ml_insights</code>\n\n"
        msg += "این دستور الگوهای پرسش و موضوعات محبوب را تحلیل می‌کند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای ML", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "analytics_predictive")
async def analytics_predictive_callback(query: CallbackQuery) -> None:
    """Handle analytics predictive callback"""
    try:
        msg = "🔮 تحلیل پیش‌بینانه\n\n"
        msg += "برای دریافت تحلیل پیش‌بینانه از دستور زیر استفاده کنید:\n"
        msg += "<code>/predictive</code>\n\n"
        msg += "این دستور پیش‌بینی بار، ذخیره‌سازی و ناهنجاری‌ها را ارائه می‌دهد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای تحلیل پیش‌بینانه", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "analytics_comprehensive")
async def analytics_comprehensive_callback(query: CallbackQuery) -> None:
    """Handle analytics comprehensive callback"""
    try:
        msg = "📊 گزارش جامع تحلیل\n\n"
        msg += "برای دریافت گزارش جامع از دستور زیر استفاده کنید:\n"
        msg += "<code>/comprehensive_analytics</code>\n\n"
        msg += "این دستور گزارش 30 روزه کامل سیستم را ارائه می‌دهد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای گزارش جامع", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "analytics_report")
async def analytics_report_callback(query: CallbackQuery) -> None:
    """Handle analytics report callback"""
    try:
        msg = "📋 گزارش تفصیلی تحلیل\n\n"
        msg += "برای دریافت گزارش تفصیلی از دستور زیر استفاده کنید:\n"
        msg += "<code>/report</code>\n\n"
        msg += "این دستور گزارش کامل تحلیل با توصیه‌های بهبود ارائه می‌دهد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای گزارش تفصیلی", show_alert=False)
        except Exception:
            pass
