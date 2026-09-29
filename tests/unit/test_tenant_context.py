"""Tests for transaction-local PostgreSQL tenant context."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.database.tenant_context import set_tenant_context


@pytest.mark.asyncio
async def test_set_tenant_context_is_transaction_local() -> None:
    session = AsyncMock(spec=AsyncSession)

    await set_tenant_context(session, "tenant_alpha")

    session.execute.assert_awaited_once()
    statement, params = session.execute.await_args.args
    assert "set_config('app.tenant_id', :tenant_id, true)" in str(statement)
    assert params == {"tenant_id": "tenant_alpha"}


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant_id", ["", "   "])
async def test_set_tenant_context_rejects_blank_tenant(tenant_id: str) -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="tenant"):
        await set_tenant_context(session, tenant_id)

    session.execute.assert_not_awaited()
