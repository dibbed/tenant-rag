"""Alembic migration contract tests for the Phase 5 PostgreSQL schema."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]


def _config(*, stdout: StringIO | None = None, database_url: str | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"), stdout=stdout)
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_has_single_initial_head() -> None:
    scripts = ScriptDirectory.from_config(_config())
    assert scripts.get_heads() == ["phase5_0004"]


def test_alembic_offline_upgrade_emits_all_phase5_tables() -> None:
    output = StringIO()
    command.upgrade(
        _config(
            stdout=output,
            database_url="postgresql+asyncpg://tenant_rag:tenant_rag@localhost/tenant_rag",
        ),
        "head",
        sql=True,
    )
    sql = output.getvalue()

    for table in (
        "tenants",
        "tenant_users",
        "tenant_api_keys",
        "tenant_quotas",
        "tenant_usage",
        "tenant_audit_logs",
        "tenant_sessions",
    ):
        assert f"CREATE TABLE {table}" in sql
