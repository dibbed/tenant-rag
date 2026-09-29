"""Mapping tests between domain models and PostgreSQL ORM records."""

from __future__ import annotations

from datetime import datetime, timezone

from ragbot.database.mappers import (
    api_key_from_record,
    audit_from_record,
    tenant_from_records,
    tenant_to_record,
    usage_from_record,
    user_from_record,
)
from ragbot.database.models import (
    TenantApiKeyRecord,
    TenantAuditLogRecord,
    TenantUsageRecord,
    TenantUserRecord,
)
from ragbot.multi_tenant.models import (
    TenantApiKey,
    TenantConfig,
    TenantLimits,
    TenantTier,
)


def test_tenant_mapping_keeps_limits_out_of_json_blob() -> None:
    domain = TenantConfig(
        tenant_id="tenant_a",
        name="Acme",
        tier=TenantTier.PREMIUM,
        limits=TenantLimits(max_documents=123, max_users=9),
        custom_settings={"region": "eu"},
    )

    tenant_record, quota_record = tenant_to_record(domain)
    restored = tenant_from_records(tenant_record, quota_record)

    assert tenant_record.tenant_id == "tenant_a"
    assert quota_record.max_documents == 123
    assert restored.limits.max_documents == 123
    assert restored.limits.max_users == 9
    assert restored.custom_settings == {"region": "eu"}


def test_user_api_key_usage_and_audit_records_restore_domain_models() -> None:
    now = datetime.now(timezone.utc)
    user = user_from_record(
        TenantUserRecord(
            user_id="user_1",
            tenant_id="tenant_a",
            username="alice",
            email="alice@example.com",
            password_hash="hash",
            role="admin",
            permissions=["api_access"],
            is_active=True,
            created_at=now,
            last_login=now,
        )
    )
    api_key = api_key_from_record(
        TenantApiKeyRecord(
            key_id="key_1",
            tenant_id="tenant_a",
            user_id="user_1",
            name="cli",
            key_hash="scrypt$...",
            key_prefix="rgb_key_1",
            permissions=["api_access"],
            created_at=now,
            expires_at=None,
            last_used_at=None,
            is_active=True,
        )
    )
    usage = usage_from_record(
        TenantUsageRecord(
            tenant_id="tenant_a",
            usage_date=now.date(),
            documents_count=2,
            queries_count=3,
            storage_used_gb=0.5,
            api_calls=4,
            avg_response_time=1.2,
            error_rate=0.0,
            satisfaction_score=0.9,
            cost_usd=1.0,
            updated_at=now,
        )
    )
    audit = audit_from_record(
        TenantAuditLogRecord(
            id=1,
            tenant_id="tenant_a",
            user_id="user_1",
            action="updated",
            resource="tenant",
            details={"field": "name"},
            success=True,
            created_at=now,
        )
    )

    assert user.user_id == "user_1"
    assert api_key == TenantApiKey(
        key_id="key_1",
        tenant_id="tenant_a",
        user_id="user_1",
        name="cli",
        key_hash="scrypt$...",
        key_prefix="rgb_key_1",
        permissions=["api_access"],
        created_at=now,
        expires_at=None,
        last_used_at=None,
        is_active=True,
    )
    assert usage.date.date() == now.date()
    assert usage.queries_count == 3
    assert audit.user_id == "user_1"
    assert audit.details == {"field": "name"}
