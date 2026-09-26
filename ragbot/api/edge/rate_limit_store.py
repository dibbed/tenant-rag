"""Rate limit stores: per-instance memory and shared Redis.

Security fix C9 (Phase 3, see docs/BASELINE_AUDIT.md). Both stores count with
the same sliding-window log: one Rate Limit Subject may make at most ``limit``
requests in any ``window`` seconds. A refused request is not recorded, and
records are deleted when their window has passed (AC-MTS-EDGE-002.5).
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import math
import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from ragbot.outputs.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

#: Redis keys are ``ratelimit:v1:<first 40 hex digits of sha256(subject)>``.
REDIS_KEY_PREFIX = "ratelimit:v1:"
#: Longest time one shared store call may take before the request falls back.
REDIS_TIMEOUT_SECONDS = 0.25
#: Time before the shared store is tried again after a failure.
FALLBACK_COOLDOWN_SECONDS = 30.0
#: Largest number of subjects that one memory store keeps.
DEFAULT_MAX_SUBJECTS = 100_000

# Sliding-window log for one subject, run atomically by Redis. It uses the
# Redis server clock, so instances with different clocks agree. Redis 5+.
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local member = ARGV[3]
local clock = redis.call('TIME')
local now_ms = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local reset_ms = window_ms
  if oldest[2] then
    reset_ms = tonumber(oldest[2]) + window_ms - now_ms
  end
  return {0, 0, reset_ms}
end
redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
return {1, limit - count - 1, tonumber(first[2]) + window_ms - now_ms}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    """The result of counting one request."""

    allowed: bool
    limit: int
    remaining: int
    #: Seconds until the oldest counted request leaves the window.
    reset_after: float
    #: Whole seconds the caller should wait; 0 when the request is allowed.
    retry_after: int
    #: Store that made the decision: ``memory`` or ``redis``.
    store: str


class RateLimitStore(Protocol):
    """Counts requests per Rate Limit Subject."""

    @property
    def name(self) -> str:
        """Short store name for logs."""
        ...

    async def hit(self, subject: str, limit: int, window: float) -> RateLimitDecision:
        """Count one request for ``subject`` and return the decision."""
        ...

    def sweep(self) -> int:
        """Delete records whose window has passed; return the subjects removed."""
        ...

    async def close(self) -> None:
        """Release the resources of the store."""
        ...


def _retry_after(reset_after: float) -> int:
    return max(1, math.ceil(reset_after))


class MemoryRateLimitStore:
    """Per-instance sliding-window log.

    Records of a subject are deleted when its window has passed: when the
    subject is counted again, during a sweep (at most once per window during
    requests, and by the background task that the application lifespan
    starts), and when the number of subjects reaches ``max_subjects`` (least
    recently used first).
    """

    name = "memory"

    def __init__(
        self,
        *,
        max_subjects: int = DEFAULT_MAX_SUBJECTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._records: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._clock = clock
        self._max_subjects = max(1, int(max_subjects))
        self._window = 60.0
        self._last_sweep = clock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    async def hit(self, subject: str, limit: int, window: float) -> RateLimitDecision:
        """Count one request for ``subject``."""
        return self.hit_now(subject, limit, window)

    def hit_now(self, subject: str, limit: int, window: float) -> RateLimitDecision:
        """Synchronous form of :meth:`hit`."""
        limit = max(1, int(limit))
        window = max(1.0, float(window))
        now = self._clock()
        cutoff = now - window
        with self._lock:
            self._window = window
            if now - self._last_sweep >= window:
                self._sweep_locked(cutoff)
                self._last_sweep = now
            timestamps = self._records.get(subject)
            if timestamps is None:
                timestamps = deque()
                self._records[subject] = timestamps
                while len(self._records) > self._max_subjects:
                    self._records.popitem(last=False)
            else:
                self._records.move_to_end(subject)
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= limit:
                reset_after = max(0.0, timestamps[0] + window - now)
                return RateLimitDecision(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_after=reset_after,
                    retry_after=_retry_after(reset_after),
                    store=self.name,
                )
            timestamps.append(now)
            reset_after = max(0.0, timestamps[0] + window - now)
            return RateLimitDecision(
                allowed=True,
                limit=limit,
                remaining=limit - len(timestamps),
                reset_after=reset_after,
                retry_after=0,
                store=self.name,
            )

    def sweep(self) -> int:
        """Delete every subject whose window has passed."""
        with self._lock:
            now = self._clock()
            self._last_sweep = now
            return self._sweep_locked(now - self._window)

    def _sweep_locked(self, cutoff: float) -> int:
        expired = [
            subject
            for subject, stamps in self._records.items()
            if not stamps or stamps[-1] <= cutoff
        ]
        for subject in expired:
            del self._records[subject]
        return len(expired)

    async def close(self) -> None:
        """Nothing to release."""


def _redis_key(subject: str) -> str:
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:40]
    return f"{REDIS_KEY_PREFIX}{digest}"


def mask_url(url: str) -> str:
    """Return ``url`` with its password, if any, replaced by ``***``."""
    try:
        parts = urlsplit(url)
        password = parts.password
        port = parts.port
    except ValueError:
        return "<invalid url>"
    if password is None:
        return url
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if port is not None:
        host = f"{host}:{port}"
    user = parts.username or ""
    netloc = f"{user}:***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class RedisRateLimitStore:
    """Shared sliding-window log in Redis: one sorted set per subject.

    One atomic Lua script prunes old entries, counts, records the request and
    sets the key TTL to the window. Keys hold a SHA-256 digest of the subject,
    so addresses and principal ids never appear in Redis.
    """

    name = "redis"

    def __init__(
        self,
        url: str,
        *,
        client: Any = None,
        timeout: float = REDIS_TIMEOUT_SECONDS,
    ) -> None:
        self.url = url
        self._timeout = timeout
        if client is None:
            import redis.asyncio as redis_asyncio

            client = redis_asyncio.Redis.from_url(
                url,
                socket_timeout=timeout,
                socket_connect_timeout=timeout,
            )
        self._client: Any = client
        self._script: Any = client.register_script(_SLIDING_WINDOW_SCRIPT)

    async def hit(self, subject: str, limit: int, window: float) -> RateLimitDecision:
        """Count one request for ``subject`` in Redis."""
        limit = max(1, int(limit))
        window_ms = max(1000, int(float(window) * 1000))
        member = f"{time.time_ns()}-{secrets.token_hex(4)}"
        result = await asyncio.wait_for(
            self._script(keys=[_redis_key(subject)], args=[limit, window_ms, member]),
            timeout=self._timeout,
        )
        allowed, remaining, reset_ms = (int(value) for value in result)
        reset_after = max(0.0, reset_ms / 1000.0)
        return RateLimitDecision(
            allowed=bool(allowed),
            limit=limit,
            remaining=max(0, remaining),
            reset_after=reset_after,
            retry_after=0 if allowed else _retry_after(reset_after),
            store=self.name,
        )

    def sweep(self) -> int:
        """Redis deletes expired keys itself (key TTL)."""
        return 0

    async def close(self) -> None:
        """Close the Redis connection pool."""
        closer = getattr(self._client, "aclose", None) or getattr(
            self._client, "close", None
        )
        if closer is None:
            return
        result = closer()
        if inspect.isawaitable(result):
            await result


class FallbackRateLimitStore:
    """Shared store with an explicit per-instance fallback.

    AC-MTS-EDGE-002.3: if the shared store fails or is too slow, the request is
    counted in the local memory store. It is never allowed without being
    counted. One warning is logged when an outage starts, the shared store is
    tried again after ``cooldown`` seconds, and one message is logged when it
    recovers.
    """

    def __init__(
        self,
        primary: RateLimitStore,
        fallback: MemoryRateLimitStore | None = None,
        *,
        cooldown: float = FALLBACK_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.primary = primary
        self.fallback = fallback if fallback is not None else MemoryRateLimitStore()
        self._cooldown = cooldown
        self._clock = clock
        self._retry_at: float | None = None
        self.outages = 0
        self.fallback_hits = 0

    @property
    def name(self) -> str:
        """Short store name for logs."""
        return f"{self.primary.name} with per-instance fallback"

    @property
    def degraded(self) -> bool:
        """True while requests are counted per instance because of an outage."""
        return self._retry_at is not None

    async def hit(self, subject: str, limit: int, window: float) -> RateLimitDecision:
        """Count in the shared store, or per instance while it is unavailable."""
        now = self._clock()
        if self._retry_at is None or now >= self._retry_at:
            try:
                decision = await self.primary.hit(subject, limit, window)
            except Exception as exc:
                if self._retry_at is None:
                    self.outages += 1
                    logger.warning(
                        "Rate limit shared store is unavailable "
                        f"({type(exc).__name__}). Requests are counted per instance "
                        "until it recovers."
                    )
                self._retry_at = now + self._cooldown
            else:
                if self._retry_at is not None:
                    self._retry_at = None
                    logger.info(
                        "Rate limit shared store recovered. Requests are counted "
                        "across instances again."
                    )
                return decision
        self.fallback_hits += 1
        return await self.fallback.hit(subject, limit, window)

    def sweep(self) -> int:
        """Delete expired records of the per-instance fallback."""
        return self.fallback.sweep()

    async def close(self) -> None:
        """Release the shared store."""
        await self.primary.close()
