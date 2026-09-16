"""
Simple UI Components for Telegram
"""

from aiogram.types import InlineKeyboardButton


class GlassmorphismButton:
    """Simple button with sparkle emoji"""

    def __init__(self, text: str, callback_data: str, **kwargs):
        self.text = text
        self.callback_data = callback_data

    def render(self) -> InlineKeyboardButton:
        """Render button with sparkle emoji"""
        return InlineKeyboardButton(
            text=f"✨ {self.text}", callback_data=self.callback_data
        )


class ModernButton:
    """Simple button with diamond emoji"""

    def __init__(self, text: str, callback_data: str, **kwargs):
        self.text = text
        self.callback_data = callback_data

    def render(self) -> InlineKeyboardButton:
        """Render button with diamond emoji"""
        return InlineKeyboardButton(
            text=f"🔹 {self.text}", callback_data=self.callback_data
        )


class ClassicButton:
    """Simple button with square emoji"""

    def __init__(self, text: str, callback_data: str, **kwargs):
        self.text = text
        self.callback_data = callback_data

    def render(self) -> InlineKeyboardButton:
        """Render button with square emoji"""
        return InlineKeyboardButton(
            text=f"▫️ {self.text}", callback_data=self.callback_data
        )
