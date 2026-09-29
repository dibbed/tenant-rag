"""PostgreSQL-backed TenantManager behavior and transaction-boundary tests."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.database.mappers import tenant_to_record
from ragbot.database.models import (
    TenantAuditLogRecord,
    TenantQuotaRecord,
    TenantRecord,
)
from ragbot.multi_tenant.models import TenantPlan, TenantTier
from ragbot.multi_tenant.tenant_manager import TenantManager


class _BeginContext(AbstractAsyncContextManager[AsyncSession]):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.exited = False

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.exited = True


class _SessionFactory:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.contexts: list[_BeginContext] = []

    def begin(self) -> _BeginContext:
        context = _BeginContext(self.session)
        self.contexts.append(context)
        return context


def _session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


def test_postgres_manager_constructor_does_not_initialize_sqlite_or_authority_dicts() -> None:
    session = _session()
    factory = _SessionFactory(session)

    manager = TenantManager(session_factory=factory)

    assert manager.uses_postgres is True
    assert not hasattr(manager, "_conn")
    assert not hasattr(manager, "tenants")
    assert not hasattr(manager, "tenant_users")
    assert not hasattr(manager, "tenant_usage")
    assert not hasattr(manager, "tenant_audit_logs")


@pytest.mark.asyncio
async def test_create_tenant_stages_tenant_quota_and_audit_in_one_transaction() -> None:
    session = _session()
    factory = _SessionFactory(session)
    manager = TenantManager(session_factory=factory)

    tenant = await manager.create_tenant(
        name="Postgres Corp",
        tier=TenantTier.PREMIUM,
        plan=TenantPlan.MONTHLY,
        tenant_id="tenant_pg",
    )

    assert tenant.tenant_id == "tenant_pg"
    assert tenant.created_at.tzinfo is not None
    assert tenant.created_at.utcoffset() == timezone.utc.utcoffset(tenant.created_at)
    assert len(factory.contexts) == 1
    assert factory.contexts[0].exited is True
    added = [call.args[0] for call in session.add.call_args_list]
    assert sum(isinstance(record, TenantRecord) for record in added) == 1
    assert sum(isinstance(record, TenantQuotaRecord) for record in added) == 1
    assert sum(isinstance(record, TenantAuditLogRecord) for record in added) == 1
    assert session.execute.await_count == 2
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_tenant_reads_postgres_records_under_tenant_context() -> None:
    seed_manager = TenantManager(session_factory=_SessionFactory(_session()))
    domain = await seed_manager.create_tenant(
        name="Read Corp",
        tier=TenantTier.BASIC,
        plan=TenantPlan.YEARLY,
        tenant_id="tenant_read",
    )
    tenant_record, quota_record = tenant_to_record(domain)

    session = _session()
    session.get.side_effect = [tenant_record, quota_record]
    manager = TenantManager(session_factory=_SessionFactory(session))

    loaded = await manager.get_tenant("tenant_read")

    assert loaded is not None
    assert loaded.tenant_id == "tenant_read"
    assert loaded.name == "Read Corp"
    assert session.get.await_count == 2
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_track_usage_uses_postgres_upsert_not_process_memory() -> None:
    session = _session()
    factory = _SessionFactory(session)
    manager = TenantManager(session_factory=factory)

    await manager.track_tenant_usage(
        "tenant_usage",
        "query",
        metadata={"response_time": 1.25},
    )

    assert len(factory.contexts) == 1
    assert session.execute.await_count == 3
    statement = session.execute.await_args_list[-1].args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "ON CONFLICT" in compiled
    assert "queries_count" in compiled
    assert not hasattr(manager, "tenant_usage")



@pytest.mark.asyncio
async def test_postgres_manager_aclose_disposes_owned_runtime() -> None:
    manager = TenantManager(session_factory=_SessionFactory(_session()))
    runtime = MagicMock()
    runtime.dispose = AsyncMock()
    manager._database_runtime = runtime

    await manager.aclose()

    runtime.dispose.assert_awaited_once_with()
