"""Tests for the offline legacy SQLite to PostgreSQL migration."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import ragbot.database.legacy_migration as legacy_migration

if TYPE_CHECKING:
    from pathlib import Path

from ragbot.database.legacy_migration import (
    LegacyMigrationError,
    LegacySnapshot,
    dry_run_report,
    normalize_legacy_datetime,
    read_legacy_snapshot,
)
from ragbot.database.models import TenantQuotaRecord, TenantRecord
from ragbot.multi_tenant.models import TenantConfig, TenantUsage, TenantUser


def _legacy_db(path: Path, *, api_user_id: str = "user_1") -> None:
    tenant = TenantConfig(
        tenant_id="tenant_a",
        name="Legacy Corp",
        created_at=datetime(2026, 9, 1, 10, 0, 0),
        updated_at=datetime(2026, 9, 2, 10, 0, 0),
    )
    user = TenantUser(
        user_id="user_1",
        tenant_id="tenant_a",
        username="alice",
        email="alice@example.com",
        password_hash="salt:hash",
        created_at=datetime(2026, 9, 1, 11, 0, 0),
    )
    usage = TenantUsage(
        tenant_id="tenant_a",
        date=datetime(2026, 9, 3, 0, 0, 0),
        queries_count=7,
    )

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE tenants (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                tier TEXT NOT NULL,
                plan TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT
            );
            CREATE TABLE tenant_users (
                user_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                user_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE tenant_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                date TEXT NOT NULL,
                usage_json TEXT NOT NULL
            );
            CREATE TABLE tenant_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE tenant_api_keys (
                key_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                permissions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                last_used_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        connection.execute(
            """
            INSERT INTO tenants (
                tenant_id, name, status, tier, plan, config_json,
                created_at, updated_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant.tenant_id,
                tenant.name,
                str(tenant.status),
                str(tenant.tier),
                str(tenant.plan),
                tenant.model_dump_json(),
                tenant.created_at.isoformat(),
                tenant.updated_at.isoformat(),
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO tenant_users (
                user_id, tenant_id, username, email, user_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user.user_id,
                user.tenant_id,
                user.username,
                user.email,
                user.model_dump_json(),
                user.created_at.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO tenant_usage (tenant_id, date, usage_json) VALUES (?, ?, ?)",
            (usage.tenant_id, usage.date.isoformat(), usage.model_dump_json()),
        )
        connection.execute(
            """
            INSERT INTO tenant_audit_logs (
                tenant_id, action, resource, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "tenant_a",
                "tenant_created",
                "tenant",
                json.dumps({"source": "legacy"}),
                datetime(2026, 9, 1, 10, 0, 0).isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO tenant_api_keys (
                key_id, tenant_id, user_id, name, key_hash, key_prefix,
                permissions_json, created_at, expires_at, last_used_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "key_1",
                "tenant_a",
                api_user_id,
                "cli",
                "scrypt$hash-must-remain-verbatim",
                "rgb_key_1_ab",
                json.dumps(["api_access"]),
                datetime(2026, 9, 1, 12, 0, 0).isoformat(),
                None,
                None,
                1,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_naive_legacy_timestamp_requires_source_timezone() -> None:
    with pytest.raises(LegacyMigrationError, match="source-timezone"):
        normalize_legacy_datetime(
            datetime(2026, 9, 1, 10, 0, 0),
            source_timezone=None,
            field_name="test.created_at",
        )


def test_usage_daily_bucket_preserves_source_local_calendar_date() -> None:
    usage = TenantUsage(
        tenant_id="tenant_a",
        date=datetime(2026, 9, 3, 0, 0, 0),
        queries_count=1,
    )

    normalized = legacy_migration._normalize_usage(
        usage,
        source_timezone="Asia/Tehran",
    )

    assert normalized.date == datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)


def test_read_snapshot_preserves_hash_and_legacy_unknown_audit_fields(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tenants.db"
    _legacy_db(source)

    snapshot = read_legacy_snapshot(source, source_timezone="UTC")

    assert snapshot.counts == {
        "tenants": 1,
        "tenant_quotas": 1,
        "tenant_users": 1,
        "tenant_api_keys": 1,
        "tenant_usage": 1,
        "tenant_audit_logs": 1,
        "tenant_sessions": 0,
    }
    assert snapshot.api_keys[0].key_hash == "scrypt$hash-must-remain-verbatim"
    assert snapshot.tenants[0].created_at.tzinfo == timezone.utc
    assert snapshot.audit_logs[0].user_id is None
    assert snapshot.audit_logs[0].success is None
    assert snapshot.audit_logs[0].ip_address is None
    assert snapshot.audit_logs[0].user_agent is None


def test_snapshot_rejects_api_key_with_missing_user(tmp_path: Path) -> None:
    source = tmp_path / "tenants.db"
    _legacy_db(source, api_user_id="missing_user")

    with pytest.raises(LegacyMigrationError, match="missing user"):
        read_legacy_snapshot(source, source_timezone="UTC")


def test_dry_run_reports_known_legacy_limitations(tmp_path: Path) -> None:
    source = tmp_path / "tenants.db"
    _legacy_db(source)
    snapshot = read_legacy_snapshot(source, source_timezone="UTC")

    report = dry_run_report(snapshot)

    assert report.dry_run is True
    assert report.counts["tenant_sessions"] == 0
    assert any("process memory" in warning for warning in report.warnings)
    assert any("authenticate again" in warning for warning in report.warnings)



@pytest.mark.asyncio
async def test_insert_snapshot_flushes_parent_tenant_before_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    events: list[tuple[str, type[Any] | None]] = []
    session.add.side_effect = lambda record: events.append(("add", type(record)))

    async def record_flush() -> None:
        events.append(("flush", None))

    session.flush.side_effect = record_flush
    monkeypatch.setattr(legacy_migration, "set_tenant_context", AsyncMock())
    snapshot = LegacySnapshot(
        tenants=[TenantConfig(tenant_id="tenant_ordered", name="Ordered Legacy")]
    )

    await legacy_migration._insert_snapshot(session, snapshot)

    assert events[:3] == [
        ("add", TenantRecord),
        ("flush", None),
        ("add", TenantQuotaRecord),
    ]


@pytest.mark.asyncio
async def test_nonempty_postgres_target_is_refused() -> None:
    session = AsyncMock()
    session.scalar.side_effect = [1, 0, 0, 0, 0, 0, 0]

    with pytest.raises(LegacyMigrationError, match="must be empty"):
        await legacy_migration._ensure_empty_target(session)

    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_migration_exception_exits_transaction_with_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    class Transaction:
        exc_type: type[BaseException] | None = None

        async def __aenter__(self) -> Any:
            return session

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: Any,
        ) -> None:
            self.exc_type = exc_type

    transaction = Transaction()

    class Factory:
        def begin(self) -> Transaction:
            return transaction

    runtime = MagicMock()
    runtime.session_factory = Factory()
    runtime.dispose = AsyncMock()

    monkeypatch.setattr(
        legacy_migration,
        "DatabaseRuntime",
        lambda *args, **kwargs: runtime,
    )
    monkeypatch.setattr(
        legacy_migration,
        "_ensure_empty_target",
        AsyncMock(),
    )
    monkeypatch.setattr(
        legacy_migration,
        "_insert_snapshot",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        await legacy_migration.migrate_snapshot(
            LegacySnapshot(),
            target_url="postgresql://user:pass@localhost/tenantrag",
        )

    assert transaction.exc_type is RuntimeError
    runtime.dispose.assert_awaited_once_with()
