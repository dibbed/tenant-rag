"""Unit tests for the browser origin allowlist (Phase 3, audit finding C10)."""

from __future__ import annotations

import pytest

from ragbot.api.edge.cors import CorsConfigError, normalize_origin, parse_cors_policy


def test_empty_setting_allows_no_origin():
    policy = parse_cors_policy("", "production")
    assert policy.mode == "disabled"
    options = policy.middleware_options()
    assert options["allow_origins"] == []
    assert options["allow_credentials"] is False
    assert options["expose_headers"] == []


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://app.example.com", "https://app.example.com"),
        ("https://APP.Example.com/", "https://app.example.com"),
        ("https://app.example.com:443", "https://app.example.com"),
        ("http://localhost:3000", "http://localhost:3000"),
        ("http://[::1]:8080", "http://[::1]:8080"),
        ("HTTP://Localhost:80", "http://localhost"),
    ],
)
def test_origins_are_normalized(value, expected):
    assert normalize_origin(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "null",
        "https://*.example.com",
        "*.example.com",
        "ftp://app.example.com",
        "app.example.com",
        "localhost:3000",
        "https://app.example.com/path",
        "https://user@app.example.com",
        "https://app.example.com?x=1",
        "https://app.example.com#top",
        "https://",
        "https://app.example.com:99999",
    ],
)
def test_invalid_origins_are_rejected(value):
    with pytest.raises(CorsConfigError, match="SECURITY_CORS_ALLOWED_ORIGINS"):
        normalize_origin(value)


def test_listed_origins_may_send_credentials():
    policy = parse_cors_policy(
        "https://app.example.com, https://admin.example.com/, https://app.example.com",
        "production",
    )
    assert policy.origins == ("https://app.example.com", "https://admin.example.com")
    assert policy.mode == "allowlist"
    options = policy.middleware_options()
    assert options["allow_credentials"] is True
    assert options["allow_methods"] == ["GET", "POST"]
    assert "X-API-Key" in options["allow_headers"]
    assert "Retry-After" in options["expose_headers"]


def test_wildcard_in_development_allows_every_origin_without_credentials():
    policy = parse_cors_policy("*", "development")
    assert policy.mode == "any-origin"
    options = policy.middleware_options()
    assert options["allow_origins"] == ["*"]
    assert options["allow_credentials"] is False


@pytest.mark.parametrize("environment", ["production", "staging", "test"])
def test_wildcard_outside_development_is_rejected(environment):
    with pytest.raises(CorsConfigError, match="ENVIRONMENT=development"):
        parse_cors_policy("*", environment)


def test_wildcard_mixed_with_origins_still_validates_them():
    policy = parse_cors_policy("*, https://app.example.com", "development")
    assert policy.allow_all
    assert policy.ignored_entries == ("https://app.example.com",)
    with pytest.raises(CorsConfigError):
        parse_cors_policy("*, not-an-origin", "development")
