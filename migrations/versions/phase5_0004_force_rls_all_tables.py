"""Harden forced RLS and add narrow cross-tenant system functions.

Revision ID: phase5_0004
Revises: phase5_0003
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op

revision = "phase5_0004"
down_revision = "phase5_0003"
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
_ADMIN_FLAG_EXPR = "pg_catalog.current_setting('app.is_system_admin', true) = 'true'"


def _owner_expr(table: str) -> str:
    return (
        "current_user = pg_catalog.pg_get_userbyid("
        "(SELECT c.relowner FROM pg_catalog.pg_class AS c "
        f"WHERE c.oid = pg_catalog.to_regclass('public.{table}')))"
    )


def _policy_expr(table: str) -> str:
    return (
        f"({_TENANT_ONLY_EXPR}) OR "
        f"(({_ADMIN_FLAG_EXPR}) AND ({_owner_expr(table)}))"
    )


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY tenant_isolation ON public.{table}")
        op.execute(
            " ".join(
                (
                    f"CREATE POLICY tenant_isolation ON public.{table}",
                    f"USING ({_policy_expr(table)})",
                    f"WITH CHECK ({_policy_expr(table)})",
                )
            )
        )
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")

    # Auth bootstrap functions need owner-scoped RLS access while executing as
    # SECURITY DEFINER. The owner check in the policy prevents a runtime role
    # from forging this access by setting the custom GUC itself.
    op.execute(
        'ALTER FUNCTION public.lookup_api_key_auth(text) '
        'SET "app.is_system_admin" = \'true\''
    )
    op.execute(
        'ALTER FUNCTION public.lookup_session_auth(text) '
        'SET "app.is_system_admin" = \'true\''
    )

    op.execute(
        """
        CREATE FUNCTION public.list_tenant_ids_admin(p_active_only boolean)
        RETURNS TABLE (tenant_id text)
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = pg_catalog, pg_temp
        SET "app.is_system_admin" = 'true'
        AS $function$
            SELECT t.tenant_id
            FROM public.tenants AS t
            WHERE (NOT p_active_only) OR t.status = 'active'
            ORDER BY t.created_at
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.list_tenant_ids_admin(boolean) FROM PUBLIC"
    )

    op.execute(
        """
        CREATE FUNCTION public.deactivate_expired_api_keys_admin(p_before timestamptz)
        RETURNS bigint
        LANGUAGE sql
        SECURITY DEFINER
        VOLATILE
        SET search_path = pg_catalog, pg_temp
        SET "app.is_system_admin" = 'true'
        AS $function$
            WITH updated AS (
                UPDATE public.tenant_api_keys
                SET is_active = false
                WHERE is_active IS TRUE
                  AND expires_at IS NOT NULL
                  AND expires_at <= p_before
                RETURNING 1
            )
            SELECT count(*)::bigint FROM updated
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "public.deactivate_expired_api_keys_admin(timestamptz) FROM PUBLIC"
    )

    op.execute(
        """
        CREATE FUNCTION public.delete_expired_sessions_admin(p_before timestamptz)
        RETURNS bigint
        LANGUAGE sql
        SECURITY DEFINER
        VOLATILE
        SET search_path = pg_catalog, pg_temp
        SET "app.is_system_admin" = 'true'
        AS $function$
            WITH deleted AS (
                DELETE FROM public.tenant_sessions
                WHERE expires_at <= p_before
                RETURNING 1
            )
            SELECT count(*)::bigint FROM deleted
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "public.delete_expired_sessions_admin(timestamptz) FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.delete_expired_sessions_admin(timestamptz)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS "
        "public.deactivate_expired_api_keys_admin(timestamptz)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.list_tenant_ids_admin(boolean)"
    )

    op.execute(
        'ALTER FUNCTION public.lookup_session_auth(text) RESET "app.is_system_admin"'
    )
    op.execute(
        'ALTER FUNCTION public.lookup_api_key_auth(text) RESET "app.is_system_admin"'
    )

    legacy_policy_expr = f"({_TENANT_ONLY_EXPR}) OR ({_ADMIN_FLAG_EXPR})"
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY tenant_isolation ON public.{table}")
        op.execute(
            " ".join(
                (
                    f"CREATE POLICY tenant_isolation ON public.{table}",
                    f"USING ({legacy_policy_expr})",
                    f"WITH CHECK ({legacy_policy_expr})",
                )
            )
        )

    op.execute("ALTER TABLE public.tenant_sessions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.tenant_api_keys NO FORCE ROW LEVEL SECURITY")
