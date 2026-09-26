"""Unit tests for Client Address resolution (Phase 3, audit finding C9)."""

from __future__ import annotations

import ipaddress
from typing import Any

import pytest

from ragbot.api.edge.client_address import (
    MAX_FORWARDED_HOPS,
    TrustedProxyConfigError,
    forwarded_proto,
    parse_ip_address,
    parse_trusted_proxies,
    rate_limit_address_key,
    resolve_client_address,
)
from ragbot.api.middleware.trusted_proxy import (
    CLIENT_ADDRESS_STATE_KEY,
    PEER_STATE_KEY,
    TrustedProxyMiddleware,
)

TRUSTED = parse_trusted_proxies("10.0.0.0/8, 192.0.2.10")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("198.51.100.7", "198.51.100.7"),
        (" 198.51.100.7 ", "198.51.100.7"),
        ("198.51.100.7:5678", "198.51.100.7"),
        ("2001:db8::1", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("::ffff:198.51.100.7", "198.51.100.7"),
    ],
)
def test_parse_ip_address_accepts_addresses(value, expected):
    assert str(parse_ip_address(value)) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "unknown",
        "300.1.1.1",
        "proxy.local",
        "1.2.3.4:http",
        "[2001:db8::1",
        "[2001:db8::1]x",
        "testclient",
    ],
)
def test_parse_ip_address_rejects_other_values(value):
    assert parse_ip_address(value) is None


def test_trusted_proxies_accept_addresses_and_networks():
    proxies = parse_trusted_proxies(" 10.0.0.0/8, 192.0.2.10 ,2001:db8::/32,, ")
    assert [str(network) for network in proxies.networks] == [
        "10.0.0.0/8",
        "192.0.2.10/32",
        "2001:db8::/32",
    ]
    assert proxies.enabled


def test_empty_trusted_proxies_trust_nobody():
    proxies = parse_trusted_proxies("")
    assert not proxies.enabled
    assert not proxies.is_trusted(ipaddress.ip_address("127.0.0.1"))


@pytest.mark.parametrize(
    "value",
    [
        "10.0.0.0/33",
        "proxy.local",
        "10.0.0.1-10.0.0.9",
        "*",
        "any",
        "0.0.0.0/0",
        "::/0",
    ],
)
def test_invalid_or_catch_all_entries_are_rejected(value):
    with pytest.raises(TrustedProxyConfigError, match="SECURITY_TRUSTED_PROXIES"):
        parse_trusted_proxies(value)


def test_wide_networks_are_reported():
    proxies = parse_trusted_proxies(
        "10.0.0.0/8, 172.16.0.0/16, 2001:db8::/32, 2001:db8:1::/48"
    )
    assert [str(network) for network in proxies.broad_networks()] == [
        "10.0.0.0/8",
        "2001:db8::/32",
    ]


@pytest.mark.parametrize(
    "peer,forwarded,expected,peer_trusted",
    [
        ("203.0.113.9", ["198.51.100.7"], "203.0.113.9", False),
        ("10.0.0.2", ["198.51.100.7"], "198.51.100.7", True),
        ("10.0.0.2", ["1.1.1.1, 198.51.100.7"], "198.51.100.7", True),
        ("10.0.0.2", ["198.51.100.7, 192.0.2.10"], "198.51.100.7", True),
        ("10.0.0.2", ["198.51.100.7", "192.0.2.10"], "198.51.100.7", True),
        ("10.0.0.2", ["10.0.0.5, 192.0.2.10"], "10.0.0.5", True),
        ("10.0.0.2", ["unknown, 10.0.0.5"], "10.0.0.5", True),
        ("10.0.0.2", ["198.51.100.7, garbage"], "10.0.0.2", True),
        ("10.0.0.2", [], "10.0.0.2", True),
        ("10.0.0.2", ["[2001:db8::7]:443"], "2001:db8::7", True),
        ("testclient", ["198.51.100.7"], "testclient", False),
        (None, ["198.51.100.7"], None, False),
    ],
)
def test_resolve_client_address(peer, forwarded, expected, peer_trusted):
    assert resolve_client_address(peer, forwarded, TRUSTED) == (expected, peer_trusted)


def test_forwarded_headers_are_ignored_without_trusted_proxies():
    proxies = parse_trusted_proxies("")
    assert resolve_client_address("127.0.0.1", ["198.51.100.7"], proxies) == (
        "127.0.0.1",
        False,
    )


def test_only_the_nearest_hops_are_examined():
    forged = ", ".join(f"203.0.113.{index % 250}" for index in range(1000))
    chain = forged + ", " + ", ".join(["10.0.0.9"] * MAX_FORWARDED_HOPS)
    address, _ = resolve_client_address("10.0.0.2", [chain], TRUSTED)
    assert address == "10.0.0.9"


@pytest.mark.parametrize(
    "values,expected",
    [
        (["https"], "https"),
        (["http, https"], "https"),
        (["HTTPS"], "https"),
        (["https", "http"], "http"),
        (["javascript"], None),
        ([], None),
    ],
)
def test_forwarded_proto(values, expected):
    assert forwarded_proto(values) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("198.51.100.7", "198.51.100.7"),
        ("::ffff:198.51.100.7", "198.51.100.7"),
        ("2001:db8:1:2::10", "2001:db8:1:2::/64"),
        ("2001:0db8:0001:0002:0000:0000:0000:0020", "2001:db8:1:2::/64"),
        ("testclient", "testclient"),
        (None, "unknown"),
    ],
)
def test_rate_limit_address_key(value, expected):
    assert rate_limit_address_key(value) == expected


async def _run_middleware(
    trusted: Any,
    client: tuple[str, int] | None,
    headers: list[tuple[str, str]],
    scope_type: str = "http",
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    async def inner(scope, _receive, _send):
        captured.update(scope)

    middleware = TrustedProxyMiddleware(inner, trusted_proxies=trusted)
    scope = {
        "type": scope_type,
        "scheme": "ws" if scope_type == "websocket" else "http",
        "client": client,
        "headers": [(name.encode(), value.encode()) for name, value in headers],
        "path": "/",
        "state": {},
    }
    await middleware(scope, None, None)
    return captured


async def test_middleware_leaves_untrusted_peers_unchanged():
    scope = await _run_middleware(
        TRUSTED,
        ("203.0.113.9", 5000),
        [("x-forwarded-for", "198.51.100.7"), ("x-forwarded-proto", "https")],
    )
    assert scope["client"] == ("203.0.113.9", 5000)
    assert scope["scheme"] == "http"
    assert scope["state"][PEER_STATE_KEY] == "203.0.113.9"
    assert scope["state"][CLIENT_ADDRESS_STATE_KEY] == "203.0.113.9"


async def test_middleware_applies_the_client_address_from_a_trusted_proxy():
    scope = await _run_middleware(
        TRUSTED,
        ("10.0.0.2", 5000),
        [("x-forwarded-for", "1.1.1.1, 198.51.100.7"), ("x-forwarded-proto", "https")],
    )
    assert scope["client"] == ("198.51.100.7", 0)
    assert scope["scheme"] == "https"
    assert scope["state"][PEER_STATE_KEY] == "10.0.0.2"
    assert scope["state"][CLIENT_ADDRESS_STATE_KEY] == "198.51.100.7"


async def test_middleware_without_trusted_proxies_ignores_loopback_headers():
    scope = await _run_middleware(
        parse_trusted_proxies(""),
        ("127.0.0.1", 5000),
        [("x-forwarded-for", "198.51.100.7")],
    )
    assert scope["client"] == ("127.0.0.1", 5000)


async def test_middleware_maps_the_websocket_scheme():
    scope = await _run_middleware(
        TRUSTED,
        ("10.0.0.2", 5000),
        [("x-forwarded-for", "198.51.100.7"), ("x-forwarded-proto", "https")],
        scope_type="websocket",
    )
    assert scope["scheme"] == "wss"
