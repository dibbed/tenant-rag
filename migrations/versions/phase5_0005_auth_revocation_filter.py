"""Filter revoked credentials from authentication bootstrap functions.

Revision ID: phase5_0005
Revises: phase5_0004
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op

revision = "phase5_0005"
down_revision = "phase5_0004"
branch_labels = None
depends_on = None


def _replace_api_key_lookup(*, active_only: bool) -> None:
    active_filter = "AND k.is_active IS TRUE" if active_only else ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.lookup_api_key_auth(p_key_id text)
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
        SET "app.is_system_admin" = 'true'
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
              {active_filter}
            LIMIT 1
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.lookup_api_key_auth(text) FROM PUBLIC"
    )


def _replace_session_lookup(*, unrevoked_only: bool) -> None:
    revoked_filter = "AND s.revoked_at IS NULL" if unrevoked_only else ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.lookup_session_auth(p_token_hash text)
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
        SET "app.is_system_admin" = 'true'
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
              {revoked_filter}
            LIMIT 1
        $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.lookup_session_auth(text) FROM PUBLIC"
    )


def upgrade() -> None:
    _replace_api_key_lookup(active_only=True)
    _replace_session_lookup(unrevoked_only=True)


def downgrade() -> None:
    _replace_session_lookup(unrevoked_only=False)
    _replace_api_key_lookup(active_only=False)
