"""Client Address resolution through trusted proxies only.

Security fix C9 (Phase 3, see docs/BASELINE_AUDIT.md).

The Client Address is the TCP peer of the connection. Headers that claim a
different address (``X-Forwarded-For``, ``X-Real-IP``, ``Forwarded``,
``CF-Connecting-IP``, ``True-Client-IP`` and similar) are ignored, with one
exception: when the TCP peer is listed in ``SECURITY_TRUSTED_PROXIES``, the
service reads ``X-Forwarded-For`` from right to left and uses the first
address that is not a trusted proxy. No proxy is trusted by default.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from collections.abc import Iterable

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]

TRUSTED_PROXIES_ENV = "SECURITY_TRUSTED_PROXIES"

#: Only the nearest hops of X-Forwarded-For are examined.
MAX_FORWARDED_HOPS = 20

#: Trusted networks wider than these prefixes get a startup warning.
BROAD_IPV4_PREFIX = 16
BROAD_IPV6_PREFIX = 48

#: IPv6 Client Addresses share one rate limit counter per network of this size.
IPV6_SUBJECT_PREFIX = 64

_CATCH_ALL_ENTRIES = frozenset({"*", "all", "any"})


class TrustedProxyConfigError(ValueError):
    """SECURITY_TRUSTED_PROXIES contains an invalid or unsafe entry."""


def parse_ip_address(value: str | None) -> IPAddress | None:
    """Parse one address from a TCP peer or an X-Forwarded-For entry.

    Accepts ``198.51.100.7``, ``198.51.100.7:5678``, ``2001:db8::1``,
    ``[2001:db8::1]`` and ``[2001:db8::1]:443``. IPv4-mapped IPv6 addresses
    are returned as IPv4. Returns ``None`` for anything else, for example
    ``unknown`` or a host name.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("["):
        end = text.find("]")
        if end == -1:
            return None
        rest = text[end + 1 :]
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return None
        text = text[1:end]
    elif text.count(":") == 1:
        host, _, port = text.partition(":")
        if not port.isdigit():
            return None
        text = host
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


@dataclass(frozen=True)
class TrustedProxies:
    """Networks whose X-Forwarded-For header the service believes."""

    networks: tuple[IPNetwork, ...] = ()

    @property
    def enabled(self) -> bool:
        """True when at least one trusted proxy network is configured."""
        return bool(self.networks)

    def is_trusted(self, address: IPAddress | None) -> bool:
        """Return True if ``address`` is inside a trusted proxy network."""
        if address is None:
            return False
        return any(address in network for network in self.networks)

    def broad_networks(self) -> list[IPNetwork]:
        """Return the trusted networks that are wide enough to warn about."""
        broad: list[IPNetwork] = []
        for network in self.networks:
            limit = BROAD_IPV4_PREFIX if network.version == 4 else BROAD_IPV6_PREFIX
            if network.prefixlen < limit:
                broad.append(network)
        return broad


def _catch_all_message(entry: str) -> str:
    return (
        f"{TRUSTED_PROXIES_ENV} entry {entry!r} would trust every client, so any "
        "caller could choose its own address. List only the addresses or "
        "networks of your reverse proxies."
    )


def parse_trusted_proxies(raw: str | None) -> TrustedProxies:
    """Parse SECURITY_TRUSTED_PROXIES: comma-separated IP addresses and networks.

    Raises TrustedProxyConfigError for an entry that is not an IP address or a
    CIDR network, and for catch-all entries (``*``, ``0.0.0.0/0``, ``::/0``).
    """
    networks: list[IPNetwork] = []
    for entry in (raw or "").split(","):
        item = entry.strip()
        if not item:
            continue
        if item.lower() in _CATCH_ALL_ENTRIES:
            raise TrustedProxyConfigError(_catch_all_message(item))
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError as exc:
            raise TrustedProxyConfigError(
                f"Invalid {TRUSTED_PROXIES_ENV} entry {item!r}: expected an IP "
                "address or a CIDR network such as 10.0.0.0/8."
            ) from exc
        if network.prefixlen == 0:
            raise TrustedProxyConfigError(_catch_all_message(item))
        networks.append(network)
    return TrustedProxies(tuple(networks))


def _forwarded_hops(values: Iterable[str]) -> list[str]:
    hops: list[str] = []
    for value in values:
        hops.extend(value.split(","))
    return hops[-MAX_FORWARDED_HOPS:]


def resolve_client_address(
    peer_host: str | None,
    forwarded_for: Iterable[str],
    trusted: TrustedProxies,
) -> tuple[str | None, bool]:
    """Return ``(client_address, peer_is_trusted)`` for one request.

    - The TCP peer is not a trusted proxy (always true when none is
      configured): the peer is the Client Address and every forwarded header
      is ignored.
    - The peer is a trusted proxy: ``X-Forwarded-For`` is read from right to
      left, and the first address that is not a trusted proxy is the Client
      Address. If every hop is trusted, the leftmost hop is used. An entry
      that is not an IP address stops the walk and the nearest trusted hop is
      used, so a malformed value never becomes the Client Address.
    """
    peer = parse_ip_address(peer_host)
    if peer is None or not trusted.is_trusted(peer):
        return peer_host, False
    nearest: IPAddress = peer
    for raw in reversed(_forwarded_hops(forwarded_for)):
        address = parse_ip_address(raw)
        if address is None:
            break
        if not trusted.is_trusted(address):
            return str(address), True
        nearest = address
    return str(nearest), True


def forwarded_proto(values: Iterable[str]) -> str | None:
    """Return ``http`` or ``https`` from the last X-Forwarded-Proto value."""
    last: str | None = None
    for value in values:
        for part in value.split(","):
            candidate = part.strip().lower()
            if candidate:
                last = candidate
    return last if last in ("http", "https") else None


def rate_limit_address_key(address: str | None) -> str:
    """Return the Client Address part of a Rate Limit Subject.

    IPv4 addresses are used as they are. IPv6 addresses are grouped by their
    /64 network, because one client normally controls a whole /64. A value
    that is not an IP address (for example ``testclient`` from Starlette's
    TestClient) is used as it is, shortened to 64 characters.
    """
    parsed = parse_ip_address(address)
    if parsed is None:
        return (address or "unknown")[:64]
    if isinstance(parsed, ipaddress.IPv6Address):
        network = ipaddress.IPv6Network((parsed, IPV6_SUBJECT_PREFIX), strict=False)
        return str(network)
    return str(parsed)
