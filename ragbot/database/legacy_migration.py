"""Offline migration from the legacy tenant SQLite store to PostgreSQL."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select

from ragbot.multi_tenant.models import TenantConfig, TenantUsage, TenantUser

from .engine import DatabaseRuntime
from .mappers import (
    api_key_to_record,
    tenant_to_record,
    user_to_record,
)
from .models import (
    TenantApiKeyRecord,
    TenantAuditLogRecord,
    TenantQuotaRecord,
    TenantRecord,
    TenantSessionRecord,
    TenantUsageRecord,
    TenantUserRecord,
)
from .tenant_context import set_system_context, set_tenant_context

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.multi_tenant.models import TenantApiKey


class LegacyMigrationError(RuntimeError):
    """Raised when the legacy source cannot be migrated safely."""


@dataclass
class LegacySnapshot:
    tenants: list[TenantConfig] = field(default_factory=list)
    users: list[TenantUser] = field(default_factory=list)
    api_keys: list[TenantApiKey] = field(default_factory=list)
    usage: list[TenantUsage] = field(default_factory=list)
    audit_logs: list[TenantAuditLogRecord] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "tenants": len(self.tenants),
            "tenant_quotas": len(self.tenants),
            "tenant_users": len(self.users),
            "tenant_api_keys": len(self.api_keys),
            "tenant_usage": len(self.usage),
            "tenant_audit_logs": len(self.audit_logs),
            "tenant_sessions": 0,
        }


@dataclass
class MigrationReport:
    counts: dict[str, int]
    warnings: list[str]
    dry_run: bool


def _source_timezone(name: str | None) -> ZoneInfo | None:
    if name is None:
        return None
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise LegacyMigrationError(f"Unknown source timezone: {name}") from exc


def normalize_legacy_datetime(
    value: str | datetime | None,
    *,
    source_timezone: str | None,
    field_name: str,
) -> datetime | None:
    """Normalize legacy timestamps to aware UTC without guessing naive timezone."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        zone = _source_timezone(source_timezone)
        if zone is None:
            raise LegacyMigrationError(
                f"{field_name} contains a naive timestamp; provide --source-timezone"
            )
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def _readonly_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise LegacyMigrationError(f"SQLite source does not exist: {path}")
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _normalize_tenant(
    tenant: TenantConfig,
    *,
    source_timezone: str | None,
) -> TenantConfig:
    payload = tenant.model_dump()
    for field_name in ("created_at", "updated_at", "expires_at"):
        payload[field_name] = normalize_legacy_datetime(
            payload.get(field_name),
            source_timezone=source_timezone,
            field_name=f"tenants.{field_name}",
        )
    return TenantConfig.model_validate(payload)


def _normalize_user(
    user: TenantUser,
    *,
    source_timezone: str | None,
) -> TenantUser:
    payload = user.model_dump()
    for field_name in ("created_at", "last_login"):
        payload[field_name] = normalize_legacy_datetime(
            payload.get(field_name),
            source_timezone=source_timezone,
            field_name=f"tenant_users.{field_name}",
        )
    return TenantUser.model_validate(payload)


def _normalize_usage(
    usage: TenantUsage,
    *,
    source_timezone: str | None,
) -> TenantUsage:
    payload = usage.model_dump()
    value = payload.get("date")
    if value is None:
        raise LegacyMigrationError("tenant_usage.date must not be NULL")

    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        zone = _source_timezone(source_timezone)
        if zone is None:
            raise LegacyMigrationError(
                "tenant_usage.date contains a naive timestamp; provide --source-timezone"
            )
        parsed = parsed.replace(tzinfo=zone)

    # tenant_usage.date is a legacy daily bucket key, not an event timestamp.
    # Preserve the source-local calendar date while storing an aware UTC marker
    # so conversion to PostgreSQL DATE cannot shift the bucket by one day.
    payload["date"] = datetime.combine(
        parsed.date(),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    return TenantUsage.model_validate(payload)


def read_legacy_snapshot(
    source_path: Path,
    *,
    source_timezone: str | None,
) -> LegacySnapshot:
    """Read and validate the legacy SQLite store without mutating it."""
    snapshot = LegacySnapshot()
    with _readonly_connection(source_path) as connection:
        required = {
            "tenants",
            "tenant_users",
            "tenant_usage",
            "tenant_audit_logs",
            "tenant_api_keys",
        }
        missing = sorted(table for table in required if not _table_exists(connection, table))
        if missing:
            raise LegacyMigrationError(
                f"Legacy SQLite source is missing tables: {', '.join(missing)}"
            )

        for row in connection.execute("SELECT config_json FROM tenants"):
            tenant = TenantConfig.model_validate_json(row["config_json"])
            snapshot.tenants.append(
                _normalize_tenant(tenant, source_timezone=source_timezone)
            )

        for row in connection.execute("SELECT user_json FROM tenant_users"):
            user = TenantUser.model_validate_json(row["user_json"])
            snapshot.users.append(
                _normalize_user(user, source_timezone=source_timezone)
            )

        for row in connection.execute("SELECT usage_json FROM tenant_usage"):
            usage = TenantUsage.model_validate_json(row["usage_json"])
            snapshot.usage.append(
                _normalize_usage(usage, source_timezone=source_timezone)
            )

        for row in connection.execute(
            """
            SELECT tenant_id, action, resource, details_json, created_at
            FROM tenant_audit_logs
            ORDER BY id
            """
        ):
            snapshot.audit_logs.append(
                TenantAuditLogRecord(
                    tenant_id=row["tenant_id"],
                    user_id=None,
                    action=row["action"],
                    resource=row["resource"],
                    details=json.loads(row["details_json"] or "{}"),
                    ip_address=None,
                    user_agent=None,
                    success=None,
                    error_message=None,
                    created_at=normalize_legacy_datetime(
                        row["created_at"],
                        source_timezone=source_timezone,
                        field_name="tenant_audit_logs.created_at",
                    ),
                )
            )

        for row in connection.execute(
            """
            SELECT key_id, tenant_id, user_id, name, key_hash, key_prefix,
                   permissions_json, created_at, expires_at, last_used_at, is_active
            FROM tenant_api_keys
            ORDER BY created_at
            """
        ):
            created_at = normalize_legacy_datetime(
                row["created_at"],
                source_timezone=source_timezone,
                field_name="tenant_api_keys.created_at",
            )
            if created_at is None:
                raise LegacyMigrationError("tenant_api_keys.created_at must not be NULL")
            snapshot.api_keys.append(
                TenantApiKey(
                    key_id=row["key_id"],
                    tenant_id=row["tenant_id"],
                    user_id=row["user_id"],
                    name=row["name"],
                    key_hash=row["key_hash"],
                    key_prefix=row["key_prefix"],
                    permissions=json.loads(row["permissions_json"] or "[]"),
                    created_at=created_at,
                    expires_at=normalize_legacy_datetime(
                        row["expires_at"],
                        source_timezone=source_timezone,
                        field_name="tenant_api_keys.expires_at",
                    ),
                    last_used_at=normalize_legacy_datetime(
                        row["last_used_at"],
                        source_timezone=source_timezone,
                        field_name="tenant_api_keys.last_used_at",
                    ),
                    is_active=bool(row["is_active"]),
                )
            )

    _validate_snapshot_relationships(snapshot)
    return snapshot


def _validate_snapshot_relationships(snapshot: LegacySnapshot) -> None:
    tenant_ids = {tenant.tenant_id for tenant in snapshot.tenants}
    if len(tenant_ids) != len(snapshot.tenants):
        raise LegacyMigrationError("Duplicate tenant_id values found in legacy source")

    user_ids = {user.user_id for user in snapshot.users}
    if len(user_ids) != len(snapshot.users):
        raise LegacyMigrationError("Duplicate user_id values found in legacy source")

    for user in snapshot.users:
        if user.tenant_id not in tenant_ids:
            raise LegacyMigrationError(
                f"User {user.user_id} references missing tenant {user.tenant_id}"
            )

    for key in snapshot.api_keys:
        if key.tenant_id not in tenant_ids:
            raise LegacyMigrationError(
                f"API key {key.key_id} references missing tenant {key.tenant_id}"
            )
        if key.user_id not in user_ids:
            raise LegacyMigrationError(
                f"API key {key.key_id} references missing user {key.user_id}"
            )

    for usage in snapshot.usage:
        if usage.tenant_id not in tenant_ids:
            raise LegacyMigrationError(
                f"Usage row references missing tenant {usage.tenant_id}"
            )

    for audit in snapshot.audit_logs:
        if audit.tenant_id not in tenant_ids:
            raise LegacyMigrationError(
                f"Audit row references missing tenant {audit.tenant_id}"
            )


_TARGET_TABLES: tuple[tuple[str, type[Any]], ...] = (
    ("tenants", TenantRecord),
    ("tenant_quotas", TenantQuotaRecord),
    ("tenant_users", TenantUserRecord),
    ("tenant_api_keys", TenantApiKeyRecord),
    ("tenant_usage", TenantUsageRecord),
    ("tenant_audit_logs", TenantAuditLogRecord),
    ("tenant_sessions", TenantSessionRecord),
)


async def _target_counts(session: AsyncSession) -> dict[str, int]:
    await set_system_context(session)
    counts: dict[str, int] = {}
    for table_name, model in _TARGET_TABLES:
        value = await session.scalar(select(func.count()).select_from(model))
        counts[table_name] = int(value or 0)
    return counts


async def _ensure_empty_target(session: AsyncSession) -> None:
    counts = await _target_counts(session)
    nonempty = {name: count for name, count in counts.items() if count}
    if nonempty:
        formatted = ", ".join(f"{name}={count}" for name, count in nonempty.items())
        raise LegacyMigrationError(
            f"PostgreSQL target tenant tables must be empty; found {formatted}"
        )


async def _insert_snapshot(session: AsyncSession, snapshot: LegacySnapshot) -> None:
    users_by_tenant: dict[str, list[TenantUser]] = {}
    keys_by_tenant: dict[str, list[TenantApiKey]] = {}
    usage_by_tenant: dict[str, list[TenantUsage]] = {}
    audits_by_tenant: dict[str, list[TenantAuditLogRecord]] = {}

    for user in snapshot.users:
        users_by_tenant.setdefault(user.tenant_id, []).append(user)
    for key in snapshot.api_keys:
        keys_by_tenant.setdefault(key.tenant_id, []).append(key)
    for usage in snapshot.usage:
        usage_by_tenant.setdefault(usage.tenant_id, []).append(usage)
    for audit in snapshot.audit_logs:
        audits_by_tenant.setdefault(audit.tenant_id, []).append(audit)

    for tenant in snapshot.tenants:
        await set_tenant_context(session, tenant.tenant_id)
        tenant_record, quota_record = tenant_to_record(tenant)
        session.add(tenant_record)
        await session.flush()
        session.add(quota_record)
        await session.flush()

        for user in users_by_tenant.get(tenant.tenant_id, []):
            session.add(user_to_record(user))
        await session.flush()

        for key in keys_by_tenant.get(tenant.tenant_id, []):
            session.add(api_key_to_record(key))
        for usage in usage_by_tenant.get(tenant.tenant_id, []):
            usage_date = usage.date.date()
            session.add(
                TenantUsageRecord(
                    tenant_id=usage.tenant_id,
                    usage_date=usage_date,
                    documents_count=usage.documents_count,
                    queries_count=usage.queries_count,
                    storage_used_gb=usage.storage_used_gb,
                    api_calls=usage.api_calls,
                    avg_response_time=usage.avg_response_time,
                    error_rate=usage.error_rate,
                    satisfaction_score=usage.satisfaction_score,
                    cost_usd=usage.cost_usd,
                )
            )
        for audit in audits_by_tenant.get(tenant.tenant_id, []):
            session.add(audit)
        await session.flush()


async def migrate_snapshot(
    snapshot: LegacySnapshot,
    *,
    target_url: str,
    echo: bool = False,
) -> MigrationReport:
    """Atomically migrate a validated snapshot into an empty PostgreSQL target."""
    runtime = DatabaseRuntime(target_url, echo=echo)
    try:
        async with runtime.session_factory.begin() as session:
            await _ensure_empty_target(session)
            await _insert_snapshot(session, snapshot)
            actual = await _target_counts(session)
            expected = snapshot.counts
            if actual != expected:
                raise LegacyMigrationError(
                    f"PostgreSQL verification count mismatch: expected={expected}, actual={actual}"
                )
    finally:
        await runtime.dispose()

    return MigrationReport(
        counts=snapshot.counts,
        warnings=_migration_warnings(),
        dry_run=False,
    )


def _migration_warnings() -> list[str]:
    return [
        (
            "Legacy tenant_usage may be incomplete because the old runtime kept "
            "usage updates in process memory instead of persisting every update."
        ),
        (
            "Legacy in-memory user sessions cannot be migrated; all users must "
            "authenticate again after cutover."
        ),
        (
            "Legacy audit rows did not persist user_id, success, error_message, "
            "ip_address, or user_agent; those fields remain NULL."
        ),
    ]


def dry_run_report(snapshot: LegacySnapshot) -> MigrationReport:
    return MigrationReport(
        counts=snapshot.counts,
        warnings=_migration_warnings(),
        dry_run=True,
    )
