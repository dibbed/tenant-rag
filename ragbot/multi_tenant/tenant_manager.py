"""Tenant management system for multi-tenant support."""

import asyncio
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from ragbot.database.engine import DatabaseRuntime
from ragbot.database.mappers import (
    apply_tenant_to_records,
    audit_from_record,
    audit_to_record,
    tenant_from_records,
    tenant_to_record,
    usage_from_record,
    user_from_record,
)
from ragbot.database.repositories import (
    AuditRepository,
    QuotaRepository,
    TenantRepository,
    UsageRepository,
    UserRepository,
)
from ragbot.database.tenant_context import set_system_context, set_tenant_context
from ragbot.outputs.logger import logger
from ragbot.rag.store.base import VectorDocument

from .models import (
    DEFAULT_TIER_CONFIGS,
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
        return True

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
        return bool(deleted)

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



    async def list_tenant_users(self, tenant_id: str) -> list[TenantUser]:
        """Return tenant users from the authoritative persistence layer."""
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            records = await UserRepository(session).list_for_tenant(tenant_id)
            return [user_from_record(record) for record in records]

    async def get_tenant_user_count(self, tenant_id: str) -> int:
        """Count users without exposing process-local persistence internals."""
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            return int(await UserRepository(session).count_for_tenant(tenant_id))

    async def list_tenant_audit_logs(
        self,
        tenant_id: str,
        *,
        limit: int = 1000,
    ) -> list[TenantAuditLog]:
        """Return recent audit events for one tenant."""
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            records = await AuditRepository(session).list_for_tenant(
                tenant_id,
                limit=limit,
            )
            return [audit_from_record(record) for record in records]

    async def list_tenant_usage(
        self,
        tenant_id: str,
        *,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TenantUsage]:
        """Return usage rows for a tenant and inclusive date range."""
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            records = await UsageRepository(session).list_between(
                tenant_id,
                start_date.date(),
                end_date.date(),
            )
            return [usage_from_record(record) for record in records]

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
        return await self._pg_create_tenant(
            name=name,
            tier=tier,
            plan=plan,
            domain=domain,
            contact_email=contact_email,
            custom_settings=custom_settings,
            tenant_id=tenant_id,
        )

    async def get_tenant(self, tenant_id: str) -> TenantConfig | None:
        """دریافت تنظیمات tenant"""
        return await self._pg_get_tenant(tenant_id)

    async def update_tenant(
        self,
        tenant_id: str,
        updates: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TenantConfig | None:
        """به‌روزرسانی تنظیمات tenant"""
        merged_updates = dict(updates or {})
        merged_updates.update(kwargs)
        return await self._pg_update_tenant(tenant_id, merged_updates)

    async def suspend_tenant(self, tenant_id: str, reason: str = "manual") -> bool:
        """تعلیق tenant"""
        return await self._pg_set_status(
            tenant_id,
            TenantStatus.SUSPENDED,
            action="tenant_suspended",
            details={"reason": reason},
        )

    async def activate_tenant(self, tenant_id: str) -> bool:
        """فعال‌سازی tenant"""
        return await self._pg_set_status(
            tenant_id,
            TenantStatus.ACTIVE,
            action="tenant_activated",
            details={},
        )

    async def delete_tenant(self, tenant_id: str) -> bool:
        """حذف tenant"""
        return await self._pg_delete_tenant(tenant_id)

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


    async def reserve_tenant_usage(self, tenant_id: str, operation: str) -> bool:
        """Atomically reserve tenant quota before external work begins."""
        if operation not in {"query", "document", "storage"}:
            return True

        today = datetime.now(timezone.utc).date()
        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            tenant = await TenantRepository(session).get(tenant_id)
            if tenant is None or tenant.status != TenantStatus.ACTIVE.value:
                return False

            quota = await QuotaRepository(session).get_for_update(tenant_id)
            if quota is None:
                return False

            usage_repo = UsageRepository(session)
            usage = await usage_repo.get(tenant_id, today)

            if operation == "query":
                current = float(usage.queries_count if usage is not None else 0)
                limit = float(quota.max_queries_per_day)
                resource = "queries"
            elif operation == "document":
                current = float(usage.documents_count if usage is not None else 0)
                limit = float(quota.max_documents)
                resource = "documents"
            else:
                current = float(usage.storage_used_gb if usage is not None else 0.0)
                limit = float(quota.max_storage_gb)
                resource = "storage"

            if current >= limit:
                await AuditRepository(session).add(
                    audit_to_record(
                        TenantAuditLog(
                            tenant_id=tenant_id,
                            action="limit_exceeded",
                            resource=resource,
                            details={"limit": limit, "usage": current},
                            timestamp=datetime.now(timezone.utc),
                        )
                    )
                )
                return False

            if operation in {"query", "document"}:
                await usage_repo.increment(
                    tenant_id=tenant_id,
                    usage_date=today,
                    operation=operation,
                )
            return True

    async def finalize_tenant_usage(
        self,
        tenant_id: str,
        operation: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Finalize metadata for a successful reserved operation."""
        if operation not in {"query", "document"}:
            return

        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            await UsageRepository(session).finalize(
                tenant_id=tenant_id,
                usage_date=datetime.now(timezone.utc).date(),
                operation=operation,
                metadata=metadata,
            )

    async def release_tenant_usage(self, tenant_id: str, operation: str) -> None:
        """Compensate a reservation when the external operation fails."""
        if operation not in {"query", "document"}:
            return

        async with self._begin_postgres() as session:
            await set_tenant_context(session, tenant_id)
            await UsageRepository(session).release(
                tenant_id=tenant_id,
                usage_date=datetime.now(timezone.utc).date(),
                operation=operation,
            )

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
        await self._pg_track_tenant_usage(tenant_id, operation, metadata)

    async def get_tenant_analytics(
        self, tenant_id: str, days: int = 30
    ) -> dict[str, Any]:
        """دریافت تحلیل‌های tenant"""
        return await self._pg_get_tenant_analytics(tenant_id, days)

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
        return await self._pg_get_tenant_usage(tenant_id)

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
            return float(round(total_cost, 2))

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
        await self._pg_log_audit(
            tenant_id,
            action,
            resource,
            details,
            user_id,
            success,
            error_message,
        )

    async def get_all_tenants(self) -> list[TenantConfig]:
        """دریافت تمام tenant ها"""
        return await self._pg_list_tenants()

    async def get_tenant_count(self) -> int:
        """تعداد کل tenant ها"""
        return len(await self._pg_list_tenants())

    async def get_active_tenants(self) -> list[TenantConfig]:
        """دریافت tenant های فعال"""
        return await self._pg_list_tenants(active_only=True)

    async def cleanup_expired_tenants(self) -> int:
        """پاکسازی tenant های منقضی شده"""
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

    async def aclose(self) -> None:
        """Release resources owned by the manager."""
        if self._database_runtime is not None:
            await self._database_runtime.dispose()
            self._database_runtime = None

