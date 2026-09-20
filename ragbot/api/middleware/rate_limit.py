"""
In-memory sliding-window rate limiting middleware for FastAPI.

Scope:
- single-process protection implemented
- distributed protection deferred (future Redis cluster limiter)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window in-memory rate limiter middleware.

    Protects API endpoints (especially expensive LLM query and document ingestion)
    from abuse and denial-of-service without external infrastructure dependencies.
    """

    DEFAULT_EXEMPT_PATHS: Set[str] = {
        "/health",
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    def __init__(
        self,
        app,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
        exempt_paths: Optional[Set[str]] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        super().__init__(app)
        # Read from settings by default, allowing constructor overrides for tests
        sec_cfg = getattr(settings, "security", None)
        self.enabled = (
            enabled
            if enabled is not None
            else getattr(sec_cfg, "enable_rate_limiting", True)
        )
        self.max_requests = (
            max_requests
            if max_requests is not None
            else getattr(sec_cfg, "rate_limit_requests", 60)
        )
        self.window_seconds = (
            window_seconds
            if window_seconds is not None
            else getattr(sec_cfg, "rate_limit_window", 60)
        )
        self.exempt_paths = exempt_paths or self.DEFAULT_EXEMPT_PATHS
        self._client_records: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request headers or remote host."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Bypass rate limits for health checks and documentation endpoints
        path = request.url.path.rstrip("/") or "/"
        if path in self.exempt_paths:
            return await call_next(request)

        now = time.time()
        client_id = self._get_client_id(request)
        cutoff = now - self.window_seconds

        with self._lock:
            # Prune expired timestamps
            timestamps = self._client_records[client_id]
            self._client_records[client_id] = [t for t in timestamps if t > cutoff]
            timestamps = self._client_records[client_id]

            if len(timestamps) >= self.max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - earliest)))
                logger.warning(
                    f"Rate limit exceeded for client {client_id} on {request.url.path}. "
                    f"Limit: {self.max_requests} req / {self.window_seconds}s. Retry after: {retry_after}s"
                )
                # Best-effort metric recording
                try:
                    from ragbot.outputs.metrics import metrics_manager
                    metrics_manager.record_rate_limit_hit(user_id=hash(client_id) % 100000)
                except Exception:
                    pass

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Please retry later.",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(earliest + self.window_seconds)),
                    },
                )

            # Record this request
            timestamps.append(now)
            remaining = max(0, self.max_requests - len(timestamps))
            reset_time = int(now + self.window_seconds)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response
