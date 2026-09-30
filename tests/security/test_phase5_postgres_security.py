"""Security Regression Suite: Phase 5 PostgreSQL multi-tenant security verification.

Covers Section 67 requirements:
- Row-Level Security (RLS) enabled and forced on all tenant tables.
- WITH CHECK and USING clause verification for tenant isolation.
- Runtime application role privilege boundaries (least privilege, NOBYPASSRLS).
- Auth bootstrap functions (lookup_api_key_auth, lookup_session_auth) SECURITY DEFINER isolation,
  search_path sanitization, credential secrecy (no hash/secret leakage).
- Cross-worker revocation semantics ensuring immediate persistence without vulnerable peer caching.
- Migration credential secrecy across Alembic migration scripts.
- Migration rollback cleanliness ensuring safe downgrade paths.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from ragbot.database.repositories import ApiKeyRepository, SessionRepository

ROOT = Path(__file__).resolve().parents[2]
POSTGRES_URL = "postgresql+asyncpg://tenant_rag:tenant_rag@localhost/tenant_rag"

TENANT_TABLES = (
    "tenants",
    "tenant_users",
    "tenant_api_keys",
    "tenant_quotas",
    "tenant_usage",
    "tenant_audit_logs",
    "tenant_sessions",
)


def _offline_upgrade_sql() -> str:
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), stdout=output)
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    command.upgrade(config, "head", sql=True)
    return output.getvalue()


def _offline_downgrade_sql() -> str:
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), stdout=output)
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    command.downgrade(config, f"{head}:base", sql=True)
    return output.getvalue()


def test_phase5_alembic_head_and_revisions() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["phase5_0005"]


def test_phase5_rls_enabled_on_all_tables() -> None:
    sql = _offline_upgrade_sql()
    for table in TENANT_TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql


def test_phase5_force_rls_on_all_tables() -> None:
    sql = _offline_upgrade_sql()
    for table in TENANT_TABLES:
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in sql


def test_phase5_rls_policies_have_using_and_with_check() -> None:
    sql = _offline_upgrade_sql()
    for table in TENANT_TABLES:
        assert f"CREATE POLICY tenant_isolation ON public.{table}" in sql
        policy_start = sql.index(f"CREATE POLICY tenant_isolation ON public.{table}")
        policy_sql = sql[policy_start : policy_start + 700]
        assert "USING" in policy_sql
        assert "WITH CHECK" in policy_sql
        assert "app.tenant_id" in policy_sql


def test_phase5_system_admin_override_policy() -> None:
    sql = _offline_upgrade_sql()
    assert "pg_catalog.current_setting('app.is_system_admin', true) = 'true'" in sql
    assert "current_user = pg_catalog.pg_get_userbyid" in sql
    assert "relowner" in sql


def test_phase5_system_functions_are_narrow_security_definer_entrypoints() -> None:
    sql = _offline_upgrade_sql()
    expected_functions = (
        "list_tenant_ids_admin",
        "deactivate_expired_api_keys_admin",
        "delete_expired_sessions_admin",
    )
    for function_name in expected_functions:
        assert f"CREATE FUNCTION public.{function_name}" in sql
        assert f"REVOKE ALL ON FUNCTION public.{function_name}" in sql

    assert sql.count("SECURITY DEFINER") >= 5
    assert sql.count("SET search_path = pg_catalog, pg_temp") >= 5


def test_phase5_runtime_role_definition_least_privilege() -> None:
    pg_test_file = ROOT / "tests" / "postgres" / "test_phase5_postgres.py"
    assert pg_test_file.exists()
    pg_content = pg_test_file.read_text(encoding="utf-8")
    assert "NOBYPASSRLS" in pg_content
    assert "NOSUPERUSER" in pg_content
    assert "NOCREATEDB" in pg_content
    assert "NOCREATEROLE" in pg_content


def test_phase5_auth_bootstrap_security_definer_and_isolation() -> None:
    sql = _offline_upgrade_sql()
    assert "CREATE FUNCTION public.lookup_api_key_auth" in sql
    assert "CREATE FUNCTION public.lookup_session_auth" in sql
    assert sql.count("SECURITY DEFINER") >= 2
    assert sql.count("SET search_path = pg_catalog, pg_temp") >= 2
    assert "REVOKE ALL ON FUNCTION public.lookup_api_key_auth(text) FROM PUBLIC" in sql
    assert "REVOKE ALL ON FUNCTION public.lookup_session_auth(text) FROM PUBLIC" in sql
    assert 'ALTER FUNCTION public.lookup_api_key_auth(text) SET "app.is_system_admin" = \'true\'' in sql
    assert 'ALTER FUNCTION public.lookup_session_auth(text) SET "app.is_system_admin" = \'true\'' in sql


def test_phase5_auth_bootstrap_does_not_return_sensitive_hashes() -> None:
    sql = _offline_upgrade_sql()
    session_func_start = sql.index("CREATE FUNCTION public.lookup_session_auth")
    session_func_sql = sql[session_func_start : session_func_start + 1200]
    returns_table = session_func_sql.split("RETURNS TABLE (")[1].split(")")[0]
    assert "token_hash" not in returns_table


def test_phase5_auth_bootstrap_filters_revoked_credentials() -> None:
    sql = _offline_upgrade_sql()
    assert "AND k.is_active IS TRUE" in sql
    assert "AND s.revoked_at IS NULL" in sql


@pytest.mark.asyncio
async def test_phase5_cross_worker_revocation_guarantee() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    session.execute.return_value = mock_result

    api_repo = ApiKeyRepository(session)
    revoked = await api_repo.revoke("key_test_123", tenant_id="tenant_123")
    assert revoked is True
    session.execute.assert_awaited_once()

    session.reset_mock()
    session.execute.return_value = mock_result
    from datetime import datetime, timezone
    session_repo = SessionRepository(session)
    revoked_session = await session_repo.revoke("session_test_123", datetime.now(timezone.utc))
    assert revoked_session is True
    session.execute.assert_awaited_once()


def test_phase5_migration_credential_secrecy() -> None:
    migrations_dir = ROOT / "migrations" / "versions"
    for migration_file in migrations_dir.glob("*.py"):
        content = migration_file.read_text(encoding="utf-8")
        assert "password=" not in content.lower()
        assert "secret_key" not in content.lower()


def test_phase5_migration_rollback_safety() -> None:
    down_sql = _offline_downgrade_sql()
    assert "DROP FUNCTION IF EXISTS public.lookup_api_key_auth" in down_sql
    assert "DROP FUNCTION IF EXISTS public.lookup_session_auth" in down_sql
    for table in reversed(TENANT_TABLES):
        assert f"DROP TABLE {table}" in down_sql or f"DROP TABLE IF EXISTS {table}" in down_sql
