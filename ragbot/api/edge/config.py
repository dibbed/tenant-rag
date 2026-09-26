"""Edge protection settings, validation and startup messages (Phase 3).

Audit findings C9, C10 and C11 (docs/BASELINE_AUDIT.md). New environment
variables, read when the application is created:

- ``SECURITY_TRUSTED_PROXIES``: reverse proxies whose X-Forwarded-For header
  is trusted. Empty by default: forwarded headers are ignored.
- ``SECURITY_RATE_LIMIT_STORAGE_URL``: ``redis://`` or ``rediss://`` URL of a
  shared rate limit store. Empty by default: each instance counts on its own.
- ``SECURITY_CORS_ALLOWED_ORIGINS``: browser origins allowed to call the API.
  Empty by default: no origin. ``*`` is accepted only when
  ``ENVIRONMENT=development``.

The existing ``SECURITY_RATE_LIMIT_REQUESTS``, ``SECURITY_RATE_LIMIT_WINDOW``
and ``SECURITY_MAX_FILE_SIZE_MB`` settings still apply. An invalid value
raises ValueError, so a misconfigured service does not start.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from ragbot.api.access_mode import DEFAULT_ENVIRONMENT, DEVELOPMENT_ENVIRONMENT
from ragbot.api.edge.client_address import (
    TRUSTED_PROXIES_ENV,
    TrustedProxies,
    parse_trusted_proxies,
)
from ragbot.api.edge.cors import CORS_ORIGINS_ENV, CorsPolicy, parse_cors_policy
from ragbot.api.edge.rate_limit_store import (
    FallbackRateLimitStore,
    MemoryRateLimitStore,
    RateLimitStore,
    RedisRateLimitStore,
    mask_url,
)
from ragbot.api.edge.rate_limiter import RateLimiter
from ragbot.api.middleware.body_size_limit import upload_limit_mb
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

if TYPE_CHECKING:
    from collections.abc import Mapping

RATE_LIMIT_STORAGE_ENV = "SECURITY_RATE_LIMIT_STORAGE_URL"
_STORAGE_SCHEMES = ("redis", "rediss")


class EdgeConfigError(ValueError):
    """An edge protection setting is invalid."""


@dataclass(frozen=True)
class EdgeConfig:
    """Effective edge protection settings of one application."""

    environment: str
    trusted_proxies: TrustedProxies
    cors: CorsPolicy
    rate_limit_storage_url: str
    rate_limit_requests: int
    rate_limit_window: int
    rate_limiting_enabled: bool
    upload_limit_mb: int


def _environment(env: Mapping[str, str]) -> str:
    return (env.get("ENVIRONMENT") or "").strip().lower() or DEFAULT_ENVIRONMENT


def _storage_url(env: Mapping[str, str]) -> str:
    value = (env.get(RATE_LIMIT_STORAGE_ENV) or "").strip()
    if not value:
        return ""
    try:
        scheme = urlsplit(value).scheme.lower()
    except ValueError as exc:
        raise EdgeConfigError(
            f"Invalid {RATE_LIMIT_STORAGE_ENV}: {mask_url(value)!r}"
        ) from exc
    if scheme not in _STORAGE_SCHEMES:
        raise EdgeConfigError(
            f"Invalid {RATE_LIMIT_STORAGE_ENV} {mask_url(value)!r}: only redis:// and "
            "rediss:// URLs are supported."
        )
    return value


def load_edge_config(environ: Mapping[str, str] | None = None) -> EdgeConfig:
    """Read and validate the edge protection settings.

    Raises ValueError (TrustedProxyConfigError, CorsConfigError or
    EdgeConfigError) for an invalid value.
    """
    env: Mapping[str, str] = os.environ if environ is None else environ
    environment = _environment(env)
    security = getattr(settings, "security", None)
    return EdgeConfig(
        environment=environment,
        trusted_proxies=parse_trusted_proxies(env.get(TRUSTED_PROXIES_ENV)),
        cors=parse_cors_policy(env.get(CORS_ORIGINS_ENV), environment),
        rate_limit_storage_url=_storage_url(env),
        rate_limit_requests=max(1, int(getattr(security, "rate_limit_requests", 60))),
        rate_limit_window=max(1, int(getattr(security, "rate_limit_window", 60))),
        rate_limiting_enabled=bool(getattr(security, "enable_rate_limiting", True)),
        upload_limit_mb=upload_limit_mb(),
    )


def build_rate_limiter(config: EdgeConfig) -> RateLimiter:
    """Create the limiter and its store for one application."""
    store: RateLimitStore
    if config.rate_limit_storage_url:
        store = FallbackRateLimitStore(
            RedisRateLimitStore(config.rate_limit_storage_url), MemoryRateLimitStore()
        )
    else:
        store = MemoryRateLimitStore()
    return RateLimiter(
        store,
        max_requests=config.rate_limit_requests,
        window_seconds=config.rate_limit_window,
        enabled=config.rate_limiting_enabled,
    )


def log_edge_protection_mode(
    config: EdgeConfig, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Log the effective edge protection settings once, at startup.

    Returns the mode of each area, for tests and diagnostics.
    """
    env: Mapping[str, str] = os.environ if environ is None else environ
    modes: dict[str, str] = {}

    proxies = config.trusted_proxies
    if proxies.enabled:
        modes["trusted_proxies"] = "configured"
        logger.info(
            f"Edge protection: X-Forwarded-For is trusted only from "
            f"{len(proxies.networks)} configured proxy network(s) ({TRUSTED_PROXIES_ENV})."
        )
        for network in proxies.broad_networks():
            logger.warning(
                f"{TRUSTED_PROXIES_ENV} entry {network} is a wide network: every client "
                "inside it can choose its own rate limit address. List only your "
                "reverse proxies."
            )
    else:
        modes["trusted_proxies"] = "none"
        logger.info(
            "Edge protection: no trusted proxy is configured. X-Forwarded-For, "
            "X-Real-IP and similar headers are ignored; the TCP peer is the client "
            "address."
        )

    if config.rate_limit_storage_url:
        modes["rate_limit_store"] = "shared"
        logger.info(
            "Edge protection: rate limits are shared through "
            f"{mask_url(config.rate_limit_storage_url)}. If that store is unavailable, "
            "requests are counted per instance until it recovers."
        )
    else:
        modes["rate_limit_store"] = "per-instance"
        logger.info(
            "Edge protection: rate limits are counted per instance; each worker "
            f"process counts separately. Set {RATE_LIMIT_STORAGE_ENV} to share them "
            "across instances."
        )
        workers = (env.get("WORKERS") or "1").strip()
        if workers.isdigit() and int(workers) > 1:
            logger.warning(
                f"WORKERS={workers} without {RATE_LIMIT_STORAGE_ENV}: each worker process "
                "applies the rate limit on its own, which multiplies the effective limit."
            )

    policy = config.cors
    modes["cors"] = policy.mode
    if policy.allow_all:
        logger.warning(
            f"INSECURE CORS: {CORS_ORIGINS_ENV}='*' lets every website call the API "
            "from a browser (credentials are not allowed). Use it only for local "
            "development."
        )
        if policy.ignored_entries:
            logger.warning(
                f"{CORS_ORIGINS_ENV} mixes '*' with other origins; the other entries "
                "have no effect."
            )
    elif policy.origins:
        logger.info(
            f"Edge protection: browser calls are allowed from {len(policy.origins)} "
            f"origin(s) ({CORS_ORIGINS_ENV})."
        )
        if config.environment != DEVELOPMENT_ENVIRONMENT:
            for origin in policy.origins:
                if origin.startswith("http://"):
                    logger.warning(
                        f"CORS origin {origin} uses plain HTTP outside development."
                    )
    else:
        logger.info(
            f"Edge protection: no browser origin is allowed ({CORS_ORIGINS_ENV} is empty)."
        )

    modes["upload_limit_mb"] = str(config.upload_limit_mb)
    logger.info(
        f"Edge protection: request bodies above {config.upload_limit_mb}MB are "
        "rejected with HTTP 413."
    )
    return modes
