"""Admin callback handlers."""

from aiogram import Router
from aiogram.types import CallbackQuery

from ragbot.app.ui.manager import ui_manager

router = Router()


@router.callback_query(lambda c: c.data == "admin_menu")
async def admin_menu_callback(query: CallbackQuery) -> None:
    """Handle admin menu callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "👑 منوی مدیریت ادمین\n\n"
        msg += "از دکمه‌های زیر برای مدیریت سیستم استفاده کنید:"

        await query.message.edit_text(msg, reply_markup=ui_manager.admin_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش منوی ادمین", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_users")
async def admin_users_callback(query: CallbackQuery) -> None:
    """Handle admin users callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "👑 مدیریت کاربران\n\n"
        msg += "قابلیت‌های مدیریت کاربران:\n"
        msg += "• مشاهده لیست کاربران\n"
        msg += "• مدیریت دسترسی‌ها\n"
        msg += "• آمار استفاده کاربران\n"
        msg += "• مسدود کردن/رفع مسدودیت\n\n"
        msg += "این قابلیت‌ها در نسخه‌های آینده اضافه خواهند شد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش مدیریت کاربران", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_settings")
async def admin_settings_callback(query: CallbackQuery) -> None:
    """Handle admin settings callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🔧 تنظیمات سیستم\n\n"
        msg += "تنظیمات قابل مدیریت:\n"
        msg += "• تنظیمات پایگاه داده\n"
        msg += "• تنظیمات Redis\n"
        msg += "• تنظیمات OCR\n"
        msg += "• تنظیمات امنیتی\n"
        msg += "• تنظیمات پلاگین‌ها\n\n"
        msg += "برای تغییر تنظیمات از فایل config استفاده کنید."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش تنظیمات سیستم", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_reports")
async def admin_reports_callback(query: CallbackQuery) -> None:
    """Handle admin reports callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "📊 گزارش‌های ادمین\n\n"
        msg += "گزارش‌های در دسترس:\n"
        msg += "• گزارش استفاده سیستم\n"
        msg += "• گزارش عملکرد\n"
        msg += "• گزارش امنیتی\n"
        msg += "• گزارش خطاها\n"
        msg += "• گزارش کاربران\n\n"
        msg += "از دستورات /report و /analytics استفاده کنید."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش گزارش‌های ادمین", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_permissions")
async def admin_permissions_callback(query: CallbackQuery) -> None:
    """Handle admin permissions callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🔐 مدیریت دسترسی‌ها\n\n"
        msg += "قابلیت‌های مدیریت دسترسی:\n"
        msg += "• تعریف نقش‌های کاربری\n"
        msg += "• تنظیم مجوزها\n"
        msg += "• مدیریت کلیدهای API\n"
        msg += "• کنترل دسترسی به دستورات\n\n"
        msg += "این قابلیت‌ها در نسخه‌های آینده اضافه خواهند شد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش مدیریت دسترسی‌ها", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_maintenance")
async def admin_maintenance_callback(query: CallbackQuery) -> None:
    """Handle admin maintenance callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🛠️ تعمیر و نگهداری\n\n"
        msg += "عملیات تعمیر و نگهداری:\n"
        msg += "• پاک‌سازی کش\n"
        msg += "• بهینه‌سازی پایگاه داده\n"
        msg += "• بررسی سلامت سیستم\n"
        msg += "• پشتیبان‌گیری خودکار\n"
        msg += "• به‌روزرسانی سیستم\n\n"
        msg += "از دستورات /reset و /health استفاده کنید."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش تعمیر و نگهداری", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_shutdown")
async def admin_shutdown_callback(query: CallbackQuery) -> None:
    """Handle admin shutdown callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🛑 خاموش کردن ربات\n\n"
        msg += "⚠️ هشدار: این عملیات ربات را کاملاً خاموش می‌کند!\n\n"
        msg += "برای خاموش کردن از دستور زیر استفاده کنید:\n"
        msg += "<code>/shutdown</code>\n\n"
        msg += "🔒 فقط ادمین‌ها می‌توانند این دستور را اجرا کنند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای خاموش کردن", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_restart")
async def admin_restart_callback(query: CallbackQuery) -> None:
    """Handle admin restart callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🔄 ری‌استارت ربات\n\n"
        msg += "⚠️ هشدار: این عملیات ربات را ری‌استارت می‌کند!\n\n"
        msg += "برای ری‌استارت از دستور زیر استفاده کنید:\n"
        msg += "<code>/restart</code>\n\n"
        msg += "🔒 فقط ادمین‌ها می‌توانند این دستور را اجرا کنند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای ری‌استارت", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_logs")
async def admin_logs_callback(query: CallbackQuery) -> None:
    """Handle admin logs callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "📋 مشاهده لاگ‌ها\n\n"
        msg += "برای مشاهده لاگ‌های سیستم از دستور زیر استفاده کنید:\n"
        msg += "<code>/logs</code>\n\n"
        msg += "این دستور آخرین 20 خط لاگ را نمایش می‌دهد.\n"
        msg += "🔒 فقط ادمین‌ها می‌توانند این دستور را اجرا کنند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای لاگ‌ها", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_clear_cache")
async def admin_clear_cache_callback(query: CallbackQuery) -> None:
    """Handle admin clear cache callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🗑️ پاک کردن کش\n\n"
        msg += "برای پاک کردن کش سیستم از دستور زیر استفاده کنید:\n"
        msg += "<code>/clear_cache</code>\n\n"
        msg += "این دستور تمام کش‌ها را پاک می‌کند:\n"
        msg += "• کش L1 و L2\n"
        msg += "• کش معنایی\n"
        msg += "• کش Redis\n\n"
        msg += "🔒 فقط ادمین‌ها می‌توانند این دستور را اجرا کنند."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای پاک کردن کش", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_status")
async def admin_status_callback(query: CallbackQuery) -> None:
    """Handle admin status callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        status_msg = ui_manager.create_admin_status_message(detailed=True)

        # Check if message is too long and needs pagination
        if len(status_msg) > 4000:
            content, keyboard = ui_manager.create_paginated_message(
                status_msg, prefix="admin_status"
            )
            await query.message.edit_text(content, reply_markup=keyboard)
        else:
            await query.message.edit_text(
                status_msg, reply_markup=ui_manager.back_keyboard
            )

        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش وضعیت سیستم", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_storage")
async def admin_storage_callback(query: CallbackQuery) -> None:
    """Handle admin storage management callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "💾 مدیریت ذخیره‌سازی\n\n"
        msg += "قابلیت‌های مدیریت ذخیره‌سازی:\n"
        msg += "• 📊 نمایش فضای استفاده شده\n"
        msg += "• 🗑️ پاک‌سازی فایل‌های موقت\n"
        msg += "• 📦 فشرده‌سازی داده‌ها\n"
        msg += "• 🔄 بهینه‌سازی فضای ذخیره\n"
        msg += "• 📋 گزارش استفاده از فضای دیسک\n\n"
        msg += "این قابلیت‌ها در نسخه‌های آینده اضافه خواهند شد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش مدیریت ذخیره‌سازی", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_optimize_db")
async def admin_optimize_db_callback(query: CallbackQuery) -> None:
    """Handle admin database optimization callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🔄 بهینه‌سازی پایگاه داده\n\n"
        msg += "برای بهینه‌سازی پایگاه داده از دستور زیر استفاده کنید:\n"
        msg += "<code>/optimize_db</code>\n\n"
        msg += "این عملیات شامل:\n"
        msg += "• 🔄 بازسازی ایندکس‌ها\n"
        msg += "• 🗑️ پاک‌سازی داده‌های غیرضروری\n"
        msg += "• 📊 آمار به‌روزرسانی\n"
        msg += "• ⚡ بهبود عملکرد\n\n"
        msg += "⚠️ این عملیات ممکن است چند دقیقه طول بکشد."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای بهینه‌سازی DB", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_cleanup")
async def admin_cleanup_callback(query: CallbackQuery) -> None:
    """Handle admin cleanup callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🧹 پاک‌سازی فایل‌ها\n\n"
        msg += "برای پاک‌سازی فایل‌های سیستم از دستور زیر استفاده کنید:\n"
        msg += "<code>/cleanup</code>\n\n"
        msg += "این عملیات شامل:\n"
        msg += "• 🗑️ حذف فایل‌های موقت\n"
        msg += "• 📦 پاک‌سازی کش‌های قدیمی\n"
        msg += "• 🔄 حذف لاگ‌های قدیمی\n"
        msg += "• 💾 آزادسازی فضای دیسک\n\n"
        msg += "⚠️ این عملیات غیرقابل برگشت است!"

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای پاک‌سازی", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_user_stats")
async def admin_user_stats_callback(query: CallbackQuery) -> None:
    """Handle admin user statistics callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "📊 آمار کاربران\n\n"
        msg += "برای مشاهده آمار کاربران از دستور زیر استفاده کنید:\n"
        msg += "<code>/user_stats</code>\n\n"
        msg += "این گزارش شامل:\n"
        msg += "• 👥 تعداد کل کاربران\n"
        msg += "• 📈 کاربران فعال\n"
        msg += "• 📊 آمار استفاده\n"
        msg += "• 🕒 زمان آخرین فعالیت\n"
        msg += "• 📋 گزارش تفصیلی\n\n"
        msg += "📊 آمار در زمان واقعی به‌روزرسانی می‌شود."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش آمار کاربران", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_ban_user")
async def admin_ban_user_callback(query: CallbackQuery) -> None:
    """Handle admin ban user callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "🚫 مسدود کردن کاربر\n\n"
        msg += "برای مسدود کردن کاربر از دستور زیر استفاده کنید:\n"
        msg += "<code>/ban_user [user_id] [reason]</code>\n\n"
        msg += "مثال:\n"
        msg += "<code>/ban_user 123456789 اسپم</code>\n\n"
        msg += "⚠️ احتیاط:\n"
        msg += "• این عملیات غیرقابل برگشت است\n"
        msg += "• کاربر مسدود شده نمی‌تواند از ربات استفاده کند\n"
        msg += "• دلیل مسدودیت در لاگ ثبت می‌شود\n\n"
        msg += "برای رفع مسدودیت از <code>/unban_user [user_id]</code> استفاده کنید."

        await query.message.edit_text(msg, reply_markup=ui_manager.back_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنمای مسدود کردن", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "admin_page_2")
async def admin_page_2_callback(query: CallbackQuery) -> None:
    """Handle admin page 2 callback"""
    try:
        if not ui_manager.is_admin_user(query.from_user.id):
            await query.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        msg = "👑 صفحه دوم مدیریت ادمین\n\n"
        msg += "🔧 دستورات پیشرفته:\n"
        msg += "• /advanced_settings - تنظیمات پیشرفته\n"
        msg += "• /system_diagnostics - تشخیص مشکلات\n"
        msg += "• /backup_system - پشتیبان‌گیری کامل\n"
        msg += "• /restore_system - بازگردانی سیستم\n"
        msg += "• /update_system - به‌روزرسانی سیستم\n"
        msg += "• /maintenance_mode - حالت تعمیر\n\n"
        msg += "⚠️ این دستورات فقط برای ادمین‌های متخصص است!"

        await query.message.edit_text(
            msg, reply_markup=ui_manager.admin_extended_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش صفحه دوم", show_alert=False)
        except Exception:
            pass
