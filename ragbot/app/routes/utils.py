"""Shared utilities and lazy service initializers for route modules.

This file extracts common helpers from the former monolithic routes.py to avoid
duplication while preserving original behavior.
"""

from typing import Any, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.services.document_service import DocumentService
from ragbot.services.integration_service import IntegrationService
from ragbot.services.rag_service import RAGService
from ragbot.app.ui.manager import ui_manager

_integration_service: Optional[IntegrationService] = None
_rag_service: Optional[RAGService] = None
_document_service: Optional[DocumentService] = None


async def maybe_await(value: Any) -> Any:
    """Await value if awaitable, else return as-is (test-friendly)."""
    try:
        if hasattr(value, "__await__"):
            return await value
    except Exception:
        pass
    return value


async def get_integration_service() -> IntegrationService:
    global _integration_service
    if _integration_service is None:
        _integration_service = IntegrationService()
        await _integration_service.initialize()
    return _integration_service


async def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        integration_service = await get_integration_service()
        _rag_service = integration_service.components["rag_service"]
    return _rag_service


async def get_document_service() -> DocumentService:
    global _document_service
    if _document_service is None:
        integration_service = await get_integration_service()
        _document_service = DocumentService(
            loaders=integration_service.components["loaders"],
            chunker=integration_service.components["chunker"],
            embedder=integration_service.components["embedder"],
            vector_store=integration_service.components["vector_store"],
            cache=integration_service.components.get("cache"),
        )
    return _document_service


async def get_bot():
    try:
        from aiogram import Bot

        return Bot.get_current()
    except Exception:
        return None


async def safe_reply(message: Message, text: str) -> None:
    try:
        res = message.reply(text)
        if hasattr(res, "__await__"):
            await res
    except Exception:
        pass


async def safe_log_error(*, error: Exception, context: str, **fields) -> None:
    try:
        fn = getattr(logger, "log_error_event", None)
        if fn is None:
            return
        res = fn(error=error, context=context, **fields)
        if hasattr(res, "__await__"):
            await res
    except Exception:
        pass


def build_performance_keyboard() -> InlineKeyboardMarkup:
    """Build performance monitoring keyboard using UI manager"""
    return ui_manager.performance_keyboard


async def safe_reply_with_kb(
    message: Message, text: str, keyboard: InlineKeyboardMarkup
) -> None:
    try:
        res = message.reply(text, reply_markup=keyboard)
        if hasattr(res, "__await__"):
            await res
    except Exception:
        pass


def is_user_authorized(user_id: int) -> bool:
    try:
        allowed = settings.allow_users_list
        return not allowed or user_id in allowed
    except Exception:
        return True


def check_rate_limit(user_id: int) -> bool:
    return True


__all__ = [
    "settings",
    "logger",
    "maybe_await",
    "get_integration_service",
    "get_rag_service",
    "get_document_service",
    "get_bot",
    "safe_reply",
    "safe_log_error",
    "build_performance_keyboard",
    "safe_reply_with_kb",
    "is_user_authorized",
    "check_rate_limit",
]
