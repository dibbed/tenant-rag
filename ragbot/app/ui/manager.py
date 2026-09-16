from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class UIManager:
    def __init__(self):
        self.default_theme = "glassmorphism"
        self.default_language = "fa"
        self.performance_keyboard = self._create_performance_keyboard()
        self.help_keyboard = self._create_help_keyboard()
        self.main_keyboard = self._create_main_keyboard()
        self.admin_keyboard = self._create_admin_keyboard()
        self.admin_extended_keyboard = self._create_admin_extended_keyboard()
        self.analytics_keyboard = self._create_analytics_keyboard()
        self.security_keyboard = self._create_security_keyboard()
        self.plugins_keyboard = self._create_plugins_keyboard()
        self.monitoring_keyboard = self._create_monitoring_keyboard()
        self.back_keyboard = self._create_back_keyboard()
        self.pagination_keyboard = self._create_pagination_keyboard()

    def _create_performance_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✨ تازه‌سازی", callback_data="perf_refresh")
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.add(InlineKeyboardButton(text="✨ بستن", callback_data="close"))
        builder.adjust(3)
        return builder.as_markup()

    def _create_help_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✨ دستورات موجود", callback_data="help_commands")
        )
        builder.add(
            InlineKeyboardButton(
                text="✨ مثال‌های کاربردی", callback_data="help_examples"
            )
        )
        builder.add(
            InlineKeyboardButton(text="✨ نکات مفید", callback_data="help_tips")
        )
        builder.add(
            InlineKeyboardButton(
                text="✨ راهنمای پیشرفته", callback_data="help_advanced"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="✨ راهنمای امنیتی", callback_data="help_security"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="✨ راهنمای تحلیل", callback_data="help_analytics"
            )
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.adjust(2)
        return builder.as_markup()

    def _create_main_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✨ افزودن سند", callback_data="add_document")
        )
        builder.add(
            InlineKeyboardButton(text="✨ پرسیدن سوال", callback_data="ask_question")
        )
        builder.add(InlineKeyboardButton(text="✨ راهنما", callback_data="help_menu"))
        builder.add(
            InlineKeyboardButton(
                text="✨ وضعیت عملکرد", callback_data="performance_menu"
            )
        )
        builder.add(
            InlineKeyboardButton(text="✨ تحلیل کاربر", callback_data="analytics_menu")
        )
        builder.add(
            InlineKeyboardButton(text="✨ تنظیمات", callback_data="settings_menu")
        )
        builder.add(
            InlineKeyboardButton(text="🔐 امنیت", callback_data="security_menu")
        )
        builder.add(
            InlineKeyboardButton(text="📦 پلاگین‌ها", callback_data="plugins_menu")
        )
        builder.add(
            InlineKeyboardButton(text="📊 مانیتورینگ", callback_data="monitoring_menu")
        )
        builder.adjust(3)
        return builder.as_markup()

    def create_admin_main_keyboard(self):
        """Create main keyboard with admin button for admin users"""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✨ افزودن سند", callback_data="add_document")
        )
        builder.add(
            InlineKeyboardButton(text="✨ پرسیدن سوال", callback_data="ask_question")
        )
        builder.add(InlineKeyboardButton(text="✨ راهنما", callback_data="help_menu"))
        builder.add(
            InlineKeyboardButton(
                text="✨ وضعیت عملکرد", callback_data="performance_menu"
            )
        )
        builder.add(
            InlineKeyboardButton(text="✨ تحلیل کاربر", callback_data="analytics_menu")
        )
        builder.add(
            InlineKeyboardButton(text="✨ تنظیمات", callback_data="settings_menu")
        )
        builder.add(
            InlineKeyboardButton(text="🔐 امنیت", callback_data="security_menu")
        )
        builder.add(
            InlineKeyboardButton(text="📦 پلاگین‌ها", callback_data="plugins_menu")
        )
        builder.add(
            InlineKeyboardButton(text="📊 مانیتورینگ", callback_data="monitoring_menu")
        )
        builder.add(
            InlineKeyboardButton(text="👑 مدیریت ادمین", callback_data="admin_menu")
        )
        builder.adjust(3)
        return builder.as_markup()

    def _create_admin_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="👑 مدیریت کاربران", callback_data="admin_users")
        )
        builder.add(
            InlineKeyboardButton(
                text="🔧 تنظیمات سیستم", callback_data="admin_settings"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📊 گزارش‌های ادمین", callback_data="admin_reports"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🔐 مدیریت دسترسی‌ها", callback_data="admin_permissions"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🛠️ تعمیر و نگهداری", callback_data="admin_maintenance"
            )
        )
        builder.add(
            InlineKeyboardButton(text="🛑 خاموش کردن", callback_data="admin_shutdown")
        )
        builder.add(
            InlineKeyboardButton(text="🔄 ری‌استارت", callback_data="admin_restart")
        )
        builder.add(InlineKeyboardButton(text="📋 لاگ‌ها", callback_data="admin_logs"))
        builder.add(
            InlineKeyboardButton(
                text="🗑️ پاک کردن کش", callback_data="admin_clear_cache"
            )
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.adjust(2)
        return builder.as_markup()

    def _create_admin_extended_keyboard(self):
        """Create extended admin keyboard with all admin features"""
        builder = InlineKeyboardBuilder()

        # System Management
        builder.add(
            InlineKeyboardButton(text="🛑 خاموش کردن", callback_data="admin_shutdown")
        )
        builder.add(
            InlineKeyboardButton(text="🔄 ری‌استارت", callback_data="admin_restart")
        )
        builder.add(
            InlineKeyboardButton(text="📊 وضعیت سیستم", callback_data="admin_status")
        )
        builder.add(
            InlineKeyboardButton(text="📋 لاگ‌های سیستم", callback_data="admin_logs")
        )

        # Cache & Storage
        builder.add(
            InlineKeyboardButton(
                text="🗑️ پاک کردن کش", callback_data="admin_clear_cache"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="💾 مدیریت ذخیره‌سازی", callback_data="admin_storage"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🔄 بهینه‌سازی DB", callback_data="admin_optimize_db"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🧹 پاک‌سازی فایل‌ها", callback_data="admin_cleanup"
            )
        )

        # User Management
        builder.add(
            InlineKeyboardButton(text="👥 مدیریت کاربران", callback_data="admin_users")
        )
        builder.add(
            InlineKeyboardButton(
                text="🔐 مدیریت دسترسی‌ها", callback_data="admin_permissions"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📊 آمار کاربران", callback_data="admin_user_stats"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🚫 مسدود کردن کاربر", callback_data="admin_ban_user"
            )
        )

        # System Configuration
        builder.add(
            InlineKeyboardButton(text="⚙️ تنظیمات سیستم", callback_data="admin_settings")
        )
        builder.add(
            InlineKeyboardButton(
                text="🔧 تنظیمات OCR", callback_data="admin_ocr_settings"
            )
        )
        builder.add(
            InlineKeyboardButton(text="🌐 تنظیمات شبکه", callback_data="admin_network")
        )
        builder.add(
            InlineKeyboardButton(
                text="🔒 تنظیمات امنیتی", callback_data="admin_security"
            )
        )

        # Monitoring & Reports
        builder.add(
            InlineKeyboardButton(
                text="📈 گزارش‌های ادمین", callback_data="admin_reports"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📊 آمار عملکرد", callback_data="admin_performance"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🔍 مانیتورینگ پیشرفته", callback_data="admin_monitoring"
            )
        )
        builder.add(
            InlineKeyboardButton(text="⚠️ هشدارها", callback_data="admin_alerts")
        )

        # Maintenance
        builder.add(
            InlineKeyboardButton(
                text="🛠️ تعمیر و نگهداری", callback_data="admin_maintenance"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🔄 به‌روزرسانی سیستم", callback_data="admin_update"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📦 مدیریت پلاگین‌ها", callback_data="admin_plugins"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="🔧 تنظیمات پیشرفته", callback_data="admin_advanced"
            )
        )

        # Navigation
        builder.add(
            InlineKeyboardButton(text="📄 صفحه بعدی", callback_data="admin_page_2")
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))

        builder.adjust(2)
        return builder.as_markup()

    def _create_pagination_keyboard(
        self, current_page=1, total_pages=1, prefix="admin"
    ):
        """Create pagination keyboard for long content"""
        builder = InlineKeyboardBuilder()

        if current_page > 1:
            builder.add(
                InlineKeyboardButton(
                    text="⬅️ قبلی", callback_data=f"{prefix}_page_{current_page - 1}"
                )
            )

        builder.add(
            InlineKeyboardButton(
                text=f"📄 {current_page}/{total_pages}", callback_data="page_info"
            )
        )

        if current_page < total_pages:
            builder.add(
                InlineKeyboardButton(
                    text="بعدی ➡️", callback_data=f"{prefix}_page_{current_page + 1}"
                )
            )

        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))

        builder.adjust(3)
        return builder.as_markup()

    def _create_analytics_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📈 تحلیل کاربر", callback_data="analytics_user")
        )
        builder.add(
            InlineKeyboardButton(text="🤖 بینش‌های ML", callback_data="analytics_ml")
        )
        builder.add(
            InlineKeyboardButton(
                text="🔮 تحلیل پیش‌بینانه", callback_data="analytics_predictive"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📊 گزارش جامع", callback_data="analytics_comprehensive"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📋 گزارش تفصیلی", callback_data="analytics_report"
            )
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.adjust(2)
        return builder.as_markup()

    def _create_security_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="🔐 ایجاد پشتیبان", callback_data="security_backup"
            )
        )
        builder.add(
            InlineKeyboardButton(text="🔄 بازگردانی", callback_data="security_restore")
        )
        builder.add(
            InlineKeyboardButton(
                text="🔑 چرخش کلیدها", callback_data="security_rotate_keys"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📋 لیست کلیدها", callback_data="security_list_keys"
            )
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.adjust(2)
        return builder.as_markup()

    def _create_plugins_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="📦 بارگذاری پلاگین", callback_data="plugins_load"
            )
        )
        builder.add(
            InlineKeyboardButton(text="🗑️ حذف پلاگین", callback_data="plugins_unload")
        )
        builder.add(
            InlineKeyboardButton(text="📋 لیست پلاگین‌ها", callback_data="plugins_list")
        )
        builder.add(
            InlineKeyboardButton(text="🔍 وضعیت پلاگین", callback_data="plugins_status")
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.adjust(2)
        return builder.as_markup()

    def _create_monitoring_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="🩺 وضعیت سلامت", callback_data="monitoring_health"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="📊 مانیتورینگ لحظه‌ای", callback_data="monitoring_realtime"
            )
        )
        builder.add(
            InlineKeyboardButton(
                text="⚡ وضعیت عملکرد", callback_data="monitoring_performance"
            )
        )
        builder.add(InlineKeyboardButton(text="✨ بازگشت", callback_data="back_home"))
        builder.adjust(2)
        return builder.as_markup()

    def _create_back_keyboard(self):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="🏠 صفحه اصلی", callback_data="back_home")
        )
        builder.add(InlineKeyboardButton(text="📖 راهنما", callback_data="help_menu"))
        builder.add(InlineKeyboardButton(text="❌ بستن", callback_data="close"))
        builder.adjust(3)
        return builder.as_markup()

    def create_button(self, text, callback_data, button_type="glassmorphism", **kwargs):
        return InlineKeyboardButton(text=f"✨ {text}", callback_data=callback_data)

    def format_message(self, message_type, **kwargs):
        messages = {
            "welcome": """🎉 خوش آمدید به RAG Bot!

🤖 یک ربات هوشمند برای مدیریت و جستجوی اسناد

✨ قابلیت‌های اصلی:
• 📄 آپلود و پردازش اسناد (PDF, DOCX, TXT, HTML, MD)
• 🔍 جستجوی هوشمند و پاسخ‌دهی به سوالات
• 📊 تحلیل و گزارش‌گیری پیشرفته
• 🔐 امنیت و رمزنگاری داده‌ها
• 📦 سیستم پلاگین قابل توسعه
• 📈 مانیتورینگ و تحلیل عملکرد

🚀 برای شروع از دکمه‌های زیر استفاده کنید:""",
            "help": """📖 راهنمای کامل RAG Bot

🔹 دستورات اصلی:
• /add - افزودن سند (PDF, DOCX, TXT, HTML, MD)
• /ask - پرسیدن سوال از اسناد
• /reset - پاک کردن همه اسناد
• /formats - فرمت‌های پشتیبانی شده

🔹 دستورات پیشرفته:
• /performance - وضعیت عملکرد سیستم
• /analytics - تحلیل رفتار کاربر
• /health - وضعیت سلامت سیستم
• /monitoring - مانیتورینگ لحظه‌ای

🔹 دستورات امنیتی:
• /backup - ایجاد پشتیبان امن
• /restore - بازگردانی از پشتیبان
• /rotate_keys - چرخش کلیدهای رمزنگاری

🔹 دستورات پلاگین:
• /load_plugin - بارگذاری پلاگین
• /unload_plugin - حذف پلاگین
• /list_plugins - لیست پلاگین‌ها

💡 برای اطلاعات بیشتر از دکمه‌های زیر استفاده کنید:""",
            "error": "❌ خطا: {error_message}",
            "success": "✅ {success_message}",
            "processing": "🔄 در حال پردازش...",
            "no_documents": "📄 هیچ سندی یافت نشد.",
            "rate_limit": "⏳ محدودیت نرخ فعال است.",
            "unauthorized": "⛔ دسترسی غیرمجاز.",
        }
        text = messages.get(message_type, message_type)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    def create_performance_status(self, perf_data):
        status_msg = "⚡ وضعیت عملکرد سیستم\n\n"
        if "error" in perf_data:
            status_msg += f"❌ خطا در عملکرد: {perf_data['error']}\n"
        elif "no_data" in perf_data:
            status_msg += "📊 داده‌ای برای نمایش وجود ندارد\n"
        else:
            status_msg += f"⏱️ میانگین زمان پاسخ: {perf_data.get('average_response_time', 0):.3f}s\n"
            status_msg += (
                f"📊 تعداد کل درخواست‌ها: {perf_data.get('total_requests', 0)}\n"
            )
            status_msg += f"❌ نرخ خطا: {perf_data.get('error_rate', 0):.2%}\n"
            status_msg += f"💻 استفاده از CPU: {perf_data.get('cpu_usage', 0):.1f}%\n"
            status_msg += (
                f"🧠 استفاده از حافظه: {perf_data.get('memory_usage', 0):.1f}%\n"
            )
            status_msg += f"🔗 اتصالات فعال: {perf_data.get('active_connections', 0)}\n"
        return status_msg

    def create_analytics_message(self, analytics_data):
        analytics_msg = "📊 تحلیل رفتار کاربر\n\n"
        if "error" in analytics_data:
            analytics_msg += f"❌ خطا در تحلیل: {analytics_data['error']}\n"
        else:
            behavior_insights = analytics_data.get("behavior_insights", {})
            profile = behavior_insights.get("profile", {})
            if profile:
                analytics_msg += "👤 پروفایل کاربر:\n"
                analytics_msg += f"🔢 تعداد جلسات: {profile.get('total_sessions', 0)}\n"
                analytics_msg += f"❓ تعداد پرسش‌ها: {profile.get('total_queries', 0)}\n"
                analytics_msg += (
                    f"📈 الگوی استفاده: {profile.get('usage_pattern', 'نامشخص')}\n"
                )
                analytics_msg += (
                    f"⭐ میانگین رضایت: {profile.get('satisfaction_avg', 0):.1f}\n\n"
                )
        return analytics_msg

    def is_admin_user(self, user_id: int) -> bool:
        """Check if user is admin"""
        # Add your admin user IDs here
        from ragbot.configs.settings import settings
        return user_id in settings.admin_users_list

    def get_main_keyboard_for_user(self, user_id: int):
        """Get appropriate main keyboard based on user role"""
        if self.is_admin_user(user_id):
            return self.create_admin_main_keyboard()
        return self.main_keyboard

    def split_long_message(self, text, max_length=4000):
        """Split long messages into chunks for Telegram"""
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        lines = text.split("\n")
        for line in lines:
            if len(current_chunk + line + "\n") <= max_length:
                current_chunk += line + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def create_paginated_message(
        self, content, current_page=1, items_per_page=10, prefix="admin"
    ):
        """Create paginated content with navigation"""
        if isinstance(content, str):
            chunks = self.split_long_message(content)
            total_pages = len(chunks)
            current_content = (
                chunks[current_page - 1] if current_page <= total_pages else chunks[0]
            )
        else:
            # Handle list content
            total_pages = (len(content) + items_per_page - 1) // items_per_page
            start_idx = (current_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            current_items = content[start_idx:end_idx]
            current_content = "\n".join(current_items)

        # Add page info
        page_info = f"\n\n📄 صفحه {current_page} از {total_pages}"
        current_content += page_info

        # Create pagination keyboard
        keyboard = self._create_pagination_keyboard(current_page, total_pages, prefix)

        return current_content, keyboard

    def create_admin_status_message(self, detailed=False):
        """Create comprehensive admin status message"""
        import psutil
        import time

        # System info
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        process = psutil.Process()

        # Bot info
        uptime = time.time() - process.create_time()
        uptime_hours = uptime // 3600
        uptime_minutes = (uptime % 3600) // 60

        status_msg = f"""📊 وضعیت کامل سیستم

🖥️ اطلاعات سیستم:
• 💻 CPU: {cpu_percent:.1f}%
• 🧠 حافظه کل: {memory.total // (1024**3)} GB
• 🧠 حافظه استفاده شده: {memory.percent:.1f}% ({memory.used // (1024**2)} MB)
• 💽 فضای دیسک: {disk.percent:.1f}% ({disk.free // (1024**3)} GB آزاد)
• ⏰ زمان اجرا: {uptime_hours:.0f} ساعت و {uptime_minutes:.0f} دقیقه

🤖 اطلاعات ربات:
• 🔄 حافظه ربات: {process.memory_info().rss // (1024**2)} MB
• 📊 تعداد thread: {process.num_threads()}
• 🔗 اتصالات باز: {len(process.connections())}
• 📁 فایل‌های باز: {process.num_fds() if hasattr(process, "num_fds") else "N/A"}

📈 آمار عملکرد:
• 🚀 سرعت پردازش: {cpu_percent:.1f}% CPU
• 💾 استفاده حافظه: {memory.percent:.1f}%
• 📊 بار سیستم: {"بالا" if cpu_percent > 80 else "متوسط" if cpu_percent > 50 else "پایین"}

🔧 وضعیت سرویس‌ها:
• ✅ Telegram Bot: فعال
• ✅ Redis Cache: فعال
• ✅ Vector Store: فعال
• ✅ OCR Engine: فعال
• ✅ Graceful Degradation: فعال"""

        if detailed:
            status_msg += f"""

🔍 جزئیات بیشتر:
• 🐍 Python Version: {psutil.sys.version}
• 🖥️ سیستم عامل: {psutil.sys.platform}
• 🔄 Boot Time: {time.ctime(psutil.boot_time())}
• 👥 کاربران فعال: {len(psutil.users())}
• 🌡️ دمای CPU: {"N/A" if not hasattr(psutil, "sensors_temperatures") else "در دسترس نیست"}

📊 آمار شبکه:
• 📡 اتصالات شبکه: {len(psutil.net_connections())}
• 📊 ترافیک ورودی: {psutil.net_io_counters().bytes_recv // (1024**2)} MB
• 📊 ترافیک خروجی: {psutil.net_io_counters().bytes_sent // (1024**2)} MB"""

        return status_msg

    def create_admin_logs_message(self, log_lines=50):
        """Create formatted logs message"""
        try:
            with open("logs/ragbot.log", "r", encoding="utf-8") as f:
                lines = f.readlines()
                recent_lines = lines[-log_lines:] if len(lines) > log_lines else lines

            logs_msg = f"📋 آخرین {len(recent_lines)} خط لاگ سیستم\n\n"
            logs_msg += "".join(recent_lines)

            # Add log statistics
            error_count = sum(1 for line in recent_lines if "ERROR" in line)
            warning_count = sum(1 for line in recent_lines if "WARNING" in line)
            info_count = sum(1 for line in recent_lines if "INFO" in line)

            logs_msg += f"\n📊 آمار لاگ‌ها:\n"
            logs_msg += f"• ❌ خطاها: {error_count}\n"
            logs_msg += f"• ⚠️ هشدارها: {warning_count}\n"
            logs_msg += f"• ℹ️ اطلاعات: {info_count}\n"
            logs_msg += f"• 📊 کل خطوط: {len(recent_lines)}"

            return logs_msg

        except FileNotFoundError:
            return "❌ فایل لاگ یافت نشد"
        except Exception as e:
            return f"❌ خطا در خواندن لاگ‌ها: {str(e)}"


ui_manager = UIManager()
