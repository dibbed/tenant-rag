"""Schema contract tests for the Phase 5 PostgreSQL tenant model."""

from __future__ import annotations

from sqlalchemy import UniqueConstraint

from ragbot.database.models import Base

EXPECTED_TABLES = {
    "tenants",
    "tenant_users",
    "tenant_api_keys",
    "tenant_quotas",
    "tenant_usage",
    "tenant_audit_logs",
    "tenant_sessions",
}


def test_phase5_metadata_contains_required_tenant_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_tenant_user_identity_is_unique_within_tenant() -> None:
    table = Base.metadata.tables["tenant_users"]
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("tenant_id", "username") in unique_sets
    assert ("tenant_id", "email") in unique_sets


def test_usage_has_one_row_per_tenant_per_day() -> None:
    table = Base.metadata.tables["tenant_usage"]
    assert tuple(column.name for column in table.primary_key.columns) == (
        "tenant_id",
        "usage_date",
    )


def test_sessions_store_only_a_unique_token_hash() -> None:
    table = Base.metadata.tables["tenant_sessions"]
    assert "token_hash" in table.c
    assert table.c.token_hash.unique is True
    assert "token" not in table.c


def test_api_keys_reference_tenant_users() -> None:
    table = Base.metadata.tables["tenant_api_keys"]
    targets = {foreign_key.target_fullname for foreign_key in table.c.user_id.foreign_keys}
    assert targets == {"tenant_users.user_id"}


def test_tenant_timestamps_are_timezone_aware() -> None:
    table = Base.metadata.tables["tenants"]
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True
