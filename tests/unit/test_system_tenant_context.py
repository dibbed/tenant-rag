"""System and tenant RLS context regression tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.database.tenant_context import set_system_context, set_tenant_context


@pytest.mark.asyncio
async def test_tenant_context_explicitly_disables_system_admin() -> None:
    session = AsyncMock(spec=AsyncSession)

    await set_tenant_context(session, "tenant_a")

    assert session.execute.await_count == 2
    first_statement, first_params = session.execute.await_args_list[0].args
    second_statement, second_params = session.execute.await_args_list[1].args
    assert "app.is_system_admin" in str(first_statement)
    assert first_params == {"is_system_admin": "false"}
    assert "app.tenant_id" in str(second_statement)
    assert second_params == {"tenant_id": "tenant_a"}


@pytest.mark.asyncio
async def test_system_context_sets_admin_and_clears_tenant() -> None:
    session = AsyncMock(spec=AsyncSession)

    await set_system_context(session)

    assert session.execute.await_count == 2
    first_statement, first_params = session.execute.await_args_list[0].args
    second_statement, second_params = session.execute.await_args_list[1].args
    assert "app.tenant_id" in str(first_statement)
    assert first_params == {"tenant_id": ""}
    assert "app.is_system_admin" in str(second_statement)
    assert second_params == {"is_system_admin": "true"}
