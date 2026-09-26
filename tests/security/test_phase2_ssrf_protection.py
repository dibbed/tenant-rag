"""Phase 2 regression tests: SSRF protection for URL ingestion.

Audit finding C6 (docs/BASELINE_AUDIT.md).

Vulnerability: POST /api/v1/documents/url fetched any http(s) URL, redirects
were followed automatically, and HTMLLoader had no host check at all. A
caller could make the server read localhost services, private networks and
cloud metadata endpoints, and then read the content back through queries.

Expected behavior: internal, private, link-local and metadata targets are
blocked before any request, on every redirect hop, and when DNS resolves a
host name to such an address. Public URLs keep working.
"""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api.app import create_app
from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders import url_guard
from ragbot.rag.loaders.html_loader import HTMLLoader
from ragbot.rag.loaders.url import URLLoader
from ragbot.rag.loaders.url_guard import (
    SafeResolver,
    UnsafeURLError,
    resolve_redirect_target,
    validate_url_target,
)
from ragbot.services.rag_service import IngestResult

BLOCKED_URLS = [
    "http://localhost",
    "http://localhost:8000/admin",
    "http://LOCALHOST/",
    "http://localhost./",
    "http://app.localhost/",
    "http://127.0.0.1",
    "http://127.0.0.1:6333/collections",
    "http://127.1/",
    "http://2130706433/",
    "http://0.0.0.0/",
    "http://10.0.0.5/",
    "http://172.16.0.1/",
    "http://192.168.1.10/",
    "http://100.64.0.1/",
    "http://169.254.169.254",
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.170.2/v2/credentials",
    "http://100.100.100.200/latest/meta-data/",
    "http://168.63.129.16/machine",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://service.internal/",
    "http://printer.local/",
    "http://[::1]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://[fd00:ec2::254]/latest/meta-data/",
    "http://[::ffff:127.0.0.1]/",
    "http://[::ffff:169.254.169.254]/",
    "http://[64:ff9b::a00:1]/",
    "http://user:pass@127.0.0.1/",
    "http://example.com" + chr(92) + "@127.0.0.1/",
    "file:///etc/passwd",
    "ftp://example.com/file",
    "gopher://127.0.0.1:6379/_INFO",
    "http:///no-host",
    "",
]

ALLOWED_URLS = [
    "https://example.com/docs",
    "https://www.python.org/",
    "https://example.com:8443/path?q=1",
    "http://93.184.216.34/",
    "https://[2606:4700:4700::1111]/",
]


class FakeResolver:
    def __init__(self, addresses):
        self.addresses = list(addresses)
        self.calls = 0

    async def resolve(self, host, port=0, family=socket.AF_INET):
        self.calls += 1
        return [
            {
                "hostname": host,
                "host": address,
                "port": port,
                "family": socket.AF_INET6 if ":" in address else socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
            for address in self.addresses
        ]

    async def close(self):
        return None


def _requested_hosts(mocked):
    return {str(key[1].host) for key in mocked.requests}


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_url_guard_blocks_internal_and_metadata_targets(url):
    with pytest.raises(UnsafeURLError):
        validate_url_target(url)


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_url_guard_allows_public_targets(url):
    assert validate_url_target(url) == url


def test_redirect_targets_are_validated():
    with pytest.raises(UnsafeURLError):
        resolve_redirect_target("https://example.com/a", "http://127.0.0.1/admin")
    with pytest.raises(UnsafeURLError):
        resolve_redirect_target("https://example.com/a", "//169.254.169.254/latest/")
    assert resolve_redirect_target("https://example.com/a/b", "/c") == "https://example.com/c"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addresses",
    [["127.0.0.1"], ["10.1.2.3"], ["169.254.169.254"], ["93.184.216.34", "192.168.0.7"], ["::1"]],
)
async def test_safe_resolver_blocks_hosts_that_resolve_to_internal_addresses(addresses):
    resolver = SafeResolver(inner=FakeResolver(addresses))
    with pytest.raises(UnsafeURLError):
        await resolver.resolve("innocent-looking.example", 80)


@pytest.mark.asyncio
async def test_safe_resolver_allows_public_addresses():
    resolver = SafeResolver(inner=FakeResolver(["93.184.216.34"]))
    results = await resolver.resolve("example.com", 443)
    assert results[0]["host"] == "93.184.216.34"


@pytest.mark.asyncio
async def test_safe_resolver_rejects_blocked_hostname_without_dns_lookup():
    inner = FakeResolver(["93.184.216.34"])
    with pytest.raises(UnsafeURLError):
        await SafeResolver(inner=inner).resolve("metadata.google.internal", 80)
    assert inner.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["http://localhost/admin", "http://127.0.0.1:8080/", "http://169.254.169.254/latest/meta-data/"],
)
async def test_url_loader_blocks_internal_targets_without_sending_a_request(url):
    with aioresponses() as mocked:
        mocked.get(url, status=200, body="INTERNAL-SECRET")
        with pytest.raises(DocumentProcessingError):
            await URLLoader().load(url)
        assert not mocked.requests


@pytest.mark.asyncio
async def disabled_url_loader_blocks_redirect_to_cloud_metadata():
    start = "https://example.com/start"
    metadata = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    with aioresponses() as mocked:
        mocked.get(start, status=302, headers={"Location": metadata})
        mocked.get(metadata, status=200, body="AWS-SECRET-ACCESS-KEY")
        with pytest.raises(DocumentProcessingError) as exc_info:
            await URLLoader().load(start)
        assert "169.254.169.254" not in _requested_hosts(mocked)
    assert "not allowed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_url_loader_blocks_hostname_that_resolves_to_private_address(monkeypatch):
    monkeypatch.setattr(url_guard, "ThreadedResolver", lambda *a, **k: FakeResolver(["10.0.0.7"]))
    with pytest.raises(DocumentProcessingError) as exc_info:
        await URLLoader().load("http://internal-app.test/page")
    assert "blocked address" in str(exc_info.value)


@pytest.mark.asyncio
async def test_url_loader_still_follows_safe_redirects():
    start = "https://example.com/start"
    final = "https://example.com/final"
    with aioresponses() as mocked:
        mocked.get(start, status=301, headers={"Location": final})
        mocked.get(final, status=200, body="<html><body><h1>Public page</h1></body></html>", headers={"content-type": "text/html"})
        document = await URLLoader().load(start)
    assert "Public page" in document.content


@pytest.mark.asyncio
async def test_html_loader_blocks_internal_url_without_sending_a_request():
    url = "http://127.0.0.1:8080/admin"
    with aioresponses() as mocked:
        mocked.get(url, status=200, body="<html><body>INTERNAL</body></html>")
        with pytest.raises(DocumentProcessingError):
            await HTMLLoader().load(url)
        assert not mocked.requests


@pytest.mark.asyncio
async def test_html_loader_blocks_redirect_to_private_address():
    start = "https://example.com/page"
    internal = "http://10.0.0.8/"
    with aioresponses() as mocked:
        mocked.get(start, status=302, headers={"Location": internal})
        mocked.get(internal, status=200, body="<html><body>INTERNAL</body></html>")
        with pytest.raises(DocumentProcessingError):
            await HTMLLoader().load(start)
        assert "10.0.0.8" not in _requested_hosts(mocked)


@pytest.fixture
def url_api():
    rag = MagicMock()
    rag.ingest_document = AsyncMock(
        return_value=IngestResult(
            success=True, document_id="doc_1", chunks_created=1, processing_time=0.01, metadata={}
        )
    )
    integration = MagicMock()
    integration.track_user_action = AsyncMock()
    integration.record_document_type = AsyncMock()
    app = create_app(lifespan_context=None)
    app.dependency_overrides[get_integration_service_dep] = lambda: integration
    app.dependency_overrides[get_rag_service_dep] = lambda: rag
    with TestClient(app) as client:
        yield client, rag


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://169.254.169.254",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://10.0.0.5/internal",
    ],
)
def test_url_ingest_api_rejects_internal_targets(url_api, url):
    client, rag = url_api
    response = client.post("/api/v1/documents/url", json={"url": url})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "URL target is not allowed"
    rag.ingest_document.assert_not_called()


def test_url_ingest_api_accepts_public_https_url(url_api):
    client, rag = url_api
    response = client.post("/api/v1/documents/url", json={"url": "https://example.com/docs/page"})
    assert response.status_code == status.HTTP_200_OK
    rag.ingest_document.assert_called_once()
