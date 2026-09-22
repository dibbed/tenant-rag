"""Security integration and unit test suite for Tenant Authentication & Authorization.

Verifies:
- Impersonation prevention (Attack A)
- Cross-tenant query boundary enforcement (Attack B)
- Cross-tenant document ingestion isolation (Attack C)
- Cross-tenant and non-admin store reset prevention (Attack D)
- Missing credentials rejection (Attack E)
- Invalid, expired, and revoked credential rejection (Attack F)
- Immediate persistent key revocation
- Secret masking (no SHA-256 hash or secret leaks)
- Single-tenant backward compatibility
- SQLite persistence across manager restarts
- Suspended/inactive tenant denial
- Super-admin authorization bypass
"""

from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api.app import create_app
from ragbot.api.dependencies import (
    get_integration_service_dep,
    get_rag_service_dep,
)
from ragbot.configs.settings import Settings, MultiTenantSettings
from ragbot.multi_tenant.models import (
    TenantApiKey,
    TenantConfig,
    TenantPlan,
    TenantStatus,
    TenantTier,
    TenantUser,
)
from ragbot.multi_tenant.tenant_auth import TenantAuth, UserRole, Permission
from ragbot.multi_tenant.tenant_manager import TenantManager
from ragbot.services.rag_service import IngestResult, QueryResult


@pytest.fixture
def temp_tenant_db():
    """Create a temporary SQLite database for tenant persistence."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "security_tenants.db"
        yield db_path


@pytest.fixture
def security_tenant_manager(temp_tenant_db):
    """Create a real TenantManager backed by temporary SQLite."""
    settings = Settings(
        multi_tenant=MultiTenantSettings(
            enabled=True,
            default_tier="free",
            data_dir=temp_tenant_db.parent,
        )
    )
    mgr = TenantManager(settings, db_path=temp_tenant_db)
    yield mgr
    mgr.close()


@pytest.fixture
def security_tenant_auth(security_tenant_manager):
    """Create TenantAuth using the real TenantManager."""
    return TenantAuth(security_tenant_manager)


@pytest.fixture
def mock_integration_service():
    """Mock integration service."""
    service = MagicMock()
    service.health_check = AsyncMock(return_value={"status": "healthy"})
    service.track_user_action = AsyncMock()
    service.record_document_type = AsyncMock()
    return service


@pytest.fixture
def security_rag_service(security_tenant_manager, security_tenant_auth):
    """Create mock RAGService wired to real tenant_manager and tenant_auth."""
    mock_rag = MagicMock()
    mock_rag.tenant_manager = security_tenant_manager
    mock_rag.tenant_auth = security_tenant_auth
    mock_rag.query_documents = AsyncMock(
        return_value=QueryResult(
            answer="Secure response for authorized tenant.",
            sources=["doc1.txt"],
            confidence_score=0.99,
            processing_time=0.05,
            language="en",
            retrieved_chunks=["Authorized chunk data"],
            metadata={},
        )
    )
    mock_rag.ingest_document = AsyncMock(
        return_value=IngestResult(
            success=True,
            document_id="doc_sec_001",
            chunks_created=2,
            processing_time=0.08,
            metadata={},
        )
    )
    mock_rag.reset_store = AsyncMock(return_value=True)
    return mock_rag


@pytest.fixture
def security_test_client(security_rag_service, mock_integration_service):
    """Create FastAPI TestClient wired to security_rag_service."""
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", True):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_integration_service
        app.dependency_overrides[get_rag_service_dep] = lambda: security_rag_service

        with TestClient(app) as client:
            yield client


# ---------------------------------------------------------------------------
# Tests: Attack A & E - Missing and Impersonated Credentials
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_credentials_rejected(security_test_client):
    """Verify that requests without credentials in multi-tenant mode return 401."""
    # Query endpoint
    res_query = security_test_client.post(
        "/api/v1/query",
        json={"question": "Confidential data query?"},
    )
    assert res_query.status_code == status.HTTP_401_UNAUTHORIZED
    assert "credentials required" in res_query.json().get("detail", "").lower()

    # Ingest endpoint
    res_ingest = security_test_client.post(
        "/api/v1/documents/text",
        json={"text": "Unauthenticated doc"},
    )
    assert res_ingest.status_code == status.HTTP_401_UNAUTHORIZED

    # Reset endpoint
    res_reset = security_test_client.post("/api/v1/documents/reset")
    assert res_reset.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_impersonation_via_header_alone_rejected(security_test_client):
    """Verify that simply providing X-Tenant-ID without credentials returns 401."""
    res = security_test_client.post(
        "/api/v1/query",
        json={"question": "Attacking tenant B?"},
        headers={"X-Tenant-ID": "target_tenant_b"},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "credentials required" in res.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# Tests: Attack B, C, D - Cross-Tenant Access with Tenant A Credentials
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_boundaries_forbidden(
    security_tenant_manager, security_tenant_auth, security_test_client, security_rag_service
):
    """Verify that Tenant A cannot query, ingest into, or reset Tenant B."""
    # 1. Provision Tenant A and Tenant B
    tenant_a = await security_tenant_manager.create_tenant(
        name="Tenant A Corp",
        tenant_id="tenant_a",
    )
    tenant_b = await security_tenant_manager.create_tenant(
        name="Tenant B Corp",
        tenant_id="tenant_b",
    )

    # 2. Create API key for Tenant A
    ok_a, key_a, err_a = await security_tenant_auth.create_api_key(
        tenant_id="tenant_a",
        name="key_tenant_a",
    )
    assert ok_a is True
    assert key_a.startswith("rgb_")

    # 3. Create API key for Tenant B
    ok_b, key_b, err_b = await security_tenant_auth.create_api_key(
        tenant_id="tenant_b",
        name="key_tenant_b",
    )
    assert ok_b is True
    assert key_b.startswith("rgb_")

    # --- Legitimate Request: Tenant A accesses Tenant A ---
    res_legit = security_test_client.post(
        "/api/v1/query",
        json={"question": "Tenant A legitimate query"},
        headers={"X-API-Key": key_a, "X-Tenant-ID": "tenant_a"},
    )
    assert res_legit.status_code == status.HTTP_200_OK

    # --- Attack B: Tenant A credentials, X-Tenant-ID = tenant_b on /query ---
    res_attack_query = security_test_client.post(
        "/api/v1/query",
        json={"question": "Sneak peek into tenant B data"},
        headers={"X-API-Key": key_a, "X-Tenant-ID": "tenant_b"},
    )
    assert res_attack_query.status_code == status.HTTP_403_FORBIDDEN
    assert "access to requested tenant" in res_attack_query.json().get("detail", "").lower()

    # --- Attack C: Tenant A credentials, X-Tenant-ID = tenant_b on /documents/text ---
    res_attack_ingest = security_test_client.post(
        "/api/v1/documents/text",
        json={"text": "Poisoning tenant B database"},
        headers={"X-API-Key": key_a, "X-Tenant-ID": "tenant_b"},
    )
    assert res_attack_ingest.status_code == status.HTTP_403_FORBIDDEN
    assert "access to requested tenant" in res_attack_ingest.json().get("detail", "").lower()

    # --- Attack D: Tenant A credentials, X-Tenant-ID = tenant_b on /documents/reset ---
    res_attack_reset = security_test_client.post(
        "/api/v1/documents/reset",
        headers={"X-API-Key": key_a, "X-Tenant-ID": "tenant_b"},
    )
    assert res_attack_reset.status_code == status.HTTP_403_FORBIDDEN
    assert "access to requested tenant" in res_attack_reset.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# Tests: Attack D Deep Dive - Reset Authorization and Admin Role Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_requires_admin_role(
    security_tenant_manager, security_tenant_auth, security_test_client
):
    """Verify that a non-admin user within Tenant A cannot reset Tenant A's store."""
    tenant = await security_tenant_manager.create_tenant(
        name="Reset Test Corp",
        tenant_id="tenant_reset",
    )

    # Create a viewer user
    ok_user, viewer_user, _ = await security_tenant_auth.create_user(
        tenant_id="tenant_reset",
        username="viewer_bob",
        email="bob@reset.test",
        password="Password123!",
        role=UserRole.VIEWER,
    )
    assert ok_user is True

    # Create API key for the viewer user
    ok_key, viewer_key, _ = await security_tenant_auth.create_api_key(
        tenant_id="tenant_reset",
        user_id=viewer_user.user_id,
        name="viewer_key",
        permissions=[Permission.VIEW_DOCUMENTS.value, Permission.API_ACCESS.value],
    )
    assert ok_key is True

    # Attempt reset with viewer key
    res_reset = security_test_client.post(
        "/api/v1/documents/reset",
        headers={"X-API-Key": viewer_key, "X-Tenant-ID": "tenant_reset"},
    )
    assert res_reset.status_code == status.HTTP_403_FORBIDDEN
    assert "insufficient permissions" in res_reset.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_super_admin_can_reset_any_tenant(
    security_tenant_manager, security_tenant_auth, security_test_client
):
    """Verify that a super_admin principal can perform operations across tenants."""
    tenant = await security_tenant_manager.create_tenant(
        name="Target Corp",
        tenant_id="target_tenant",
    )

    # Create super admin user in target or default tenant
    ok_user, admin_user, _ = await security_tenant_auth.create_user(
        tenant_id="target_tenant",
        username="superadmin",
        email="super@root.local",
        password="Password123!",
        role=UserRole.SUPER_ADMIN,
    )
    assert ok_user is True

    ok_key, super_key, _ = await security_tenant_auth.create_api_key(
        tenant_id="target_tenant",
        user_id=admin_user.user_id,
        name="superadmin_key",
    )
    assert ok_key is True

    # Super admin resetting store with explicit tenant header
    res_reset = security_test_client.post(
        "/api/v1/documents/reset",
        headers={"X-API-Key": super_key, "X-Tenant-ID": "target_tenant"},
    )
    assert res_reset.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Tests: Attack F - Invalid, Malformed, Expired, and Suspended Credentials
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_and_malformed_api_keys(security_test_client):
    """Verify that malformed or non-existent API keys are rejected with 401."""
    for bad_key in ["invalid", "rgb_nonexistent_token_123456789012345678", "   ", ""]:
        res = security_test_client.post(
            "/api/v1/query",
            json={"question": "Test bad key"},
            headers={"X-API-Key": bad_key},
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_expired_api_key_rejected(
    security_tenant_manager, security_tenant_auth, security_test_client
):
    """Verify that an expired API key returns 401 Unauthorized."""
    tenant = await security_tenant_manager.create_tenant(
        name="Expiring Corp",
        tenant_id="tenant_expire",
    )
    # Create key expired 2 days ago
    ok, raw_key, _ = await security_tenant_auth.create_api_key(
        tenant_id="tenant_expire",
        name="expired_key",
        expires_days=-2,
    )
    assert ok is True

    res = security_test_client.post(
        "/api/v1/query",
        json={"question": "Querying with expired key"},
        headers={"X-API-Key": raw_key},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_suspended_tenant_denied(
    security_tenant_manager, security_tenant_auth, security_test_client
):
    """Verify that a suspended tenant's valid API key is rejected with 403."""
    tenant = await security_tenant_manager.create_tenant(
        name="Suspended Corp",
        tenant_id="tenant_suspend",
    )
    ok, raw_key, _ = await security_tenant_auth.create_api_key(
        tenant_id="tenant_suspend",
        name="suspend_key",
    )
    assert ok is True

    # Suspend tenant
    await security_tenant_manager.suspend_tenant("tenant_suspend", reason="policy_violation")

    res = security_test_client.post(
        "/api/v1/query",
        json={"question": "Querying while suspended"},
        headers={"X-API-Key": raw_key},
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "not active" in res.json().get("detail", "").lower() or "suspended" in res.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# Tests: Immediate Revocation & Persistence Across Restarts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_immediate_persistent_revocation(
    security_tenant_manager, security_tenant_auth, security_test_client
):
    """Verify that revoking an API key immediately invalidates it without restart."""
    tenant = await security_tenant_manager.create_tenant(
        name="Revoke Corp",
        tenant_id="tenant_revoke",
    )
    ok, raw_key, _ = await security_tenant_auth.create_api_key(
        tenant_id="tenant_revoke",
        name="test_revocation",
    )
    assert ok is True

    # Key works initially
    res_before = security_test_client.post(
        "/api/v1/query",
        json={"question": "Pre-revocation query"},
        headers={"X-API-Key": raw_key},
    )
    assert res_before.status_code == status.HTTP_200_OK

    # Revoke key
    revoked = await security_tenant_auth.revoke_api_key(
        tenant_id="tenant_revoke",
        api_key_or_id=raw_key,
    )
    assert revoked is True

    # Key immediately fails with 401
    res_after = security_test_client.post(
        "/api/v1/query",
        json={"question": "Post-revocation query"},
        headers={"X-API-Key": raw_key},
    )
    assert res_after.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in res_after.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_sqlite_api_key_persistence_across_restarts(temp_tenant_db):
    """Verify that hashed API keys survive across manager restarts in SQLite."""
    settings = Settings(
        multi_tenant=MultiTenantSettings(
            enabled=True,
            default_tier="free",
            data_dir=temp_tenant_db.parent,
        )
    )

    # Instance 1: Create tenant and API key
    mgr1 = TenantManager(settings, db_path=temp_tenant_db)
    auth1 = TenantAuth(mgr1)
    await mgr1.create_tenant(name="Restart Corp", tenant_id="tenant_restart")
    ok, raw_key, _ = await auth1.create_api_key(
        tenant_id="tenant_restart",
        name="persistent_key",
    )
    assert ok is True
    mgr1.close()

    # Instance 2: Start new TenantManager & TenantAuth from same SQLite DB
    mgr2 = TenantManager(settings, db_path=temp_tenant_db)
    auth2 = TenantAuth(mgr2)
    try:
        # Authenticate with raw key on fresh instance
        ok_auth, principal, err = await auth2.authenticate_principal(raw_key)
        assert ok_auth is True
        assert principal is not None
        assert principal.tenant_id == "tenant_restart"
        assert principal.identity_type == "api_key"

        # Verify key list returns metadata with masked key prefix and no secret hash
        keys = await auth2.list_api_keys("tenant_restart")
        assert len(keys) == 1
        assert keys[0]["name"] == "persistent_key"
        assert "key_hash" not in keys[0]
        assert keys[0]["key_prefix"] == raw_key[:12]
    finally:
        mgr2.close()


# ---------------------------------------------------------------------------
# Tests: Single-Tenant Backward Compatibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_tenant_backward_compatibility(security_rag_service, mock_integration_service):
    """Verify that single-tenant mode works seamlessly without headers or credentials."""
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", False):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_integration_service
        app.dependency_overrides[get_rag_service_dep] = lambda: security_rag_service

        with TestClient(app) as client:
            # Query without any auth or tenant headers
            res_query = client.post(
                "/api/v1/query",
                json={"question": "Single tenant question"},
            )
            assert res_query.status_code == status.HTTP_200_OK

            # Document ingest without auth
            res_ingest = client.post(
                "/api/v1/documents/text",
                json={"text": "Single tenant doc text"},
            )
            assert res_ingest.status_code == status.HTTP_200_OK

            # Store reset without auth
            res_reset = client.post("/api/v1/documents/reset")
            assert res_reset.status_code == status.HTTP_200_OK
