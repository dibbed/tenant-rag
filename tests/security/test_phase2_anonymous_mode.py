"""Phase 2 regression tests: secure default authentication mode.

Audit finding C5 (docs/BASELINE_AUDIT.md).

Vulnerability: with MULTI_TENANT_ENABLED=false (the default) every API route,
including POST /api/v1/documents/reset, accepted requests without any
credentials.

Expected behavior: anonymous access needs BOTH ENVIRONMENT=development AND
ALLOW_ANONYMOUS=true. Any other combination rejects API requests with HTTP
401. The effective mode is logged at startup, with a warning for insecure
mode.
"""

from __future__ import annotations

import io
import sys
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api import access_mode
from ragbot.api.access_mode import (
    ANONYMOUS_DISABLED_DETAIL,
    anonymous_access_allowed,
    log_access_mode_warnings,
)
from ragbot.api.app import create_app
from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.services.rag_service import IngestResult, QueryResult


def _mock_rag():
    rag = MagicMock()
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


@contextmanager
def api_client(multi_tenant_enabled: bool):
    rag = _mock_rag()
    integration = MagicMock()
    integration.health_check = AsyncMock(
        return_value={"status": "healthy", "timestamp": 1.0, "components": {}, "issues": []}
    )
    integration.track_user_action = AsyncMock()
    integration.record_document_type = AsyncMock()
    integration.components = {}
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", multi_tenant_enabled):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: integration
        app.dependency_overrides[get_rag_service_dep] = lambda: rag
        with TestClient(app) as client:
            yield client, rag


def _call_all_routes(client):
    return {
        "query": client.post("/api/v1/query", json={"question": "hello"}),
        "text": client.post("/api/v1/documents/text", json={"text": "hello world"}),
        "url": client.post("/api/v1/documents/url", json={"url": "https://example.com/doc"}),
        "upload": client.post(
            "/api/v1/documents/upload",
            files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
        ),
        "reset": client.post("/api/v1/documents/reset"),
    }


@pytest.fixture
def production_defaults(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ALLOW_ANONYMOUS", raising=False)


def test_default_configuration_requires_authentication(production_defaults):
    with api_client(multi_tenant_enabled=False) as (client, rag):
        for name, response in _call_all_routes(client).items():
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, name
            assert response.json()["detail"] == ANONYMOUS_DISABLED_DETAIL
        assert client.get("/health").status_code == status.HTTP_200_OK
        assert client.get("/api/v1/health").status_code == status.HTTP_200_OK
    rag.query_documents.assert_not_called()
    rag.ingest_document.assert_not_called()
    rag.reset_store.assert_not_called()


def test_allow_anonymous_outside_development_is_rejected(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with api_client(multi_tenant_enabled=False) as (client, rag):
        for name, response in _call_all_routes(client).items():
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, name
    rag.reset_store.assert_not_called()


def test_development_environment_alone_does_not_allow_anonymous(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ALLOW_ANONYMOUS", raising=False)
    with api_client(multi_tenant_enabled=False) as (client, rag):
        assert client.post("/api/v1/query", json={"question": "hi"}).status_code == 401
        assert client.post("/api/v1/documents/reset").status_code == 401
    rag.reset_store.assert_not_called()


def test_explicit_development_mode_allows_anonymous_access(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with api_client(multi_tenant_enabled=False) as (client, rag):
        assert client.post("/api/v1/query", json={"question": "hi"}).status_code == 200
        assert client.post("/api/v1/documents/text", json={"text": "hi there"}).status_code == 200
        assert client.post("/api/v1/documents/reset").status_code == 200
    rag.reset_store.assert_called_once()


def test_allow_anonymous_is_ignored_when_multi_tenant_is_enabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with api_client(multi_tenant_enabled=True) as (client, rag):
        response = client.post("/api/v1/query", json={"question": "hi"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "credentials required" in response.json()["detail"].lower()
    rag.query_documents.assert_not_called()


@pytest.mark.parametrize(
    "environment,allow,expected",
    [
        (None, None, False),
        ("production", "true", False),
        ("staging", "1", False),
        ("development", None, False),
        ("development", "false", False),
        ("development", "true", True),
        ("Development", "YES", True),
        (" development ", "on", True),
    ],
)
def test_anonymous_access_requires_both_settings(monkeypatch, environment, allow, expected):
    for name, value in (("ENVIRONMENT", environment), ("ALLOW_ANONYMOUS", allow)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert anonymous_access_allowed() is expected


def test_startup_warning_when_insecure_mode_is_enabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with patch.object(access_mode, "logger") as fake_logger:
        assert log_access_mode_warnings(multi_tenant_enabled=False) == "anonymous"
    message = fake_logger.warning.call_args[0][0]
    assert "INSECURE" in message


def test_startup_warning_when_api_is_locked(production_defaults):
    with patch.object(access_mode, "logger") as fake_logger:
        assert log_access_mode_warnings(multi_tenant_enabled=False) == "locked"
    assert "401" in fake_logger.warning.call_args[0][0]


def test_startup_warning_when_allow_anonymous_is_ignored_outside_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_ANONYMOUS", "true")
    with patch.object(access_mode, "logger") as fake_logger:
        assert log_access_mode_warnings(multi_tenant_enabled=False) == "locked"
    assert "ignored" in fake_logger.warning.call_args[0][0]


def test_multi_tenant_mode_is_reported_as_authenticated(production_defaults):
    with patch.object(access_mode, "logger") as fake_logger:
        assert log_access_mode_warnings(multi_tenant_enabled=True) == "authenticated"
    fake_logger.warning.assert_not_called()


def test_create_app_reports_access_mode_at_startup():
    # On Python 3.10, patch("ragbot.api.app.<name>") resolves ragbot.api.app to
    # the FastAPI instance that ragbot.api exports, so patch the module itself.
    with patch.object(sys.modules["ragbot.api.app"], "log_access_mode_warnings") as reporter:
        create_app(lifespan_context=None)
    reporter.assert_called_once()
