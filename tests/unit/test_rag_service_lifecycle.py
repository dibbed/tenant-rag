"""Lifecycle tests for RAGService-owned resources."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ragbot.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_shutdown_disposes_tenant_database_runtime() -> None:
    service = object.__new__(RAGService)
    manager = MagicMock()
    manager.aclose = AsyncMock()
    service.tenant_manager = manager

    await service.shutdown()

    manager.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_shutdown_is_safe_without_multi_tenant_manager() -> None:
    service = object.__new__(RAGService)
    service.tenant_manager = None

    await service.shutdown()
