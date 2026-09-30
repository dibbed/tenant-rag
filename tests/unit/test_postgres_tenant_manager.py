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
    assert session.flush.await_count == 1
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_tenant_flushes_parent_before_quota() -> None:
    session = _session()
    events: list[tuple[str, type[Any] | None]] = []
    session.add.side_effect = lambda record: events.append(("add", type(record)))

    async def record_flush() -> None:
        events.append(("flush", None))

    session.flush.side_effect = record_flush
    manager = TenantManager(session_factory=_SessionFactory(session))

    await manager.create_tenant(
        name="Ordered Corp",
        tier=TenantTier.FREE,
        plan=TenantPlan.MONTHLY,
        tenant_id="tenant_ordered",
    )

    assert events[:3] == [
        ("add", TenantRecord),
        ("flush", None),
        ("add", TenantQuotaRecord),
    ]


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



@pytest.mark.asyncio
async def test_postgres_query_quota_reservation_is_atomic_and_short_lived() -> None:


    seed_manager = TenantManager(session_factory=_SessionFactory(_session()))
    tenant = await seed_manager.create_tenant(
        name="Quota Corp",
        tier=TenantTier.FREE,
        plan=TenantPlan.MONTHLY,
        tenant_id="tenant_quota",
    )
    tenant_record, quota_record = tenant_to_record(tenant)

    session = _session()
    session.get.side_effect = [tenant_record, None]
    quota_result = MagicMock()
    quota_result.first.return_value = quota_record
    session.scalars.return_value = quota_result
    manager = TenantManager(session_factory=_SessionFactory(session))

    allowed = await manager.reserve_tenant_usage("tenant_quota", "query")

    assert allowed is True
    statement = session.execute.await_args_list[-1].args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "ON CONFLICT" in compiled
    assert "queries_count" in compiled
    assert session.commit.await_count == 0


@pytest.mark.asyncio
async def test_postgres_query_quota_reservation_rejects_at_limit_with_audit() -> None:
    from datetime import date

    from ragbot.database.models import TenantUsageRecord

    seed_manager = TenantManager(session_factory=_SessionFactory(_session()))
    tenant = await seed_manager.create_tenant(
        name="Quota Corp",
        tier=TenantTier.FREE,
        plan=TenantPlan.MONTHLY,
        tenant_id="tenant_limit",
    )
    tenant_record, quota_record = tenant_to_record(tenant)
    usage = TenantUsageRecord(
        tenant_id="tenant_limit",
        usage_date=date.today(),
        queries_count=quota_record.max_queries_per_day,
    )

    session = _session()
    session.get.side_effect = [tenant_record, usage]
    quota_result = MagicMock()
    quota_result.first.return_value = quota_record
    session.scalars.return_value = quota_result
    manager = TenantManager(session_factory=_SessionFactory(session))

    allowed = await manager.reserve_tenant_usage("tenant_limit", "query")

    assert allowed is False
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(record, TenantAuditLogRecord) for record in added)


@pytest.mark.asyncio
async def test_postgres_release_usage_compensates_failed_query() -> None:
    session = _session()
    result = MagicMock()
    result.rowcount = 1
    session.execute.side_effect = [MagicMock(), MagicMock(), result]
    manager = TenantManager(session_factory=_SessionFactory(session))

    await manager.release_tenant_usage("tenant_a", "query")

    statement = session.execute.await_args_list[-1].args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "UPDATE tenant_usage" in compiled
    assert "queries_count" in compiled



@pytest.mark.asyncio
async def test_postgres_manager_lists_users_without_process_local_dicts() -> None:
    from datetime import datetime, timezone

    from ragbot.database.models import TenantUserRecord

    session = _session()
    result = MagicMock()
    result.all.return_value = [
        TenantUserRecord(
            user_id="user_1",
            tenant_id="tenant_a",
            username="alice",
            email="alice@example.com",
            role="user",
            permissions=[],
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
    ]
    session.scalars.return_value = result
    manager = TenantManager(session_factory=_SessionFactory(session))

    users = await manager.list_tenant_users("tenant_a")

    assert [user.user_id for user in users] == ["user_1"]
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_postgres_manager_lists_usage_for_date_range() -> None:
    from datetime import date, datetime

    from ragbot.database.models import TenantUsageRecord

    session = _session()
    result = MagicMock()
    result.all.return_value = [
        TenantUsageRecord(
            tenant_id="tenant_a",
            usage_date=date(2026, 9, 29),
            documents_count=0,
            queries_count=3,
            storage_used_gb=0.0,
            api_calls=0,
            avg_response_time=0.0,
            error_rate=0.0,
            satisfaction_score=0.0,
            cost_usd=0.0,
        )
    ]
    session.scalars.return_value = result
    manager = TenantManager(session_factory=_SessionFactory(session))

    usage = await manager.list_tenant_usage(
        "tenant_a",
        start_date=datetime(2026, 9, 29, tzinfo=timezone.utc),
        end_date=datetime(2026, 9, 29, 23, 59, tzinfo=timezone.utc),
    )

    assert len(usage) == 1
    assert usage[0].queries_count == 3



def test_postgres_manager_rejects_sqlite_database_url() -> None:
    settings = MagicMock()
    settings.database.url = "sqlite:///./data/ragbot.db"
    settings.database.echo = False
    settings.database.pool_size = 5
    settings.database.max_overflow = 10

    with pytest.raises(ValueError, match="PostgreSQL"):
        TenantManager(settings)
