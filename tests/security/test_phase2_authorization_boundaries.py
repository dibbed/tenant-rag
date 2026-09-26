"""Phase 2 regression tests: authorization levels and tenant boundaries.

Audit finding C4 (docs/BASELINE_AUDIT.md).

Vulnerability: authenticate_principal() marked any API key with the
manage_tenant permission as a super admin, and super admins skip the
X-Tenant-ID boundary check. Key permissions are chosen per key, so a
tenant-scoped credential could read, write, reset and manage every tenant.
The reset check also let the manager role reset a tenant store.

Expected behavior: system_admin comes from the super_admin role only;
tenant_admin (role admin) manages and resets its own tenant only; other
principals are limited to their own tenant and explicit permissions.
Cross-tenant attempts return HTTP 403.
"""

from __future__ import annotations

from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, status
from fastapi.testclient import TestClient

from ragbot.api.app import create_app
from ragbot.api.dependencies import (
    get_integration_service_dep,
    get_rag_service_dep,
    require_tenant_admin,
)
from ragbot.configs.settings import MultiTenantSettings, Settings
from ragbot.multi_tenant.authorization import (
    AuthorizationLevel,
    authorization_level_for_role,
    can_access_tenant,
    can_manage_tenant,
    can_reset_tenant_store,
    is_system_admin,
)
from ragbot.multi_tenant.models import AuthenticatedPrincipal, TenantTier
from ragbot.multi_tenant.tenant_auth import Permission, TenantAuth, UserRole
from ragbot.multi_tenant.tenant_manager import TenantManager
from ragbot.services.rag_service import IngestResult, QueryResult

MANAGE_PATH = "/phase2-test/tenant-management"


@pytest.fixture
def manager(tmp_path):
    db_path = tmp_path / "phase2_authz.db"
    settings = Settings(
        multi_tenant=MultiTenantSettings(enabled=True, default_tier="free", data_dir=tmp_path)
    )
    mgr = TenantManager(settings, db_path=db_path)
    yield mgr
    mgr.close()


@pytest.fixture
def auth(manager):
    return TenantAuth(manager)


@pytest.fixture
def rag_service(manager, auth):
    rag = MagicMock()
    rag.tenant_manager = manager
    rag.tenant_auth = auth
    rag.query_documents = AsyncMock(
        return_value=QueryResult(
            answer="ok",
            sources=[],
            confidence_score=1.0,
            processing_time=0.01,
            language="en",
            retrieved_chunks=[],
            metadata={},
        )
    )
    rag.ingest_document = AsyncMock(
        return_value=IngestResult(
            success=True, document_id="doc_1", chunks_created=1, processing_time=0.01, metadata={}
        )
    )
    rag.reset_store = AsyncMock(return_value=True)
    return rag


@pytest.fixture
def client(rag_service):
    integration = MagicMock()
    integration.track_user_action = AsyncMock()
    integration.record_document_type = AsyncMock()
    integration.components = {}
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", True):
        app = create_app(lifespan_context=None)

        @app.post(MANAGE_PATH)
        async def manage_tenant(principal=Depends(require_tenant_admin)):
            return {"managed": True}

        app.dependency_overrides[get_integration_service_dep] = lambda: integration
        app.dependency_overrides[get_rag_service_dep] = lambda: rag_service
        with TestClient(app) as test_client:
            yield test_client


async def _setup(manager, auth) -> Dict[str, str]:
    for tenant_id in ("tenant_a", "tenant_b", "ops_root"):
        await manager.create_tenant(name=tenant_id, tenant_id=tenant_id, tier=TenantTier.ENTERPRISE)

    async def user_key(tenant_id, username, role, permissions=None):
        ok, user, err = await auth.create_user(
            tenant_id=tenant_id,
            username=username,
            email=f"{username}@{tenant_id}.test",
            password="Str0ng-Passw0rd!",
            role=role,
        )
        assert ok, err
        ok, raw, err = await auth.create_api_key(
            tenant_id=tenant_id, user_id=user.user_id, name=f"{username}_key", permissions=permissions
        )
        assert ok, err
        return raw

    api = Permission.API_ACCESS.value
    keys = {
        "admin_a": await user_key("tenant_a", "admin_a", UserRole.ADMIN),
        "manager_a": await user_key("tenant_a", "manager_a", UserRole.MANAGER),
        "user_a": await user_key(
            "tenant_a",
            "user_a",
            UserRole.USER,
            [api, Permission.VIEW_DOCUMENTS.value, Permission.UPLOAD_DOCUMENTS.value, Permission.ASK_QUESTIONS.value],
        ),
        "deleter_a": await user_key(
            "tenant_a",
            "deleter_a",
            UserRole.VIEWER,
            [api, Permission.VIEW_DOCUMENTS.value, Permission.DELETE_DOCUMENTS.value],
        ),
        "admin_b": await user_key("tenant_b", "admin_b", UserRole.ADMIN),
        "system_admin": await user_key("ops_root", "root", UserRole.SUPER_ADMIN),
    }
    ok, raw, err = await auth.create_api_key(
        tenant_id="tenant_a",
        name="mgmt_key",
        permissions=[
            api,
            Permission.VIEW_DOCUMENTS.value,
            Permission.ASK_QUESTIONS.value,
            Permission.MANAGE_TENANT.value,
        ],
    )
    assert ok, err
    keys["manage_tenant_key_a"] = raw
    return keys


def _headers(key, tenant):
    return {"X-API-Key": key, "X-Tenant-ID": tenant}


def _tenants_called(mock):
    return [call.kwargs.get("tenant_id") for call in mock.call_args_list]


@pytest.mark.asyncio
async def test_tenant_admin_cannot_read_tenant_b_data(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    response = client.post(
        "/api/v1/query", json={"question": "B secrets?"}, headers=_headers(keys["admin_a"], "tenant_b")
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "tenant_b" not in _tenants_called(rag_service.query_documents)


@pytest.mark.asyncio
async def test_tenant_admin_cannot_ingest_into_tenant_b(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    response = client.post(
        "/api/v1/documents/text", json={"text": "poison"}, headers=_headers(keys["admin_a"], "tenant_b")
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    rag_service.ingest_document.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_admin_cannot_reset_tenant_b(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    response = client.post("/api/v1/documents/reset", headers=_headers(keys["admin_a"], "tenant_b"))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    rag_service.reset_store.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_admin_cannot_manage_tenant_b(manager, auth, client):
    keys = await _setup(manager, auth)
    assert client.post(MANAGE_PATH, headers=_headers(keys["admin_a"], "tenant_b")).status_code == 403
    assert client.post(MANAGE_PATH, headers=_headers(keys["admin_a"], "tenant_a")).status_code == 200


@pytest.mark.asyncio
async def test_manage_tenant_permission_does_not_grant_system_admin(manager, auth, client, rag_service):
    """C4 core issue: a key permission must never become cross-tenant access."""
    keys = await _setup(manager, auth)
    key = keys["manage_tenant_key_a"]

    ok, principal, error = await auth.authenticate_principal(key)
    assert ok is True, error
    assert principal.is_super_admin is False
    assert is_system_admin(principal) is False

    headers = _headers(key, "tenant_b")
    assert client.post("/api/v1/query", json={"question": "x"}, headers=headers).status_code == 403
    assert client.post("/api/v1/documents/reset", headers=headers).status_code == 403
    assert client.post(MANAGE_PATH, headers=headers).status_code == 403
    rag_service.reset_store.assert_not_called()
    assert "tenant_b" not in _tenants_called(rag_service.query_documents)


@pytest.mark.asyncio
async def test_tenant_admin_can_reset_own_tenant(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    response = client.post("/api/v1/documents/reset", headers=_headers(keys["admin_a"], "tenant_a"))
    assert response.status_code == status.HTTP_200_OK
    rag_service.reset_store.assert_called_once_with(tenant_id="tenant_a")


@pytest.mark.asyncio
async def test_manager_role_without_delete_permission_cannot_reset(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    response = client.post("/api/v1/documents/reset", headers=_headers(keys["manager_a"], "tenant_a"))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    rag_service.reset_store.assert_not_called()


@pytest.mark.asyncio
async def test_normal_user_cannot_reset_or_manage_own_tenant(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    headers = _headers(keys["user_a"], "tenant_a")
    assert client.post("/api/v1/query", json={"question": "x"}, headers=headers).status_code == 200
    assert client.post("/api/v1/documents/reset", headers=headers).status_code == 403
    assert client.post(MANAGE_PATH, headers=headers).status_code == 403
    rag_service.reset_store.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_delete_permission_allows_reset_of_own_tenant_only(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    key = keys["deleter_a"]
    assert client.post("/api/v1/documents/reset", headers=_headers(key, "tenant_b")).status_code == 403
    assert client.post("/api/v1/documents/reset", headers=_headers(key, "tenant_a")).status_code == 200
    rag_service.reset_store.assert_called_once_with(tenant_id="tenant_a")


@pytest.mark.asyncio
async def test_system_admin_can_access_manage_and_reset_any_tenant(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    headers = _headers(keys["system_admin"], "tenant_b")
    assert client.post("/api/v1/query", json={"question": "x"}, headers=headers).status_code == 200
    assert client.post(MANAGE_PATH, headers=headers).status_code == 200
    assert client.post("/api/v1/documents/reset", headers=headers).status_code == 200
    rag_service.reset_store.assert_called_once_with(tenant_id="tenant_b")


@pytest.mark.asyncio
async def test_tenant_b_admin_cannot_reach_tenant_a(manager, auth, client, rag_service):
    keys = await _setup(manager, auth)
    headers = _headers(keys["admin_b"], "tenant_a")
    assert client.post("/api/v1/query", json={"question": "x"}, headers=headers).status_code == 403
    assert client.post("/api/v1/documents/reset", headers=headers).status_code == 403
    rag_service.reset_store.assert_not_called()


def _principal(role, super_flag=False, tenant="tenant_a", permissions=()):
    return AuthenticatedPrincipal(
        principal_id="p1",
        identity_type="api_key",
        tenant_id=tenant,
        role=role,
        permissions=list(permissions),
        is_super_admin=super_flag,
    )


def test_authorization_levels_come_from_role_only():
    assert authorization_level_for_role("super_admin") is AuthorizationLevel.SYSTEM_ADMIN
    assert authorization_level_for_role(UserRole.ADMIN) is AuthorizationLevel.TENANT_ADMIN
    for role in ("manager", "user", "viewer", "api_user", None):
        assert authorization_level_for_role(role) is AuthorizationLevel.USER

    admin = _principal("admin", permissions=["manage_tenant", "system_settings"])
    assert not is_system_admin(admin)
    assert can_manage_tenant(admin, "tenant_a") and not can_manage_tenant(admin, "tenant_b")

    forged_flag = _principal("admin", super_flag=True)
    assert not is_system_admin(forged_flag)
    assert not can_access_tenant(forged_flag, "tenant_b")

    unflagged_root = _principal("super_admin", super_flag=False)
    assert not is_system_admin(unflagged_root)
    assert not can_access_tenant(unflagged_root, "tenant_b")

    root = _principal("super_admin", super_flag=True, tenant="ops_root")
    assert is_system_admin(root)
    assert can_manage_tenant(root, "tenant_b") and can_reset_tenant_store(root, "tenant_b")

    deleter = _principal("user", permissions=["delete_documents"])
    assert can_reset_tenant_store(deleter, "tenant_a")
    assert not can_reset_tenant_store(deleter, "tenant_b")
    assert not can_manage_tenant(deleter, "tenant_a")

    manager_role = _principal("manager", permissions=["manage_users", "manage_tenant"])
    assert not can_reset_tenant_store(manager_role, "tenant_a")
    assert not can_access_tenant(None, "tenant_a")
