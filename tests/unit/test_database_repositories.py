"""Repository contract tests for PostgreSQL tenant persistence."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.database.models import TenantAuditLogRecord
from ragbot.database.repositories import (
    ApiKeyRepository,
    AuditRepository,
    SessionRepository,
    UsageRepository,
)


@pytest.mark.asyncio
async def test_api_key_bootstrap_uses_narrow_security_definer_function() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.mappings.return_value.first.return_value = {
        "key_id": "key_1",
        "tenant_id": "tenant_a",
        "user_id": "user_1",
        "name": "cli",
        "key_hash": "scrypt$...",
        "key_prefix": "rgb_key_1",
        "permissions": ["api_access"],
        "created_at": None,
        "expires_at": None,
        "last_used_at": None,
        "is_active": True,
    }
    session.execute.return_value = result

    record = await ApiKeyRepository(session).lookup_auth("key_1")

    statement, params = session.execute.await_args.args
    assert "public.lookup_api_key_auth(:key_id)" in str(statement)
    assert params == {"key_id": "key_1"}
    assert record is not None
    assert record["tenant_id"] == "tenant_a"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_bootstrap_uses_hashed_token_lookup() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.mappings.return_value.first.return_value = {
        "session_id": "sess_1",
        "tenant_id": "tenant_a",
        "user_id": "user_1",
        "created_at": None,
        "expires_at": None,
        "last_used_at": None,
        "revoked_at": None,
        "ip_address": None,
        "user_agent": None,
    }
    session.execute.return_value = result

    record = await SessionRepository(session).lookup_auth("deadbeef")

    statement, params = session.execute.await_args.args
    assert "public.lookup_session_auth(:token_hash)" in str(statement)
    assert params == {"token_hash": "deadbeef"}
    assert record is not None
    assert record["user_id"] == "user_1"
    session.commit.assert_not_awaited()


def test_usage_increment_statement_is_atomic_postgres_upsert() -> None:
    statement = UsageRepository.increment_statement(
        tenant_id="tenant_a",
        usage_date=date(2026, 9, 29),
        operation="query",
        metadata={"response_time": 1.2},
    )
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert "ON CONFLICT" in compiled
    assert "queries_count = (tenant_usage.queries_count + " in compiled
    assert "tenant_id" in compiled
    assert "usage_date" in compiled


@pytest.mark.asyncio
async def test_audit_repository_adds_without_committing() -> None:
    session = AsyncMock(spec=AsyncSession)
    record = TenantAuditLogRecord(
        tenant_id="tenant_a",
        action="tenant_updated",
        resource="tenant",
        details={"field": "name"},
        success=True,
    )

    await AuditRepository(session).add(record)

    session.add.assert_called_once_with(record)
    session.commit.assert_not_awaited()



def test_quota_for_update_uses_row_lock() -> None:
    from ragbot.database.repositories import QuotaRepository

    statement = QuotaRepository.for_update_statement("tenant_a")
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert "tenant_quotas" in compiled
    assert "FOR UPDATE" in compiled


def test_user_count_is_scoped_to_tenant() -> None:
    from ragbot.database.repositories import UserRepository

    statement = UserRepository.count_statement("tenant_a")
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert "count(" in compiled.lower()
    assert "tenant_users.tenant_id = 'tenant_a'" in compiled


def test_expired_api_key_cleanup_is_update_not_delete() -> None:
    from datetime import datetime, timezone

    from ragbot.database.repositories import ApiKeyRepository

    statement = ApiKeyRepository.deactivate_expired_statement(
        datetime(2026, 9, 29, tzinfo=timezone.utc)
    )
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))

    assert compiled.startswith("UPDATE tenant_api_keys")
    assert "is_active=" in compiled.replace(" ", "")
    assert "expires_at" in compiled
