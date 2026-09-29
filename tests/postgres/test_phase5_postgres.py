"""Real PostgreSQL verification for Phase 5 tenant persistence.

These tests are intentionally kept out of the normal local unit-test dependency
path. The dedicated CI PostgreSQL job sets TEST_DATABASE_URL and runs Alembic
before executing this module.
"""

from __future__ import annotations

import os
import uuid

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from ragbot.database.engine import normalize_async_postgres_url

OWNER_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
RUNTIME_ROLE = "tenantrag_app_ci"

pytestmark = pytest.mark.skipif(
    not OWNER_URL,
    reason="TEST_DATABASE_URL is required for real PostgreSQL verification",
)


def _engine() -> AsyncEngine:
    return create_async_engine(
        normalize_async_postgres_url(OWNER_URL),
        poolclass=NullPool,
    )


async def _provision_runtime_role(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_catalog.pg_roles
                        WHERE rolname = '{RUNTIME_ROLE}'
                    ) THEN
                        CREATE ROLE {RUNTIME_ROLE}
                            NOLOGIN
                            NOSUPERUSER
                            NOCREATEDB
                            NOCREATEROLE
                            NOINHERIT
                            NOBYPASSRLS;
                    END IF;
                END
                $$;
                """
            )
        )
        await connection.execute(
            text(
                f"""
                ALTER ROLE {RUNTIME_ROLE}
                    NOLOGIN
                    NOSUPERUSER
                    NOCREATEDB
                    NOCREATEROLE
                    NOINHERIT
                    NOBYPASSRLS
                """
            )
        )
        await connection.execute(
            text(f"GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE}")
        )
        await connection.execute(
            text(
                f"""
                GRANT SELECT, INSERT, UPDATE, DELETE
                ON ALL TABLES IN SCHEMA public
                TO {RUNTIME_ROLE}
                """
            )
        )
        await connection.execute(
            text(
                f"""
                GRANT USAGE, SELECT
                ON ALL SEQUENCES IN SCHEMA public
                TO {RUNTIME_ROLE}
                """
            )
        )
        await connection.execute(
            text(
                f"""
                GRANT EXECUTE
                ON FUNCTION public.lookup_api_key_auth(text)
                TO {RUNTIME_ROLE}
                """
            )
        )
        await connection.execute(
            text(
                f"""
                GRANT EXECUTE
                ON FUNCTION public.lookup_session_auth(text)
                TO {RUNTIME_ROLE}
                """
            )
        )


async def _seed_tenant(engine: AsyncEngine, tenant_id: str, name: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO public.tenants (
                    tenant_id, name, status, tier, plan
                ) VALUES (
                    :tenant_id, :name, 'active', 'free', 'trial'
                )
                """
            ),
            {"tenant_id": tenant_id, "name": name},
        )


@pytest.mark.asyncio
async def test_alembic_database_is_at_repository_head() -> None:
    engine = _engine()
    try:
        config = Config("alembic.ini")
        scripts = ScriptDirectory.from_config(config)
        expected_head = scripts.get_current_head()

        async with engine.connect() as connection:
            actual_head = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )

        assert actual_head == expected_head
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_role_is_not_privileged_to_bypass_rls() -> None:
    engine = _engine()
    try:
        await _provision_runtime_role(engine)
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
                        FROM pg_catalog.pg_roles
                        WHERE rolname = :role
                        """
                    ),
                    {"role": RUNTIME_ROLE},
                )
            ).one()

        assert row.rolsuper is False
        assert row.rolcreatedb is False
        assert row.rolcreaterole is False
        assert row.rolbypassrls is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_all_tenant_tables_have_rls_enabled() -> None:
    engine = _engine()
    try:
        expected = {
            "tenants",
            "tenant_users",
            "tenant_api_keys",
            "tenant_quotas",
            "tenant_usage",
            "tenant_audit_logs",
            "tenant_sessions",
        }
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT c.relname, c.relrowsecurity
                        FROM pg_catalog.pg_class AS c
                        JOIN pg_catalog.pg_namespace AS n
                          ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relname IN (
                              'tenants',
                              'tenant_users',
                              'tenant_api_keys',
                              'tenant_quotas',
                              'tenant_usage',
                              'tenant_audit_logs',
                              'tenant_sessions'
                          )
                        """
                    )
                )
            ).all()

        assert {row.relname for row in rows} == expected
        assert all(row.relrowsecurity for row in rows)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_role_is_default_deny_without_tenant_context() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    try:
        await _provision_runtime_role(engine)
        await _seed_tenant(engine, tenant_id, "Default Deny")

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            count = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM public.tenants
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            )

        assert count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_context_limits_select_and_with_check_blocks_cross_tenant_insert() -> None:
    engine = _engine()
    tenant_a = f"tenant_{uuid.uuid4().hex}"
    tenant_b = f"tenant_{uuid.uuid4().hex}"
    try:
        await _provision_runtime_role(engine)
        await _seed_tenant(engine, tenant_a, "Tenant A")
        await _seed_tenant(engine, tenant_b, "Tenant B")

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            await connection.execute(
                text(
                    """
                    SELECT pg_catalog.set_config(
                        'app.is_system_admin', 'false', true
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    SELECT pg_catalog.set_config(
                        'app.tenant_id', :tenant_id, true
                    )
                    """
                ),
                {"tenant_id": tenant_a},
            )
            visible = (
                await connection.execute(
                    text(
                        """
                        SELECT tenant_id
                        FROM public.tenants
                        WHERE tenant_id IN (:tenant_a, :tenant_b)
                        ORDER BY tenant_id
                        """
                    ),
                    {"tenant_a": tenant_a, "tenant_b": tenant_b},
                )
            ).scalars().all()

        assert visible == [tenant_a]

        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
                await connection.execute(
                    text(
                        """
                        SELECT pg_catalog.set_config(
                            'app.is_system_admin', 'false', true
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        SELECT pg_catalog.set_config(
                            'app.tenant_id', :tenant_id, true
                        )
                        """
                    ),
                    {"tenant_id": tenant_a},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO public.tenants (
                            tenant_id, name, status, tier, plan
                        ) VALUES (
                            :tenant_id, 'Blocked', 'active', 'free', 'trial'
                        )
                        """
                    ),
                    {"tenant_id": f"tenant_{uuid.uuid4().hex}_other"},
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auth_bootstrap_functions_work_for_runtime_role_without_tenant_context() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    user_id = f"user_{uuid.uuid4().hex}"
    key_id = f"key_{uuid.uuid4().hex}"
    token_hash = uuid.uuid4().hex + uuid.uuid4().hex
    try:
        await _provision_runtime_role(engine)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenants (
                        tenant_id, name, status, tier, plan
                    ) VALUES (
                        :tenant_id, 'Auth Tenant', 'active', 'free', 'trial'
                    )
                    """
                ),
                {"tenant_id": tenant_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_users (
                        user_id, tenant_id, username, email, role, permissions
                    ) VALUES (
                        :user_id, :tenant_id, 'api-user', :email, 'user',
                        '["api_access"]'::jsonb
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "email": f"{user_id}@example.test",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_api_keys (
                        key_id, tenant_id, user_id, name, key_hash, key_prefix,
                        permissions
                    ) VALUES (
                        :key_id, :tenant_id, :user_id, 'ci',
                        'scrypt$ci-test', 'rgb_ci_test',
                        '["api_access"]'::jsonb
                    )
                    """
                ),
                {
                    "key_id": key_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_sessions (
                        session_id, tenant_id, user_id, token_hash, expires_at
                    ) VALUES (
                        :session_id, :tenant_id, :user_id, :token_hash,
                        now() + interval '1 hour'
                    )
                    """
                ),
                {
                    "session_id": f"session_{uuid.uuid4().hex}",
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "token_hash": token_hash,
                },
            )

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            key_row = (
                await connection.execute(
                    text("SELECT * FROM public.lookup_api_key_auth(:key_id)"),
                    {"key_id": key_id},
                )
            ).mappings().one()
            session_row = (
                await connection.execute(
                    text(
                        "SELECT * FROM public.lookup_session_auth(:token_hash)"
                    ),
                    {"token_hash": token_hash},
                )
            ).mappings().one()

        assert key_row["tenant_id"] == tenant_id
        assert key_row["user_id"] == user_id
        assert session_row["tenant_id"] == tenant_id
        assert session_row["user_id"] == user_id
        assert "token_hash" not in session_row
    finally:
        await engine.dispose()
