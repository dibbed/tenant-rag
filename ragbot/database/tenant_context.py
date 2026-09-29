"""Transaction-local PostgreSQL tenant context helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Scope the current transaction to exactly one tenant for PostgreSQL RLS."""
    normalized = tenant_id.strip()
    if not normalized:
        raise ValueError("tenant_id must not be blank")

    await session.execute(
        text("SELECT pg_catalog.set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": normalized},
    )
