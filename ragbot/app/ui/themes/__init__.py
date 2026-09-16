"""
Simple Themes for Telegram
"""

from aiogram.types import InlineKeyboardButton


class ThemeManager:
    """Simple theme manager"""

    def __init__(self):
        self.current_theme = "glassmorphism"

    def get_theme(self, theme_name: str = None):
        """Get theme instance"""
        return self

    def set_current_theme(self, theme_name: str):
        """Set current theme"""
        self.current_theme = theme_name
