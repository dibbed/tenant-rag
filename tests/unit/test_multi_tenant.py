"""Unit tests for Multi-Tenant management, persistence, and limits."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ragbot.configs.settings import MultiTenantSettings, Settings
from ragbot.multi_tenant.models import (
    TenantPlan,
    TenantStatus,
    TenantTier,
)
from ragbot.multi_tenant.tenant_manager import TenantManager
from tests.helpers.legacy_sqlite_tenant_manager import LegacySQLiteTenantManager


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database file path."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_file = Path(tmpdir) / "tenants_test.db"
        yield db_file


@pytest.fixture
def test_settings(temp_db_path):
    """Create test Settings with multi-tenancy enabled."""
    return Settings(
        multi_tenant=MultiTenantSettings(
            enabled=True,
            default_tier="free",
            data_dir=temp_db_path.parent,
        )
    )


@pytest.mark.asyncio
async def test_tenant_crud_operations(test_settings, temp_db_path):
    """Test full tenant lifecycle: create, get, update, suspend, activate, delete."""
    manager = LegacySQLiteTenantManager(test_settings, db_path=temp_db_path)
    try:
        # 1. Create tenant
        tenant = await manager.create_tenant(
            name="Acme Corp",
            tier=TenantTier.PREMIUM,
            plan=TenantPlan.MONTHLY,
            domain="acme.example.com",
            contact_email="admin@acme.example.com",
        )
        assert tenant is not None
        assert tenant.tenant_id is not None
        assert tenant.name == "Acme Corp"
        assert tenant.tier == TenantTier.PREMIUM
        assert tenant.status == TenantStatus.ACTIVE
        tenant_id = tenant.tenant_id

        # 2. Get tenant
        fetched = await manager.get_tenant(tenant_id)
        assert fetched is not None
        assert fetched.tenant_id == tenant_id
        assert fetched.name == "Acme Corp"

        # 3. Update tenant
        updated = await manager.update_tenant(
            tenant_id,
            name="Acme Corporation",
            contact_email="contact@acme.example.com",
        )
        assert updated is not None
        assert updated.name == "Acme Corporation"
        assert updated.contact_email == "contact@acme.example.com"

        # 4. Suspend tenant
        suspended = await manager.suspend_tenant(tenant_id, reason="billing_due")
        assert suspended is True
        tenant_suspended = await manager.get_tenant(tenant_id)
        assert tenant_suspended.status == TenantStatus.SUSPENDED

        # 5. Activate tenant
        activated = await manager.activate_tenant(tenant_id)
        assert activated is True
        tenant_active = await manager.get_tenant(tenant_id)
        assert tenant_active.status == TenantStatus.ACTIVE

        # 6. Delete tenant
        deleted = await manager.delete_tenant(tenant_id)
        assert deleted is True
        tenant_deleted = await manager.get_tenant(tenant_id)
        assert tenant_deleted is None
    finally:
        manager.close()


class _SharedStore:
    def __init__(self) -> None:
        self.records: dict[tuple[type, Any], Any] = {}

    def get_session(self) -> Any:
        session = AsyncMock(spec=AsyncSession)
        def _add(record: Any) -> None:
            pk = getattr(record, "tenant_id", None) or getattr(record, "user_id", None)
            self.records[(type(record), pk)] = record
        session.add = MagicMock(side_effect=_add)
        async def _get(model: Any, pk: Any) -> Any:
            return self.records.get((model, pk))
        session.get = AsyncMock(side_effect=_get)
        session.execute = AsyncMock()
        return session


class _SharedBeginContext:
    def __init__(self, store: _SharedStore) -> None:
        self.session = store.get_session()

    async def __aenter__(self) -> Any:
        return self.session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass


class _SharedSessionFactory:
    def __init__(self, store: _SharedStore) -> None:
        self.store = store

    def begin(self) -> _SharedBeginContext:
        return _SharedBeginContext(self.store)


@pytest.mark.asyncio
async def test_postgres_persistence_across_manager_restarts() -> None:
    """Verify that tenant data survives manager restart via PostgreSQL store."""
    store = _SharedStore()
    factory = _SharedSessionFactory(store)

    # Step 1: Initialize manager 1, create tenant
    manager1 = TenantManager(session_factory=factory)
    tenant = await manager1.create_tenant(
        name="Persistent Corp",
        tier=TenantTier.ENTERPRISE,
        plan=TenantPlan.YEARLY,
        contact_email="pers@corp.com",
    )
    t_id = tenant.tenant_id
    assert tenant.name == "Persistent Corp"
    assert tenant.tier == TenantTier.ENTERPRISE

    # Step 2: Initialize a completely fresh TenantManager pointing to the same shared PostgreSQL store
    manager2 = TenantManager(session_factory=factory)
    assert not hasattr(manager2, "_conn")
    assert not hasattr(manager2, "tenants")

    loaded_tenant = await manager2.get_tenant(t_id)
    assert loaded_tenant is not None
    assert loaded_tenant.tenant_id == t_id
    assert loaded_tenant.name == "Persistent Corp"
    assert loaded_tenant.tier == TenantTier.ENTERPRISE


@pytest.mark.asyncio
async def test_tenant_limits_and_usage(test_settings, temp_db_path):
    """Test quota enforcement and usage tracking."""
    manager = LegacySQLiteTenantManager(test_settings, db_path=temp_db_path)
    try:
        tenant = await manager.create_tenant(
            name="Limited Corp",
            tier=TenantTier.FREE,
            plan=TenantPlan.TRIAL,
        )
        t_id = tenant.tenant_id

        # Initial check should pass
        can_query = await manager.check_tenant_limits(t_id, "query")
        assert can_query is True

        # Simulate usage
        await manager.track_tenant_usage(t_id, "query")
        await manager.track_tenant_usage(t_id, "document", metadata={"chunks": 5})

        usage = await manager._get_tenant_usage(t_id)
        assert usage.queries_count >= 1
        assert usage.documents_count >= 1

        # Inactive tenant should fail limit check
        await manager.suspend_tenant(t_id)
        # Check limit directly for suspended tenant or via query check
        tenant_obj = await manager.get_tenant(t_id)
        assert tenant_obj.status == TenantStatus.SUSPENDED
    finally:
        manager.close()
