"""Trusted proxy middleware: sets the Client Address of every request.

Security fix C9 (Phase 3, see docs/BASELINE_AUDIT.md). This is the only place
in the service that interprets forwarded headers. ``ragbot/main.py`` starts
uvicorn with ``proxy_headers=False`` so that uvicorn does not rewrite the
client address first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.datastructures import Headers

from ragbot.api.edge.client_address import (
    TrustedProxies,
    forwarded_proto,
    resolve_client_address,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

PEER_STATE_KEY = "edge_peer"
CLIENT_ADDRESS_STATE_KEY = "edge_client_address"


class TrustedProxyMiddleware:
    """Pure ASGI middleware. It must run before every other middleware.

    - The TCP peer is not a trusted proxy: the request is left unchanged, and
      ``X-Forwarded-For``, ``X-Real-IP``, ``Forwarded`` and similar headers
      have no effect.
    - The TCP peer is a trusted proxy: ``scope["client"]`` is set to the
      address the proxy reports, and ``X-Forwarded-Proto`` sets the scheme.
    """

    def __init__(
        self, app: ASGIApp, trusted_proxies: TrustedProxies | None = None
    ) -> None:
        self.app = app
        self.trusted_proxies = (
            trusted_proxies if trusted_proxies is not None else TrustedProxies()
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            peer_host: str | None = client[0] if client else None
            state: dict[str, Any] = scope.setdefault("state", {})
            state[PEER_STATE_KEY] = peer_host
            address = peer_host
            if self.trusted_proxies.enabled and peer_host is not None:
                headers = Headers(scope=scope)
                address, peer_trusted = resolve_client_address(
                    peer_host, headers.getlist("x-forwarded-for"), self.trusted_proxies
                )
                if peer_trusted:
                    scope["client"] = (address, 0)
                    proto = forwarded_proto(headers.getlist("x-forwarded-proto"))
                    if proto is not None:
                        if scope["type"] == "websocket":
                            scope["scheme"] = "wss" if proto == "https" else "ws"
                        else:
                            scope["scheme"] = proto
            state[CLIENT_ADDRESS_STATE_KEY] = address
        await self.app(scope, receive, send)
