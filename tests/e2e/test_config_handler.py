"""
Tests for /config handler and env-backed OCR defaults.
"""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Chat, Message, User

from ragbot.app.routes import config_handler
from ragbot.configs.settings import settings
from ragbot.rag.loaders.pdf import PDFLoader


@pytest.mark.asyncio
async def test_config_handler_en(monkeypatch) -> None:
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    msg = Message(
        message_id=1,
        date=123,
        chat=chat,
        from_user=user,
        content_type="text",
        options={},
        text="/config",
    )
    # Force EN for deterministic message
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("aiogram.types.Message.reply") as mock_reply:
        mock_reply.return_value = AsyncMock()
        await config_handler(msg)
        assert mock_reply.called


def test_pdf_loader_env_defaults(monkeypatch):
    # Configure settings.rag defaults
    monkeypatch.setattr(settings.rag, "ocr_enabled", True, raising=False)
    monkeypatch.setattr(settings.rag, "ocr_engine", "easyocr", raising=False)
    monkeypatch.setattr(settings.rag, "ocr_lang", "fa", raising=False)
    monkeypatch.setattr(settings.rag, "google_token_path", "token.json", raising=False)

    loader = PDFLoader()
    assert loader.extract_images is True
    assert loader.ocr_engine == "easyocr"
    assert loader.ocr_lang == "fa"
    assert loader.google_token_path == "token.json"
