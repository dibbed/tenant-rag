"""
Simple Localization for Telegram
"""


class LocalizationManager:
    """Simple localization manager"""

    def __init__(self, language: str = "fa"):
        self.language = language
        self.translations = {
            "fa": {
                "refresh": "تازه‌سازی",
                "back": "بازگشت",
                "close": "بستن",
                "help_commands": "دستورات موجود",
                "help_examples": "مثال‌های کاربردی",
                "help_tips": "نکات مفید",
                "help_advanced": "راهنمای پیشرفته",
                "help_security": "راهنمای امنیتی",
                "help_analytics": "راهنمای تحلیل",
                "welcome": "🎉 خوش آمدید به RAG Bot!",
                "help": "📖 راهنمای استفاده",
                "error": "❌ خطا: {error_message}",
                "success": "✅ {success_message}",
                "processing": "🔄 در حال پردازش...",
                "no_documents": "📄 هیچ سندی یافت نشد.",
                "rate_limit": "⏳ محدودیت نرخ فعال است.",
                "unauthorized": "⛔ دسترسی غیرمجاز.",
            },
            "en": {
                "refresh": "Refresh",
                "back": "Back",
                "close": "Close",
                "help_commands": "Available Commands",
                "help_examples": "Usage Examples",
                "help_tips": "Useful Tips",
                "help_advanced": "Advanced Guide",
                "help_security": "Security Guide",
                "help_analytics": "Analytics Guide",
                "welcome": "🎉 Welcome to RAG Bot!",
                "help": "📖 User Guide",
                "error": "❌ Error: {error_message}",
                "success": "✅ {success_message}",
                "processing": "🔄 Processing...",
                "no_documents": "📄 No documents found.",
                "rate_limit": "⏳ Rate limit exceeded.",
                "unauthorized": "⛔ Unauthorized access.",
            },
        }

    def get(self, key: str, **kwargs) -> str:
        """Get translated text"""
        translations = self.translations.get(self.language, self.translations["fa"])
        text = translations.get(key, key)

        # Format with kwargs if provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass

        return text

    def set_language(self, language: str):
        """Set language"""
        if language in self.translations:
            self.language = language
