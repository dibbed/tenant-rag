"""Integration tests for the shared Redis rate limit store (REQ-MTS-EDGE-002).

They need a Redis server. Set TEST_REDIS_URL; the CI workflow provides a
redis:7-alpine service and uses database 15. Without it the tests are skipped;
tests/unit/test_edge_rate_limit_store.py covers the same logic with a fake
client.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

REDIS_URL = os.getenv("TEST_REDIS_URL", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not REDIS_URL,
        reason="TEST_REDIS_URL is not set; the CI workflow provides a Redis service",
    ),
]


def _redis_client() -> Any:
    import redis.asyncio as redis_asyncio

    return redis_asyncio.Redis.from_url(REDIS_URL)


def _provider(value: Any) -> Callable[[], Any]:
    def provide() -> Any:
        return value

    return provide


async def test_limit_is_exact_under_concurrency():
    from ragbot.api.edge.rate_limit_store import RedisRateLimitStore

    store = RedisRateLimitStore(REDIS_URL, timeout=5.0)
    try:
        subject = f"integration:{uuid.uuid4()}"
        decisions = await asyncio.gather(
            *(store.hit(subject, 10, 60) for _ in range(50))
        )
    finally:
        await store.close()
    assert sum(1 for decision in decisions if decision.allowed) == 10
    assert all(
        decision.retry_after >= 1 for decision in decisions if not decision.allowed
    )
    assert all(decision.store == "redis" for decision in decisions)


async def test_records_expire_with_the_window():
    from ragbot.api.edge.rate_limit_store import RedisRateLimitStore, _redis_key

    store = RedisRateLimitStore(REDIS_URL, timeout=5.0)
    client = _redis_client()
    subject = f"integration:{uuid.uuid4()}"
    try:
        await store.hit(subject, 3, 1)
        ttl = await client.pttl(_redis_key(subject))
        assert 0 < ttl <= 1000
        await asyncio.sleep(1.3)
        assert await client.exists(_redis_key(subject)) == 0
    finally:
        await store.close()
        await client.aclose()


async def test_two_application_instances_share_one_counter(monkeypatch):
    from ragbot.api.app import create_app
    from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
    from ragbot.configs.settings import settings
    from ragbot.services.rag_service import QueryResult

    client = _redis_client()
    await client.flushdb()
    await client.aclose()

    monkeypatch.setenv("SECURITY_RATE_LIMIT_STORAGE_URL", REDIS_URL)
    monkeypatch.delenv("SECURITY_TRUSTED_PROXIES", raising=False)
    monkeypatch.delenv("SECURITY_CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setattr(settings.security, "rate_limit_requests", 3)
    monkeypatch.setattr(settings.security, "rate_limit_window", 60)
    monkeypatch.setattr(settings.multi_tenant, "enabled", False)

    apps = []
    for _ in range(2):
        app = create_app(lifespan_context=None)
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
        integration = MagicMock()
        integration.track_user_action = AsyncMock()
        integration.record_document_type = AsyncMock()
        app.dependency_overrides[get_integration_service_dep] = _provider(integration)
        app.dependency_overrides[get_rag_service_dep] = _provider(rag)
        apps.append(app)

    codes = []
    try:
        for index in range(4):
            transport = httpx.ASGITransport(
                app=apps[index % 2], client=("198.51.100.77", 40000)
            )
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as http:
                response = await http.post("/api/v1/query", json={"question": "hi"})
                codes.append(response.status_code)
    finally:
        for app in apps:
            await app.state.rate_limiter.aclose()
    assert codes == [200, 200, 200, 429]
