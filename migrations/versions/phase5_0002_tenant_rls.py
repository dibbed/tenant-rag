"""Enforce tenant row-level security and auth bootstrap functions.

Revision ID: phase5_0002
Revises: phase5_0001
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op

revision = "phase5_0002"
down_revision = "phase5_0001"
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

FORCED_RLS_TABLES = (
    "tenants",
    "tenant_users",
    "tenant_quotas",
    "tenant_usage",
    "tenant_audit_logs",
)

_POLICY_EXPR = (
    "tenant_id = pg_catalog.current_setting('app.tenant_id', true)"
)


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            " ".join(
                (
                    f"CREATE POLICY tenant_isolation ON public.{table}",
                    f"USING ({_POLICY_EXPR})",
                    f"WITH CHECK ({_POLICY_EXPR})",
                )
            )
        )

    # Authentication bootstrap functions below execute as the migration/table
    # owner so these two tables cannot FORCE owner participation in RLS.
    # Normal runtime roles are still subject to their RLS policies.
    for table in FORCED_RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE FUNCTION public.lookup_api_key_auth(p_key_id text)
        RETURNS TABLE (
            key_id text,
            tenant_id text,
            user_id text,
            name text,
            key_hash text,
            key_prefix text,
            permissions jsonb,
            created_at timestamptz,
            expires_at timestamptz,
            last_used_at timestamptz,
            is_active boolean
        )
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = pg_catalog, pg_temp
        AS $function$
            SELECT
                k.key_id,
                k.tenant_id,
                k.user_id,
                k.name,
                k.key_hash,
                k.key_prefix,
                k.permissions,
                k.created_at,
                k.expires_at,
                k.last_used_at,
                k.is_active
            FROM public.tenant_api_keys AS k
            WHERE k.key_id = p_key_id
            LIMIT 1
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.lookup_api_key_auth(text) FROM PUBLIC"
    )

    op.execute(
        """
        CREATE FUNCTION public.lookup_session_auth(p_token_hash text)
        RETURNS TABLE (
            session_id text,
            tenant_id text,
            user_id text,
            created_at timestamptz,
            expires_at timestamptz,
            last_used_at timestamptz,
            revoked_at timestamptz,
            ip_address text,
            user_agent text
        )
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = pg_catalog, pg_temp
        AS $function$
            SELECT
                s.session_id,
                s.tenant_id,
                s.user_id,
                s.created_at,
                s.expires_at,
                s.last_used_at,
                s.revoked_at,
                s.ip_address,
                s.user_agent
            FROM public.tenant_sessions AS s
            WHERE s.token_hash = p_token_hash
            LIMIT 1
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.lookup_session_auth(text) FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.lookup_session_auth(text)")
    op.execute("DROP FUNCTION IF EXISTS public.lookup_api_key_auth(text)")

    for table in reversed(TENANT_TABLES):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation ON public.{table}"
        )
        if table in FORCED_RLS_TABLES:
            op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
