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
        connect_args={"server_settings": {"app.is_system_admin": "true"}},
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
        await connection.execute(
            text(
                f"""
                GRANT EXECUTE
                ON FUNCTION public.list_tenant_ids_admin(boolean)
                TO {RUNTIME_ROLE}
                """
            )
        )
        await connection.execute(
            text(
                f"""
                GRANT EXECUTE
                ON FUNCTION public.deactivate_expired_api_keys_admin(timestamptz)
                TO {RUNTIME_ROLE}
                """
            )
        )
        await connection.execute(
            text(
                f"""
                GRANT EXECUTE
                ON FUNCTION public.delete_expired_sessions_admin(timestamptz)
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
                        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
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
        assert all(row.relforcerowsecurity for row in rows)
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


@pytest.mark.asyncio
async def test_cross_tenant_rls_update() -> None:
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
                text("SELECT pg_catalog.set_config('app.is_system_admin', 'false', true)")
            )
            await connection.execute(
                text("SELECT pg_catalog.set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": tenant_a},
            )
            result = await connection.execute(
                text("UPDATE public.tenants SET name = 'hacked' WHERE tenant_id = :tenant_b"),
                {"tenant_b": tenant_b},
            )
            assert result.rowcount == 0

        async with engine.connect() as connection:
            name = await connection.scalar(
                text("SELECT name FROM public.tenants WHERE tenant_id = :tenant_b"),
                {"tenant_b": tenant_b},
            )
            assert name == "Tenant B"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_tenant_rls_delete() -> None:
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
                text("SELECT pg_catalog.set_config('app.is_system_admin', 'false', true)")
            )
            await connection.execute(
                text("SELECT pg_catalog.set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": tenant_a},
            )
            result = await connection.execute(
                text("DELETE FROM public.tenants WHERE tenant_id = :tenant_b"),
                {"tenant_b": tenant_b},
            )
            assert result.rowcount == 0

        async with engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT count(*) FROM public.tenants WHERE tenant_id = :tenant_b"),
                {"tenant_b": tenant_b},
            )
            assert exists == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rls_blocks_unscoped_repository_query() -> None:
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
                text("SELECT pg_catalog.set_config('app.is_system_admin', 'false', true)")
            )
            await connection.execute(
                text("SELECT pg_catalog.set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": tenant_a},
            )
            count = await connection.scalar(
                text(
                    "SELECT count(*) FROM public.tenants WHERE tenant_id IN (:tenant_a, :tenant_b)"
                ),
                {"tenant_a": tenant_a, "tenant_b": tenant_b},
            )
            assert count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_cannot_forge_system_admin_context() -> None:
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
                text("SELECT pg_catalog.set_config('app.is_system_admin', 'true', true)")
            )
            rows = (
                await connection.execute(
                    text(
                        "SELECT tenant_id FROM public.tenants WHERE tenant_id IN (:a, :b) ORDER BY tenant_id"
                    ),
                    {"a": tenant_a, "b": tenant_b},
                )
            ).scalars().all()
            assert rows == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_uses_narrow_system_function_for_cross_tenant_listing() -> None:
    engine = _engine()
    tenant_a = f"tenant_{uuid.uuid4().hex}"
    tenant_b = f"tenant_{uuid.uuid4().hex}"
    try:
        await _provision_runtime_role(engine)
        await _seed_tenant(engine, tenant_a, "Tenant A")
        await _seed_tenant(engine, tenant_b, "Tenant B")

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT tenant_id
                        FROM public.list_tenant_ids_admin(false)
                        WHERE tenant_id IN (:a, :b)
                        ORDER BY tenant_id
                        """
                    ),
                    {"a": tenant_a, "b": tenant_b},
                )
            ).scalars().all()
            assert sorted(rows) == sorted([tenant_a, tenant_b])
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_create_rollback() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    try:
        with pytest.raises(RuntimeError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO public.tenants (tenant_id, name, status, tier, plan) VALUES (:t, 'Rollback', 'active', 'free', 'trial')"
                    ),
                    {"t": tenant_id},
                )
                raise RuntimeError("forced transaction failure")

        async with engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM public.tenants WHERE tenant_id = :t"),
                {"t": tenant_id},
            )
            assert count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_duplicate_user() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    user_id_1 = f"user_{uuid.uuid4().hex}"
    user_id_2 = f"user_{uuid.uuid4().hex}"
    try:
        await _seed_tenant(engine, tenant_id, "User Tenant")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_users (user_id, tenant_id, username, email, role, permissions)
                    VALUES (:u, :t, 'duplicate_user', 'u1@example.com', 'user', '[]'::jsonb)
                    """
                ),
                {"u": user_id_1, "t": tenant_id},
            )

        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO public.tenant_users (user_id, tenant_id, username, email, role, permissions)
                        VALUES (:u, :t, 'duplicate_user', 'u2@example.com', 'user', '[]'::jsonb)
                        """
                    ),
                    {"u": user_id_2, "t": tenant_id},
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_quota_concurrent_limit() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    try:
        await _seed_tenant(engine, tenant_id, "Quota Tenant")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_quotas (tenant_id, max_users, max_documents, max_storage_gb, max_queries_per_day, features)
                    VALUES (:t, 10, 100, 10.0, 1000, '{}'::jsonb)
                    """
                ),
                {"t": tenant_id},
            )
            quota_row = (
                await connection.execute(
                    text("SELECT * FROM public.tenant_quotas WHERE tenant_id = :t FOR UPDATE"),
                    {"t": tenant_id},
                )
            ).mappings().one()
            assert quota_row["max_queries_per_day"] == 1000
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_usage_atomic_increment() -> None:
    from datetime import datetime, timezone

    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    today = datetime.now(timezone.utc).date()
    try:
        await _seed_tenant(engine, tenant_id, "Usage Tenant")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_usage (tenant_id, usage_date, queries_count, documents_count, storage_used_gb, api_calls)
                    VALUES (:t, :d, 1, 0, 0.0, 0)
                    ON CONFLICT (tenant_id, usage_date) DO UPDATE
                    SET queries_count = public.tenant_usage.queries_count + EXCLUDED.queries_count
                    """
                ),
                {"t": tenant_id, "d": today},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_usage (tenant_id, usage_date, queries_count, documents_count, storage_used_gb, api_calls)
                    VALUES (:t, :d, 5, 0, 0.0, 0)
                    ON CONFLICT (tenant_id, usage_date) DO UPDATE
                    SET queries_count = public.tenant_usage.queries_count + EXCLUDED.queries_count
                    """
                ),
                {"t": tenant_id, "d": today},
            )

        async with engine.connect() as connection:
            count = await connection.scalar(
                text(
                    "SELECT queries_count FROM public.tenant_usage WHERE tenant_id = :t AND usage_date = :d"
                ),
                {"t": tenant_id, "d": today},
            )
            assert count == 6
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_key_multi_worker_revocation() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    user_id = f"user_{uuid.uuid4().hex}"
    key_id = f"key_{uuid.uuid4().hex}"
    try:
        await _provision_runtime_role(engine)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO public.tenants (tenant_id, name, status, tier, plan) VALUES (:t, 'Key Tenant', 'active', 'free', 'trial')"
                ),
                {"t": tenant_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO public.tenant_users (user_id, tenant_id, username, email, role, permissions) VALUES (:u, :t, 'u', 'u@test.local', 'user', '[]'::jsonb)"
                ),
                {"u": user_id, "t": tenant_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_api_keys (key_id, tenant_id, user_id, name, key_hash, key_prefix, permissions, is_active)
                    VALUES (:k, :t, :u, 'worker-key', 'hash123', 'pfx', '[]'::jsonb, true)
                    """
                ),
                {"k": key_id, "t": tenant_id, "u": user_id},
            )

        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE public.tenant_api_keys SET is_active = false WHERE key_id = :k"),
                {"k": key_id},
            )

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            key_row = (
                await connection.execute(
                    text("SELECT * FROM public.lookup_api_key_auth(:k)"),
                    {"k": key_id},
                )
            ).mappings().first()
            assert key_row is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_validate_cross_worker() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    user_id = f"user_{uuid.uuid4().hex}"
    session_id = f"sess_{uuid.uuid4().hex}"
    token_hash = uuid.uuid4().hex + uuid.uuid4().hex
    try:
        await _provision_runtime_role(engine)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO public.tenants (tenant_id, name, status, tier, plan) VALUES (:t, 'Sess Tenant', 'active', 'free', 'trial')"
                ),
                {"t": tenant_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO public.tenant_users (user_id, tenant_id, username, email, role, permissions) VALUES (:u, :t, 'u', 'u@sess.local', 'user', '[]'::jsonb)"
                ),
                {"u": user_id, "t": tenant_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_sessions (session_id, tenant_id, user_id, token_hash, expires_at)
                    VALUES (:s, :t, :u, :th, now() + interval '1 hour')
                    """
                ),
                {"s": session_id, "t": tenant_id, "u": user_id, "th": token_hash},
            )

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            session_row = (
                await connection.execute(
                    text("SELECT * FROM public.lookup_session_auth(:th)"),
                    {"th": token_hash},
                )
            ).mappings().first()
            assert session_row is not None
            assert session_row["session_id"] == session_id
            assert session_row["tenant_id"] == tenant_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_logout_cross_worker() -> None:
    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    user_id = f"user_{uuid.uuid4().hex}"
    session_id = f"sess_{uuid.uuid4().hex}"
    token_hash = uuid.uuid4().hex + uuid.uuid4().hex
    try:
        await _provision_runtime_role(engine)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO public.tenants (tenant_id, name, status, tier, plan) VALUES (:t, 'Logout Tenant', 'active', 'free', 'trial')"
                ),
                {"t": tenant_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO public.tenant_users (user_id, tenant_id, username, email, role, permissions) VALUES (:u, :t, 'u', 'u@logout.local', 'user', '[]'::jsonb)"
                ),
                {"u": user_id, "t": tenant_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO public.tenant_sessions (session_id, tenant_id, user_id, token_hash, expires_at)
                    VALUES (:s, :t, :u, :th, now() + interval '1 hour')
                    """
                ),
                {"s": session_id, "t": tenant_id, "u": user_id, "th": token_hash},
            )

        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE public.tenant_sessions SET revoked_at = now() WHERE session_id = :s"),
                {"s": session_id},
            )

        async with engine.begin() as connection:
            await connection.execute(text(f"SET LOCAL ROLE {RUNTIME_ROLE}"))
            session_row = (
                await connection.execute(
                    text("SELECT * FROM public.lookup_session_auth(:th)"),
                    {"th": token_hash},
                )
            ).mappings().first()
            assert session_row is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_migration_failure_rollback() -> None:
    from ragbot.database.engine import DatabaseRuntime
    from ragbot.database.legacy_migration import LegacySnapshot, _insert_snapshot
    from ragbot.multi_tenant.models import TenantConfig, TenantPlan, TenantTier

    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    snapshot = LegacySnapshot(
        tenants=[
            TenantConfig(
                tenant_id=tenant_id,
                name="Rollback Mig Tenant",
                tier=TenantTier.FREE,
                plan=TenantPlan.TRIAL,
            )
        ]
    )
    runtime = DatabaseRuntime(OWNER_URL)
    try:
        with pytest.raises(RuntimeError):
            async with runtime.session_factory.begin() as session:
                await _insert_snapshot(session, snapshot)
                raise RuntimeError("simulated migration failure mid-transaction")

        async with engine.connect() as connection:
            count = await connection.scalar(
                text("SELECT count(*) FROM public.tenants WHERE tenant_id = :t"),
                {"t": tenant_id},
            )
            assert count == 0
    finally:
        await runtime.dispose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_migration_refuses_nonempty_target() -> None:
    from ragbot.database.engine import DatabaseRuntime
    from ragbot.database.legacy_migration import (
        LegacyMigrationError,
        _ensure_empty_target,
    )

    engine = _engine()
    tenant_id = f"tenant_{uuid.uuid4().hex}"
    try:
        await _seed_tenant(engine, tenant_id, "Existing Tenant")
        runtime = DatabaseRuntime(OWNER_URL)
        try:
            async with runtime.session_factory.begin() as session:
                with pytest.raises(LegacyMigrationError, match="must be empty"):
                    await _ensure_empty_target(session)
        finally:
            await runtime.dispose()
    finally:
        await engine.dispose()
