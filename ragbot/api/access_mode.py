"""Authentication mode of the HTTP API.

Security fix C5 (Phase 2 hardening, see docs/BASELINE_AUDIT.md).

Before this change the API accepted every request without credentials when
multi-tenant mode was off, and multi-tenant mode is off by default.

Rules now:

- ``MULTI_TENANT_ENABLED=true``: every request except the health endpoints
  needs a valid API key or session token. ``ALLOW_ANONYMOUS`` has no effect.
- ``MULTI_TENANT_ENABLED=false``: there is no credential store. Anonymous
  access is allowed only when BOTH ``ENVIRONMENT=development`` AND
  ``ALLOW_ANONYMOUS=true`` are set. Otherwise every request except the health
  endpoints is rejected with HTTP 401.

The values are read from the process environment when a request arrives.
The settings module loads ``.env`` into the environment at import time, so
values from ``.env`` apply too. ``ENVIRONMENT`` defaults to ``production``.
"""

from __future__ import annotations

import os
from typing import Optional

from ragbot.outputs.logger import logger

DEVELOPMENT_ENVIRONMENT = "development"
DEFAULT_ENVIRONMENT = "production"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

ANONYMOUS_DISABLED_DETAIL = (
    "Authentication required. Set MULTI_TENANT_ENABLED=true and send an API key. "
    "Anonymous access is only available when ENVIRONMENT=development and "
    "ALLOW_ANONYMOUS=true."
)


def current_environment() -> str:
    """Return the deployment environment name (lowercase)."""
    value = os.getenv("ENVIRONMENT", "")
    return value.strip().lower() or DEFAULT_ENVIRONMENT


def anonymous_access_requested() -> bool:
    """Return True if ALLOW_ANONYMOUS is set to a true value."""
    return os.getenv("ALLOW_ANONYMOUS", "").strip().lower() in _TRUE_VALUES


def anonymous_access_allowed() -> bool:
    """Return True only for ENVIRONMENT=development AND ALLOW_ANONYMOUS=true."""
    return (
        anonymous_access_requested()
        and current_environment() == DEVELOPMENT_ENVIRONMENT
    )


def _multi_tenant_enabled() -> bool:
    from ragbot.configs.settings import settings

    return bool(getattr(getattr(settings, "multi_tenant", object()), "enabled", False))


def log_access_mode_warnings(multi_tenant_enabled: Optional[bool] = None) -> str:
    """Log the effective authentication mode once at startup.

    Returns the mode name: ``authenticated``, ``anonymous`` (insecure
    development mode) or ``locked`` (all API requests are rejected).
    """
    enabled = (
        _multi_tenant_enabled()
        if multi_tenant_enabled is None
        else bool(multi_tenant_enabled)
    )
    requested = anonymous_access_requested()
    environment = current_environment()

    if enabled:
        if requested:
            logger.warning(
                "ALLOW_ANONYMOUS is ignored because MULTI_TENANT_ENABLED=true: "
                "all API requests require credentials."
            )
        return "authenticated"

    if anonymous_access_allowed():
        logger.warning(
            "INSECURE MODE: anonymous API access is enabled "
            "(ENVIRONMENT=development, ALLOW_ANONYMOUS=true). Any client can "
            "query, ingest and reset the knowledge base. Never use this "
            "setting in production."
        )
        return "anonymous"

    if requested:
        logger.warning(
            f"ALLOW_ANONYMOUS=true is ignored because ENVIRONMENT={environment!r} "
            "is not 'development'. API requests will be rejected with HTTP 401 "
            "until MULTI_TENANT_ENABLED=true is set."
        )
    else:
        logger.warning(
            "MULTI_TENANT_ENABLED=false and anonymous access is not enabled: all "
            "API requests except /health will be rejected with HTTP 401. Set "
            "MULTI_TENANT_ENABLED=true and issue API keys, or for local "
            "development set ENVIRONMENT=development and ALLOW_ANONYMOUS=true."
        )
    return "locked"
