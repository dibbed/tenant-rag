"""Rate Limit Subjects, the two counting stages, headers and the 429 response.

Security fix C9 (Phase 3, see docs/BASELINE_AUDIT.md). Each request is
counted exactly once:

1. ``RateLimitMiddleware`` counts a request that carries no credential header
   (``X-API-Key`` or ``Authorization``) against its Client Address, before the
   request body is read.
2. Any other request is counted after authentication. The
   ``enforce_rate_limit`` dependency counts it against its Principal, and
   ``get_current_principal`` counts a failed credential against the Client
   Address before it answers 401.

A subject over its limit gets HTTP 429 with ``Retry-After``. Health checks
and documentation are never counted.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from ragbot.api.edge.client_address import rate_limit_address_key
from ragbot.api.edge.rate_limit_store import (
    MemoryRateLimitStore,
    RateLimitDecision,
    RateLimitStore,
)
from ragbot.outputs.logger import logger

if TYPE_CHECKING:
    from collections.abc import Iterable

LIMITER_STATE_KEY = "edge_rate_limiter"
COUNTED_STATE_KEY = "edge_rate_limit_counted"
DECISION_STATE_KEY = "edge_rate_limit_decision"

RATE_LIMIT_DETAIL = "Rate limit exceeded. Please retry later."
CREDENTIAL_HEADERS = ("x-api-key", "authorization")
DEFAULT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {"/health", "/api/v1/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
)

# Refusals are logged at most once per subject and window; at most this many
# subjects are remembered for that purpose.
_MAX_LOGGED_SUBJECTS = 10_000


def principal_subject(tenant_id: str, principal_id: str) -> str:
    """Rate Limit Subject of an authenticated Principal."""
    return f"principal:{tenant_id}:{principal_id}"


def address_subject(address: str | None) -> str:
    """Rate Limit Subject of a Client Address."""
    return f"address:{rate_limit_address_key(address)}"


def rate_limit_headers(
    decision: RateLimitDecision, now: float | None = None
) -> dict[str, str]:
    """Response headers that describe a decision."""
    current = time.time() if now is None else now
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(max(0, decision.remaining)),
        "X-RateLimit-Reset": str(int(current + decision.reset_after)),
    }
    if not decision.allowed:
        headers["Retry-After"] = str(decision.retry_after)
    return headers


def rate_limit_response(decision: RateLimitDecision) -> JSONResponse:
    """HTTP 429 response for a refused request."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": RATE_LIMIT_DETAIL, "retry_after": decision.retry_after},
        headers=rate_limit_headers(decision),
    )


class RateLimitExceeded(HTTPException):
    """HTTP 429 raised by a dependency after authentication."""

    def __init__(self, decision: RateLimitDecision) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_DETAIL,
            headers=rate_limit_headers(decision),
        )
        self.decision = decision


async def rate_limit_exceeded_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Give refusals after authentication the same body as the middleware."""
    decision = getattr(exc, "decision", None)
    if isinstance(decision, RateLimitDecision):
        return rate_limit_response(decision)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": RATE_LIMIT_DETAIL},
    )


class RateLimiter:
    """Counts requests per Rate Limit Subject in one store."""

    def __init__(
        self,
        store: RateLimitStore | None = None,
        *,
        max_requests: int = 10,
        window_seconds: float = 60,
        enabled: bool = True,
        exempt_paths: Iterable[str] | None = None,
    ) -> None:
        self.store: RateLimitStore = (
            store if store is not None else MemoryRateLimitStore()
        )
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self.enabled = bool(enabled)
        self.exempt_paths: frozenset[str] = (
            frozenset(exempt_paths)
            if exempt_paths is not None
            else DEFAULT_EXEMPT_PATHS
        )
        self._last_logged: dict[str, float] = {}
        self._sweep_task: asyncio.Task[None] | None = None

    def is_exempt(self, path: str) -> bool:
        """Health checks and documentation are never rate limited."""
        return (path.rstrip("/") or "/") in self.exempt_paths

    async def hit(self, subject: str) -> RateLimitDecision:
        """Count one request for ``subject``."""
        decision = await self.store.hit(subject, self.max_requests, self.window_seconds)
        if not decision.allowed:
            self._report_refusal(subject, decision)
        return decision

    def _report_refusal(self, subject: str, decision: RateLimitDecision) -> None:
        now = time.monotonic()
        last = self._last_logged.get(subject)
        if last is None or now - last >= self.window_seconds:
            if len(self._last_logged) >= _MAX_LOGGED_SUBJECTS:
                self._last_logged.clear()
            self._last_logged[subject] = now
            logger.warning(
                f"Rate limit exceeded for {subject}. Limit: {decision.limit} requests "
                f"per {self.window_seconds}s. Retry after: {decision.retry_after}s"
            )
        with contextlib.suppress(Exception):
            from ragbot.outputs.metrics import metrics_manager

            metrics_manager.record_rate_limit_hit(user_id=hash(subject) % 100000)

    def start_background_sweep(self) -> None:
        """Delete expired records once per window, even without requests."""
        if self._sweep_task is not None and not self._sweep_task.done():
            return
        self._sweep_task = asyncio.get_running_loop().create_task(self._sweep_forever())

    async def _sweep_forever(self) -> None:
        while True:
            await asyncio.sleep(self.window_seconds)
            with contextlib.suppress(Exception):
                self.store.sweep()

    async def aclose(self) -> None:
        """Stop the background sweep and release the store."""
        task, self._sweep_task = self._sweep_task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        with contextlib.suppress(Exception):
            await self.store.close()


def get_request_limiter(request: Request) -> RateLimiter | None:
    """The limiter that RateLimitMiddleware attached to this request."""
    limiter = getattr(request.state, LIMITER_STATE_KEY, None)
    return limiter if isinstance(limiter, RateLimiter) else None


async def count_request(request: Request, principal: Any | None = None) -> None:
    """Stage 2: count a request that stage 1 did not count.

    ``principal`` is the authenticated Principal, or ``None`` when the request
    is not authenticated; the request then counts against its Client Address.
    Raises RateLimitExceeded when the subject is over its limit.
    """
    limiter = get_request_limiter(request)
    if limiter is None or not limiter.enabled:
        return
    if getattr(request.state, COUNTED_STATE_KEY, False):
        return
    tenant_id = getattr(principal, "tenant_id", None)
    principal_id = getattr(principal, "principal_id", None)
    if tenant_id and principal_id:
        subject = principal_subject(str(tenant_id), str(principal_id))
    else:
        client = request.client
        subject = address_subject(client.host if client else None)
    decision = await limiter.hit(subject)
    setattr(request.state, COUNTED_STATE_KEY, True)
    setattr(request.state, DECISION_STATE_KEY, decision)
    if not decision.allowed:
        raise RateLimitExceeded(decision)


async def count_unauthenticated_request(request: Request) -> None:
    """Count a request that failed authentication against its Client Address."""
    await count_request(request, None)
