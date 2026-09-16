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
    import sys
    routes_mod = sys.modules.get("ragbot.app.routes")
    if routes_mod is not None:
        patched = getattr(routes_mod, "get_integration_service", None)
        if patched is not None and patched is not get_integration_service:
            res = patched()
            return await res if hasattr(res, "__await__") else res
    global _integration_service
    if _integration_service is None:
        _integration_service = IntegrationService()
        await _integration_service.initialize()
    return _integration_service


async def get_rag_service() -> RAGService:
    import sys
    routes_mod = sys.modules.get("ragbot.app.routes")
    if routes_mod is not None:
        patched = getattr(routes_mod, "get_rag_service", None)
        if patched is not None and patched is not get_rag_service:
            res = patched()
            return await res if hasattr(res, "__await__") else res
    global _rag_service
    if _rag_service is None:
        integration_service = await get_integration_service()
        _rag_service = integration_service.components["rag_service"]
    return _rag_service


async def get_document_service() -> DocumentService:
    global _document_service
    import sys
    routes_mod = sys.modules.get("ragbot.app.routes")
    if routes_mod is not None:
        patched = getattr(routes_mod, "get_document_service", None)
        if patched is not None and patched is not get_document_service:
            res = patched()
            return await res if hasattr(res, "__await__") else res
    if _document_service is None:
        DocServiceClass = getattr(routes_mod, "DocumentService", DocumentService) if routes_mod else DocumentService
        integration_service = await get_integration_service()
        _document_service = DocServiceClass(
            loaders=integration_service.components["loaders"],
            chunker=integration_service.components["chunker"],
            embedder=integration_service.components["embedder"],
            vector_store=integration_service.components["vector_store"],
            cache=integration_service.components.get("cache"),
        )
    return _document_service


async def get_bot():
    import sys
    routes_mod = sys.modules.get("ragbot.app.routes")
    if routes_mod is not None:
        patched = getattr(routes_mod, "get_bot", None)
        if patched is not None and patched is not get_bot:
            res = patched()
            return await res if hasattr(res, "__await__") else res
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
    import sys
    routes_mod = sys.modules.get("ragbot.app.routes")
    if routes_mod is not None:
        patched = getattr(routes_mod, "is_user_authorized", None)
        if patched is not None and patched is not is_user_authorized:
            return patched(user_id)
    try:
        current_settings = getattr(routes_mod, "settings", settings) if routes_mod else settings
        allowed = current_settings.allow_users_list
        return not allowed or user_id in allowed
    except Exception:
        return True


def check_rate_limit(user_id: int) -> bool:
    return True


_safe_reply = safe_reply
_maybe_await = maybe_await

__all__ = [
    "settings",
    "logger",
    "maybe_await",
    "_maybe_await",
    "get_integration_service",
    "get_rag_service",
    "get_document_service",
    "get_bot",
    "safe_reply",
    "_safe_reply",
    "safe_log_error",
    "build_performance_keyboard",
    "safe_reply_with_kb",
    "is_user_authorized",
    "check_rate_limit",
    "DocumentService",
    "IntegrationService",
    "RAGService",
]
