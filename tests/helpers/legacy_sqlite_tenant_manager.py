"""Test-only adapter for characterizing the removed legacy SQLite runtime.

Production TenantManager no longer accepts or selects SQLite. These tests keep
the old persistence/security behavior covered until the legacy compatibility
code can be deleted entirely in a later cleanup.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ragbot.multi_tenant.models import (
    DEFAULT_TIER_CONFIGS,
    TenantApiKey,
    TenantAuditLog,
    TenantConfig,
    TenantPlan,
    TenantPolicy,
    TenantStatus,
    TenantTier,
    TenantUsage,
    TenantUser,
)
from ragbot.multi_tenant.tenant_manager import TenantManager
from ragbot.outputs.logger import logger

if TYPE_CHECKING:
    from pathlib import Path


class LegacySQLiteTenantManager(TenantManager):
    """Explicit test-only entry point for the historical SQLite code path."""

    db_path: Path
    _conn: sqlite3.Connection

    def __init__(self, settings: Any | None, db_path: Path) -> None:
        self.settings = settings
        self.tenant_policies: dict[str, list[TenantPolicy]] = {}
        self._tenant_cache: dict[str, Any] = {}
        self._isolation_rules: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        self._database_runtime = None
        self._session_factory = None

        self.tenants: dict[str, TenantConfig] = {}
        self.tenant_users: dict[str, list[TenantUser]] = {}
        self.tenant_usage: dict[str, list[TenantUsage]] = {}
        self.tenant_audit_logs: dict[str, list[TenantAuditLog]] = {}
        self.db_path = db_path

        self._init_db()
        self._load_persisted_data()

    @property
    def uses_postgres(self) -> bool:
        return False

    def _init_db(self) -> None:
        if str(self.db_path) == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)

        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_users (
                    user_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    user_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    usage_json TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_api_keys (
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
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON tenant_api_keys (key_hash)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON tenant_api_keys (tenant_id)
            """)

    def _load_persisted_data(self) -> None:
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT tenant_id, config_json FROM tenants")
            for tenant_id, config_json in cursor.fetchall():
                try:
                    cfg = TenantConfig.model_validate_json(config_json)
                    self.tenants[tenant_id] = cfg
                    self.tenant_users.setdefault(tenant_id, [])
                    self.tenant_usage.setdefault(tenant_id, [])
                    self.tenant_policies.setdefault(tenant_id, [])
                    self.tenant_audit_logs.setdefault(tenant_id, [])
                except Exception as e:  # noqa: PERF203 - intentional per-iteration fault isolation
                    logger.error(f"Failed to load persisted tenant {tenant_id}: {e}")

            cursor.execute("SELECT tenant_id, user_json FROM tenant_users")
            for tid, u_json in cursor.fetchall():
                try:
                    user = TenantUser.model_validate_json(u_json)
                    self.tenant_users.setdefault(tid, []).append(user)
                except Exception as e:  # noqa: PERF203 - intentional per-iteration fault isolation
                    logger.error(f"Failed to load tenant user for {tid}: {e}")
        except Exception as e:
            logger.error(f"Error loading persisted tenant data: {e}")

    def save_user(self, user: TenantUser) -> None:
        if user.tenant_id not in self.tenant_users:
            self.tenant_users[user.tenant_id] = []
        self.tenant_users[user.tenant_id] = [
            u for u in self.tenant_users[user.tenant_id] if u.user_id != user.user_id
        ]
        self.tenant_users[user.tenant_id].append(user)

        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO tenant_users (user_id, tenant_id, username, email, user_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user.user_id,
                    user.tenant_id,
                    user.username,
                    user.email,
                    user.model_dump_json(),
                    user.created_at.isoformat(),
                ),
            )

    def save_api_key(self, api_key: TenantApiKey) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO tenant_api_keys (
                    key_id, tenant_id, user_id, name, key_hash, key_prefix,
                    permissions_json, created_at, expires_at, last_used_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    api_key.key_id,
                    api_key.tenant_id,
                    api_key.user_id,
                    api_key.name,
                    api_key.key_hash,
                    api_key.key_prefix,
                    json.dumps(api_key.permissions),
                    api_key.created_at.isoformat(),
                    api_key.expires_at.isoformat() if api_key.expires_at else None,
                    api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                    1 if api_key.is_active else 0,
                ),
            )

    def get_api_key_by_hash(self, key_hash: str) -> TenantApiKey | None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT key_id, tenant_id, user_id, name, key_hash, key_prefix,
                   permissions_json, created_at, expires_at, last_used_at, is_active
            FROM tenant_api_keys
            WHERE key_hash = ? AND is_active = 1
            """,
            (key_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return TenantApiKey(
            key_id=row[0],
            tenant_id=row[1],
            user_id=row[2],
            name=row[3],
            key_hash=row[4],
            key_prefix=row[5],
            permissions=json.loads(row[6]) if row[6] else [],
            created_at=datetime.fromisoformat(row[7]),
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
            last_used_at=datetime.fromisoformat(row[9]) if row[9] else None,
            is_active=bool(row[10]),
        )

    def get_api_key_by_id(self, key_id: str) -> TenantApiKey | None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT key_id, tenant_id, user_id, name, key_hash, key_prefix,
                   permissions_json, created_at, expires_at, last_used_at, is_active
            FROM tenant_api_keys
            WHERE key_id = ?
            """,
            (key_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return TenantApiKey(
            key_id=row[0],
            tenant_id=row[1],
            user_id=row[2],
            name=row[3],
            key_hash=row[4],
            key_prefix=row[5],
            permissions=json.loads(row[6]) if row[6] else [],
            created_at=datetime.fromisoformat(row[7]),
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
            last_used_at=datetime.fromisoformat(row[9]) if row[9] else None,
            is_active=bool(row[10]),
        )

    def revoke_api_key(self, key_id: str, tenant_id: str | None = None) -> bool:
        with self._conn:
            if tenant_id:
                cursor = self._conn.execute(
                    "UPDATE tenant_api_keys SET is_active = 0 WHERE key_id = ? AND tenant_id = ?",
                    (key_id, tenant_id),
                )
            else:
                cursor = self._conn.execute(
                    "UPDATE tenant_api_keys SET is_active = 0 WHERE key_id = ?",
                    (key_id,),
                )
            return cursor.rowcount > 0

    def list_api_keys(self, tenant_id: str) -> list[TenantApiKey]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT key_id, tenant_id, user_id, name, key_hash, key_prefix,
                   permissions_json, created_at, expires_at, last_used_at, is_active
            FROM tenant_api_keys
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        )
        return [
            TenantApiKey(
                key_id=row[0],
                tenant_id=row[1],
                user_id=row[2],
                name=row[3],
                key_hash=row[4],
                key_prefix=row[5],
                permissions=json.loads(row[6]) if row[6] else [],
                created_at=datetime.fromisoformat(row[7]),
                expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
                last_used_at=datetime.fromisoformat(row[9]) if row[9] else None,
                is_active=bool(row[10]),
            )
            for row in cursor.fetchall()
        ]

    async def create_tenant(
        self,
        name: str,
        tier: TenantTier = TenantTier.FREE,
        plan: TenantPlan = TenantPlan.TRIAL,
        domain: str | None = None,
        contact_email: str | None = None,
        custom_settings: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> TenantConfig:
        async with self._lock:
            tenant_id = tenant_id or str(uuid.uuid4())
            base_config = DEFAULT_TIER_CONFIGS[tier]
            custom_settings = custom_settings or {}
            expires_at = None
            if plan == TenantPlan.TRIAL:
                expires_at = datetime.now() + timedelta(days=14)
            elif plan == TenantPlan.MONTHLY:
                expires_at = datetime.now() + timedelta(days=30)
            elif plan == TenantPlan.YEARLY:
                expires_at = datetime.now() + timedelta(days=365)

            tenant_config = TenantConfig(
                tenant_id=tenant_id,
                name=name,
                domain=domain,
                tier=tier,
                plan=plan,
                limits=base_config.limits,
                features=base_config.features,
                expires_at=expires_at,
                contact_email=contact_email,
                custom_settings=custom_settings,
            )

            self.tenants[tenant_id] = tenant_config
            self.tenant_users.setdefault(tenant_id, [])
            self.tenant_usage.setdefault(tenant_id, [])
            self.tenant_policies.setdefault(tenant_id, [])
            self.tenant_audit_logs.setdefault(tenant_id, [])

            status_val = tenant_config.status.value if hasattr(tenant_config.status, "value") else str(tenant_config.status)
            tier_val = tenant_config.tier.value if hasattr(tenant_config.tier, "value") else str(tenant_config.tier)
            plan_val = tenant_config.plan.value if hasattr(tenant_config.plan, "value") else str(tenant_config.plan)

            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO tenants (tenant_id, name, status, tier, plan, config_json, created_at, updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        tenant_config.tenant_id,
                        tenant_config.name,
                        status_val,
                        tier_val,
                        plan_val,
                        tenant_config.model_dump_json(),
                        tenant_config.created_at.isoformat(),
                        tenant_config.updated_at.isoformat(),
                        tenant_config.expires_at.isoformat() if tenant_config.expires_at else None,
                    ),
                )

            await self._log_audit(
                tenant_id=tenant_id,
                action="tenant_created",
                resource="tenant",
                details={"name": name, "tier": tier_val, "plan": plan_val},
            )
            return tenant_config

    async def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        tenant = self.tenants.get(tenant_id)
        if tenant and tenant.expires_at and datetime.now() > tenant.expires_at:
            await self.suspend_tenant(tenant_id, "expired")
            return None
        return tenant

    async def update_tenant(
        self,
        tenant_id: str,
        updates: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TenantConfig | None:
        merged_updates = dict(updates or {})
        merged_updates.update(kwargs)
        async with self._lock:
            tenant = self.tenants.get(tenant_id)
            if not tenant:
                return None

            for key, value in merged_updates.items():
                if hasattr(tenant, key):
                    setattr(tenant, key, value)

            tenant.updated_at = datetime.now()
            status_val = tenant.status.value if hasattr(tenant.status, "value") else str(tenant.status)
            tier_val = tenant.tier.value if hasattr(tenant.tier, "value") else str(tenant.tier)
            plan_val = tenant.plan.value if hasattr(tenant.plan, "value") else str(tenant.plan)

            with self._conn:
                self._conn.execute(
                    "UPDATE tenants SET status=?, tier=?, plan=?, config_json=?, updated_at=? WHERE tenant_id=?",
                    (
                        status_val,
                        tier_val,
                        plan_val,
                        tenant.model_dump_json(),
                        tenant.updated_at.isoformat(),
                        tenant_id,
                    ),
                )

            await self._log_audit(
                tenant_id=tenant_id,
                action="tenant_updated",
                resource="tenant",
                details=merged_updates,
            )
            return tenant

    async def suspend_tenant(self, tenant_id: str, reason: str = "") -> bool:
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.SUSPENDED
        tenant.updated_at = datetime.now()
        with self._conn:
            self._conn.execute(
                "UPDATE tenants SET status='suspended', updated_at=? WHERE tenant_id=?",
                (tenant.updated_at.isoformat(), tenant_id),
            )
        await self._log_audit(
            tenant_id=tenant_id,
            action="tenant_suspended",
            resource="tenant",
            details={"reason": reason},
        )
        return True

    async def activate_tenant(self, tenant_id: str) -> bool:
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        tenant.status = TenantStatus.ACTIVE
        tenant.updated_at = datetime.now()
        with self._conn:
            self._conn.execute(
                "UPDATE tenants SET status='active', updated_at=? WHERE tenant_id=?",
                (tenant.updated_at.isoformat(), tenant_id),
            )
        await self._log_audit(
            tenant_id=tenant_id,
            action="tenant_activated",
            resource="tenant",
        )
        return True

    async def delete_tenant(self, tenant_id: str) -> bool:
        async with self._lock:
            if tenant_id not in self.tenants:
                return False
            del self.tenants[tenant_id]
            self.tenant_users.pop(tenant_id, None)
            self.tenant_usage.pop(tenant_id, None)
            self.tenant_policies.pop(tenant_id, None)
            self.tenant_audit_logs.pop(tenant_id, None)

            with self._conn:
                self._conn.execute("DELETE FROM tenants WHERE tenant_id=?", (tenant_id,))
                self._conn.execute("DELETE FROM tenant_users WHERE tenant_id=?", (tenant_id,))
                self._conn.execute("DELETE FROM tenant_api_keys WHERE tenant_id=?", (tenant_id,))
                self._conn.execute("DELETE FROM tenant_usage WHERE tenant_id=?", (tenant_id,))
                self._conn.execute("DELETE FROM tenant_audit_logs WHERE tenant_id=?", (tenant_id,))
            return True

    async def track_tenant_usage(
        self,
        tenant_id: str,
        metric: str = "query",
        amount: int | dict[str, Any] | None = 1,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(amount, dict):
            _ = amount
            amount = 1
        elif amount is None:
            amount = 1
        _ = metadata
        usage = await self._get_tenant_usage(tenant_id)
        if metric == "query":
            usage.queries_count += amount
        elif metric == "document":
            usage.documents_count += amount

    async def check_tenant_limits(
        self,
        tenant_id: str,
        operation: str,
        amount: int = 1,
    ) -> bool:
        _ = (operation, amount)
        tenant = await self.get_tenant(tenant_id)
        return bool(tenant and tenant.status == TenantStatus.ACTIVE)

    async def list_tenant_users(self, tenant_id: str) -> list[TenantUser]:
        return list(self.tenant_users.get(tenant_id, []))

    async def get_tenant_user_count(self, tenant_id: str) -> int:
        return len(self.tenant_users.get(tenant_id, []))

    async def list_tenant_audit_logs(
        self,
        tenant_id: str,
        *,
        limit: int = 1000,
    ) -> list[TenantAuditLog]:
        logs = list(self.tenant_audit_logs.get(tenant_id, []))
        return sorted(logs, key=lambda item: item.timestamp, reverse=True)[:limit]

    async def list_tenant_usage(
        self,
        tenant_id: str,
        *,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TenantUsage]:
        return [
            usage
            for usage in self.tenant_usage.get(tenant_id, [])
            if start_date <= usage.date <= end_date
        ]

    async def get_all_tenants(self) -> list[TenantConfig]:
        return list(self.tenants.values())

    async def get_tenant_count(self) -> int:
        return len(self.tenants)

    async def get_active_tenants(self) -> list[TenantConfig]:
        return [
            tenant
            for tenant in self.tenants.values()
            if tenant.status == TenantStatus.ACTIVE
        ]

    async def cleanup_expired_tenants(self) -> int:
        expired_count = 0
        current_time = datetime.now()
        for tenant_id, tenant in list(self.tenants.items()):
            if tenant.expires_at and current_time > tenant.expires_at:
                await self.suspend_tenant(tenant_id, "expired")
                expired_count += 1
        return expired_count

    async def reserve_tenant_usage(self, tenant_id: str, operation: str) -> bool:
        return await self.check_tenant_limits(tenant_id, operation)

    async def finalize_tenant_usage(
        self,
        tenant_id: str,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.track_tenant_usage(tenant_id, operation, 1, metadata)

    async def release_tenant_usage(self, tenant_id: str, operation: str) -> None:
        pass

    async def _get_tenant_usage(
        self,
        tenant_id: str,
        target_date: Any | None = None,
    ) -> TenantUsage:
        records = self.tenant_usage.get(tenant_id, [])
        if not records:
            u = TenantUsage(tenant_id=tenant_id, date=datetime.now())
            self.tenant_usage.setdefault(tenant_id, []).append(u)
            return u
        return records[0]

    async def _log_audit(
        self,
        tenant_id: str,
        action: str,
        resource: str,
        details: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None:
        log = TenantAuditLog(
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            details=details or {},
            user_id=user_id,
        )
        self.tenant_audit_logs.setdefault(tenant_id, []).append(log)

    async def get_audit_logs(
        self,
        tenant_id: str,
        limit: int = 100,
    ) -> list[TenantAuditLog]:
        logs = self.tenant_audit_logs.get(tenant_id, [])
        return sorted(logs, key=lambda item: item.timestamp, reverse=True)[:limit]

    def close(self) -> None:
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()

    async def aclose(self) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
