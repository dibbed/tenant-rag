"""Rate limit middleware: stage 1 of edge rate limiting.

Security fix C9 (Phase 3, see docs/BASELINE_AUDIT.md). This pure ASGI
middleware:

- counts every request without a credential header against its Client
  Address before the request body is read, and answers HTTP 429 when the
  address is over its limit;
- attaches the limiter to the request, so that ``enforce_rate_limit`` and
  ``get_current_principal`` count requests with a credential after
  authentication (see ``ragbot/api/edge/rate_limiter.py``);
- adds the ``X-RateLimit-*`` headers to every counted response.

The Client Address comes from ``scope["client"]``, which
``TrustedProxyMiddleware`` sets. Forwarded headers are never read here.
Health checks and documentation are never counted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from starlette.datastructures import Headers, MutableHeaders

from ragbot.api.edge.rate_limit_store import MemoryRateLimitStore
from ragbot.api.edge.rate_limiter import (
    COUNTED_STATE_KEY,
    CREDENTIAL_HEADERS,
    DECISION_STATE_KEY,
    DEFAULT_EXEMPT_PATHS,
    LIMITER_STATE_KEY,
    RateLimiter,
    address_subject,
    rate_limit_headers,
    rate_limit_response,
)
from ragbot.configs.settings import settings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RateLimitMiddleware:
    """Sliding-window rate limiting per Rate Limit Subject (pure ASGI).

    Protects the expensive routes (question answering and document ingestion)
    from abuse. ``limiter`` is shared with the application (``app.state``);
    without it, the middleware builds a per-instance limiter from the
    arguments or the security settings.
    """

    DEFAULT_EXEMPT_PATHS: ClassVar[set[str]] = set(DEFAULT_EXEMPT_PATHS)

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int | None = None,
        window_seconds: int | None = None,
        exempt_paths: Iterable[str] | None = None,
        enabled: bool | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.app = app
        if limiter is None:
            # Read from settings by default, allowing constructor overrides for tests
            sec_cfg = getattr(settings, "security", None)
            limiter = RateLimiter(
                MemoryRateLimitStore(),
                max_requests=(
                    max_requests
                    if max_requests is not None
                    else getattr(sec_cfg, "rate_limit_requests", 60)
                ),
                window_seconds=(
                    window_seconds
                    if window_seconds is not None
                    else getattr(sec_cfg, "rate_limit_window", 60)
                ),
                enabled=(
                    enabled
                    if enabled is not None
                    else getattr(sec_cfg, "enable_rate_limiting", True)
                ),
                exempt_paths=exempt_paths or self.DEFAULT_EXEMPT_PATHS,
            )
        self.limiter = limiter

    @property
    def enabled(self) -> bool:
        return self.limiter.enabled

    @property
    def max_requests(self) -> int:
        return self.limiter.max_requests

    @property
    def window_seconds(self) -> int:
        return self.limiter.window_seconds

    @property
    def exempt_paths(self) -> frozenset[str]:
        return self.limiter.exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limiter = self.limiter
        if (
            scope["type"] != "http"
            or not limiter.enabled
            or limiter.is_exempt(scope.get("path", ""))
        ):
            await self.app(scope, receive, send)
            return

        state: dict[str, Any] = scope.setdefault("state", {})
        state[LIMITER_STATE_KEY] = limiter
        request_headers = Headers(scope=scope)
        if not any(request_headers.get(name) for name in CREDENTIAL_HEADERS):
            client = scope.get("client")
            decision = await limiter.hit(address_subject(client[0] if client else None))
            state[COUNTED_STATE_KEY] = True
            state[DECISION_STATE_KEY] = decision
            if not decision.allowed:
                await rate_limit_response(decision)(scope, receive, send)
                return

        async def send_with_rate_limit_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                decision = state.get(DECISION_STATE_KEY)
                if decision is not None:
                    message.setdefault("headers", [])
                    headers = MutableHeaders(scope=message)
                    if "x-ratelimit-limit" not in headers:
                        for name, value in rate_limit_headers(decision).items():
                            if name.lower() not in headers:
                                headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_rate_limit_headers)
