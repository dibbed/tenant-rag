"""Comprehensive API-First backend tests.

Verifies application lifecycle, health endpoints, query pipeline integration,
document ingestion, store reset, error translation, and absence of Telegram coupling.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api.app import app, create_app
from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.rag.exceptions import EmbeddingError, VectorStoreError
from ragbot.services.rag_service import IngestResult, QueryResult


@pytest.fixture
def mock_integration_service():
    """Mock integration service providing mocked RAG and health services."""
    service = MagicMock()
    service.health_check = AsyncMock(
        return_value={
            "status": "healthy",
            "timestamp": 1234567890.0,
            "components": {
                "rag_service": {"status": "healthy"},
                "vector_store": {"status": "healthy"},
            },
            "issues": [],
        }
    )
    service.track_user_action = AsyncMock()
    service.record_document_type = AsyncMock()

    mock_rag = MagicMock()
    mock_rag.query_documents = AsyncMock(
        return_value=QueryResult(
            answer="RAG is Retrieval-Augmented Generation.",
            sources=["doc1.pdf", "doc2.txt"],
            confidence_score=0.92,
            processing_time=0.15,
            language="en",
            retrieved_chunks=["chunk 1 content", "chunk 2 content"],
            metadata={"model": "gpt-4"},
        )
    )
    mock_rag.ingest_document = AsyncMock(
        return_value=IngestResult(
            success=True,
            document_id="doc_test_123",
            chunks_created=5,
            processing_time=0.25,
            metadata={"filename": "sample.pdf"},
        )
    )
    mock_rag.reset_store = AsyncMock(return_value=True)
    service.get_rag_service.return_value = mock_rag
    service.components = {"rag_service": mock_rag}
    return service


@pytest.fixture
def client(mock_integration_service):
    """FastAPI TestClient with overridden service dependencies."""
    test_app = create_app()

    test_app.dependency_overrides[get_integration_service_dep] = (
        lambda: mock_integration_service
    )
    test_app.dependency_overrides[get_rag_service_dep] = (
        lambda: mock_integration_service.get_rag_service()
    )

    with TestClient(test_app) as tc:
        yield tc

    test_app.dependency_overrides.clear()


class TestApiApplicationLifecycle:
    """Verify application lifecycle, startup/shutdown, and state isolation."""

    def test_app_imports_without_telegram_credentials(self):
        """API module imports cleanly without requiring any Telegram environment."""
        import ragbot.api

        assert hasattr(ragbot.api, "app")
        assert hasattr(ragbot.api, "create_app")

    def test_application_lifespan(self):
        """Application startup initializes services and shutdown releases them."""
        with patch(
            "ragbot.api.app.get_integration_service", new_callable=AsyncMock
        ) as mock_get_svc, patch(
            "ragbot.api.app.shutdown_integration_service", new_callable=AsyncMock
        ) as mock_shutdown:
            mock_svc = MagicMock()
            mock_svc.get_rag_service.return_value = MagicMock()
            mock_get_svc.return_value = mock_svc

            custom_app = create_app()
            with TestClient(custom_app):
                assert mock_get_svc.called
                assert custom_app.state.integration_service == mock_svc

            assert mock_shutdown.called

    def test_services_not_recreated_per_request(self, client, mock_integration_service):
        """Shared service instances are reused across sequential requests."""
        resp1 = client.get("/health")
        resp2 = client.get("/health")
        assert resp1.status_code == status.HTTP_200_OK
        assert resp2.status_code == status.HTTP_200_OK
        assert mock_integration_service.health_check.call_count == 2


class TestHealthRoutes:
    """Verify /health and /api/v1/health endpoints."""

    def test_health_endpoints_healthy(self, client, mock_integration_service):
        """Healthy status returns 200 with structured component breakdown."""
        for endpoint in ["/health", "/api/v1/health"]:
            response = client.get(endpoint)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["timestamp"] == 1234567890.0
            assert "rag_service" in data["components"]

    def test_health_endpoint_unhealthy_status(self, client, mock_integration_service):
        """Unhealthy status returns HTTP 503 Service Unavailable."""
        mock_integration_service.health_check.return_value = {
            "status": "unhealthy",
            "timestamp": 1234567890.0,
            "components": {"vector_store": {"status": "unhealthy"}},
            "issues": ["Vector store unreachable"],
        }
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "unhealthy"
        assert len(data["issues"]) > 0

    def test_health_endpoint_exception_handling(self, client, mock_integration_service):
        """Health check exceptions are caught and represented as 503 without crashing."""
        mock_integration_service.health_check.side_effect = RuntimeError(
            "Service check exploded"
        )
        response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "unhealthy"


class TestQueryRoutes:
    """Verify /api/v1/query endpoint."""

    def test_query_success(self, client, mock_integration_service):
        """Valid query reaches RAG service and preserves structured responses."""
        payload = {"question": "What is RAG?", "language": "en"}
        response = client.post("/api/v1/query", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["answer"] == "RAG is Retrieval-Augmented Generation."
        assert data["sources"] == ["doc1.pdf", "doc2.txt"]
        assert data["confidence_score"] == 0.92
        assert data["language"] == "en"
        assert len(data["retrieved_chunks"]) == 2

    def test_query_validation_error(self, client):
        """Missing or empty question triggers 422 Unprocessable Entity."""
        response = client.post("/api/v1/query", json={"question": ""})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_embedding_provider_error(self, client, mock_integration_service):
        """Model provider error maps to HTTP 503 without leaking stacktrace."""
        mock_rag = mock_integration_service.get_rag_service()
        mock_rag.query_documents.side_effect = EmbeddingError("API key quota exceeded")

        response = client.post("/api/v1/query", json={"question": "Test question"})
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "Model provider service unavailable" in data["detail"]

    def test_query_vector_store_error(self, client, mock_integration_service):
        """Vector store query error maps to HTTP 500 without leaking internals."""
        mock_rag = mock_integration_service.get_rag_service()
        mock_rag.query_documents.side_effect = VectorStoreError("Index corrupted")

        response = client.post("/api/v1/query", json={"question": "Test question"})
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "Vector store query failure" in data["detail"]


class TestDocumentIngestRoutes:
    """Verify document upload, text ingestion, URL ingestion, and store reset."""

    def test_upload_document_success(self, client, mock_integration_service):
        """Valid file upload reaches RAG service and cleans up temp files."""
        captured_path: list[Path] = []
        original_ingest = mock_integration_service.get_rag_service().ingest_document

        async def capture_temp_file(source, *args, **kwargs):
            p = Path(source)
            captured_path.append(p)
            assert p.exists()  # Temp file must exist during ingestion
            return await original_ingest(source, *args, **kwargs)

        mock_rag = mock_integration_service.get_rag_service()
        mock_rag.ingest_document.side_effect = capture_temp_file

        file_content = b"%PDF-1.4 Mock PDF content for RAG testing"
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("manual.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["document_id"] == "doc_test_123"

        # Verify temp file was cleaned up
        assert len(captured_path) == 1
        assert not captured_path[0].exists()

    def test_upload_document_unsupported_format(self, client):
        """Disallowed file extension returns HTTP 415 Unsupported Media Type."""
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("malicious.exe", io.BytesIO(b"bad"), "application/x-msdownload")},
        )
        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

    def test_upload_temp_cleanup_on_failure(self, client, mock_integration_service):
        """Temporary file is reliably deleted even if ingestion raises an exception."""
        captured_path: list[Path] = []

        async def failing_ingest(source, *args, **kwargs):
            p = Path(source)
            captured_path.append(p)
            raise RuntimeError("Parser crashed unexpectedly")

        mock_rag = mock_integration_service.get_rag_service()
        mock_rag.ingest_document.side_effect = failing_ingest

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("broken.pdf", io.BytesIO(b"%PDF content"), "application/pdf")},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert len(captured_path) == 1
        assert not captured_path[0].exists()

    def test_text_ingest_success(self, client, mock_integration_service):
        """Direct text ingestion succeeds and returns structured IngestResponse."""
        payload = {
            "text": "Antigravity is an advanced coding agent architecture.",
            "title": "Agent Overview",
        }
        response = client.post("/api/v1/documents/text", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["chunks_created"] == 5

    def test_text_ingest_empty_rejected(self, client):
        """Empty text payload is rejected with 400 or 422."""
        response = client.post("/api/v1/documents/text", json={"text": "   "})
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_url_ingest_success(self, client, mock_integration_service):
        """Valid HTTP URL is passed to document ingestion service."""
        payload = {"url": "https://example.com/docs/rag-architecture"}
        response = client.post("/api/v1/documents/url", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_url_ingest_invalid_scheme(self, client):
        """Non-HTTP URL is rejected with 400 Bad Request."""
        payload = {"url": "ftp://files.example.com/doc.pdf"}
        response = client.post("/api/v1/documents/url", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reset_store_success(self, client, mock_integration_service):
        """Store reset clears vector store and returns ResetResponse."""
        with patch("ragbot.api.routes.documents.cache_manager") as mock_cache:
            mock_cache.initialize = AsyncMock()
            mock_cache.clear = AsyncMock(return_value=True)
            mock_cache.clear_semantic_cache = AsyncMock(return_value=True)

            response = client.post("/api/v1/documents/reset")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["cache_cleared"] is True


class TestNoTelegramRuntimeCoupling:
    """Verify complete removal of aiogram and Telegram runtime dependencies."""

    def test_no_production_import_references_aiogram(self):
        """No Python file under ragbot/ imports aiogram."""
        root_dir = Path(__file__).resolve().parent.parent.parent / "ragbot"
        violating_files = []

        for py_path in root_dir.rglob("*.py"):
            content = py_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                stripped = line.strip()
                if (
                    stripped.startswith("import aiogram")
                    or stripped.startswith("from aiogram")
                    or "import aiogram" in stripped
                ):
                    violating_files.append((str(py_path), stripped))

        assert not violating_files, f"Found residual aiogram imports: {violating_files}"
