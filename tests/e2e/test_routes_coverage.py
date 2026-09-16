"""
Additional coverage tests for app.routes helpers and error branches.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiogram.types import Message, Chat, User, Document

import ragbot.app.routes as routes


@pytest.mark.asyncio
async def test_maybe_await_exception_path():
    class Evil:
        def __getattr__(self, name):
            if name == "__await__":
                raise RuntimeError("boom")
            raise AttributeError()

    out = await routes._maybe_await(Evil())
    assert isinstance(out, Evil)


@pytest.mark.asyncio
async def test_get_document_service_cached():
    # Ensure function sets and returns a service instance
    with patch("ragbot.app.routes.DocumentService") as DS:
        DS.return_value = MagicMock()
        s1 = await routes.get_document_service()
        s2 = await routes.get_document_service()
        assert s1 is s2


@pytest.mark.asyncio
async def test_safe_reply_exception_path():
    class FakeMsg:
        def reply(self, *_a, **_k):
            raise RuntimeError("fail")

    await routes._safe_reply(FakeMsg(), "hi")


def test_is_user_authorized_exception_path(monkeypatch):
    class BadSettings:
        @property
        def allow_users_list(self):
            raise RuntimeError("bad")

    monkeypatch.setattr(routes, "settings", BadSettings(), raising=False)
    assert routes.is_user_authorized(1) is True


@pytest.mark.asyncio
async def test_start_handler_error_branch():
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/start")
    with patch.object(routes.logger, "info", side_effect=Exception("x")):
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await routes.start_handler(msg)
            assert mock_reply.called


@pytest.mark.asyncio
async def test_help_handler_error_branch():
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/help")
    with patch.object(routes.logger, "info", side_effect=Exception("x")):
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await routes.help_handler(msg)
            assert mock_reply.called


@pytest.mark.asyncio
async def test_status_handler_error_branch():
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/status")
    with patch("ragbot.app.routes.get_rag_service", side_effect=Exception("x")):
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await routes.status_handler(msg)
            assert mock_reply.called


@pytest.mark.asyncio
async def test_add_handler_file_too_large():
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    doc = Document(file_id="f", file_unique_id="u", file_name="x.pdf", mime_type="application/pdf", file_size=10**9)
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="document", options={}, document=doc)
    with patch("aiogram.types.Message.reply") as mock_reply:
        status = AsyncMock()
        status.edit_text = AsyncMock()
        mock_reply.return_value = status
        await routes.add_handler(msg)
        assert status.edit_text.called


@pytest.mark.asyncio
async def test_add_handler_no_text_no_doc():
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="")
    with patch("aiogram.types.Message.reply") as mock_reply:
        status = AsyncMock()
        status.edit_text = AsyncMock()
        mock_reply.return_value = status
        await routes.add_handler(msg)
        assert status.edit_text.called


@pytest.mark.asyncio
async def test_reset_handler_general_exception():
    user = User(id=1, is_bot=False, first_name="A")
    chat = Chat(id=1, type="private")
    msg = Message(message_id=1, date=123, chat=chat, from_user=user, content_type="text", options={}, text="/reset")
    with patch("ragbot.app.routes.get_rag_service", side_effect=Exception("x")):
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await routes.reset_handler(msg)
            assert mock_reply.called

