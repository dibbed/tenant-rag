"""Request body size limit: the first stage of upload protection.

Security fix C11 (Phase 3, see docs/BASELINE_AUDIT.md). This pure ASGI
middleware applies the Upload Size Limit (``SECURITY_MAX_FILE_SIZE_MB``) to
every request body, plus 64 KiB for multipart framing:

- A declared ``Content-Length`` above the limit is answered with HTTP 413
  before any part of the body is read. A client that sent
  ``Expect: 100-continue`` then never sends the body.
- Otherwise the received bytes are counted. When the count passes the limit,
  the middleware stops reading, gives the application no more data and
  answers HTTP 413 itself, whatever the application does with the
  interrupted body.
- An invalid ``Content-Length`` is answered with HTTP 400.

The upload route then copies the file to disk in bounded chunks and applies
the exact file size limit (``ragbot/api/routes/documents.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from ragbot.configs.settings import settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: Room for multipart boundaries and part headers on top of the file size.
MULTIPART_ALLOWANCE_BYTES = 64 * 1024
DEFAULT_UPLOAD_LIMIT_MB = 50


def upload_limit_mb() -> int:
    """The Upload Size Limit in MB (``SECURITY_MAX_FILE_SIZE_MB``, default 50)."""
    value = getattr(
        getattr(settings, "security", None), "max_file_size_mb", DEFAULT_UPLOAD_LIMIT_MB
    )
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_UPLOAD_LIMIT_MB


def payload_too_large_response(max_mb: int) -> JSONResponse:
    """HTTP 413 response that tells the caller the limit (AC-MTS-EDGE-004.4)."""
    return JSONResponse(
        status_code=413,
        content={
            "detail": f"Request body exceeds maximum allowed size of {max_mb}MB",
            "max_size_mb": max_mb,
            "max_size_bytes": max_mb * 1024 * 1024,
        },
        headers={"Connection": "close"},
    )


class RequestBodyTooLarge(Exception):
    """Raised to the application when the received body passes the limit."""


class BodySizeLimitMiddleware:
    """Rejects request bodies larger than the Upload Size Limit."""

    def __init__(
        self,
        app: ASGIApp,
        max_size_mb: int | Callable[[], int] | None = None,
        allowance_bytes: int = MULTIPART_ALLOWANCE_BYTES,
    ) -> None:
        self.app = app
        self._max_size_mb: int | Callable[[], int] = (
            max_size_mb if max_size_mb is not None else upload_limit_mb
        )
        self.allowance_bytes = max(0, int(allowance_bytes))

    def limits(self) -> tuple[int, int]:
        """Return ``(limit_mb, body_limit_bytes)``."""
        raw = self._max_size_mb() if callable(self._max_size_mb) else self._max_size_mb
        max_mb = max(1, int(raw))
        return max_mb, max_mb * 1024 * 1024 + self.allowance_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_mb, body_limit = self.limits()
        declared_values = Headers(scope=scope).getlist("content-length")
        if declared_values:
            distinct = {value.strip() for value in declared_values}
            declared = next(iter(distinct)) if len(distinct) == 1 else ""
            if not declared.isdigit():
                invalid = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                    headers={"Connection": "close"},
                )
                await invalid(scope, receive, send)
                return
            if int(declared) > body_limit:
                await payload_too_large_response(max_mb)(scope, receive, send)
                return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > body_limit:
                    exceeded = True
                    raise RequestBodyTooLarge(f"request body passed {body_limit} bytes")
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded and not response_started:
                # The 413 below replaces the response to the interrupted body.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started:
            await payload_too_large_response(max_mb)(scope, receive, send)
