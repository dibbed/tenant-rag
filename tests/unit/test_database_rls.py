"""Security contract tests for PostgreSQL row-level tenant isolation."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

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

FORCED_RLS_TABLES = (
    "tenants",
    "tenant_users",
    "tenant_quotas",
    "tenant_usage",
    "tenant_audit_logs",
)


def _offline_sql() -> str:
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), stdout=output)
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    command.upgrade(config, "head", sql=True)
    return output.getvalue()


def test_rls_migration_is_current_head() -> None:
    scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert scripts.get_heads() == ["phase5_0003"]


def test_all_tenant_tables_enable_row_level_security() -> None:
    sql = _offline_sql()
    for table in TENANT_TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql


def test_non_bootstrap_tables_force_owner_through_rls() -> None:
    sql = _offline_sql()
    for table in FORCED_RLS_TABLES:
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in sql


def test_rls_policy_checks_both_existing_and_new_rows() -> None:
    sql = _offline_sql()
    assert "pg_catalog.current_setting('app.tenant_id', true)" in sql
    for table in TENANT_TABLES:
        assert f"CREATE POLICY tenant_isolation ON public.{table}" in sql
        policy_start = sql.index(f"CREATE POLICY tenant_isolation ON public.{table}")
        policy_sql = sql[policy_start : policy_start + 700]
        assert "USING" in policy_sql
        assert "WITH CHECK" in policy_sql





def test_rls_policy_supports_explicit_system_admin_context() -> None:
    sql = _offline_sql()
    assert "pg_catalog.current_setting('app.is_system_admin', true) = 'true'" in sql


def test_auth_bootstrap_functions_are_security_definer_and_not_public() -> None:
    sql = _offline_sql()

    assert "CREATE FUNCTION public.lookup_api_key_auth" in sql
    assert "CREATE FUNCTION public.lookup_session_auth" in sql
    assert sql.count("SECURITY DEFINER") >= 2
    assert sql.count("SET search_path = pg_catalog, pg_temp") >= 2
    assert (
        "REVOKE ALL ON FUNCTION public.lookup_api_key_auth(text) FROM PUBLIC"
        in sql
    )
    assert (
        "REVOKE ALL ON FUNCTION public.lookup_session_auth(text) FROM PUBLIC"
        in sql
    )
