"""Phase 3.5 regression tests: tenant verification fails closed (C7) and has no test-framework branch (C8).

Audit findings C7 and C8 (docs/BASELINE_AUDIT.md,
docs/security/PHASE3_5_SECURITY_HARDENING.md).

C7: get_authorized_tenant_context logged an unexpected tenant lookup error at
debug level and let the request continue as authorized (fail open). It also
skipped the check when the RAG service had no tenant manager.
Expected: unknown or error is never authorized. A lookup error or a missing
tenant registry answers HTTP 503 without internal details; a tenant that does
not exist, is not active or has an unknown status answers HTTP 403. The route
is not called.

C8: ragbot/api/dependencies.py imported unittest.mock.MagicMock and skipped the
existence and status checks for MagicMock objects.
Expected: production code has no test-framework branch; tests replace the
tenant registry with a dependency override or a fake.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ragbot.api import dependencies
from ragbot.api.app import create_app
from ragbot.api.dependencies import (
    get_current_principal,
    get_integration_service_dep,
    get_rag_service_dep,
)
from ragbot.configs.settings import MultiTenantSettings, Settings, settings
from ragbot.multi_tenant.models import AuthenticatedPrincipal, TenantConfig, TenantStatus
from ragbot.multi_tenant.tenant_auth import TenantAuth
from ragbot.multi_tenant.tenant_manager import TenantManager
from ragbot.services.rag_service import QueryResult

ROOT = Path(__file__).resolve().parents[2]
QUERY = {"question": "What is the policy?"}
UNAVAILABLE = "Tenant verification is temporarily unavailable"


class _Rag:
    """RAG service fake without unittest.mock; its tenant manager is the registry under test."""

    def __init__(self, tenant_manager: Any = None, tenant_auth: Any = None) -> None:
        self.tenant_manager = tenant_manager
        self.tenant_auth = tenant_auth
        self.queries: list[dict[str, Any]] = []

    async def query_documents(self, **kwargs: Any) -> QueryResult:
        self.queries.append(kwargs)
        return QueryResult(
            answer="ok",
            sources=[],
            confidence_score=1.0,
            processing_time=0.01,
            language="en",
            retrieved_chunks=[],
            metadata={},
        )


class _Integration:
    """Integration service fake for the query route."""

    components: dict[str, Any] = {}

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "timestamp": 1.0, "components": {}, "issues": []}

    async def track_user_action(self, **_: Any) -> None:
        return None

    async def record_document_type(self, *_: Any, **__: Any) -> None:
        return None


class _Registry:
    """Tenant registry fake with fixed answers or a fixed error."""

    def __init__(self, tenants: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.tenants = dict(tenants or {})
        self.error = error
        self.lookups: list[str] = []

    async def get_tenant(self, tenant_id: str) -> Any:
        self.lookups.append(tenant_id)
        if self.error is not None:
            raise self.error
        return self.tenants.get(tenant_id)


def _tenant(status: TenantStatus = TenantStatus.ACTIVE) -> TenantConfig:
    return TenantConfig(tenant_id="tenant_a", name="Tenant A", status=status)


def _principal(tenant_id: str = "tenant_a") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_id=f"key_{uuid.uuid4().hex}",
        identity_type="api_key",
        tenant_id=tenant_id,
        role="admin",
        permissions=["ask_questions"],
    )


@pytest.fixture(autouse=True)
def multi_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.multi_tenant, "enabled", True)


def _app(rag: _Rag, principal: AuthenticatedPrincipal | None = None) -> Any:
    app = create_app(lifespan_context=None)
    app.dependency_overrides[get_integration_service_dep] = _Integration
    app.dependency_overrides[get_rag_service_dep] = lambda: rag
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    return app


def _query(app: Any, headers: dict[str, str] | None = None) -> Any:
    with TestClient(app) as client:
        return client.post(
            "/api/v1/query", json=QUERY, headers={"X-Tenant-ID": "tenant_a", **(headers or {})}
        )


# C7: existing, missing, inactive and unknown tenants


def test_an_active_tenant_is_allowed() -> None:
    rag = _Rag(_Registry({"tenant_a": _tenant()}))
    response = _query(_app(rag, _principal()))
    assert response.status_code == 200
    assert [call["tenant_id"] for call in rag.queries] == ["tenant_a"]


def test_a_missing_tenant_is_refused() -> None:
    rag = _Rag(_Registry({}))
    response = _query(_app(rag, _principal()))
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant 'tenant_a' does not exist"
    assert rag.queries == []


@pytest.mark.parametrize("status", [TenantStatus.SUSPENDED, TenantStatus.INACTIVE, TenantStatus.PENDING])
def test_an_inactive_tenant_is_refused(status: TenantStatus) -> None:
    rag = _Rag(_Registry({"tenant_a": _tenant(status)}))
    response = _query(_app(rag, _principal()))
    assert response.status_code == 403
    assert response.json()["detail"] == "Tenant 'tenant_a' is not active"
    assert rag.queries == []


@pytest.mark.parametrize(
    "record",
    [
        SimpleNamespace(),
        SimpleNamespace(status=None),
        SimpleNamespace(status="unknown"),
        SimpleNamespace(status=3),
        {"status": "active"},
    ],
    ids=["no-status", "status-none", "status-unknown", "status-number", "dict-record"],
)
def test_a_tenant_with_an_unknown_status_is_refused(record: Any) -> None:
    rag = _Rag(_Registry({"tenant_a": record}))
    response = _query(_app(rag, _principal()))
    assert response.status_code == 403
    assert rag.queries == []


# C7: lookup failures fail closed


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("database is locked: postgresql://tenant_admin:hunter2@db/tenants"),
        OSError("disk I/O error"),
        ConnectionError("tenant store unreachable"),
        TimeoutError("tenant lookup timed out"),
        KeyError("tenant_a"),
    ],
    ids=["runtime-error", "os-error", "connection-error", "timeout", "key-error"],
)
def test_a_lookup_error_fails_closed_without_internal_details(error: Exception) -> None:
    registry = _Registry(error=error)
    rag = _Rag(registry)
    response = _query(_app(rag, _principal()))
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE
    assert "hunter2" not in response.text
    assert type(error).__name__ not in response.text
    assert registry.lookups == ["tenant_a"]
    assert rag.queries == []


@pytest.mark.parametrize(
    "registry",
    [None, SimpleNamespace(), SimpleNamespace(get_tenant="not callable")],
    ids=["no-registry", "no-get-tenant", "get-tenant-not-callable"],
)
def test_an_unavailable_registry_fails_closed(registry: Any) -> None:
    rag = _Rag(registry)
    response = _query(_app(rag, _principal()))
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE
    assert rag.queries == []


def test_a_lookup_error_is_logged_for_operators(monkeypatch: pytest.MonkeyPatch) -> None:
    real = dependencies.logger
    messages: list[str] = []

    class _RecordingLogger:
        def __getattr__(self, name: str) -> Any:
            return getattr(real, name)

        def error(self, message: str, *args: Any, **kwargs: Any) -> None:
            messages.append(message)

    monkeypatch.setattr(dependencies, "logger", _RecordingLogger())
    rag = _Rag(_Registry(error=RuntimeError("tenant backend down")))
    assert _query(_app(rag, _principal())).status_code == 503
    assert any(
        "tenant_a" in message and "RuntimeError" in message and "tenant backend down" in message
        for message in messages
    )


# C8: no test-framework branch in the authentication and authorization code


def test_authentication_code_does_not_use_test_frameworks() -> None:
    paths = sorted([*(ROOT / "ragbot" / "api").rglob("*.py"), *(ROOT / "ragbot" / "multi_tenant").rglob("*.py")])
    assert paths
    offenders = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name.split(".")[0] in {"unittest", "mock", "pytest"} for name in names):
                offenders.append(f"{path.relative_to(ROOT)} imports {names}")
        for marker in ("MagicMock", "AsyncMock", "NonCallableMock", "_mock_"):
            if marker in source:
                offenders.append(f"{path.relative_to(ROOT)} mentions {marker}")
    assert offenders == []


def test_a_mock_registry_without_the_tenant_is_refused() -> None:
    """Before C8, a MagicMock tenant manager let a missing tenant pass."""
    from unittest.mock import MagicMock

    registry = MagicMock()
    registry.get_tenant.return_value = None
    rag = _Rag(registry)
    response = _query(_app(rag, _principal()))
    assert response.status_code == 403
    assert rag.queries == []


def test_a_mock_tenant_status_is_not_trusted() -> None:
    """Before C8, a tenant record whose status was a MagicMock passed the status check."""
    from unittest.mock import MagicMock

    rag = _Rag(_Registry({"tenant_a": MagicMock()}))
    response = _query(_app(rag, _principal()))
    assert response.status_code == 403
    assert rag.queries == []


def test_a_dependency_override_replaces_the_tenant_registry() -> None:
    rag = _Rag(tenant_manager=None)
    app = _app(rag, _principal())
    app.dependency_overrides[dependencies.get_tenant_registry] = lambda: _Registry({"tenant_a": _tenant()})
    assert _query(app).status_code == 200
    app.dependency_overrides[dependencies.get_tenant_registry] = lambda: _Registry(
        {"tenant_a": _tenant(TenantStatus.SUSPENDED)}
    )
    assert _query(app).status_code == 403
    assert len(rag.queries) == 1


async def test_the_production_path_needs_no_mocks(tmp_path: Path) -> None:
    """Real TenantManager, TenantAuth and API key: no unittest.mock object in the request path."""
    manager = TenantManager(
        Settings(multi_tenant=MultiTenantSettings(enabled=True, default_tier="free", data_dir=tmp_path)),
        db_path=tmp_path / "tenants.db",
    )
    try:
        auth = TenantAuth(manager)
        await manager.create_tenant(name="Tenant A", tenant_id="tenant_a")
        ok, key, error = await auth.create_api_key(tenant_id="tenant_a", name="p35-key")
        assert ok, error
        rag = _Rag(tenant_manager=manager, tenant_auth=auth)
        app = _app(rag)
        headers = {"X-API-Key": key, "X-Tenant-ID": "tenant_a"}
        with TestClient(app) as client:
            allowed = client.post("/api/v1/query", json=QUERY, headers=headers)
            missing = client.post("/api/v1/query", json=QUERY)
            invalid = client.post("/api/v1/query", json=QUERY, headers={"X-API-Key": "rgb_invalid_secret"})
            await manager.suspend_tenant("tenant_a", reason="p35 regression test")
            suspended = client.post("/api/v1/query", json=QUERY, headers=headers)
        assert allowed.status_code == 200
        assert missing.status_code == 401
        assert invalid.status_code == 401
        assert suspended.status_code in (401, 403)
        assert len(rag.queries) == 1
    finally:
        manager.close()
