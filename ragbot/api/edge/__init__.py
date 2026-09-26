"""Edge protection for the HTTP API (Phase 3 security hardening).

Audit findings C9, C10 and C11 in docs/BASELINE_AUDIT.md:

- ``client_address``: the Client Address is the TCP peer. Forwarded headers
  are used only when the peer is a configured trusted proxy.
- ``rate_limit_store`` and ``rate_limiter``: rate limits per Principal or per
  Client Address, with an optional shared Redis store and an explicit
  per-instance fallback.
- ``cors``: the browser origin allowlist.
- ``config``: environment settings, validation and startup messages.

See docs/features/edge-protection/README.md.
"""
