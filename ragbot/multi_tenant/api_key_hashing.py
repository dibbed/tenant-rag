"""API key format, hashing and verification for tenant credentials.

Security fix C3 (Phase 2 hardening, see docs/BASELINE_AUDIT.md).

Before this change, API keys were stored as unsalted SHA-256 digests, and the
lookup code also accepted the stored digest itself as a credential. Anyone
who could read ``tenants.db`` (or a backup) could authenticate without the
secret key.

Key format (returned once, never stored)::

    rgb_<key_id>_<secret>

- ``key_id``: 32 lowercase hex characters (``uuid4().hex``). It is stored in
  ``tenant_api_keys.key_id`` and used for direct lookup, so the slow KDF runs
  once per verification.
- ``secret``: ``secrets.token_urlsafe(32)`` (256 bits of entropy).

Stored credential (``tenant_api_keys.key_hash``)::

    scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>

The full key string, including the key id, is the scrypt input, so a stored
hash cannot be moved to another key id.

Legacy keys (``rgb_<token>`` with an unsalted SHA-256 ``key_hash``) are
rejected with :data:`LEGACY_API_KEY_ERROR`. Operators must issue new keys.
See SECURITY.md, "API key migration".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

API_KEY_PREFIX = "rgb_"

# scrypt cost for new keys. n=2**14 and r=8 need about 16 MiB of memory and
# take tens of milliseconds per verification on current CPUs.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_SALT_BYTES = 16
SCRYPT_MAXMEM = 64 * 1024 * 1024

# Upper bounds for parameters read from storage, so a tampered database row
# cannot make verification use unbounded CPU or memory.
_MAX_SCRYPT_N = 2**20
_MAX_SCRYPT_R = 32
_MAX_SCRYPT_P = 16
_MAX_DKLEN = 64

# Successful verifications are remembered in process memory for a short time
# (key id and a SHA-256 digest of the presented key) so scrypt does not run
# on every request. The cache is never persisted and does not bypass the
# revocation or expiry checks.
VERIFIED_KEY_CACHE_TTL_SECONDS = 300.0
VERIFIED_KEY_CACHE_MAX_ENTRIES = 10000

_SCHEME = "scrypt"
_API_KEY_RE = re.compile(r"^rgb_([0-9a-f]{32})_([A-Za-z0-9_-]{32,128})$")
_LEGACY_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

LEGACY_API_KEY_ERROR = (
    "Legacy API key format is no longer accepted. Issue a new API key and "
    "revoke the old one (see SECURITY.md, 'API key migration')."
)


@dataclass(frozen=True)
class ParsedApiKey:
    """The two parts of a current-format API key."""

    key_id: str
    secret: str


def generate_api_key() -> Tuple[str, str]:
    """Create a new key id and raw API key. Returns ``(key_id, raw_key)``."""
    key_id = uuid.uuid4().hex
    secret = secrets.token_urlsafe(32)
    return key_id, f"{API_KEY_PREFIX}{key_id}_{secret}"


def parse_api_key(raw_key: object) -> Optional[ParsedApiKey]:
    """Parse a current-format key. Returns None for any other input."""
    if not isinstance(raw_key, str):
        return None
    match = _API_KEY_RE.match(raw_key.strip())
    if match is None:
        return None
    return ParsedApiKey(key_id=match.group(1), secret=match.group(2))


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_api_key_secret(
    raw_key: str, *, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P
) -> str:
    """Return the stored scrypt credential for a raw API key."""
    salt = secrets.token_bytes(SCRYPT_SALT_BYTES)
    digest = hashlib.scrypt(
        raw_key.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=SCRYPT_MAXMEM,
        dklen=SCRYPT_DKLEN,
    )
    return f"{_SCHEME}${n}${r}${p}${_b64encode(salt)}${_b64encode(digest)}"


def is_scrypt_hash(stored: object) -> bool:
    """Return True if a stored credential uses the scrypt scheme."""
    return isinstance(stored, str) and stored.startswith(_SCHEME + "$")


def is_legacy_sha256_hash(stored: object) -> bool:
    """Return True if a stored credential is a legacy SHA-256 hex digest."""
    return isinstance(stored, str) and _LEGACY_SHA256_RE.match(stored) is not None


def describe_hash_scheme(stored: object) -> str:
    """Return ``scrypt``, ``legacy-sha256`` or ``unknown`` for a stored hash."""
    if is_scrypt_hash(stored):
        return "scrypt"
    if is_legacy_sha256_hash(stored):
        return "legacy-sha256"
    return "unknown"


def legacy_sha256_digest(raw_key: str) -> str:
    """SHA-256 digest of the legacy scheme.

    Used only to detect and revoke legacy keys. Never used to authenticate.
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _parse_stored(stored: str) -> Optional[Tuple[int, int, int, bytes, bytes]]:
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != _SCHEME:
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = _b64decode(parts[4])
        expected = _b64decode(parts[5])
    except (TypeError, ValueError):
        return None
    if n < 2 or n > _MAX_SCRYPT_N or n & (n - 1):
        return None
    if not 1 <= r <= _MAX_SCRYPT_R or not 1 <= p <= _MAX_SCRYPT_P:
        return None
    if not salt or not 16 <= len(expected) <= _MAX_DKLEN:
        return None
    return n, r, p, salt, expected


def verify_api_key_secret(raw_key: str, stored: str) -> bool:
    """Verify a raw key against a stored scrypt credential in constant time."""
    if not isinstance(raw_key, str) or not is_scrypt_hash(stored):
        return False
    parsed = _parse_stored(stored)
    if parsed is None:
        return False
    n, r, p, salt, expected = parsed
    try:
        candidate = hashlib.scrypt(
            raw_key.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except (MemoryError, ValueError):
        return False
    return hmac.compare_digest(candidate, expected)
