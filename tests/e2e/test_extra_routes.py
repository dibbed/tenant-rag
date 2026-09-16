"""
Additional route handler smoke tests to improve coverage of /start and /status.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, User, Chat

from ragbot.app.routes import (
    start_handler,
    status_handler,
    help_handler,
    add_handler,
    ask_handler,
    reset_handler,
)
from ragbot.configs.settings import settings
from ragbot.rag.exceptions import VectorStoreError, EmbeddingError


@pytest.fixture
def fake_user() -> User:
    return User(
        id=12345,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
    )


@pytest.fixture
def fake_chat() -> Chat:
    return Chat(id=67890, type="private")


@pytest.mark.asyncio
async def test_start_handler_smoke(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=1,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/start",
    )

    # Patch reply to return an awaitable mock
    with patch("aiogram.types.Message.reply") as mock_reply:
        mock_status_message = AsyncMock()
        mock_reply.return_value = mock_status_message
        await start_handler(message)
        assert mock_reply.called


@pytest.mark.asyncio
async def test_status_handler_smoke(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=1,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/status",
    )

    # Prepare a minimal health status object
    component_health = SimpleNamespace(status="healthy", response_time=12.34)
    health_status = SimpleNamespace(
        overall_status="ok",
        timestamp=datetime.utcnow(),
        uptime=123.4,
        components={"vector_store": component_health, "embedder": component_health},
    )

    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_health_status = AsyncMock(return_value=health_status)
        mock_get_service.return_value = mock_service

        # Patch reply to return an awaitable mock
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_status_message = AsyncMock()
            mock_reply.return_value = mock_status_message
            await status_handler(message)
            assert mock_service.get_health_status.called
            assert mock_reply.called


@pytest.mark.asyncio
async def test_start_handler_english(fake_user: User, fake_chat: Chat, monkeypatch) -> None:
    message = Message(
        message_id=2,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/start",
    )
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("aiogram.types.Message.reply") as mock_reply:
        mock_reply.return_value = AsyncMock()
        await start_handler(message)
        assert mock_reply.called


@pytest.mark.asyncio
async def test_help_handler_english(fake_user: User, fake_chat: Chat, monkeypatch) -> None:
    message = Message(
        message_id=3,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/help",
    )
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("aiogram.types.Message.reply") as mock_reply:
        mock_reply.return_value = AsyncMock()
        await help_handler(message)
        assert mock_reply.called


@pytest.mark.asyncio
async def test_status_handler_english(fake_user: User, fake_chat: Chat, monkeypatch) -> None:
    message = Message(
        message_id=4,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/status",
    )
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    component_health = SimpleNamespace(status="healthy", response_time=3.21)
    health_status = SimpleNamespace(
        overall_status="ok",
        timestamp=datetime.utcnow(),
        uptime=42.0,
        components={"store": component_health},
    )
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_health_status = AsyncMock(return_value=health_status)
        mock_get_service.return_value = mock_service
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await status_handler(message)
            assert mock_reply.called


@pytest.mark.asyncio
async def test_add_handler_text_english(fake_user: User, fake_chat: Chat, monkeypatch) -> None:
    message = Message(
        message_id=5,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/add This is a test",
    )
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.ingest_document = AsyncMock(
            return_value=SimpleNamespace(success=True, document_id="id123", chunks_created=2, processing_time=0.12)
        )
        mock_get_service.return_value = mock_service
        with patch("aiogram.types.Message.reply") as mock_reply:
            status = AsyncMock()
            status.edit_text = AsyncMock()
            mock_reply.return_value = status
            await add_handler(message)
            assert mock_service.ingest_document.called
            assert status.edit_text.called


@pytest.mark.asyncio
async def test_add_handler_no_input(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=6,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/add",
    )
    with patch("aiogram.types.Message.reply") as mock_reply:
        status = AsyncMock()
        status.edit_text = AsyncMock()
        mock_reply.return_value = status
        await add_handler(message)
        assert status.edit_text.called


@pytest.mark.asyncio
async def test_ask_handler_english(fake_user: User, fake_chat: Chat, monkeypatch) -> None:
    message = Message(
        message_id=7,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/ask What is coverage?",
    )
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.query_documents = AsyncMock(
            return_value=SimpleNamespace(answer="An indicator.", sources=["doc"], confidence_score=0.8, processing_time=0.01)
        )
        mock_get_service.return_value = mock_service
        with patch("aiogram.types.Message.reply") as mock_reply:
            status = AsyncMock()
            status.edit_text = AsyncMock()
            mock_reply.return_value = status
            await ask_handler(message)
            assert status.edit_text.called


@pytest.mark.asyncio
async def test_add_handler_reply_fallback(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=12,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/add content",
    )
    with patch("aiogram.types.Message.reply") as mock_reply:
        mock_reply.side_effect = Exception("boom")
        with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(
                return_value=SimpleNamespace(success=True, document_id="idX", chunks_created=1, processing_time=0.01)
            )
            mock_get_service.return_value = mock_service
            await add_handler(message)


@pytest.mark.asyncio
async def test_add_handler_processing_error(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=13,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/add text",
    )
    with patch("aiogram.types.Message.reply") as mock_reply:
        status = AsyncMock()
        status.edit_text = AsyncMock()
        mock_reply.return_value = status
        with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(
                return_value=SimpleNamespace(success=False, error_message="bad")
            )
            mock_get_service.return_value = mock_service
            await add_handler(message)
            assert status.edit_text.called


@pytest.mark.asyncio
async def test_add_handler_exceptions(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=14,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/add text",
    )
    # VectorStoreError path
    with patch("aiogram.types.Message.reply") as mock_reply:
        status = AsyncMock()
        status.edit_text = AsyncMock()
        mock_reply.return_value = status
        with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(side_effect=VectorStoreError("oops"))
            mock_get_service.return_value = mock_service
            await add_handler(message)
            assert status.edit_text.called
    # DocumentProcessingError path
    from ragbot.rag.exceptions import DocumentProcessingError
    with patch("aiogram.types.Message.reply") as mock_reply:
        status = AsyncMock()
        status.edit_text = AsyncMock()
        mock_reply.return_value = status
        with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(side_effect=DocumentProcessingError("bad doc"))
            mock_get_service.return_value = mock_service
            await add_handler(message)
            assert status.edit_text.called


@pytest.mark.asyncio
async def test_ask_handler_reply_fallback(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=15,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/ask hello",
    )
    with patch("aiogram.types.Message.reply") as mock_reply:
        mock_reply.side_effect = Exception("boom")
        with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(
                return_value=SimpleNamespace(answer="ok", sources=[], confidence_score=0.1, processing_time=0.01)
            )
            mock_get_service.return_value = mock_service
            await ask_handler(message)


@pytest.mark.asyncio
async def test_reset_handler_with_reset_store_only(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=16,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/reset",
    )
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        class _Svc:
            async def reset_store(self):
                return True
        mock_get_service.return_value = _Svc()
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await reset_handler(message)

    # VectorStoreError path
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        svc = MagicMock()
        svc.reset_vector_store = AsyncMock(side_effect=VectorStoreError("fail"))
        mock_get_service.return_value = svc
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await reset_handler(message)


@pytest.mark.asyncio
async def test_ask_handler_vector_store_error(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=8,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/ask VS error",
    )
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.query_documents = AsyncMock(side_effect=VectorStoreError("boom"))
        mock_get_service.return_value = mock_service
        with patch("aiogram.types.Message.reply") as mock_reply:
            status = AsyncMock()
            status.edit_text = AsyncMock()
            mock_reply.return_value = status
            await ask_handler(message)
            assert status.edit_text.called


@pytest.mark.asyncio
async def test_ask_handler_embedding_error(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=9,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/ask Emb error",
    )
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.query_documents = AsyncMock(side_effect=EmbeddingError("nope"))
        mock_get_service.return_value = mock_service
        with patch("aiogram.types.Message.reply") as mock_reply:
            status = AsyncMock()
            status.edit_text = AsyncMock()
            mock_reply.return_value = status
            await ask_handler(message)
            assert status.edit_text.called


@pytest.mark.asyncio
async def test_reset_handler_english(fake_user: User, fake_chat: Chat, monkeypatch) -> None:
    message = Message(
        message_id=10,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/reset",
    )
    monkeypatch.setattr(settings, "default_lang", "en", raising=False)
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        svc = MagicMock()
        svc.reset_vector_store = AsyncMock(return_value=True)
        mock_get_service.return_value = svc
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await reset_handler(message)
            assert mock_reply.called


@pytest.mark.asyncio
async def test_reset_handler_failure(fake_user: User, fake_chat: Chat) -> None:
    message = Message(
        message_id=11,
        date=1234567890,
        chat=fake_chat,
        from_user=fake_user,
        content_type="text",
        options={},
        text="/reset",
    )
    with patch("ragbot.app.routes.get_rag_service") as mock_get_service:
        svc = MagicMock()
        svc.reset_vector_store = AsyncMock(return_value=False)
        mock_get_service.return_value = svc
        with patch("aiogram.types.Message.reply") as mock_reply:
            mock_reply.return_value = AsyncMock()
            await reset_handler(message)
            assert mock_reply.called
