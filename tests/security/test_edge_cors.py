"""Phase 3 regression tests: browser calls only from allowed origins.

Audit finding C10 (docs/BASELINE_AUDIT.md), requirement REQ-MTS-EDGE-003.

Vulnerability: CORS allowed every origin with credentials
(allow_origins=["*"], allow_credentials=True), so any website could call the
API from a user's browser and read the answers.

Expected behavior: no origin is allowed by default.
SECURITY_CORS_ALLOWED_ORIGINS lists the allowed origins. '*' allows every
origin without credentials and is accepted only with ENVIRONMENT=development,
so production must list its origins. Invalid entries stop startup.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ALLOWED = "https://app.example.com"
EVIL = "https://evil.example"
QUERY = {"question": "hello"}
REQUESTED_HEADERS = "authorization,content-type,x-api-key,x-tenant-id"


def preflight(client: TestClient, origin: str):
    return client.options(
        "/api/v1/query",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": REQUESTED_HEADERS,
        },
    )


@pytest.mark.parametrize("environment", ["production", "development"])
def test_no_origin_is_allowed_by_default(edge_app, environment):
    app, _ = edge_app(environment=environment)
    with TestClient(app) as client:
        pre = preflight(client, EVIL)
        simple = client.post("/api/v1/query", json=QUERY, headers={"Origin": EVIL})
        health = client.get(
            "/health", headers={"Origin": ALLOWED, "Cookie": "session=1"}
        )
    assert pre.status_code == 400
    assert "access-control-allow-origin" not in pre.headers
    assert "access-control-allow-origin" not in simple.headers
    assert "access-control-allow-credentials" not in simple.headers
    assert "access-control-allow-origin" not in health.headers


def test_allowed_origin_is_permitted(edge_app):
    app, _ = edge_app(cors_origins=ALLOWED, environment="production")
    with TestClient(app) as client:
        pre = preflight(client, ALLOWED)
        simple = client.get("/health", headers={"Origin": ALLOWED})
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == ALLOWED
    assert pre.headers["access-control-allow-credentials"] == "true"
    assert "POST" in pre.headers["access-control-allow-methods"]
    allowed_headers = pre.headers["access-control-allow-headers"].lower()
    for header in ("authorization", "content-type", "x-api-key", "x-tenant-id"):
        assert header in allowed_headers
    assert simple.headers["access-control-allow-origin"] == ALLOWED
    assert "origin" in simple.headers.get("vary", "").lower()
    exposed = simple.headers["access-control-expose-headers"].lower()
    assert "retry-after" in exposed
    assert "x-ratelimit-remaining" in exposed


@pytest.mark.parametrize(
    "origin",
    [
        EVIL,
        "http://app.example.com",
        "https://app.example.com:8443",
        "https://sub.app.example.com",
        "https://app.example.com.evil.test",
        "null",
    ],
)
def test_origins_that_are_not_listed_are_rejected(edge_app, origin):
    app, _ = edge_app(cors_origins=ALLOWED, environment="production")
    with TestClient(app) as client:
        pre = preflight(client, origin)
        simple = client.get("/health", headers={"Origin": origin})
    assert pre.status_code == 400
    assert "access-control-allow-origin" not in pre.headers
    assert "access-control-allow-origin" not in simple.headers


def test_request_without_origin_gets_no_cors_headers(edge_app):
    app, _ = edge_app(cors_origins=ALLOWED, environment="development")
    with TestClient(app) as client:
        response = client.post("/api/v1/query", json=QUERY)
    assert response.status_code == 200
    assert not [
        name for name in response.headers if name.lower().startswith("access-control-")
    ]


def test_development_allows_the_wildcard_without_credentials(edge_app):
    app, _ = edge_app(cors_origins="*", environment="development")
    with TestClient(app) as client:
        pre = preflight(client, EVIL)
        simple = client.post("/api/v1/query", json=QUERY, headers={"Origin": EVIL})
        with_cookie = client.post(
            "/api/v1/query", json=QUERY, headers={"Origin": EVIL, "Cookie": "session=1"}
        )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in pre.headers
    assert simple.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in simple.headers
    assert "access-control-allow-credentials" not in with_cookie.headers


def test_development_does_not_allow_local_origins_by_itself(edge_app):
    local = "http://localhost:3000"
    app, _ = edge_app(environment="development")
    with TestClient(app) as client:
        refused = preflight(client, local)
    listed_app, _ = edge_app(cors_origins=local, environment="development")
    with TestClient(listed_app) as client:
        allowed = preflight(client, local)
    assert refused.status_code == 400
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == local


@pytest.mark.parametrize("environment", ["production", "staging", ""])
def test_production_rejects_the_wildcard(edge_app, environment):
    with pytest.raises(ValueError, match="SECURITY_CORS_ALLOWED_ORIGINS"):
        edge_app(cors_origins="*", environment=environment)


def test_production_accepts_an_explicit_list(edge_app):
    app, _ = edge_app(
        cors_origins="https://app.example.com, https://admin.example.com/",
        environment="production",
    )
    assert app.state.edge_config.cors.origins == (
        "https://app.example.com",
        "https://admin.example.com",
    )
    with TestClient(app) as client:
        allowed = preflight(client, "https://admin.example.com")
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://admin.example.com"


@pytest.mark.parametrize(
    "value",
    [
        "https://*.example.com",
        "null",
        "ftp://app.example.com",
        "app.example.com",
        "https://app.example.com/path",
        "https://user@app.example.com",
        "https://app.example.com?x=1",
    ],
)
def test_invalid_origin_entries_stop_startup(edge_app, value):
    with pytest.raises(ValueError, match="SECURITY_CORS_ALLOWED_ORIGINS"):
        edge_app(cors_origins=value, environment="development")


def test_rate_limit_and_size_errors_are_readable_by_allowed_origins(edge_app):
    app, _ = edge_app(limit=1, cors_origins=ALLOWED, environment="development")
    with TestClient(app) as client:
        client.post("/api/v1/query", json=QUERY, headers={"Origin": ALLOWED})
        limited = client.post("/api/v1/query", json=QUERY, headers={"Origin": ALLOWED})
    assert limited.status_code == 429
    assert limited.headers["access-control-allow-origin"] == ALLOWED
    size_app, _ = edge_app(
        limit=5, upload_mb=1, cors_origins=ALLOWED, environment="development"
    )
    with TestClient(size_app) as client:
        too_large = client.post(
            "/api/v1/documents/upload",
            files={"file": ("big.txt", b"a" * (2 * 1024 * 1024), "text/plain")},
            headers={"Origin": ALLOWED},
        )
    assert too_large.status_code == 413
    assert too_large.headers["access-control-allow-origin"] == ALLOWED


def test_preflight_requests_do_not_use_the_rate_limit(edge_app):
    app, _ = edge_app(limit=2, cors_origins=ALLOWED, environment="development")
    with TestClient(app) as client:
        codes = [preflight(client, ALLOWED).status_code for _ in range(5)]
        response = client.post("/api/v1/query", json=QUERY, headers={"Origin": ALLOWED})
    assert codes == [200] * 5
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Remaining"] == "1"


def test_cors_does_not_replace_authentication(edge_app):
    app, rag = edge_app(
        cors_origins=ALLOWED,
        environment="development",
        multi_tenant=True,
        principals={},
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/query", json=QUERY, headers={"Origin": EVIL})
    assert response.status_code == 401
    assert "access-control-allow-origin" not in response.headers
    rag.query_documents.assert_not_called()


def test_middleware_order_puts_cors_before_rate_limiting():
    from fastapi.middleware.cors import CORSMiddleware

    from ragbot.api.app import create_app
    from ragbot.api.middleware.body_size_limit import BodySizeLimitMiddleware
    from ragbot.api.middleware.rate_limit import RateLimitMiddleware
    from ragbot.api.middleware.trusted_proxy import TrustedProxyMiddleware

    app = create_app(lifespan_context=None)
    assert [middleware.cls for middleware in app.user_middleware] == [
        TrustedProxyMiddleware,
        CORSMiddleware,
        RateLimitMiddleware,
        BodySizeLimitMiddleware,
    ]
