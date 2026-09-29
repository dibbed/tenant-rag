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

    assert session.execute.await_count == 2
    first_statement, first_params = session.execute.await_args_list[0].args
    second_statement, second_params = session.execute.await_args_list[1].args
    assert "set_config('app.is_system_admin', :is_system_admin, true)" in str(
        first_statement
    )
    assert first_params == {"is_system_admin": "false"}
    assert "set_config('app.tenant_id', :tenant_id, true)" in str(second_statement)
    assert second_params == {"tenant_id": "tenant_alpha"}


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant_id", ["", "   "])
async def test_set_tenant_context_rejects_blank_tenant(tenant_id: str) -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="tenant"):
        await set_tenant_context(session, tenant_id)

    session.execute.assert_not_awaited()
