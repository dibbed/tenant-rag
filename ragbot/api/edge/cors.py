"""Browser origin allowlist (Security fix C10, Phase 3).

``SECURITY_CORS_ALLOWED_ORIGINS`` lists the origins that may call the API from
a browser. It is empty by default, and then no origin is allowed.

- An entry is an origin: ``scheme://host`` or ``scheme://host:port`` with the
  scheme ``http`` or ``https``. The ``null`` origin, wildcards inside an origin
  (``https://*.example.com``) and entries with a user, path, query or fragment
  stop startup with an error.
- ``*`` allows every origin, without credentials. It is accepted only when
  ``ENVIRONMENT=development``. In any other environment it stops startup, so a
  production deployment must list its origins explicitly.
- Listed origins may send credentials.

CORS controls what a browser may read. The server still processes requests
from other origins, and authentication stays the access control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from ragbot.api.access_mode import DEVELOPMENT_ENVIRONMENT

CORS_ORIGINS_ENV = "SECURITY_CORS_ALLOWED_ORIGINS"
ALLOWED_METHODS: tuple[str, ...] = ("GET", "POST")
ALLOWED_HEADERS: tuple[str, ...] = (
    "Authorization",
    "Content-Type",
    "X-API-Key",
    "X-Tenant-ID",
)
EXPOSED_HEADERS: tuple[str, ...] = (
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)
PREFLIGHT_MAX_AGE_SECONDS = 600


class CorsConfigError(ValueError):
    """SECURITY_CORS_ALLOWED_ORIGINS contains an invalid or unsafe entry."""


@dataclass(frozen=True)
class CorsPolicy:
    """The effective CORS policy."""

    origins: tuple[str, ...] = ()
    allow_all: bool = False
    ignored_entries: tuple[str, ...] = ()

    @property
    def mode(self) -> str:
        """``disabled`` (no origin), ``allowlist`` or ``any-origin``."""
        if self.allow_all:
            return "any-origin"
        return "allowlist" if self.origins else "disabled"

    @property
    def allow_credentials(self) -> bool:
        """Credentials are allowed only for explicitly listed origins."""
        return bool(self.origins) and not self.allow_all

    def middleware_options(self) -> dict[str, Any]:
        """Keyword arguments for Starlette's CORSMiddleware."""
        enabled = self.allow_all or bool(self.origins)
        return {
            "allow_origins": ["*"] if self.allow_all else list(self.origins),
            "allow_credentials": self.allow_credentials,
            "allow_methods": list(ALLOWED_METHODS),
            "allow_headers": list(ALLOWED_HEADERS),
            "expose_headers": list(EXPOSED_HEADERS) if enabled else [],
            "max_age": PREFLIGHT_MAX_AGE_SECONDS,
        }


def _invalid(entry: str, reason: str) -> CorsConfigError:
    return CorsConfigError(f"Invalid {CORS_ORIGINS_ENV} entry {entry!r}: {reason}")


def normalize_origin(entry: str) -> str:
    """Validate one configured origin and return its canonical form."""
    value = entry.strip()
    if value.lower() == "null":
        raise _invalid(
            value, "the null origin is shared by sandboxed pages and local files."
        )
    if "*" in value:
        raise _invalid(
            value,
            "wildcards inside an origin are not supported. List each origin, or use "
            "'*' alone with ENVIRONMENT=development.",
        )
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise _invalid(value, "it is not a valid origin.") from exc
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if scheme not in ("http", "https") or not host:
        raise _invalid(value, "expected scheme://host[:port] with http or https.")
    if (
        parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise _invalid(value, "an origin has no user, path, query or fragment.")
    if ":" in host:
        host = f"[{host}]"
    default_port = 443 if scheme == "https" else 80
    if port is None or port == default_port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def parse_cors_policy(raw: str | None, environment: str) -> CorsPolicy:
    """Parse SECURITY_CORS_ALLOWED_ORIGINS for the given ENVIRONMENT."""
    entries = [item.strip() for item in (raw or "").split(",") if item.strip()]
    if not entries:
        return CorsPolicy()
    if "*" in entries:
        if environment != DEVELOPMENT_ENVIRONMENT:
            raise CorsConfigError(
                f"{CORS_ORIGINS_ENV}='*' would let every website call the API from a "
                "browser. It is accepted only when ENVIRONMENT=development (current: "
                f"{environment!r}). List the allowed origins instead."
            )
        others = tuple(entry for entry in entries if entry != "*")
        for entry in others:
            normalize_origin(entry)
        return CorsPolicy(allow_all=True, ignored_entries=others)
    origins: list[str] = []
    for entry in entries:
        origin = normalize_origin(entry)
        if origin not in origins:
            origins.append(origin)
    return CorsPolicy(origins=tuple(origins))
