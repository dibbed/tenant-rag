"""Main callback handlers - basic UI interactions."""

from aiogram import Router
from aiogram.types import CallbackQuery

from ragbot.app.ui.manager import ui_manager
from .utils import get_integration_service, safe_reply_with_kb

router = Router()


@router.callback_query(lambda c: c.data == "add_document")
async def add_document_callback(query: CallbackQuery) -> None:
    """Handle add document callback"""
    try:
        msg = "📄 برای افزودن سند، یکی از روش‌های زیر را استفاده کنید:\n\n"
        msg += "🔹 ارسال فایل PDF، DOCX، TXT\n"
        msg += "🔹 ارسال لینک URL\n"
        msg += "🔹 ارسال متن مستقیم\n"
        msg += "🔹 ارسال تصویر (با OCR)\n\n"
        msg += "یا از دستور /add استفاده کنید."

        await query.message.edit_text(msg, reply_markup=ui_manager.main_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنما", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "ask_question")
async def ask_question_callback(query: CallbackQuery) -> None:
    """Handle ask question callback"""
    try:
        msg = "❓ برای پرسیدن سوال:\n\n"
        msg += "🔹 سوال خود را تایپ کنید\n"
        msg += "🔹 یا از دستور /ask استفاده کنید\n\n"
        msg += "مثال: 'چگونه می‌توانم فایل PDF آپلود کنم؟'"

        await query.message.edit_text(msg, reply_markup=ui_manager.main_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنما", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "help_menu")
async def help_menu_callback(query: CallbackQuery) -> None:
    """Handle help menu callback"""
    try:
        help_text = ui_manager.format_message("help")
        await query.message.edit_text(help_text, reply_markup=ui_manager.help_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش راهنما", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "performance_menu")
async def performance_menu_callback(query: CallbackQuery) -> None:
    """Handle performance menu callback"""
    try:
        integration_service = await get_integration_service()
        perf_summary = await integration_service.get_performance_summary()
        status_msg = ui_manager.create_performance_status(perf_summary)

        await query.message.edit_text(
            status_msg, reply_markup=ui_manager.performance_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش وضعیت عملکرد", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "analytics_menu")
async def analytics_menu_callback(query: CallbackQuery) -> None:
    """Handle analytics menu callback"""
    try:
        integration_service = await get_integration_service()
        user_analytics = await integration_service.get_user_analytics(
            str(query.from_user.id)
        )
        analytics_msg = ui_manager.create_analytics_message(user_analytics)

        await query.message.edit_text(
            analytics_msg, reply_markup=ui_manager.main_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش تحلیل", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "settings_menu")
async def settings_menu_callback(query: CallbackQuery) -> None:
    """Handle settings menu callback"""
    try:
        msg = "⚙️ تنظیمات ربات:\n\n"
        msg += "🔹 زبان: فارسی\n"
        msg += "🔹 تم: شیشه‌ای\n"
        msg += "🔹 OCR: فعال\n"
        msg += "🔹 Cache: فعال\n\n"
        msg += "برای تغییر تنظیمات از دستورات مربوطه استفاده کنید."

        await query.message.edit_text(msg, reply_markup=ui_manager.main_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("خطا در نمایش تنظیمات", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "perf_refresh")
async def perf_refresh_callback(query: CallbackQuery) -> None:
    try:
        integration_service = await get_integration_service()
        perf_summary = await integration_service.get_performance_summary()
        resource_summary = await integration_service.get_resource_summary()
        gd_metrics = await integration_service.get_graceful_degradation_metrics()
        gd_status = await integration_service.get_degradation_system_status()

        # Use UI manager to create performance status message
        status_msg = ui_manager.create_performance_status(perf_summary)

        # Add resource summary
        if "error" not in resource_summary and "no_data" not in resource_summary:
            current = resource_summary.get("current", {})
            averages = resource_summary.get("averages", {})

            if ui_manager.default_language == "fa":
                status_msg += "\n💾 وضعیت منابع:\n"
                status_msg += f"💻 CPU فعلی: {current.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"🧠 حافظه فعلی: {current.get('memory_percent', 0):.1f}%\n"
                )
                status_msg += f"💽 دیسک فعلی: {current.get('disk_usage', 0):.1f}%\n"
                status_msg += f"📊 میانگین CPU: {averages.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"📊 میانگین حافظه: {averages.get('memory_percent', 0):.1f}%\n"
                )
            else:
                status_msg += "\n💾 Resource Status:\n"
                status_msg += f"💻 Current CPU: {current.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"🧠 Current Memory: {current.get('memory_percent', 0):.1f}%\n"
                )
                status_msg += f"💽 Current Disk: {current.get('disk_usage', 0):.1f}%\n"
                status_msg += f"📊 Average CPU: {averages.get('cpu_percent', 0):.1f}%\n"
                status_msg += (
                    f"📊 Average Memory: {averages.get('memory_percent', 0):.1f}%\n"
                )

        try:
            await query.message.edit_text(
                status_msg, reply_markup=ui_manager.performance_keyboard
            )
        except Exception:
            await safe_reply_with_kb(
                query.message, status_msg, ui_manager.performance_keyboard
            )
        await query.answer()
    except Exception:
        try:
            await query.answer("Refresh failed", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "back_home")
async def back_home_callback(query: CallbackQuery) -> None:
    try:
        # Return to main menu with appropriate keyboard based on user role
        welcome_text = ui_manager.format_message("welcome")

        # Get appropriate keyboard based on user role
        keyboard = ui_manager.get_main_keyboard_for_user(query.from_user.id)

        try:
            await query.message.edit_text(welcome_text, reply_markup=keyboard)
        except Exception:
            await safe_reply_with_kb(query.message, welcome_text, keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("OK", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "close")
async def close_callback(query: CallbackQuery) -> None:
    try:
        await query.message.delete()
        await query.answer()
    except Exception:
        try:
            await query.answer("Closed", show_alert=False)
        except Exception:
            pass


# Help callbacks
@router.callback_query(lambda c: c.data == "help_commands")
async def help_commands_callback(query: CallbackQuery) -> None:
    """Show help commands"""
    try:
        help_text = ui_manager.format_message("help")
        await query.message.edit_text(help_text, reply_markup=ui_manager.help_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("Help commands", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "help_examples")
async def help_examples_callback(query: CallbackQuery) -> None:
    """Show help examples"""
    try:
        if ui_manager.default_language == "fa":
            examples_text = """
📚 <b>مثال‌های کاربردی</b>

🔍 <b>جستجوی ساده</b>:
• "چگونه می‌توانم فایل PDF آپلود کنم؟"
• "آخرین تغییرات در سیستم چیست؟"

📊 <b>درخواست آمار</b>:
• "آمار عملکرد سیستم را نشان بده"
• "چند سند در سیستم داریم؟"

⚙️ <b>تنظیمات</b>:
• "زبان OCR را به انگلیسی تغییر بده"
• "پلاگین‌های فعال را نشان بده"

💡 <b>نکات</b>:
• از کلمات کلیدی استفاده کنید
• سوالات خود را واضح بپرسید
• از دستورات کوتاه استفاده کنید
"""
        else:
            examples_text = """
📚 <b>Usage Examples</b>

🔍 <b>Simple Search</b>:
• "How can I upload a PDF file?"
• "What are the latest system changes?"

📊 <b>Request Statistics</b>:
• "Show system performance stats"
• "How many documents do we have?"

⚙️ <b>Settings</b>:
• "Change OCR language to English"
• "Show active plugins"

💡 <b>Tips</b>:
• Use keywords
• Ask clear questions
• Use short commands
"""

        await query.message.edit_text(
            examples_text, reply_markup=ui_manager.help_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("Help examples", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "help_tips")
async def help_tips_callback(query: CallbackQuery) -> None:
    """Show help tips"""
    try:
        if ui_manager.default_language == "fa":
            tips_text = """
💡 <b>نکات مفید</b>

🎯 <b>بهترین روش‌ها</b>:
• سوالات خود را کوتاه و واضح بپرسید
• از کلمات کلیدی استفاده کنید
• برای جستجوی دقیق‌تر، جزئیات بیشتری ارائه دهید

⚡ <b>عملکرد بهتر</b>:
• فایل‌های کوچک‌تر سریع‌تر پردازش می‌شوند
• از فرمت‌های پشتیبانی شده استفاده کنید
• سیستم را مرتباً به‌روزرسانی کنید

🔒 <b>امنیت</b>:
• اطلاعات حساس را در سوالات قرار ندهید
• از دستورات امنیتی استفاده کنید
• دسترسی‌ها را بررسی کنید

📱 <b>استفاده موبایل</b>:
• از دکمه‌های کیبورد استفاده کنید
• پیام‌های کوتاه ارسال کنید
• از قابلیت‌های لمسی استفاده کنید
"""
        else:
            tips_text = """
💡 <b>Useful Tips</b>

🎯 <b>Best Practices</b>:
• Ask short and clear questions
• Use keywords
• Provide more details for precise search

⚡ <b>Better Performance</b>:
• Smaller files process faster
• Use supported formats
• Keep system updated regularly

🔒 <b>Security</b>:
• Don't include sensitive info in questions
• Use security commands
• Check access permissions

📱 <b>Mobile Usage</b>:
• Use keyboard buttons
• Send short messages
• Use touch features
"""

        await query.message.edit_text(tips_text, reply_markup=ui_manager.help_keyboard)
        await query.answer()
    except Exception:
        try:
            await query.answer("Help tips", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "help_advanced")
async def help_advanced_callback(query: CallbackQuery) -> None:
    """Show advanced help"""
    try:
        if ui_manager.default_language == "fa":
            advanced_text = """
🚀 <b>راهنمای پیشرفته</b>

🔧 <b>دستورات پیشرفته</b>:
• <b>/performance</b> - نمایش وضعیت عملکرد
• <b>/analytics</b> - تحلیل رفتار کاربر
• <b>/plugins</b> - مدیریت پلاگین‌ها
• <b>/monitoring</b> - مانیتورینگ سیستم

⚙️ <b>تنظیمات پیشرفته</b>:
• <b>/setchunk</b> [size] - تنظیم اندازه chunk
• <b>/setstrategy</b> [strategy] - تنظیم استراتژی
• <b>/setocr</b> [lang] - تنظیم زبان OCR

📊 <b>آمار و گزارش‌ها</b>:
• <b>/stats</b> - آمار کلی سیستم
• <b>/logs</b> - نمایش لاگ‌ها
• <b>/health</b> - وضعیت سلامت سیستم

🔐 <b>دستورات امنیتی</b>:
• <b>/auth</b> - احراز هویت
• <b>/permissions</b> - مدیریت دسترسی‌ها
• <b>/security</b> - تنظیمات امنیتی
"""
        else:
            advanced_text = """
🚀 <b>Advanced Guide</b>

🔧 <b>Advanced Commands</b>:
• <b>/performance</b> - Show performance status
• <b>/analytics</b> - User behavior analytics
• <b>/plugins</b> - Plugin management
• <b>/monitoring</b> - System monitoring

⚙️ <b>Advanced Settings</b>:
• <b>/setchunk</b> [size] - Set chunk size
• <b>/setstrategy</b> [strategy] - Set strategy
• <b>/setocr</b> [lang] - Set OCR language

📊 <b>Statistics & Reports</b>:
• <b>/stats</b> - System overview stats
• <b>/logs</b> - Show logs
• <b>/health</b> - System health status

🔐 <b>Security Commands</b>:
• <b>/auth</b> - Authentication
• <b>/permissions</b> - Access management
• <b>/security</b> - Security settings
"""

        await query.message.edit_text(
            advanced_text, reply_markup=ui_manager.help_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("Advanced help", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "help_security")
async def help_security_callback(query: CallbackQuery) -> None:
    """Show security help"""
    try:
        if ui_manager.default_language == "fa":
            security_text = """
🔐 <b>راهنمای امنیتی</b>

🛡️ <b>دستورات امنیتی</b>:
• <b>/auth</b> - احراز هویت کاربر
• <b>/permissions</b> - مدیریت دسترسی‌ها
• <b>/security</b> - تنظیمات امنیتی
• <b>/encrypt</b> - رمزنگاری داده‌ها

🔒 <b>امنیت داده‌ها</b>:
• تمام داده‌ها رمزنگاری می‌شوند
• دسترسی‌ها کنترل می‌شوند
• لاگ‌های امنیتی ثبت می‌شوند
• پشتیبان‌گیری منظم انجام می‌شود

⚠️ <b>هشدارهای امنیتی</b>:
• از اطلاعات حساس محافظت کنید
• دسترسی‌های غیرضروری را محدود کنید
• سیستم را مرتباً به‌روزرسانی کنید
• لاگ‌ها را بررسی کنید

🚨 <b>در صورت مشکل</b>:
• فوراً دسترسی را قطع کنید
• مدیر سیستم را مطلع کنید
• لاگ‌های مربوطه را بررسی کنید
• اقدامات امنیتی لازم را انجام دهید
"""
        else:
            security_text = """
🔐 <b>Security Guide</b>

🛡️ <b>Security Commands</b>:
• <b>/auth</b> - User authentication
• <b>/permissions</b> - Access management
• <b>/security</b> - Security settings
• <b>/encrypt</b> - Data encryption

🔒 <b>Data Security</b>:
• All data is encrypted
• Access is controlled
• Security logs are recorded
• Regular backups are performed

⚠️ <b>Security Warnings</b>:
• Protect sensitive information
• Limit unnecessary access
• Keep system updated
• Review logs regularly

🚨 <b>In Case of Issues</b>:
• Immediately cut access
• Notify system administrator
• Review relevant logs
• Take necessary security measures
"""

        await query.message.edit_text(
            security_text, reply_markup=ui_manager.help_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("Security help", show_alert=False)
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "help_analytics")
async def help_analytics_callback(query: CallbackQuery) -> None:
    """Show analytics help"""
    try:
        if ui_manager.default_language == "fa":
            analytics_text = """
📊 <b>راهنمای تحلیل</b>

📈 <b>دستورات تحلیل</b>:
• <b>/analytics</b> - تحلیل رفتار کاربر
• <b>/performance</b> - آمار عملکرد سیستم
• <b>/stats</b> - آمار کلی سیستم
• <b>/reports</b> - گزارش‌های تفصیلی

📊 <b>نوع آمار</b>:
• تعداد جلسات کاربر
• تعداد پرسش‌ها
• زمان پاسخ سیستم
• نرخ موفقیت عملیات

📋 <b>گزارش‌ها</b>:
• گزارش روزانه
• گزارش هفتگی
• گزارش ماهانه
• گزارش‌های سفارشی

💡 <b>نکات تحلیل</b>:
• آمارها هر ساعت به‌روزرسانی می‌شوند
• گزارش‌ها در قالب‌های مختلف ارائه می‌شوند
• امکان فیلتر کردن داده‌ها وجود دارد
• آمارها برای بهینه‌سازی استفاده می‌شوند
"""
        else:
            analytics_text = """
📊 <b>Analytics Guide</b>

📈 <b>Analytics Commands</b>:
• <b>/analytics</b> - User behavior analytics
• <b>/performance</b> - System performance stats
• <b>/stats</b> - System overview stats
• <b>/reports</b> - Detailed reports

📊 <b>Types of Statistics</b>:
• User session count
• Query count
• System response time
• Operation success rate

📋 <b>Reports</b>:
• Daily reports
• Weekly reports
• Monthly reports
• Custom reports

💡 <b>Analytics Tips</b>:
• Statistics are updated hourly
• Reports are provided in various formats
• Data filtering is available
• Statistics are used for optimization
"""

        await query.message.edit_text(
            analytics_text, reply_markup=ui_manager.help_keyboard
        )
        await query.answer()
    except Exception:
        try:
            await query.answer("Analytics help", show_alert=False)
        except Exception:
            pass
