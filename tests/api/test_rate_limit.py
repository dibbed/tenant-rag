"""Tests for API sliding-window rate limiting middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from ragbot.api.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def rate_limited_app() -> FastAPI:
    """Create a test application with low rate limit threshold for testing."""
    app = FastAPI()
    # 3 requests per 10-second window for testing
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=3,
        window_seconds=10,
        exempt_paths={"/health", "/docs"},
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/resource")
    def resource():
        return {"data": "resource_content"}

    return app


def test_rate_limit_headers_and_success_under_threshold(rate_limited_app):
    """Requests under limit succeed and contain X-RateLimit headers."""
    client = TestClient(rate_limited_app)

    resp1 = client.get("/api/resource")
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.headers["X-RateLimit-Limit"] == "3"
    assert resp1.headers["X-RateLimit-Remaining"] == "2"

    resp2 = client.get("/api/resource")
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.headers["X-RateLimit-Remaining"] == "1"


def test_rate_limit_exceeded_returns_429(rate_limited_app):
    """Requests exceeding limit receive 429 Too Many Requests with Retry-After header."""
    client = TestClient(rate_limited_app)

    # 3 requests allowed
    for _ in range(3):
        r = client.get("/api/resource")
        assert r.status_code == status.HTTP_200_OK

    # 4th request must be blocked
    blocked = client.get("/api/resource")
    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in blocked.headers
    data = blocked.json()
    assert "Rate limit exceeded" in data["detail"]
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_exempt_paths_never_blocked(rate_limited_app):
    """Exempt endpoints (/health) are never throttled even under burst traffic."""
    client = TestClient(rate_limited_app)

    # Spam 10 requests to exempt path
    for _ in range(10):
        resp = client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {"status": "ok"}


def test_rate_limit_disabled():
    """When rate limiting is disabled, requests pass through unrestricted."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60, enabled=False)

    @app.get("/test")
    def test_ep():
        return {"ok": True}

    client = TestClient(app)
    for _ in range(5):
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_200_OK
