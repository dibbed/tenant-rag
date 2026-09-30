"""Add explicit system-admin RLS context.

Revision ID: phase5_0003
Revises: phase5_0002
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op

revision = "phase5_0003"
down_revision = "phase5_0002"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "tenants",
    "tenant_users",
    "tenant_api_keys",
    "tenant_quotas",
    "tenant_usage",
    "tenant_audit_logs",
    "tenant_sessions",
)

_TENANT_ONLY_EXPR = "tenant_id = pg_catalog.current_setting('app.tenant_id', true)"
_ADMIN_EXPR = "pg_catalog.current_setting('app.is_system_admin', true) = 'true'"
_POLICY_EXPR = f"({_TENANT_ONLY_EXPR}) OR ({_ADMIN_EXPR})"


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY tenant_isolation ON public.{table}")
        op.execute(
            " ".join(
                (
                    f"CREATE POLICY tenant_isolation ON public.{table}",
                    f"USING ({_POLICY_EXPR})",
                    f"WITH CHECK ({_POLICY_EXPR})",
                )
            )
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY tenant_isolation ON public.{table}")
        op.execute(
            " ".join(
                (
                    f"CREATE POLICY tenant_isolation ON public.{table}",
                    f"USING ({_TENANT_ONLY_EXPR})",
                    f"WITH CHECK ({_TENANT_ONLY_EXPR})",
                )
            )
        )
