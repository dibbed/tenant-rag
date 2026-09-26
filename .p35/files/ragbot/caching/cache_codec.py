"""Safe value encoding for the Redis cache (no pickle).

Security (Phase 3.5, Bandit B301): the Redis cache stored values with pickle.
Anyone who could write to the Redis database (a shared or exposed Redis, or
another service with the same credentials) could store a crafted value and run
code in the application when it read the cache.

A cache entry is now UTF-8 JSON in a versioned envelope::

    {"format": "tenant-rag/cache", "version": 1, "value": <JSON value>}

Only JSON values are stored: None, bool, int, finite float, str, and lists and
objects with string keys. Tuples are stored as lists, NumPy arrays as lists and
NumPy scalars as numbers. Any other value raises CacheEncodeError when it is
stored, so it is not cached.

decode_cache_value accepts only this envelope. A legacy pickle entry of an
earlier version, an entry of another format or version, and malformed data
raise CacheDecodeError, and the cache treats them as misses. Nothing is ever
unpickled, so legacy entries need no migration: they are replaced when the
value is cached again, or they expire with their TTL.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

FORMAT = "tenant-rag/cache"
VERSION = 1
MAX_DEPTH = 64
_ENVELOPE_KEYS = frozenset({"format", "version", "value"})
# The first byte of a pickle of protocol 2 or later (PROTO opcode).
_PICKLE_MARKER = b"\x80"


class CacheCodecError(ValueError):
    """A value cannot be stored in, or read from, the cache."""


class CacheEncodeError(CacheCodecError):
    """The value has no JSON form."""


class CacheDecodeError(CacheCodecError):
    """The cache entry is not a valid entry of this format and version."""


class LegacyPickleEntryError(CacheDecodeError):
    """The cache entry was written with pickle by an earlier version; it is not read."""


def _plain(value: Any, depth: int = 0) -> Any:
    """Return ``value`` as JSON types, or raise CacheEncodeError."""
    if depth > MAX_DEPTH:
        raise CacheEncodeError("the value is nested too deeply")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CacheEncodeError("NaN and infinite numbers cannot be cached")
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(item, depth + 1) for item in value]
    if isinstance(value, dict):
        plain: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CacheEncodeError(f"object keys must be strings, not {type(key).__name__}")
            plain[key] = _plain(item, depth + 1)
        return plain
    if isinstance(value, (np.ndarray, np.generic)):
        return _plain(value.tolist(), depth + 1)
    raise CacheEncodeError(f"a value of type {type(value).__name__} cannot be cached")


def encode_cache_value(value: Any) -> bytes:
    """Encode ``value`` as a versioned JSON cache entry."""
    envelope = {"format": FORMAT, "version": VERSION, "value": _plain(value)}
    text = json.dumps(envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return text.encode("utf-8")


def _reject_constant(name: str) -> Any:
    raise CacheDecodeError(f"the cache entry contains {name}")


def decode_cache_value(data: Any) -> Any:
    """Decode a cache entry written by encode_cache_value."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise CacheDecodeError(f"a cache entry must be bytes, not {type(data).__name__}")
    raw = bytes(data)
    if raw.startswith(_PICKLE_MARKER):
        raise LegacyPickleEntryError(
            "the cache entry has the legacy pickle format; it is ignored and never unpickled"
        )
    try:
        envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except CacheDecodeError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise CacheDecodeError(f"the cache entry is not valid JSON: {exc}") from None
    if (
        not isinstance(envelope, dict)
        or set(envelope) != _ENVELOPE_KEYS
        or envelope["format"] != FORMAT
    ):
        raise CacheDecodeError("the cache entry is not a tenant-rag cache entry")
    version = envelope["version"]
    if type(version) is not int or version != VERSION:
        raise CacheDecodeError(f"unsupported cache entry version {version!r}")
    return envelope["value"]
