"""PostgreSQL TenantAuth behavior tests."""

from __future__ import annotations

import hashlib
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.database.models import (
    TenantApiKeyRecord,
    TenantAuditLogRecord,
    TenantQuotaRecord,
    TenantSessionRecord,
    TenantUserRecord,
)
from ragbot.multi_tenant.models import TenantConfig, TenantLimits, TenantStatus
from ragbot.multi_tenant.tenant_auth import Permission, TenantAuth, UserRole


class _BeginContext(AbstractAsyncContextManager[AsyncSession]):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _SessionFactory:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def begin(self) -> _BeginContext:
        return _BeginContext(self.session)


class _PgManager:
    uses_postgres = True

    def __init__(self, session: AsyncSession) -> None:
        self._session_factory = _SessionFactory(session)

    def _begin_postgres(self) -> _BeginContext:
        return self._session_factory.begin()

    async def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        return TenantConfig(
            tenant_id=tenant_id,
            name="Tenant",
            status=TenantStatus.ACTIVE,
            limits=TenantLimits(max_users=5),
        )


def _session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_postgres_create_user_locks_quota_and_stages_user_and_audit() -> None:
    session = _session()
    quota = TenantQuotaRecord(
        tenant_id="tenant_a",
        max_documents=100,
        max_queries_per_day=100,
        max_storage_gb=1.0,
        max_users=5,
        max_concurrent_queries=2,
        retention_days=7,
        api_rate_limit=10,
    )
    scalars = MagicMock()
    scalars.first.side_effect = [quota, None, None]
    session.scalars.return_value = scalars
    session.scalar.return_value = 0
    auth = TenantAuth(_PgManager(session))

    ok, user, error = await auth.create_user(
        tenant_id="tenant_a",
        username="alice",
        email="alice@example.com",
        password="StrongPassword123!",
        role=UserRole.ADMIN,
    )

    assert ok is True
    assert error is None
    assert user is not None
    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(record, TenantUserRecord) for record in added)
    assert any(isinstance(record, TenantAuditLogRecord) for record in added)
    assert session.commit.await_count == 0


@pytest.mark.asyncio
async def test_postgres_create_session_stores_hash_not_raw_token() -> None:
    session = _session()
    auth = TenantAuth(_PgManager(session))
    user = MagicMock()
    user.user_id = "user_1"
    user.tenant_id = "tenant_a"

    raw_token = await auth._create_user_session(user)

    records = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], TenantSessionRecord)
    ]
    assert len(records) == 1
    record = records[0]
    assert record.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert raw_token != record.token_hash
    assert raw_token not in repr(record)


@pytest.mark.asyncio
async def test_postgres_validate_session_uses_bootstrap_then_tenant_context() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    lookup = MagicMock()
    lookup.mappings.return_value.first.return_value = {
        "session_id": "sess_1",
        "tenant_id": "tenant_a",
        "user_id": "user_1",
        "created_at": now,
        "expires_at": now + timedelta(hours=1),
        "last_used_at": now,
        "revoked_at": None,
        "ip_address": None,
        "user_agent": None,
    }
    touch_result = MagicMock()
    session.execute.side_effect = [lookup, MagicMock(), MagicMock(), touch_result]
    session.get.return_value = TenantUserRecord(
        user_id="user_1",
        tenant_id="tenant_a",
        username="alice",
        email="alice@example.com",
        password_hash="salt:hash",
        role=UserRole.USER.value,
        permissions=[Permission.VIEW_DOCUMENTS.value],
        is_active=True,
        created_at=now,
    )
    auth = TenantAuth(_PgManager(session))

    ok, user = await auth.validate_session("raw-session-token")

    assert ok is True
    assert user is not None
    assert user.user_id == "user_1"
    first_statement = session.execute.await_args_list[0].args[0]
    assert "lookup_session_auth" in str(first_statement)


@pytest.mark.asyncio
async def test_postgres_logout_revokes_session_from_database() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    lookup = MagicMock()
    lookup.mappings.return_value.first.return_value = {
        "session_id": "sess_1",
        "tenant_id": "tenant_a",
        "user_id": "user_1",
        "created_at": now,
        "expires_at": now + timedelta(hours=1),
        "last_used_at": now,
        "revoked_at": None,
        "ip_address": None,
        "user_agent": None,
    }
    revoke_result = MagicMock()
    revoke_result.rowcount = 1
    session.execute.side_effect = [lookup, MagicMock(), MagicMock(), revoke_result]
    auth = TenantAuth(_PgManager(session))

    assert await auth.logout_user("raw-session-token") is True


@pytest.mark.asyncio
async def test_postgres_create_api_key_stages_key_and_audit_atomically() -> None:
    session = _session()
    user = TenantUserRecord(
        user_id="user_1",
        tenant_id="tenant_a",
        username="alice",
        email="alice@example.com",
        password_hash=None,
        role=UserRole.ADMIN.value,
        permissions=[Permission.API_ACCESS.value],
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.get.return_value = user
    auth = TenantAuth(_PgManager(session))

    ok, raw_key, error = await auth.create_api_key(
        tenant_id="tenant_a",
        user_id="user_1",
        name="cli",
    )

    assert ok is True
    assert error is None
    assert raw_key is not None
    added = [call.args[0] for call in session.add.call_args_list]
    key_records = [record for record in added if isinstance(record, TenantApiKeyRecord)]
    assert len(key_records) == 1
    assert raw_key not in key_records[0].key_hash
    assert any(isinstance(record, TenantAuditLogRecord) for record in added)


@pytest.mark.asyncio
async def test_postgres_cleanup_expired_sessions_uses_database() -> None:
    session = _session()
    session.scalar.return_value = 3
    auth = TenantAuth(_PgManager(session))

    assert await auth.cleanup_expired_sessions() == 3
    statement, _params = session.scalar.await_args.args
    assert "public.delete_expired_sessions_admin(:before)" in str(statement)


@pytest.mark.asyncio
async def test_postgres_cleanup_expired_api_keys_deactivates_in_database() -> None:
    session = _session()
    session.scalar.return_value = 2
    auth = TenantAuth(_PgManager(session))

    assert await auth.cleanup_expired_api_keys() == 2
    statement, _params = session.scalar.await_args.args
    assert "public.deactivate_expired_api_keys_admin(:before)" in str(statement)
