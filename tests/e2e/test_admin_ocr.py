"""
Tests for admin OCR toggle and engine selection commands.
"""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Message, Chat, User

from ragbot.app.routes import ocr_on_handler, ocr_off_handler, set_ocr_engine_handler
from ragbot.configs.settings import settings


@pytest.mark.asyncio
async def test_ocr_on_off_toggle(monkeypatch):
    user = User(id=42, is_bot=False, first_name="Admin")
    chat = Chat(id=1, type="private")
    msg_on = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/ocron")
    msg_off = Message(message_id=2, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/ocroff")

    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("ragbot.app.routes.is_user_authorized", return_value=True):
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await ocr_on_handler(msg_on)
            assert settings.rag.ocr_enabled is True
            await ocr_off_handler(msg_off)
            assert settings.rag.ocr_enabled is False


@pytest.mark.asyncio
async def test_set_ocr_engine_command(monkeypatch):
    user = User(id=42, is_bot=False, first_name="Admin")
    chat = Chat(id=1, type="private")
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/setocr easyocr")

    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("ragbot.app.routes.is_user_authorized", return_value=True):
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await set_ocr_engine_handler(msg)
            assert settings.rag.ocr_engine == "easyocr"

