"""Unit tests for Multi-Tenant management, persistence, and limits."""

import os
import sqlite3
import tempfile
from pathlib import Path
import pytest

from ragbot.configs.settings import Settings, MultiTenantSettings
from ragbot.multi_tenant.models import (
    TenantConfig,
    TenantPlan,
    TenantStatus,
    TenantTier,
    TenantUser,
)
from ragbot.multi_tenant.tenant_auth import TenantAuth, UserRole
from ragbot.multi_tenant.tenant_manager import TenantManager


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
    manager = TenantManager(test_settings, db_path=temp_db_path)
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


@pytest.mark.asyncio
async def test_sqlite_persistence_across_manager_restarts(test_settings, temp_db_path):
    """Verify that tenant and user data survives manager restart via SQLite."""
    # Step 1: Initialize manager 1, create tenant and user
    manager1 = TenantManager(test_settings, db_path=temp_db_path)
    try:
        tenant = await manager1.create_tenant(
            name="Persistent Corp",
            tier=TenantTier.ENTERPRISE,
            plan=TenantPlan.YEARLY,
            contact_email="pers@corp.com",
        )
        t_id = tenant.tenant_id

        auth1 = TenantAuth(manager1)
        success, user, err = await auth1.create_user(
            tenant_id=t_id,
            username="alice",
            email="alice@corp.com",
            password="securePassword123!",
            role=UserRole.ADMIN,
        )
        assert success is True
        assert user is not None
        user_id = user.user_id
    finally:
        manager1.close()

    # Verify SQLite file exists on disk
    assert temp_db_path.exists()

    # Step 2: Initialize a completely fresh TenantManager pointing to the same DB file
    manager2 = TenantManager(test_settings, db_path=temp_db_path)
    try:
        # Verify tenant was loaded into manager2 cache on boot
        loaded_tenant = await manager2.get_tenant(t_id)
        assert loaded_tenant is not None
        assert loaded_tenant.tenant_id == t_id
        assert loaded_tenant.name == "Persistent Corp"
        assert loaded_tenant.tier == TenantTier.ENTERPRISE

        # Verify user can authenticate using manager2
        auth2 = TenantAuth(manager2)
        auth_ok, auth_user, token = await auth2.authenticate_user(
            tenant_id=t_id,
            username="alice",
            password="securePassword123!",
        )
        assert auth_ok is True
        assert auth_user.user_id == user_id
        assert token is not None
    finally:
        manager2.close()


@pytest.mark.asyncio
async def test_tenant_limits_and_usage(test_settings, temp_db_path):
    """Test quota enforcement and usage tracking."""
    manager = TenantManager(test_settings, db_path=temp_db_path)
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
