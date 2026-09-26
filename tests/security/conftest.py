"""Shared fixtures for the Phase 3 edge protection regression tests.

Audit findings C9, C10 and C11 (docs/BASELINE_AUDIT.md). The fixtures build
the real application with ``create_app`` and replace only the RAG and
integration services.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
)
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ragbot.configs.settings import settings
from ragbot.services.rag_service import IngestResult, QueryResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

EDGE_ENV_VARS = (
    "SECURITY_TRUSTED_PROXIES",
    "SECURITY_CORS_ALLOWED_ORIGINS",
    "SECURITY_RATE_LIMIT_STORAGE_URL",
)
MULTIPART_BOUNDARY = "edgeprotectionboundary"


def _mock_rag() -> MagicMock:
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
            success=True,
            document_id="doc_1",
            chunks_created=1,
            processing_time=0.01,
            metadata={},
        )
    )
    rag.reset_store = AsyncMock(return_value=True)
    return rag


def _mock_integration() -> MagicMock:
    integration = MagicMock()
    integration.health_check = AsyncMock(
        return_value={
            "status": "healthy",
            "timestamp": 1.0,
            "components": {},
            "issues": [],
        }
    )
    integration.track_user_action = AsyncMock()
    integration.record_document_type = AsyncMock()
    integration.components = {}
    return integration


def _provider(value: Any) -> Callable[[], Any]:
    def provide() -> Any:
        return value

    return provide


@pytest.fixture
def edge_app(monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[Any, MagicMock]]:
    """Factory for the real application with edge protection settings.

    ``principals`` maps credential values to AuthenticatedPrincipal objects;
    every other credential fails authentication.
    """
    from ragbot.api.app import create_app
    from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep

    for name in EDGE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    def build(
        *,
        limit: int = 5,
        window: int = 60,
        upload_mb: int = 50,
        trusted_proxies: str | None = None,
        cors_origins: str | None = None,
        storage_url: str | None = None,
        environment: str | None = None,
        multi_tenant: bool = False,
        principals: dict[str, Any] | None = None,
    ) -> tuple[Any, MagicMock]:
        for name, value in (
            ("SECURITY_TRUSTED_PROXIES", trusted_proxies),
            ("SECURITY_CORS_ALLOWED_ORIGINS", cors_origins),
            ("SECURITY_RATE_LIMIT_STORAGE_URL", storage_url),
            ("ENVIRONMENT", environment),
        ):
            if value is not None:
                monkeypatch.setenv(name, value)
        monkeypatch.setattr(settings.security, "rate_limit_requests", limit)
        monkeypatch.setattr(settings.security, "rate_limit_window", window)
        monkeypatch.setattr(settings.security, "max_file_size_mb", upload_mb)
        monkeypatch.setattr(settings.multi_tenant, "enabled", multi_tenant)

        app = create_app(lifespan_context=None)
        rag = _mock_rag()
        if principals is not None:
            known = dict(principals)

            async def authenticate(credential: str) -> tuple[bool, Any, str | None]:
                principal = known.get(credential)
                if principal is None:
                    return False, None, "Invalid API key"
                return True, principal, None

            rag.tenant_auth = MagicMock()
            rag.tenant_auth.authenticate_principal = AsyncMock(side_effect=authenticate)
        app.dependency_overrides[get_integration_service_dep] = _provider(
            _mock_integration()
        )
        app.dependency_overrides[get_rag_service_dep] = _provider(rag)
        return app, rag

    return build


@pytest.fixture
def peer_client() -> Callable[[Any, str], httpx.AsyncClient]:
    """Factory for an HTTP client whose requests come from one TCP peer."""

    def build(app: Any, peer: str) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app, client=(peer, 40000))
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    return build


@dataclass
class AsgiResult:
    """Response of a direct ASGI call, with body read statistics."""

    status: int
    headers: dict[str, str]
    body: bytes
    receive_calls: int
    bytes_sent: int

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def multipart_upload(
    size: int, *, filename: str = "upload.txt", chunk_size: int = 64 * 1024
) -> tuple[list[tuple[str, str]], Iterator[bytes], int]:
    """Return (headers, body chunks, total length) for a one-file upload.

    The file content is generated chunk by chunk and never held in memory.
    """
    head = (
        f"--{MULTIPART_BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode()
    tail = f"\r\n--{MULTIPART_BOUNDARY}--\r\n".encode()

    def chunks() -> Iterator[bytes]:
        yield head
        block = b"a" * chunk_size
        remaining = size
        while remaining > 0:
            count = min(chunk_size, remaining)
            yield block if count == chunk_size else block[:count]
            remaining -= count
        yield tail

    headers = [("content-type", f"multipart/form-data; boundary={MULTIPART_BOUNDARY}")]
    return headers, chunks(), len(head) + size + len(tail)


@pytest.fixture
def multipart() -> Callable[..., tuple[list[tuple[str, str]], Iterator[bytes], int]]:
    """The multipart_upload helper."""
    return multipart_upload


@pytest.fixture
def asgi_call() -> Callable[..., Any]:
    """Call the ASGI application directly with a chunked request body.

    The result reports how often the application asked for body data and how
    many body bytes it received, so tests can prove when reading stopped.
    Like a real server, ``receive`` waits once the body is complete (the
    client stays connected) and reports a disconnect only after 5 seconds.
    """

    async def call(
        app: Any,
        *,
        path: str,
        chunks: Iterable[bytes],
        headers: Sequence[tuple[str, str]] = (),
        method: str = "POST",
        peer: str = "198.51.100.99",
    ) -> AsgiResult:
        iterator = iter(chunks)
        receive_calls = 0
        bytes_sent = 0
        finished = False
        messages: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            nonlocal receive_calls, bytes_sent, finished
            receive_calls += 1
            if finished:
                await asyncio.sleep(5)
                return {"type": "http.disconnect"}
            chunk = next(iterator, None)
            if chunk is None:
                finished = True
                return {"type": "http.request", "body": b"", "more_body": False}
            bytes_sent += len(chunk)
            return {"type": "http.request", "body": chunk, "more_body": True}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in headers
            ],
            "client": (peer, 40000),
            "server": ("testserver", 80),
            "state": {},
        }
        await app(scope, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(
            m.get("body", b"") for m in messages if m["type"] == "http.response.body"
        )
        response_headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in start.get("headers", [])
        }
        return AsgiResult(
            start["status"], response_headers, body, receive_calls, bytes_sent
        )

    return call
