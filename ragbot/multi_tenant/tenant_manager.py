"""Tenant management system for multi-tenant support."""

import asyncio
import json
import sqlite3
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ragbot.database.engine import DatabaseRuntime
from ragbot.database.mappers import (
    apply_tenant_to_records,
    audit_to_record,
    tenant_from_records,
    tenant_to_record,
    usage_from_record,
)
from ragbot.database.repositories import (
    AuditRepository,
    QuotaRepository,
    TenantRepository,
    UsageRepository,
)
from ragbot.database.tenant_context import set_system_context, set_tenant_context
from ragbot.outputs.logger import logger
from ragbot.rag.store.base import VectorDocument

from .models import (
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


class TenantManager:
    """مدیریت tenant ها و جداسازی داده‌ها با پشتیبانی از ذخیره‌سازی پایدار"""

    def __init__(
        self,
        settings: Any | None = None,
        db_path: Any | None = None,
        *,
        session_factory: Any | None = None,
    ) -> None:
        self.settings = settings
        self.tenant_policies: dict[str, list[TenantPolicy]] = {}

        # Non-authoritative caches used only for request-local isolation helpers.
        self._tenant_cache: dict[str, Any] = {}
        self._isolation_rules: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        self._database_runtime: DatabaseRuntime | None = None
        self._session_factory = session_factory
        self._legacy_sqlite = db_path is not None

        if self._legacy_sqlite:
            assert db_path is not None
            self.tenants: dict[str, TenantConfig] = {}
            self.tenant_users: dict[str, list[TenantUser]] = {}
            self.tenant_usage: dict[str, list[TenantUsage]] = {}
            self.tenant_audit_logs: dict[str, list[TenantAuditLog]] = {}
            self.db_path = db_path
            self._init_db()
            self._load_persisted_data()
            logger.info(f"TenantManager initialized in legacy SQLite mode at {self.db_path}")
            return

        if self._session_factory is None:
            if settings is None or getattr(settings, "database", None) is None:
                raise ValueError(
                    "PostgreSQL TenantManager requires settings.database or session_factory"
                )
            database = settings.database
            self._database_runtime = DatabaseRuntime(
                database.url,
                echo=database.echo,
                pool_size=database.pool_size,
                max_overflow=database.max_overflow,
            )
            self._session_factory = self._database_runtime.session_factory

        logger.info("TenantManager initialized with PostgreSQL persistence")

    @property
    def uses_postgres(self) -> bool:
        """Whether this manager uses the PostgreSQL authoritative store."""
        return not self._legacy_sqlite

    def _init_db(self) -> None:
        """Initialize SQLite persistence tables."""
        if str(self.db_path) == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            p = Path(self.db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(p), check_same_thread=False)

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
        """Load stored tenants and users into memory cache on startup."""
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

            logger.info(f"Loaded {len(self.tenants)} persisted tenants from database")
        except Exception as e:
            logger.error(f"Error loading persisted tenant data: {e}")

    def save_user(self, user: TenantUser) -> None:
        """Persist tenant user in memory and database."""
        try:
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
        except Exception as e:
            logger.error(f"Error saving tenant user: {e}")

    def save_api_key(self, api_key: TenantApiKey) -> None:
        """Persist tenant API key in database."""
        try:
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
        except Exception as e:
            logger.error(f"Error saving tenant API key: {e}")
            raise

    def get_api_key_by_hash(self, key_hash: str) -> TenantApiKey | None:
        """Lookup active API key by cryptographic SHA-256 hash."""
        try:
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
        except Exception as e:
            logger.error(f"Error fetching API key by hash: {e}")
            return None

    def get_api_key_by_id(self, key_id: str) -> TenantApiKey | None:
        """Lookup API key by key ID."""
        try:
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
        except Exception as e:
            logger.error(f"Error fetching API key by id {key_id}: {e}")
            return None

    def revoke_api_key(self, key_id: str, tenant_id: str | None = None) -> bool:
        """Revoke API key immediately in persistent storage."""
        try:
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
        except Exception as e:
            logger.error(f"Error revoking API key {key_id}: {e}")
            return False

    def list_api_keys(self, tenant_id: str) -> list[TenantApiKey]:
        """List all API keys belonging to a tenant."""
        try:
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
            keys = [
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
            return keys
        except Exception as e:
            logger.error(f"Error listing API keys for tenant {tenant_id}: {e}")
            return []

    def update_api_key_last_used(self, key_id: str) -> None:
        """Update last_used_at timestamp for an API key."""
        try:
            with self._conn:
                self._conn.execute(
                    "UPDATE tenant_api_keys SET last_used_at = ? WHERE key_id = ?",
                    (datetime.now().isoformat(), key_id),
                )
        except Exception as e:
            logger.debug(f"Error updating API key last_used_at: {e}")


    def _begin_postgres(self) -> Any:
        if self._session_factory is None:
            raise RuntimeError("PostgreSQL session factory is not configured")
        return self._session_factory.begin()

    @staticmethod
    def _is_expired(expires_at: datetime | None) -> bool:
        if expires_at is None:
            return False
        now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
        return now > expires_at

    async def _pg_load_tenant(self, session: Any, tenant_id: str) -> TenantConfig | None:
        tenant_record = await TenantRepository(session).get(tenant_id)
        if tenant_record is None:
            return None
        quota_record = await QuotaRepository(session).get(tenant_id)
        if quota_record is None:
            raise RuntimeError(f"Tenant {tenant_id} has no quota row")
        return tenant_from_records(tenant_record, quota_record)

    async def _pg_create_tenant(
        self,
        *,
        name: str,
        tier: TenantTier,
        plan: TenantPlan,
        domain: str | None,
        contact_email: str | None,
        custom_settings: dict[str, Any] | None,
        tenant_id: str | None,
    ) -> TenantConfig:
        tenant_id = tenant_id or str(uuid.uuid4())
        base_config = DEFAULT_TIER_CONFIGS[tier]
        now = datetime.now(timezone.utc)

        expires_at = None
        if plan == TenantPlan.TRIAL:
            expires_at = now + timedelta(days=14)
        elif plan == TenantPlan.MONTHLY:
            expires_at = now + timedelta(days=30)
        elif plan == TenantPlan.YEARLY:
            expires_at = now + timedelta(days=365)

        tenant = TenantConfig(
            tenant_id=tenant_id,
            name=name,
            domain=domain,
            tier=tier,
            plan=plan,
            limits=replace(base_config.limits),
            features=replace(base_config.features),
            expires_at=expires_at,
            contact_email=contact_email,
            custom_settings=dict(custom_settings or {}),
            created_at=now,
            updated_at=now,
        )
        tenant_record, quota_record = tenant_to_record(tenant)
        audit = TenantAuditLog(
            tenant_id=tenant_id,
            action="tenant_created",
            resource="tenant",
            details={
                "name": name,
                "tier": tier.value if isinstance(tier, TenantTier) else str(tier),
                "plan": plan.value if isinstance(plan, TenantPlan) else str(plan),
            },
            timestamp=now,
        )

        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            await TenantRepository(session).add(tenant_record)
            await QuotaRepository(session).add(quota_record)
            await AuditRepository(session).add(audit_to_record(audit))

        logger.info(f"Tenant created in PostgreSQL: {tenant_id} ({name})")
        return tenant

    async def _pg_get_tenant(self, tenant_id: str) -> TenantConfig | None:
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            tenant = await self._pg_load_tenant(session, tenant_id)

        if tenant is not None and self._is_expired(tenant.expires_at):
            await self._pg_set_status(
                tenant_id,
                TenantStatus.SUSPENDED,
                action="tenant_suspended",
                details={"reason": "expired"},
            )
            return None
        return tenant

    async def _pg_update_tenant(
        self,
        tenant_id: str,
        merged_updates: dict[str, Any],
    ) -> TenantConfig | None:
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            tenant_record = await TenantRepository(session).get(tenant_id)
            if tenant_record is None:
                return None
            quota_record = await QuotaRepository(session).get(tenant_id)
            if quota_record is None:
                raise RuntimeError(f"Tenant {tenant_id} has no quota row")

            current = tenant_from_records(tenant_record, quota_record)
            payload = current.model_dump()
            payload.update(merged_updates)
            payload["updated_at"] = datetime.now(timezone.utc)
            updated = TenantConfig.model_validate(payload)
            apply_tenant_to_records(updated, tenant_record, quota_record)

            audit = TenantAuditLog(
                tenant_id=tenant_id,
                action="tenant_updated",
                resource="tenant",
                details=merged_updates,
                timestamp=updated.updated_at,
            )
            await AuditRepository(session).add(audit_to_record(audit))

        logger.info(f"Tenant updated in PostgreSQL: {tenant_id}")
        return updated

    async def _pg_set_status(
        self,
        tenant_id: str,
        status: TenantStatus,
        *,
        action: str,
        details: dict[str, Any],
    ) -> bool:
        now = datetime.now(timezone.utc)
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            tenant_record = await TenantRepository(session).get(tenant_id)
            if tenant_record is None:
                return False
            tenant_record.status = status.value
            tenant_record.updated_at = now
            audit = TenantAuditLog(
                tenant_id=tenant_id,
                action=action,
                resource="tenant",
                details=details,
                timestamp=now,
            )
            await AuditRepository(session).add(audit_to_record(audit))
        return True

    async def _pg_delete_tenant(self, tenant_id: str) -> bool:
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            if await TenantRepository(session).get(tenant_id) is None:
                return False
            deleted = await TenantRepository(session).delete(tenant_id)
        if deleted:
            self._tenant_cache.pop(tenant_id, None)
            self.tenant_policies.pop(tenant_id, None)
        return deleted

    async def _pg_get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        today = datetime.now(timezone.utc).date()
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            record = await UsageRepository(session).get(tenant_id, today)
        if record is None:
            return TenantUsage(
                tenant_id=tenant_id,
                date=datetime.combine(
                    today,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
            )
        return usage_from_record(record)

    async def _pg_track_tenant_usage(
        self,
        tenant_id: str,
        operation: str,
        metadata: dict[str, Any] | None,
    ) -> None:
        today = datetime.now(timezone.utc).date()
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            if await TenantRepository(session).get(tenant_id) is None:
                return
            await UsageRepository(session).increment(
                tenant_id=tenant_id,
                usage_date=today,
                operation=operation,
                metadata=metadata,
            )

    async def _pg_log_audit(
        self,
        tenant_id: str,
        action: str,
        resource: str,
        details: dict[str, Any],
        user_id: str | None,
        success: bool,
        error_message: str | None,
        *,
        session: Any | None = None,
    ) -> None:
        audit = TenantAuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            details=details,
            success=success,
            error_message=error_message,
            timestamp=datetime.now(timezone.utc),
        )
        record = audit_to_record(audit)
        if session is not None:
            await AuditRepository(session).add(record)
            return

        async with self._begin_postgres() as own_session:
            await set_tenant_context(own_session, tenant_id)
            await AuditRepository(own_session).add(record)

    async def _pg_list_tenants(self, *, active_only: bool = False) -> list[TenantConfig]:
        async with self._begin_postgres() as session:
            await set_system_context(session)
            repository = TenantRepository(session)
            records = (
                await repository.list_active()
                if active_only
                else await repository.list_all()
            )
            tenants: list[TenantConfig] = []
            quotas = QuotaRepository(session)
            for record in records:
                quota = await quotas.get(record.tenant_id)
                if quota is None:
                    logger.error(f"Tenant {record.tenant_id} has no quota row")
                    continue
                tenants.append(tenant_from_records(record, quota))
            return tenants


    async def _pg_get_tenant_analytics(
        self, tenant_id: str, days: int
    ) -> dict[str, Any]:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            tenant = await self._pg_load_tenant(session, tenant_id)
            if tenant is None:
                return {"error": "Tenant not found"}
            records = await UsageRepository(session).list_between(
                tenant_id,
                start_date,
                end_date,
            )

        usage_records = [usage_from_record(record) for record in records]
        total_queries = sum(usage.queries_count for usage in usage_records)
        total_documents = sum(usage.documents_count for usage in usage_records)
        total_storage = sum(usage.storage_used_gb for usage in usage_records)
        total_api_calls = sum(usage.api_calls for usage in usage_records)
        total_cost = sum(usage.cost_usd for usage in usage_records)

        count = len(usage_records)
        avg_response_time = (
            sum(usage.avg_response_time for usage in usage_records) / count
            if count
            else 0.0
        )
        avg_error_rate = (
            sum(usage.error_rate for usage in usage_records) / count
            if count
            else 0.0
        )
        avg_satisfaction = (
            sum(usage.satisfaction_score for usage in usage_records) / count
            if count
            else 0.0
        )

        query_capacity = tenant.limits.max_queries_per_day * days
        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "tier": tenant.tier,
            "period_days": days,
            "usage_summary": {
                "total_queries": total_queries,
                "total_documents": total_documents,
                "total_storage_gb": total_storage,
                "total_api_calls": total_api_calls,
                "total_cost_usd": total_cost,
            },
            "performance_metrics": {
                "avg_response_time": avg_response_time,
                "avg_error_rate": avg_error_rate,
                "avg_satisfaction_score": avg_satisfaction,
            },
            "limits": {
                "max_queries_per_day": tenant.limits.max_queries_per_day,
                "max_documents": tenant.limits.max_documents,
                "max_storage_gb": tenant.limits.max_storage_gb,
                "max_users": tenant.limits.max_users,
            },
            "usage_percentage": {
                "queries": (total_queries / query_capacity * 100)
                if query_capacity
                else 0.0,
                "documents": (
                    total_documents / tenant.limits.max_documents * 100
                    if tenant.limits.max_documents
                    else 0.0
                ),
                "storage": (
                    total_storage / tenant.limits.max_storage_gb * 100
                    if tenant.limits.max_storage_gb
                    else 0.0
                ),
            },
            "features_enabled": asdict(tenant.features),
        }

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
        """ایجاد tenant جدید و ذخیره در دیتابیس پایدار"""
        if self.uses_postgres:
            return await self._pg_create_tenant(
                name=name,
                tier=tier,
                plan=plan,
                domain=domain,
                contact_email=contact_email,
                custom_settings=custom_settings,
                tenant_id=tenant_id,
            )

        async with self._lock:
            try:
                tenant_id = tenant_id or str(uuid.uuid4())

                # ایجاد تنظیمات بر اساس tier
                base_config = DEFAULT_TIER_CONFIGS[tier]

                # تنظیمات سفارشی
                custom_settings = custom_settings or {}

                # محاسبه تاریخ انقضا
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

                # ذخیره tenant در حافظه
                self.tenants[tenant_id] = tenant_config
                self.tenant_users.setdefault(tenant_id, [])
                self.tenant_usage.setdefault(tenant_id, [])
                self.tenant_policies.setdefault(tenant_id, [])
                self.tenant_audit_logs.setdefault(tenant_id, [])

                # ذخیره پایدار در دیتابیس
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

                # ثبت audit log
                await self._log_audit(
                    tenant_id=tenant_id,
                    action="tenant_created",
                    resource="tenant",
                    details={"name": name, "tier": tier_val, "plan": plan_val},
                )

                logger.info(f"Tenant created: {tenant_id} ({name})")
                return tenant_config

            except Exception as e:
                logger.error(f"Error creating tenant: {e}")
                raise

    async def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        """دریافت تنظیمات tenant"""
        if self.uses_postgres:
            return await self._pg_get_tenant(tenant_id)

        try:
            tenant = self.tenants.get(tenant_id)
            # بررسی انقضا
            if tenant and tenant.expires_at and datetime.now() > tenant.expires_at:
                await self._suspend_tenant(tenant_id, "expired")
                return None
            return tenant
        except Exception as e:
            logger.error(f"Error getting tenant {tenant_id}: {e}")
            return None

    async def update_tenant(
        self,
        tenant_id: str,
        updates: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TenantConfig | None:
        """به‌روزرسانی تنظیمات tenant"""
        merged_updates = dict(updates or {})
        merged_updates.update(kwargs)
        if self.uses_postgres:
            return await self._pg_update_tenant(tenant_id, merged_updates)

        async with self._lock:
            try:
                tenant = self.tenants.get(tenant_id)
                if not tenant:
                    return None

                # به‌روزرسانی فیلدها
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

                # ثبت audit log
                await self._log_audit(
                    tenant_id=tenant_id,
                    action="tenant_updated",
                    resource="tenant",
                    details=merged_updates,
                )

                logger.info(f"Tenant updated: {tenant_id}")
                return tenant

            except Exception as e:
                logger.error(f"Error updating tenant {tenant_id}: {e}")
                return None

    async def suspend_tenant(self, tenant_id: str, reason: str = "manual") -> bool:
        """تعلیق tenant"""
        if self.uses_postgres:
            return await self._pg_set_status(
                tenant_id,
                TenantStatus.SUSPENDED,
                action="tenant_suspended",
                details={"reason": reason},
            )
        return await self._suspend_tenant(tenant_id, reason)

    async def _suspend_tenant(self, tenant_id: str, reason: str) -> bool:
        """تعلیق داخلی tenant"""
        if self.uses_postgres:
            return await self._pg_set_status(
                tenant_id,
                TenantStatus.SUSPENDED,
                action="tenant_suspended",
                details={"reason": reason},
            )

        async with self._lock:
            try:
                tenant = self.tenants.get(tenant_id)
                if not tenant:
                    return False

                tenant.status = TenantStatus.SUSPENDED
                tenant.updated_at = datetime.now()

                with self._conn:
                    self._conn.execute(
                        "UPDATE tenants SET status=?, config_json=?, updated_at=? WHERE tenant_id=?",
                        (
                            tenant.status.value,
                            tenant.model_dump_json(),
                            tenant.updated_at.isoformat(),
                            tenant_id,
                        ),
                    )

                # ثبت audit log
                await self._log_audit(
                    tenant_id=tenant_id,
                    action="tenant_suspended",
                    resource="tenant",
                    details={"reason": reason},
                )

                logger.info(f"Tenant suspended: {tenant_id} (reason: {reason})")
                return True

            except Exception as e:
                logger.error(f"Error suspending tenant {tenant_id}: {e}")
                return False

    async def activate_tenant(self, tenant_id: str) -> bool:
        """فعال‌سازی tenant"""
        if self.uses_postgres:
            return await self._pg_set_status(
                tenant_id,
                TenantStatus.ACTIVE,
                action="tenant_activated",
                details={},
            )

        async with self._lock:
            try:
                tenant = self.tenants.get(tenant_id)
                if not tenant:
                    return False

                tenant.status = TenantStatus.ACTIVE
                tenant.updated_at = datetime.now()

                with self._conn:
                    self._conn.execute(
                        "UPDATE tenants SET status=?, config_json=?, updated_at=? WHERE tenant_id=?",
                        (
                            tenant.status.value,
                            tenant.model_dump_json(),
                            tenant.updated_at.isoformat(),
                            tenant_id,
                        ),
                    )

                # ثبت audit log
                await self._log_audit(
                    tenant_id=tenant_id,
                    action="tenant_activated",
                    resource="tenant",
                    details={},
                )

                logger.info(f"Tenant activated: {tenant_id}")
                return True

            except Exception as e:
                logger.error(f"Error activating tenant {tenant_id}: {e}")
                return False

    async def delete_tenant(self, tenant_id: str) -> bool:
        """حذف tenant"""
        if self.uses_postgres:
            return await self._pg_delete_tenant(tenant_id)

        async with self._lock:
            try:
                if tenant_id not in self.tenants:
                    return False

                # حذف تمام داده‌های مربوط به tenant
                del self.tenants[tenant_id]
                self.tenant_users.pop(tenant_id, None)
                self.tenant_usage.pop(tenant_id, None)
                self.tenant_policies.pop(tenant_id, None)
                self.tenant_audit_logs.pop(tenant_id, None)

                # پاک کردن cache
                if tenant_id in self._tenant_cache:
                    del self._tenant_cache[tenant_id]

                with self._conn:
                    self._conn.execute("DELETE FROM tenants WHERE tenant_id=?", (tenant_id,))
                    self._conn.execute("DELETE FROM tenant_users WHERE tenant_id=?", (tenant_id,))
                    self._conn.execute("DELETE FROM tenant_api_keys WHERE tenant_id=?", (tenant_id,))
                    self._conn.execute("DELETE FROM tenant_usage WHERE tenant_id=?", (tenant_id,))
                    self._conn.execute("DELETE FROM tenant_audit_logs WHERE tenant_id=?", (tenant_id,))

                logger.info(f"Tenant deleted: {tenant_id}")
                return True

            except Exception as e:
                logger.error(f"Error deleting tenant {tenant_id}: {e}")
                return False

    async def isolate_data(
        self, tenant_id: str, documents: list[VectorDocument]
    ) -> list[VectorDocument]:
        """جداسازی داده‌ها بر اساس tenant"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                return []

            # اعمال قوانین جداسازی
            isolated_docs = []
            for doc in documents:
                # اضافه کردن tenant_id به metadata
                if not hasattr(doc, "metadata"):
                    doc.metadata = {}

                doc.metadata["tenant_id"] = tenant_id
                doc.metadata["tenant_tier"] = tenant.tier
                doc.metadata["created_at"] = datetime.now().isoformat()

                # اعمال فیلتر محتوا
                if tenant.content_filtering:
                    if await self._apply_content_filter(doc, tenant):
                        isolated_docs.append(doc)
                else:
                    isolated_docs.append(doc)

            logger.debug(
                f"Data isolated for tenant {tenant_id}: {len(isolated_docs)} documents"
            )
            return isolated_docs

        except Exception as e:
            logger.error(f"Error isolating data for tenant {tenant_id}: {e}")
            return []

    async def apply_tenant_policies(
        self, tenant_id: str, query: str
    ) -> tuple[str, dict[str, Any]]:
        """اعمال سیاست‌های tenant بر روی query"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant or tenant.status != TenantStatus.ACTIVE:
                return query, {}

            policies = self.tenant_policies.get(tenant_id, [])
            applied_policies = {}

            # اعمال سیاست‌ها بر اساس اولویت
            sorted_policies = sorted(policies, key=lambda p: p.priority, reverse=True)

            for policy in sorted_policies:
                if not policy.is_active:
                    continue

                # بررسی شرایط
                if await self._check_policy_conditions(policy, query, tenant):
                    # اعمال اقدامات
                    query, policy_result = await self._apply_policy_actions(
                        policy, query, tenant
                    )
                    applied_policies[policy.policy_name] = policy_result

            logger.debug(
                f"Applied {len(applied_policies)} policies for tenant {tenant_id}"
            )
            return query, applied_policies

        except Exception as e:
            logger.error(f"Error applying policies for tenant {tenant_id}: {e}")
            return query, {}

    async def check_tenant_limits(self, tenant_id: str, operation: str) -> bool:
        """بررسی محدودیت‌های tenant"""
        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                return False

            limits = tenant.limits
            usage = await self._get_tenant_usage(tenant_id)

            # بررسی محدودیت‌ها بر اساس نوع عملیات
            if operation == "query":
                if usage.queries_count >= limits.max_queries_per_day:
                    await self._log_audit(
                        tenant_id=tenant_id,
                        action="limit_exceeded",
                        resource="queries",
                        details={
                            "limit": limits.max_queries_per_day,
                            "usage": usage.queries_count,
                        },
                    )
                    return False

            elif operation == "document":
                if usage.documents_count >= limits.max_documents:
                    await self._log_audit(
                        tenant_id=tenant_id,
                        action="limit_exceeded",
                        resource="documents",
                        details={
                            "limit": limits.max_documents,
                            "usage": usage.documents_count,
                        },
                    )
                    return False

            elif (
                operation == "storage"
                and usage.storage_used_gb >= limits.max_storage_gb
            ):
                await self._log_audit(
                        tenant_id=tenant_id,
                        action="limit_exceeded",
                        resource="storage",
                        details={
                            "limit": limits.max_storage_gb,
                            "usage": usage.storage_used_gb,
                        },
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking limits for tenant {tenant_id}: {e}")
            return False

    async def track_tenant_usage(
        self,
        tenant_id: str,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """ردیابی استفاده tenant"""
        if self.uses_postgres:
            await self._pg_track_tenant_usage(tenant_id, operation, metadata)
            return

        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                return

            # دریافت یا ایجاد usage record برای امروز
            today = datetime.now().date()
            usage_records = self.tenant_usage.get(tenant_id, [])

            today_usage = None
            for usage in usage_records:
                if usage.date.date() == today:
                    today_usage = usage
                    break

            if not today_usage:
                today_usage = TenantUsage(
                    tenant_id=tenant_id,
                    date=datetime.now(),
                )
                usage_records.append(today_usage)
                self.tenant_usage[tenant_id] = usage_records

            # به‌روزرسانی آمار
            metadata = metadata or {}

            if operation == "query":
                today_usage.queries_count += 1
                today_usage.avg_response_time = metadata.get("response_time", 0)
                today_usage.error_rate = metadata.get("error_rate", 0)
                today_usage.satisfaction_score = metadata.get("satisfaction", 0)

            elif operation == "document":
                today_usage.documents_count += 1
                today_usage.storage_used_gb += metadata.get("size_gb", 0)

            elif operation == "api_call":
                today_usage.api_calls += 1

            # محاسبه هزینه
            today_usage.cost_usd = await self._calculate_usage_cost(tenant, today_usage)

            logger.debug(f"Usage tracked for tenant {tenant_id}: {operation}")

        except Exception as e:
            logger.error(f"Error tracking usage for tenant {tenant_id}: {e}")

    async def get_tenant_analytics(
        self, tenant_id: str, days: int = 30
    ) -> dict[str, Any]:
        """دریافت تحلیل‌های tenant"""
        if self.uses_postgres:
            return await self._pg_get_tenant_analytics(tenant_id, days)

        try:
            tenant = await self.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            # دریافت آمار استفاده
            usage_records = self.tenant_usage.get(tenant_id, [])
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            filtered_usage = [
                usage for usage in usage_records if start_date <= usage.date <= end_date
            ]

            # محاسبه آمار
            total_queries = sum(usage.queries_count for usage in filtered_usage)
            total_documents = sum(usage.documents_count for usage in filtered_usage)
            total_storage = sum(usage.storage_used_gb for usage in filtered_usage)
            total_api_calls = sum(usage.api_calls for usage in filtered_usage)
            total_cost = sum(usage.cost_usd for usage in filtered_usage)

            avg_response_time = 0.0
            avg_error_rate = 0.0
            avg_satisfaction = 0.0

            if filtered_usage:
                avg_response_time = sum(
                    usage.avg_response_time for usage in filtered_usage
                ) / len(filtered_usage)
                avg_error_rate = sum(
                    usage.error_rate for usage in filtered_usage
                ) / len(filtered_usage)
                avg_satisfaction = sum(
                    usage.satisfaction_score for usage in filtered_usage
                ) / len(filtered_usage)

            analytics = {
                "tenant_id": tenant_id,
                "tenant_name": tenant.name,
                "tier": tenant.tier,
                "period_days": days,
                "usage_summary": {
                    "total_queries": total_queries,
                    "total_documents": total_documents,
                    "total_storage_gb": total_storage,
                    "total_api_calls": total_api_calls,
                    "total_cost_usd": total_cost,
                },
                "performance_metrics": {
                    "avg_response_time": avg_response_time,
                    "avg_error_rate": avg_error_rate,
                    "avg_satisfaction_score": avg_satisfaction,
                },
                "limits": {
                    "max_queries_per_day": tenant.limits.max_queries_per_day,
                    "max_documents": tenant.limits.max_documents,
                    "max_storage_gb": tenant.limits.max_storage_gb,
                    "max_users": tenant.limits.max_users,
                },
                "usage_percentage": {
                    "queries": (
                        total_queries / (tenant.limits.max_queries_per_day * days)
                    )
                    * 100,
                    "documents": (total_documents / tenant.limits.max_documents) * 100,
                    "storage": (total_storage / tenant.limits.max_storage_gb) * 100,
                },
                "features_enabled": asdict(tenant.features),
            }

            return analytics

        except Exception as e:
            logger.error(f"Error getting analytics for tenant {tenant_id}: {e}")
            return {"error": str(e)}

    async def _apply_content_filter(
        self, doc: VectorDocument, tenant: TenantConfig
    ) -> bool:
        """اعمال فیلتر محتوا"""
        try:
            # بررسی محتوای سند بر اساس سیاست‌های tenant
            content = getattr(doc, "content", "") or getattr(doc, "text", "")

            # فیلترهای ساده
            if tenant.content_filtering:
                # بررسی کلمات ممنوعه
                forbidden_words = tenant.custom_settings.get("forbidden_words", [])
                if any(word.lower() in content.lower() for word in forbidden_words):
                    return False

                # بررسی طول محتوا
                min_length = tenant.custom_settings.get("min_content_length", 10)
                if len(content) < min_length:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error applying content filter: {e}")
            return True

    async def _check_policy_conditions(
        self, policy: TenantPolicy, query: str, tenant: TenantConfig
    ) -> bool:
        """بررسی شرایط سیاست"""
        try:
            for condition in policy.conditions:
                if condition == "time_based":
                    # بررسی زمان‌بندی
                    current_hour = datetime.now().hour
                    allowed_hours = policy.rules.get("allowed_hours", list(range(24)))
                    if current_hour not in allowed_hours:
                        return False

                elif condition == "query_length":
                    # بررسی طول query
                    max_length = policy.rules.get("max_query_length", 1000)
                    if len(query) > max_length:
                        return False

                elif condition == "tier_based":
                    # بررسی tier
                    required_tier = policy.rules.get("required_tier", TenantTier.FREE)
                    if tenant.tier.value < required_tier.value:
                        return False

            return True

        except Exception as e:
            logger.error(f"Error checking policy conditions: {e}")
            return False

    async def _apply_policy_actions(
        self, policy: TenantPolicy, query: str, tenant: TenantConfig
    ) -> tuple[str, dict[str, Any]]:
        """اعمال اقدامات سیاست"""
        try:
            result: dict[str, Any] = {
                "policy": policy.policy_name,
                "actions_applied": [],
            }

            for action in policy.actions:
                if action == "query_modification":
                    # تغییر query
                    prefix = policy.rules.get("query_prefix", "")
                    suffix = policy.rules.get("query_suffix", "")
                    query = f"{prefix} {query} {suffix}".strip()
                    result["actions_applied"].append("query_modification")

                elif action == "rate_limiting":
                    # محدودیت نرخ
                    result["actions_applied"].append("rate_limiting")

                elif action == "logging":
                    # ثبت لاگ
                    result["actions_applied"].append("logging")

            return query, result

        except Exception as e:
            logger.error(f"Error applying policy actions: {e}")
            return query, {}

    async def _get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        """دریافت آمار استفاده tenant"""
        if self.uses_postgres:
            return await self._pg_get_tenant_usage(tenant_id)

        try:
            usage_records = self.tenant_usage.get(tenant_id, [])
            if not usage_records:
                return TenantUsage(tenant_id=tenant_id, date=datetime.now())

            # بازگشت آخرین record
            return max(usage_records, key=lambda x: x.date)

        except Exception as e:
            logger.error(f"Error getting tenant usage: {e}")
            return TenantUsage(tenant_id=tenant_id, date=datetime.now())

    async def _calculate_usage_cost(
        self, tenant: TenantConfig, usage: TenantUsage
    ) -> float:
        """محاسبه هزینه استفاده"""
        try:
            # هزینه‌های پایه بر اساس tier
            base_costs = {
                TenantTier.FREE: 0.0,
                TenantTier.BASIC: 10.0,
                TenantTier.PREMIUM: 50.0,
                TenantTier.ENTERPRISE: 200.0,
            }

            base_cost = base_costs.get(tenant.tier, 0.0)

            # هزینه‌های اضافی بر اساس استفاده
            query_cost = usage.queries_count * 0.001  # $0.001 per query
            storage_cost = usage.storage_used_gb * 0.1  # $0.1 per GB
            api_cost = usage.api_calls * 0.01  # $0.01 per API call

            total_cost = base_cost + query_cost + storage_cost + api_cost
            return round(total_cost, 2)

        except Exception as e:
            logger.error(f"Error calculating usage cost: {e}")
            return 0.0

    async def _log_audit(
        self,
        tenant_id: str,
        action: str,
        resource: str,
        details: dict[str, Any],
        user_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """ثبت audit log"""
        if self.uses_postgres:
            await self._pg_log_audit(
                tenant_id,
                action,
                resource,
                details,
                user_id,
                success,
                error_message,
            )
            return

        try:
            audit_log = TenantAuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource=resource,
                details=details,
                success=success,
                error_message=error_message,
            )

            if tenant_id not in self.tenant_audit_logs:
                self.tenant_audit_logs[tenant_id] = []

            self.tenant_audit_logs[tenant_id].append(audit_log)

            # نگه داشتن فقط آخرین 1000 log
            if len(self.tenant_audit_logs[tenant_id]) > 1000:
                self.tenant_audit_logs[tenant_id] = self.tenant_audit_logs[tenant_id][
                    -1000:
                ]

            if hasattr(self, "_conn") and self._conn:
                try:
                    with self._conn:
                        self._conn.execute(
                            "INSERT INTO tenant_audit_logs (tenant_id, action, resource, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
                            (
                                tenant_id,
                                action,
                                resource,
                                json.dumps(details),
                                audit_log.timestamp.isoformat(),
                            ),
                        )
                except Exception as db_e:
                    logger.warning(f"Error persisting audit log: {db_e}")

        except Exception as e:
            logger.error(f"Error logging audit: {e}")

    async def get_all_tenants(self) -> list[TenantConfig]:
        """دریافت تمام tenant ها"""
        if self.uses_postgres:
            return await self._pg_list_tenants()
        return list(self.tenants.values())

    async def get_tenant_count(self) -> int:
        """تعداد کل tenant ها"""
        if self.uses_postgres:
            return len(await self._pg_list_tenants())
        return len(self.tenants)

    async def get_active_tenants(self) -> list[TenantConfig]:
        """دریافت tenant های فعال"""
        if self.uses_postgres:
            return await self._pg_list_tenants(active_only=True)
        return [
            tenant
            for tenant in self.tenants.values()
            if tenant.status == TenantStatus.ACTIVE
        ]

    async def cleanup_expired_tenants(self) -> int:
        """پاکسازی tenant های منقضی شده"""
        if self.uses_postgres:
            expired_count = 0
            for tenant in await self._pg_list_tenants():
                if self._is_expired(tenant.expires_at) and await self._pg_set_status(
                    tenant.tenant_id,
                    TenantStatus.SUSPENDED,
                    action="tenant_suspended",
                    details={"reason": "expired"},
                ):
                    expired_count += 1
            logger.info(f"Cleaned up {expired_count} expired PostgreSQL tenants")
            return expired_count

        try:
            expired_count = 0
            current_time = datetime.now()

            for tenant_id, tenant in list(self.tenants.items()):
                if tenant.expires_at and current_time > tenant.expires_at:
                    await self._suspend_tenant(tenant_id, "expired")
                    expired_count += 1

            logger.info(f"Cleaned up {expired_count} expired tenants")
            return expired_count

        except Exception as e:
            logger.error(f"Error cleaning up expired tenants: {e}")
            return 0

    async def aclose(self) -> None:
        """Release resources owned by the manager."""
        if self._database_runtime is not None:
            await self._database_runtime.dispose()
            self._database_runtime = None
            return
        if self._legacy_sqlite:
            self.close()

    def close(self) -> None:
        """Close the legacy SQLite database connection."""
        try:
            if hasattr(self, "_conn") and self._conn:
                self._conn.close()
        except Exception as e:
            logger.debug(f"Error closing tenant database connection: {e}")

    def __del__(self) -> None:
        self.close()

