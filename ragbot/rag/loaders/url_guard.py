"""Server-side request forgery (SSRF) protection for outbound URL fetches.

Security fix C6 (Phase 2 hardening, see docs/BASELINE_AUDIT.md).

Before this change, ``/api/v1/documents/url`` fetched any http(s) URL,
followed redirects automatically, and had no host or IP restriction. The
fetched content was indexed and could be read back with ``/api/v1/query``, so
a caller could read internal services and cloud metadata endpoints.

Every loader that fetches a client-supplied URL now uses this module:

1. ``validate_url_target()`` runs before any network access. It accepts only
   ``http`` and ``https`` URLs with a host, and rejects:

   - localhost and internal host names (``localhost``, ``*.localhost``,
     ``*.local``, ``*.internal``, ``*.localdomain``, metadata host names),
   - IP literals that are not globally routable: loopback, RFC 1918 private,
     link-local, carrier-grade NAT, unique-local IPv6, multicast, reserved and
     unspecified addresses, including IPv4-mapped, NAT64, 6to4 and Teredo
     IPv6 forms and short numeric IPv4 forms such as ``127.1``,
   - cloud metadata addresses, including public ones such as the Azure
     WireServer address ``168.63.129.16``.

2. Redirects are never followed automatically. Each ``Location`` target is
   validated with ``validate_url_target()`` before it is requested.

3. ``SafeResolver`` checks every address that DNS returns, at connect time.
   This blocks host names that resolve to internal addresses and DNS
   rebinding between validation and connection. aiohttp does not call the
   resolver for IP-literal hosts; step 1 covers those.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any, Dict, List, Mapping, Optional, Union
from urllib.parse import urljoin, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver
from aiohttp.resolver import ThreadedResolver
from yarl import URL

from ragbot.rag.exceptions import DocumentProcessingError

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_REDIRECTS = 5
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "instance-data.ec2.internal",
    }
)
BLOCKED_HOSTNAME_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain")

# Cloud metadata and platform endpoints. Most of these are already
# non-global, but 168.63.129.16 (Azure WireServer) is a public address.
BLOCKED_IP_ADDRESSES = frozenset(
    ipaddress.ip_address(address)
    for address in (
        "169.254.169.254",  # AWS, GCP, Azure, OpenStack, DigitalOcean metadata
        "169.254.170.2",  # AWS ECS task metadata
        "100.100.100.200",  # Alibaba Cloud metadata
        "168.63.129.16",  # Azure WireServer
        "fd00:ec2::254",  # AWS IPv6 metadata
    )
)

_NAT64_NETWORK = ipaddress.ip_network("64:ff9b::/96")
_BACKSLASH = chr(92)
_NUMERIC_IPV4_CHARS = frozenset("0123456789abcdefxABCDEFX.")


class UnsafeURLError(DocumentProcessingError):
    """Raised when a URL points to a destination that must not be fetched."""

    def __init__(
        self, message: str, source: Optional[str] = None, details: Any = None
    ) -> None:
        super().__init__(message, document_type="url", source=source, details=details)


def _to_ip(address: Union[str, IPAddress]) -> Optional[IPAddress]:
    if isinstance(address, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return address
    try:
        return ipaddress.ip_address(str(address).strip().strip("[]"))
    except ValueError:
        return None


def _embedded_ipv4(ip: IPAddress) -> Optional[ipaddress.IPv4Address]:
    """Return the IPv4 address embedded in an IPv6 transition address."""
    if not isinstance(ip, ipaddress.IPv6Address):
        return None
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64_NETWORK:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    return None


def is_blocked_ip(address: Union[str, IPAddress]) -> bool:
    """Return True if an IP address must never be contacted.

    Input that cannot be parsed as an IP address is treated as blocked.
    """
    ip = _to_ip(address)
    if ip is None:
        return True
    if ip in BLOCKED_IP_ADDRESSES:
        return True
    embedded = _embedded_ipv4(ip)
    if embedded is not None and is_blocked_ip(embedded):
        return True
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    return not ip.is_global


def _numeric_ipv4(host: str) -> Optional[ipaddress.IPv4Address]:
    """Parse short or numeric IPv4 forms such as ``127.1`` or ``2130706433``.

    System resolvers accept these forms, so they are checked like IP literals.
    """
    if not host or not set(host) <= _NUMERIC_IPV4_CHARS:
        return None
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except (OSError, ValueError):
        return None


def _check_host(host: str, source: str) -> None:
    """Raise UnsafeURLError if a host name or IP literal is not allowed."""
    normalized = (host or "").strip().strip("[]").rstrip(".").lower()
    if not normalized:
        raise UnsafeURLError("URL has no host", source=source)
    if normalized in BLOCKED_HOSTNAMES or normalized.endswith(
        BLOCKED_HOSTNAME_SUFFIXES
    ):
        raise UnsafeURLError(f"URL target is not allowed: {normalized}", source=source)
    literal = _to_ip(normalized) or _numeric_ipv4(normalized)
    if literal is not None and is_blocked_ip(literal):
        raise UnsafeURLError(f"URL target is not allowed: {normalized}", source=source)


def validate_url_target(url: str) -> str:
    """Check that a URL may be fetched, before any network access.

    Returns the URL without surrounding whitespace, or raises UnsafeURLError.
    DNS is not resolved here; SafeResolver checks the resolved addresses at
    connect time.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURLError("URL is empty", source=str(url))
    candidate = url.strip()
    if _BACKSLASH in candidate or any(
        ord(ch) < 0x21 or ord(ch) == 0x7F for ch in candidate
    ):
        raise UnsafeURLError("URL contains forbidden characters", source=candidate)
    try:
        parts = urlsplit(candidate)
        _ = parts.port  # raises ValueError for an invalid port
        parsed = URL(candidate)
    except (TypeError, ValueError) as exc:
        raise UnsafeURLError("URL is malformed", source=candidate) from exc

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"URL scheme is not allowed: {scheme or '(none)'}", source=candidate
        )

    # Check the host as urllib and yarl (used by aiohttp) both see it, so a
    # parser difference cannot hide an internal target.
    if not parts.hostname or not parsed.host:
        raise UnsafeURLError("URL has no host", source=candidate)
    _check_host(parts.hostname, candidate)
    _check_host(parsed.host, candidate)
    return candidate


def resolve_redirect_target(current_url: str, location: str) -> str:
    """Resolve a redirect Location against the current URL and validate it."""
    target = urljoin(current_url, (location or "").strip())
    return validate_url_target(target)


class SafeResolver(AbstractResolver):
    """aiohttp resolver that rejects internal addresses at connect time."""

    def __init__(self, inner: Optional[Any] = None) -> None:
        self._inner = inner if inner is not None else ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> List[Dict[str, Any]]:
        _check_host(host, host)
        results = await self._inner.resolve(host, port, family)
        if not results:
            raise OSError(f"DNS lookup returned no addresses for {host}")
        for entry in results:
            address = entry.get("host") if isinstance(entry, Mapping) else None
            if address is None or is_blocked_ip(address):
                raise UnsafeURLError(
                    f"URL target resolves to a blocked address: {host}", source=host
                )
        return list(results)

    async def close(self) -> None:
        await self._inner.close()


def build_safe_connector() -> aiohttp.TCPConnector:
    """Return a TCP connector whose DNS resolution rejects internal addresses.

    Call it from a running event loop.
    """
    return aiohttp.TCPConnector(resolver=SafeResolver())


async def fetch_text_safely(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20.0,
    cookies: Optional[Any] = None,
    max_redirects: int = MAX_REDIRECTS,
) -> str:
    """GET a URL and return its text, with SSRF protection on every hop.

    Raises UnsafeURLError for blocked targets. HTTP and network failures raise
    the usual aiohttp errors (``raise_for_status`` is applied to the final
    response).
    """
    current_url = validate_url_target(url)
    async with aiohttp.ClientSession(
        headers=headers, connector=build_safe_connector()
    ) as session:
        for _ in range(max_redirects + 1):
            async with session.get(
                current_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=False,
                cookies=cookies,
            ) as response:
                location = response.headers.get("Location")
                if response.status in REDIRECT_STATUSES and location:
                    current_url = resolve_redirect_target(current_url, location)
                    continue
                response.raise_for_status()
                return await response.text()
    raise UnsafeURLError(f"Too many redirects for URL: {url}", source=url)
