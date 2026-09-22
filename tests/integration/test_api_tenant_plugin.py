"""Integration tests for FastAPI routes with Multi-Tenant headers and Plugin lifecycle."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api.app import create_app
from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.configs.settings import Settings, MultiTenantSettings
from ragbot.services.rag_service import IngestResult, QueryResult


@pytest.fixture
def mock_integration_service():
    """Mock integration service providing mocked RAG and tracking methods."""
    service = MagicMock()
    service.health_check = AsyncMock(return_value={"status": "healthy"})
    service.track_user_action = AsyncMock()
    service.record_document_type = AsyncMock()
    return service


@pytest.fixture
def mock_multi_tenant_rag_service():
    """Mock RAGService configured for multi-tenant route verification."""
    mock_rag = MagicMock()
    mock_rag.query_documents = AsyncMock(
        return_value=QueryResult(
            answer="Multi-tenant test response.",
            sources=["doc1.pdf"],
            confidence_score=0.95,
            processing_time=0.1,
            language="en",
            retrieved_chunks=["tenant specific chunk"],
            metadata={},
        )
    )
    mock_rag.ingest_document = AsyncMock(
        return_value=IngestResult(
            success=True,
            document_id="doc_tenant_001",
            chunks_created=3,
            processing_time=0.15,
            metadata={},
        )
    )
    mock_rag.reset_store = AsyncMock(return_value=True)
    return mock_rag


def test_query_route_with_tenant_header(mock_multi_tenant_rag_service, mock_integration_service):
    """Verify /api/v1/query propagates X-Tenant-ID header to rag_service."""
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", True):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_integration_service
        app.dependency_overrides[get_rag_service_dep] = lambda: mock_multi_tenant_rag_service

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={"question": "What is our company policy?"},
                headers={"X-Tenant-ID": "acme_tenant_99"},
            )
            assert response.status_code == status.HTTP_200_OK
            mock_multi_tenant_rag_service.query_documents.assert_called_once()
            call_kwargs = mock_multi_tenant_rag_service.query_documents.call_args.kwargs
            assert call_kwargs.get("tenant_id") == "acme_tenant_99"


def test_document_text_ingest_with_tenant_header(mock_multi_tenant_rag_service, mock_integration_service):
    """Verify /api/v1/documents/text propagates X-Tenant-ID header to rag_service."""
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", True):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_integration_service
        app.dependency_overrides[get_rag_service_dep] = lambda: mock_multi_tenant_rag_service

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documents/text",
                json={"text": "Confidential internal tenant document content."},
                headers={"X-Tenant-ID": "acme_tenant_99"},
            )
            assert response.status_code == status.HTTP_200_OK
            mock_multi_tenant_rag_service.ingest_document.assert_called_once()
            call_kwargs = mock_multi_tenant_rag_service.ingest_document.call_args.kwargs
            assert call_kwargs.get("tenant_id") == "acme_tenant_99"


def test_document_reset_with_tenant_header(mock_multi_tenant_rag_service, mock_integration_service):
    """Verify /api/v1/documents/reset propagates X-Tenant-ID header to rag_service."""
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", True):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_integration_service
        app.dependency_overrides[get_rag_service_dep] = lambda: mock_multi_tenant_rag_service

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documents/reset",
                headers={"X-Tenant-ID": "acme_tenant_99"},
            )
            assert response.status_code == status.HTTP_200_OK
            mock_multi_tenant_rag_service.reset_store.assert_called_once()
            call_kwargs = mock_multi_tenant_rag_service.reset_store.call_args.kwargs
            assert call_kwargs.get("tenant_id") == "acme_tenant_99"


def test_single_tenant_mode_ignores_tenant_header(mock_multi_tenant_rag_service, mock_integration_service):
    """When multi-tenancy is disabled, tenant_id evaluates to None (single-tenant)."""
    with patch("ragbot.api.dependencies.settings.multi_tenant.enabled", False):
        app = create_app(lifespan_context=None)
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_integration_service
        app.dependency_overrides[get_rag_service_dep] = lambda: mock_multi_tenant_rag_service

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query",
                json={"question": "Single tenant question"},
                headers={"X-Tenant-ID": "some_ignored_tenant"},
            )
            assert response.status_code == status.HTTP_200_OK
            mock_multi_tenant_rag_service.query_documents.assert_called_once()
            call_kwargs = mock_multi_tenant_rag_service.query_documents.call_args.kwargs
            assert call_kwargs.get("tenant_id") is None
