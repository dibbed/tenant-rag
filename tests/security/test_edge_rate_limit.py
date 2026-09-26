"""Phase 3 regression tests: rate limits count the real caller.

Audit finding C9 (docs/BASELINE_AUDIT.md), requirements REQ-MTS-EDGE-001 and
REQ-MTS-EDGE-002.

Vulnerability: the rate limiter used the first X-Forwarded-For entry as the
client address. A client that sent a new forged value with every request was
never limited. Authenticated requests counted against the address instead of
the principal, and rate limit records were never deleted.

Expected behavior: without a trusted proxy, forwarded headers are ignored and
the TCP peer is the Client Address. Behind a trusted proxy, the address the
proxy reports is used. Authenticated requests count against the Principal;
other requests, failed authentication attempts included, count against the
Client Address. Health checks are never limited.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.multi_tenant.models import AuthenticatedPrincipal

QUERY = {"question": "What is edge protection?"}
QUERY_PATH = "/api/v1/query"


def forged_headers(index: int) -> dict[str, str]:
    """Every common header that claims a client address, with a new value."""
    address = f"203.0.113.{index + 1}"
    return {
        "X-Forwarded-For": address,
        "X-Real-IP": address,
        "Forwarded": f"for={address}",
        "CF-Connecting-IP": address,
        "True-Client-IP": address,
        "X-Client-IP": address,
    }


def make_principal(key_id: str, tenant_id: str = "tenant-a") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_id=key_id,
        identity_type="api_key",
        tenant_id=tenant_id,
        role="user",
        permissions=["api_access", "ask_questions"],
    )


async def _codes(client, count: int, headers: dict[str, str]) -> list[int]:
    codes = []
    for _ in range(count):
        response = await client.post(QUERY_PATH, json=QUERY, headers=headers)
        codes.append(response.status_code)
    return codes


# Forged forwarding headers and trusted proxies


async def test_forged_forwarding_headers_do_not_bypass_the_limit(edge_app, peer_client):
    app, rag = edge_app(limit=3)
    codes = []
    async with peer_client(app, "198.51.100.10") as client:
        for index in range(4):
            response = await client.post(
                QUERY_PATH, json=QUERY, headers=forged_headers(index)
            )
            codes.append(response.status_code)
    assert codes == [200, 200, 200, 429]
    assert rag.query_documents.await_count == 3


async def test_trusted_proxy_disabled_ignores_forwarded_headers(edge_app, peer_client):
    app, _ = edge_app(limit=2)
    codes = []
    async with peer_client(app, "127.0.0.1") as local:
        for index in range(3):
            response = await local.post(
                QUERY_PATH,
                json=QUERY,
                headers={"X-Forwarded-For": f"198.51.100.{index}"},
            )
            codes.append(response.status_code)
    async with peer_client(app, "127.0.0.2") as other:
        other_code = (await other.post(QUERY_PATH, json=QUERY)).status_code
    assert codes == [200, 200, 429]
    assert other_code == 200


async def test_trusted_proxy_enabled_uses_the_reported_client(edge_app, peer_client):
    app, _ = edge_app(limit=2, trusted_proxies="10.0.0.0/8")
    async with peer_client(app, "10.0.0.2") as proxy:
        first = await _codes(proxy, 3, {"X-Forwarded-For": "198.51.100.7"})
        # The client adds a forged entry; the proxy appends the real address.
        forged_prefix = await _codes(
            proxy, 1, {"X-Forwarded-For": "1.1.1.1, 198.51.100.7"}
        )
        second = await _codes(proxy, 2, {"X-Forwarded-For": "198.51.100.8"})
    assert first == [200, 200, 429]
    assert forged_prefix == [429]
    assert second == [200, 200]


async def test_trusted_proxy_chain_uses_the_first_untrusted_address(
    edge_app, peer_client
):
    app, _ = edge_app(limit=1, trusted_proxies="10.0.0.0/8, 192.0.2.10")
    async with peer_client(app, "10.0.0.2") as proxy:
        first = await _codes(proxy, 1, {"X-Forwarded-For": "198.51.100.20, 192.0.2.10"})
        again = await _codes(
            proxy, 1, {"X-Forwarded-For": "203.0.113.50, 198.51.100.20, 192.0.2.10"}
        )
    assert first == [200]
    assert again == [429]


async def test_forwarded_header_from_an_untrusted_peer_is_ignored(
    edge_app, peer_client
):
    app, _ = edge_app(limit=2, trusted_proxies="10.0.0.0/8")
    codes = []
    async with peer_client(app, "203.0.113.9") as client:
        for index in range(3):
            response = await client.post(
                QUERY_PATH,
                json=QUERY,
                headers={"X-Forwarded-For": f"198.51.100.{index}"},
            )
            codes.append(response.status_code)
    assert codes == [200, 200, 429]


async def test_ipv6_clients_in_one_64_network_share_a_counter(edge_app, peer_client):
    app, _ = edge_app(limit=2)
    async with (
        peer_client(app, "2001:db8:1:2::10") as first,
        peer_client(app, "2001:db8:1:2::20") as neighbour,
        peer_client(app, "2001:db8:1:3::10") as other,
    ):
        codes = [
            (await first.post(QUERY_PATH, json=QUERY)).status_code,
            (await neighbour.post(QUERY_PATH, json=QUERY)).status_code,
            (await first.post(QUERY_PATH, json=QUERY)).status_code,
            (await other.post(QUERY_PATH, json=QUERY)).status_code,
        ]
    assert codes == [200, 200, 429, 200]


@pytest.mark.parametrize(
    "value", ["10.0.0.0/33", "proxy.local", "*", "0.0.0.0/0", "::/0"]
)
def test_invalid_trusted_proxy_configuration_stops_startup(edge_app, value):
    with pytest.raises(ValueError, match="SECURITY_TRUSTED_PROXIES"):
        edge_app(trusted_proxies=value)


def test_startup_log_states_proxy_trust_and_counting_mode(edge_app, monkeypatch):
    from ragbot.api.edge import config as edge_config

    fake_logger = MagicMock()
    monkeypatch.setattr(edge_config, "logger", fake_logger)
    edge_app()
    messages = [
        call.args[0]
        for call in fake_logger.info.call_args_list + fake_logger.warning.call_args_list
    ]
    assert any("no trusted proxy is configured" in message for message in messages)
    assert any("counted per instance" in message for message in messages)


# Limits, headers and exemptions


def test_requests_over_the_limit_get_429_with_retry_information(edge_app):
    app, rag = edge_app(limit=3)
    with TestClient(app) as client:
        allowed = [client.post(QUERY_PATH, json=QUERY) for _ in range(3)]
        refused = client.post(QUERY_PATH, json=QUERY)
    assert [response.status_code for response in allowed] == [200, 200, 200]
    assert [response.headers["X-RateLimit-Remaining"] for response in allowed] == [
        "2",
        "1",
        "0",
    ]
    assert refused.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert int(refused.headers["Retry-After"]) >= 1
    assert refused.json()["retry_after"] >= 1
    assert "Rate limit exceeded" in refused.json()["detail"]
    assert refused.headers["X-RateLimit-Limit"] == "3"
    assert refused.headers["X-RateLimit-Remaining"] == "0"
    assert "X-RateLimit-Reset" in refused.headers
    assert rag.query_documents.await_count == 3


def test_health_checks_are_never_rate_limited(edge_app):
    app, _ = edge_app(limit=1)
    with TestClient(app) as client:
        assert client.post(QUERY_PATH, json=QUERY).status_code == 200
        assert client.post(QUERY_PATH, json=QUERY).status_code == 429
        for _ in range(5):
            assert client.get("/health").status_code == 200
            assert client.get("/api/v1/health").status_code == 200


def test_each_request_is_counted_once(edge_app):
    app, _ = edge_app(limit=5)
    with TestClient(app) as client:
        remaining = [
            client.post(QUERY_PATH, json=QUERY).headers["X-RateLimit-Remaining"]
            for _ in range(5)
        ]
    assert remaining == ["4", "3", "2", "1", "0"]


def test_request_with_a_credential_in_anonymous_mode_is_counted_once(edge_app):
    app, _ = edge_app(limit=2)
    with TestClient(app) as client:
        responses = [
            client.post(QUERY_PATH, json=QUERY, headers={"X-API-Key": "ignored-in-dev"})
            for _ in range(3)
        ]
    assert [response.status_code for response in responses] == [200, 200, 429]
    assert [
        response.headers.get("X-RateLimit-Remaining") for response in responses[:2]
    ] == [
        "1",
        "0",
    ]


async def test_requests_without_credentials_are_refused_before_the_body_is_read(
    edge_app, asgi_call
):
    app, _ = edge_app(limit=2, multi_tenant=True, principals={})
    results = []
    for _ in range(3):
        results.append(
            await asgi_call(
                app,
                path="/api/v1/documents/text",
                chunks=[b'{"text": "hello"}'],
                headers=[
                    ("content-type", "application/json"),
                    ("content-length", "17"),
                ],
            )
        )
    assert [result.status for result in results] == [401, 401, 429]
    assert results[2].receive_calls == 0


# Authenticated identity


async def test_authenticated_requests_count_against_the_principal(
    edge_app, peer_client
):
    principals = {"key-a": make_principal("key-a"), "key-b": make_principal("key-b")}
    app, _ = edge_app(limit=2, multi_tenant=True, principals=principals)
    async with peer_client(app, "198.51.100.30") as client:
        key_a = await _codes(client, 2, {"X-API-Key": "key-a"})
        key_b = await _codes(client, 2, {"X-API-Key": "key-b"})
        key_a_over = await client.post(
            QUERY_PATH, json=QUERY, headers={"X-API-Key": "key-a"}
        )
    assert key_a == [200, 200]
    assert key_b == [200, 200]
    assert key_a_over.status_code == 429
    assert key_a_over.json()["retry_after"] >= 1
    assert int(key_a_over.headers["Retry-After"]) >= 1


async def test_one_principal_from_two_addresses_shares_one_counter(
    edge_app, peer_client
):
    app, _ = edge_app(
        limit=2, multi_tenant=True, principals={"key-a": make_principal("key-a")}
    )
    headers = {"X-API-Key": "key-a"}
    async with (
        peer_client(app, "198.51.100.40") as first,
        peer_client(app, "198.51.100.41") as second,
    ):
        codes = [
            (await first.post(QUERY_PATH, json=QUERY, headers=headers)).status_code,
            (await second.post(QUERY_PATH, json=QUERY, headers=headers)).status_code,
            (await first.post(QUERY_PATH, json=QUERY, headers=headers)).status_code,
        ]
    assert codes == [200, 200, 429]


async def test_failed_authentication_counts_against_the_address(edge_app, peer_client):
    app, rag = edge_app(
        limit=3, multi_tenant=True, principals={"key-a": make_principal("key-a")}
    )
    failures = []
    async with peer_client(app, "198.51.100.50") as client:
        for index in range(4):
            failures.append(
                await client.post(
                    QUERY_PATH, json=QUERY, headers={"X-API-Key": f"wrong-{index}"}
                )
            )
        valid = await client.post(
            QUERY_PATH, json=QUERY, headers={"X-API-Key": "key-a"}
        )
    assert [response.status_code for response in failures] == [401, 401, 401, 429]
    assert (
        failures[0].json()["detail"]
        == "Invalid, expired, or revoked authentication credentials"
    )
    assert "Retry-After" in failures[3].headers
    # A valid key from the same address counts against its own principal.
    assert valid.status_code == 200
    assert rag.query_documents.await_count == 1


# Several instances


async def test_instances_that_share_a_store_share_the_limit(edge_app, peer_client):
    from ragbot.api.edge.rate_limit_store import MemoryRateLimitStore

    shared = MemoryRateLimitStore()
    first_app, _ = edge_app(limit=3)
    second_app, _ = edge_app(limit=3)
    first_app.state.rate_limiter.store = shared
    second_app.state.rate_limiter.store = shared
    async with (
        peer_client(first_app, "198.51.100.60") as first,
        peer_client(second_app, "198.51.100.60") as second,
    ):
        codes = [
            (await first.post(QUERY_PATH, json=QUERY)).status_code,
            (await second.post(QUERY_PATH, json=QUERY)).status_code,
            (await first.post(QUERY_PATH, json=QUERY)).status_code,
            (await second.post(QUERY_PATH, json=QUERY)).status_code,
        ]
    assert codes == [200, 200, 200, 429]


async def test_instances_without_a_shared_store_count_separately(edge_app, peer_client):
    first_app, _ = edge_app(limit=2)
    second_app, _ = edge_app(limit=2)
    async with (
        peer_client(first_app, "198.51.100.61") as first,
        peer_client(second_app, "198.51.100.61") as second,
    ):
        first_codes = await _codes(first, 3, {})
        second_codes = await _codes(second, 3, {})
    assert first_codes == [200, 200, 429]
    assert second_codes == [200, 200, 429]


def test_unavailable_shared_store_falls_back_to_per_instance_counting(
    edge_app, monkeypatch
):
    from ragbot.api.edge import rate_limit_store

    fake_logger = MagicMock()
    monkeypatch.setattr(rate_limit_store, "logger", fake_logger)
    # Nothing listens on port 1, so every shared store call fails at once.
    app, _ = edge_app(limit=2, storage_url="redis://127.0.0.1:1/0")
    with TestClient(app) as client:
        codes = [client.post(QUERY_PATH, json=QUERY).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    outage_warnings = [
        call.args[0]
        for call in fake_logger.warning.call_args_list
        if "unavailable" in call.args[0]
    ]
    assert len(outage_warnings) == 1


def test_every_api_route_except_health_enforces_the_rate_limit():
    from ragbot.api.app import create_app
    from ragbot.api.dependencies import enforce_rate_limit

    app = create_app(lifespan_context=None)
    exempt = {"/health", "/api/v1/health"}
    missing = []
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        path = getattr(route, "path", "")
        if dependant is None or path in exempt:
            continue
        calls = {dependency.call for dependency in dependant.dependencies}
        if enforce_rate_limit not in calls:
            missing.append(path)
    assert missing == []
