"""Tests for the Phase 5 async PostgreSQL runtime foundation."""

from __future__ import annotations

import pytest

from ragbot.database.engine import DatabaseRuntime, normalize_async_postgres_url


def test_normalize_async_postgres_url_accepts_standard_postgres_url() -> None:
    assert (
        normalize_async_postgres_url("postgresql://user:pass@localhost/tenantrag")
        == "postgresql+asyncpg://user:pass@localhost/tenantrag"
    )


def test_normalize_async_postgres_url_preserves_asyncpg_url() -> None:
    url = "postgresql+asyncpg://user:pass@localhost/tenantrag"
    assert normalize_async_postgres_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///./data/tenants.db",
        "sqlite+aiosqlite:///:memory:",
        "mysql://user:pass@localhost/db",
        "",
    ],
)
def test_normalize_async_postgres_url_rejects_non_postgres_urls(url: str) -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_async_postgres_url(url)


def test_database_runtime_builds_async_session_factory_without_connecting() -> None:
    runtime = DatabaseRuntime(
        "postgresql://user:pass@localhost/tenantrag",
        echo=True,
        pool_size=7,
        max_overflow=3,
    )

    try:
        assert runtime.engine.url.drivername == "postgresql+asyncpg"
        assert runtime.session_factory.kw["expire_on_commit"] is False
        assert runtime.session_factory.kw["autoflush"] is True
    finally:
        runtime.engine.sync_engine.dispose(close=False)
