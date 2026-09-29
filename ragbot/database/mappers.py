"""Mappings between PostgreSQL ORM records and multi-tenant domain models."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, time, timezone

from ragbot.multi_tenant.models import (
    TenantApiKey,
    TenantAuditLog,
    TenantConfig,
    TenantFeatures,
    TenantLimits,
    TenantPlan,
    TenantStatus,
    TenantTier,
    TenantUsage,
    TenantUser,
)

from .models import (
    TenantApiKeyRecord,
    TenantAuditLogRecord,
    TenantQuotaRecord,
    TenantRecord,
    TenantUsageRecord,
    TenantUserRecord,
)


def tenant_to_record(
    tenant: TenantConfig,
) -> tuple[TenantRecord, TenantQuotaRecord]:
    """Split a domain tenant into normalized tenant and quota rows."""
    tenant_record = TenantRecord(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        domain=tenant.domain,
        status=tenant.status.value if isinstance(tenant.status, TenantStatus) else tenant.status,
        tier=tenant.tier.value if isinstance(tenant.tier, TenantTier) else tenant.tier,
        plan=tenant.plan.value if isinstance(tenant.plan, TenantPlan) else tenant.plan,
        features=asdict(tenant.features),
        custom_settings=dict(tenant.custom_settings),
        encryption_enabled=tenant.encryption_enabled,
        data_isolation=tenant.data_isolation,
        audit_logging=tenant.audit_logging,
        content_filtering=tenant.content_filtering,
        language_preference=tenant.language_preference,
        timezone=tenant.timezone,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        expires_at=tenant.expires_at,
    )
    quota_record = TenantQuotaRecord(
        tenant_id=tenant.tenant_id,
        max_documents=tenant.limits.max_documents,
        max_queries_per_day=tenant.limits.max_queries_per_day,
        max_storage_gb=tenant.limits.max_storage_gb,
        max_users=tenant.limits.max_users,
        max_concurrent_queries=tenant.limits.max_concurrent_queries,
        retention_days=tenant.limits.retention_days,
        api_rate_limit=tenant.limits.api_rate_limit,
        updated_at=tenant.updated_at,
    )
    return tenant_record, quota_record


def tenant_from_records(
    tenant: TenantRecord,
    quota: TenantQuotaRecord,
) -> TenantConfig:
    """Reconstruct the public tenant model from normalized rows."""
    return TenantConfig(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        domain=tenant.domain,
        status=TenantStatus(tenant.status),
        tier=TenantTier(tenant.tier),
        plan=TenantPlan(tenant.plan),
        limits=TenantLimits(
            max_documents=quota.max_documents,
            max_queries_per_day=quota.max_queries_per_day,
            max_storage_gb=quota.max_storage_gb,
            max_users=quota.max_users,
            max_concurrent_queries=quota.max_concurrent_queries,
            retention_days=quota.retention_days,
            api_rate_limit=quota.api_rate_limit,
        ),
        features=TenantFeatures(**tenant.features),
        encryption_enabled=tenant.encryption_enabled,
        data_isolation=tenant.data_isolation,
        audit_logging=tenant.audit_logging,
        content_filtering=tenant.content_filtering,
        language_preference=tenant.language_preference,
        timezone=tenant.timezone,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        expires_at=tenant.expires_at,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        custom_settings=dict(tenant.custom_settings),
    )




def apply_tenant_to_records(
    tenant: TenantConfig,
    tenant_record: TenantRecord,
    quota_record: TenantQuotaRecord,
) -> None:
    """Copy a validated domain tenant onto already-loaded ORM rows."""
    fresh_tenant, fresh_quota = tenant_to_record(tenant)

    for column in TenantRecord.__table__.columns:
        if column.key != "tenant_id":
            setattr(tenant_record, column.key, getattr(fresh_tenant, column.key))

    for column in TenantQuotaRecord.__table__.columns:
        if column.key != "tenant_id":
            setattr(quota_record, column.key, getattr(fresh_quota, column.key))


def user_to_record(user: TenantUser) -> TenantUserRecord:
    return TenantUserRecord(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        password_hash=user.password_hash,
        role=user.role,
        permissions=list(user.permissions),
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


def user_from_record(user: TenantUserRecord) -> TenantUser:
    return TenantUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        password_hash=user.password_hash,
        role=user.role,
        permissions=list(user.permissions),
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


def api_key_to_record(api_key: TenantApiKey) -> TenantApiKeyRecord:
    return TenantApiKeyRecord(
        key_id=api_key.key_id,
        tenant_id=api_key.tenant_id,
        user_id=api_key.user_id,
        name=api_key.name,
        key_hash=api_key.key_hash,
        key_prefix=api_key.key_prefix,
        permissions=list(api_key.permissions),
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
    )


def api_key_from_record(api_key: TenantApiKeyRecord) -> TenantApiKey:
    return TenantApiKey(
        key_id=api_key.key_id,
        tenant_id=api_key.tenant_id,
        user_id=api_key.user_id,
        name=api_key.name,
        key_hash=api_key.key_hash,
        key_prefix=api_key.key_prefix,
        permissions=list(api_key.permissions),
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
    )


def usage_from_record(usage: TenantUsageRecord) -> TenantUsage:
    return TenantUsage(
        tenant_id=usage.tenant_id,
        date=datetime.combine(usage.usage_date, time.min, tzinfo=timezone.utc),
        documents_count=usage.documents_count,
        queries_count=usage.queries_count,
        storage_used_gb=usage.storage_used_gb,
        api_calls=usage.api_calls,
        avg_response_time=usage.avg_response_time,
        error_rate=usage.error_rate,
        satisfaction_score=usage.satisfaction_score,
        cost_usd=usage.cost_usd,
    )


def audit_to_record(audit: TenantAuditLog) -> TenantAuditLogRecord:
    return TenantAuditLogRecord(
        tenant_id=audit.tenant_id,
        user_id=audit.user_id,
        action=audit.action,
        resource=audit.resource,
        details=dict(audit.details),
        ip_address=audit.ip_address,
        user_agent=audit.user_agent,
        success=audit.success,
        error_message=audit.error_message,
        created_at=audit.timestamp,
    )


def audit_from_record(audit: TenantAuditLogRecord) -> TenantAuditLog:
    return TenantAuditLog(
        tenant_id=audit.tenant_id,
        user_id=audit.user_id,
        action=audit.action,
        resource=audit.resource,
        details=dict(audit.details),
        ip_address=audit.ip_address,
        user_agent=audit.user_agent,
        success=True if audit.success is None else audit.success,
        error_message=audit.error_message,
        timestamp=audit.created_at,
    )
