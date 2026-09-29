"""Create the Phase 5 PostgreSQL tenant schema.

Revision ID: phase5_0001
Revises:
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "phase5_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "custom_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("encryption_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("data_isolation", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("audit_logging", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("content_filtering", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("language_preference", sa.Text(), server_default=sa.text("'fa'"), nullable=False),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'Asia/Tehran'"), nullable=False),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "plan IN ('trial', 'monthly', 'yearly', 'custom')",
            name="ck_tenants_plan_valid",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'inactive', 'pending')",
            name="ck_tenants_status_valid",
        ),
        sa.CheckConstraint(
            "tier IN ('free', 'basic', 'premium', 'enterprise')",
            name="ck_tenants_tier_valid",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_tenants"),
    )

    op.create_table(
        "tenant_users",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_users_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_tenant_users"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_tenant_users_tenant_email"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_tenant_users_tenant_username"),
    )
    op.create_index("ix_tenant_users_tenant_id", "tenant_users", ["tenant_id"], unique=False)

    op.create_table(
        "tenant_quotas",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("max_documents", sa.Integer(), nullable=False),
        sa.Column("max_queries_per_day", sa.Integer(), nullable=False),
        sa.Column("max_storage_gb", sa.Float(), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=False),
        sa.Column("max_concurrent_queries", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("api_rate_limit", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("api_rate_limit >= 0", name="ck_tenant_quotas_api_rate_limit_nonnegative"),
        sa.CheckConstraint("max_concurrent_queries >= 0", name="ck_tenant_quotas_max_concurrent_nonnegative"),
        sa.CheckConstraint("max_documents >= 0", name="ck_tenant_quotas_max_documents_nonnegative"),
        sa.CheckConstraint("max_queries_per_day >= 0", name="ck_tenant_quotas_max_queries_nonnegative"),
        sa.CheckConstraint("max_storage_gb >= 0", name="ck_tenant_quotas_max_storage_nonnegative"),
        sa.CheckConstraint("max_users >= 0", name="ck_tenant_quotas_max_users_nonnegative"),
        sa.CheckConstraint("retention_days >= 0", name="ck_tenant_quotas_retention_days_nonnegative"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_quotas_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_tenant_quotas"),
    )

    op.create_table(
        "tenant_usage",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("documents_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("queries_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("storage_used_gb", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("api_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_response_time", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_rate", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("satisfaction_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("api_calls >= 0", name="ck_tenant_usage_api_calls_nonnegative"),
        sa.CheckConstraint("documents_count >= 0", name="ck_tenant_usage_documents_count_nonnegative"),
        sa.CheckConstraint("queries_count >= 0", name="ck_tenant_usage_queries_count_nonnegative"),
        sa.CheckConstraint("storage_used_gb >= 0", name="ck_tenant_usage_storage_used_nonnegative"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_usage_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "usage_date", name="pk_tenant_usage"),
    )

    op.create_table(
        "tenant_audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_audit_logs_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_audit_logs"),
    )
    op.create_index(
        "ix_tenant_audit_logs_tenant_created",
        "tenant_audit_logs",
        ["tenant_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "tenant_api_keys",
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_api_keys_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["tenant_users.user_id"],
            name="fk_tenant_api_keys_user_id_tenant_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("key_id", name="pk_tenant_api_keys"),
    )
    op.create_index("ix_tenant_api_keys_key_hash", "tenant_api_keys", ["key_hash"], unique=False)
    op.create_index("ix_tenant_api_keys_tenant_id", "tenant_api_keys", ["tenant_id"], unique=False)

    op.create_table(
        "tenant_sessions",
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_sessions_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["tenant_users.user_id"],
            name="fk_tenant_sessions_user_id_tenant_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_tenant_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_tenant_sessions_token_hash"),
    )
    op.create_index("ix_tenant_sessions_expires_at", "tenant_sessions", ["expires_at"], unique=False)
    op.create_index(
        "ix_tenant_sessions_tenant_user",
        "tenant_sessions",
        ["tenant_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_sessions_tenant_user", table_name="tenant_sessions")
    op.drop_index("ix_tenant_sessions_expires_at", table_name="tenant_sessions")
    op.drop_table("tenant_sessions")

    op.drop_index("ix_tenant_api_keys_tenant_id", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_key_hash", table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")

    op.drop_index("ix_tenant_audit_logs_tenant_created", table_name="tenant_audit_logs")
    op.drop_table("tenant_audit_logs")
    op.drop_table("tenant_usage")
    op.drop_table("tenant_quotas")

    op.drop_index("ix_tenant_users_tenant_id", table_name="tenant_users")
    op.drop_table("tenant_users")
    op.drop_table("tenants")
