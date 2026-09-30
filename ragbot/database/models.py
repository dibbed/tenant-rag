"""SQLAlchemy models for PostgreSQL-backed multi-tenant persistence."""

from __future__ import annotations

from datetime import (  # noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime
    date,
    datetime,
)
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for the Phase 5 relational schema."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TenantRecord(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'inactive', 'pending')",
            name="status_valid",
        ),
        CheckConstraint(
            "tier IN ('free', 'basic', 'premium', 'enterprise')",
            name="tier_valid",
        ),
        CheckConstraint(
            "plan IN ('trial', 'monthly', 'yearly', 'custom')",
            name="plan_valid",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    tier: Mapped[str] = mapped_column(Text, nullable=False, default="free")
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="trial")
    features: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    custom_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    encryption_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    data_isolation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    audit_logging: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    content_filtering: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    language_preference: Mapped[str] = mapped_column(
        Text, nullable=False, default="fa", server_default=text("'fa'")
    )
    timezone: Mapped[str] = mapped_column(
        Text, nullable=False, default="Asia/Tehran", server_default=text("'Asia/Tehran'")
    )
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantUserRecord(Base):
    __tablename__ = "tenant_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="tenant_username"),
        UniqueConstraint("tenant_id", "email", name="tenant_email"),
        Index("ix_tenant_users_tenant_id", "tenant_id"),
    )

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user")
    permissions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantApiKeyRecord(Base):
    __tablename__ = "tenant_api_keys"
    __table_args__ = (
        Index("ix_tenant_api_keys_tenant_id", "tenant_id"),
        Index("ix_tenant_api_keys_key_hash", "key_hash"),
    )

    key_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenant_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class TenantQuotaRecord(Base):
    __tablename__ = "tenant_quotas"
    __table_args__ = (
        CheckConstraint("max_documents >= 0", name="max_documents_nonnegative"),
        CheckConstraint("max_queries_per_day >= 0", name="max_queries_nonnegative"),
        CheckConstraint("max_storage_gb >= 0", name="max_storage_nonnegative"),
        CheckConstraint("max_users >= 0", name="max_users_nonnegative"),
        CheckConstraint("max_concurrent_queries >= 0", name="max_concurrent_nonnegative"),
        CheckConstraint("retention_days >= 0", name="retention_days_nonnegative"),
        CheckConstraint("api_rate_limit >= 0", name="api_rate_limit_nonnegative"),
    )

    tenant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    max_documents: Mapped[int] = mapped_column(Integer, nullable=False)
    max_queries_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    max_storage_gb: Mapped[float] = mapped_column(Float, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent_queries: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    api_rate_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TenantUsageRecord(Base):
    __tablename__ = "tenant_usage"
    __table_args__ = (
        CheckConstraint("documents_count >= 0", name="documents_count_nonnegative"),
        CheckConstraint("queries_count >= 0", name="queries_count_nonnegative"),
        CheckConstraint("storage_used_gb >= 0", name="storage_used_nonnegative"),
        CheckConstraint("api_calls >= 0", name="api_calls_nonnegative"),
    )

    tenant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_date: Mapped[date] = mapped_column(Date, primary_key=True)
    documents_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    queries_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    storage_used_gb: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )
    api_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    avg_response_time: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )
    error_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )
    satisfaction_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )
    cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TenantAuditLogRecord(Base):
    __tablename__ = "tenant_audit_logs"
    __table_args__ = (Index("ix_tenant_audit_logs_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool | None] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TenantSessionRecord(Base):
    __tablename__ = "tenant_sessions"
    __table_args__ = (
        Index("ix_tenant_sessions_tenant_user", "tenant_id", "user_id"),
        Index("ix_tenant_sessions_expires_at", "expires_at"),
    )

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tenant_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
