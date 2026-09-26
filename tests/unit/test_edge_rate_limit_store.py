"""Unit tests for rate limit stores, the limiter and edge settings (C9)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from ragbot.api.edge import rate_limit_store
from ragbot.api.edge.rate_limit_store import (
    FallbackRateLimitStore,
    MemoryRateLimitStore,
    RateLimitDecision,
    RedisRateLimitStore,
    mask_url,
)
from ragbot.api.edge.rate_limiter import (
    RateLimiter,
    address_subject,
    principal_subject,
    rate_limit_headers,
)


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeScript:
    """Stands in for the Redis Lua script, with the same sliding-window rules."""

    def __init__(self, fail: BaseException | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[list[str], list[Any]]] = []
        self.memory = MemoryRateLimitStore()

    async def __call__(self, keys: list[str], args: list[Any]) -> list[int]:
        self.calls.append((keys, args))
        if self.fail is not None:
            raise self.fail
        limit, window_ms, _member = args
        decision = self.memory.hit_now(keys[0], int(limit), int(window_ms) / 1000)
        return [
            int(decision.allowed),
            decision.remaining,
            int(decision.reset_after * 1000),
        ]


class FakeRedis:
    def __init__(self, fail: BaseException | None = None) -> None:
        self.script = FakeScript(fail)
        self.closed = False

    def register_script(self, source: str) -> FakeScript:
        assert "ZREMRANGEBYSCORE" in source
        assert "PEXPIRE" in source
        assert "TIME" in source
        return self.script

    async def aclose(self) -> None:
        self.closed = True


# Memory store


def test_memory_store_allows_the_limit_then_refuses():
    store = MemoryRateLimitStore(clock=FakeClock())
    decisions = [store.hit_now("s", 3, 60) for _ in range(4)]
    assert [decision.allowed for decision in decisions] == [True, True, True, False]
    assert [decision.remaining for decision in decisions] == [2, 1, 0, 0]
    assert decisions[3].retry_after == 60
    assert decisions[3].store == "memory"


def test_refused_requests_are_not_recorded_and_the_window_slides():
    clock = FakeClock()
    store = MemoryRateLimitStore(clock=clock)
    store.hit_now("s", 2, 10)
    clock.advance(5)
    store.hit_now("s", 2, 10)
    assert not store.hit_now("s", 2, 10).allowed
    clock.advance(5.1)
    decision = store.hit_now("s", 2, 10)
    assert decision.allowed
    assert decision.remaining == 0


def test_records_are_deleted_after_their_window():
    clock = FakeClock()
    store = MemoryRateLimitStore(clock=clock)
    for index in range(50):
        store.hit_now(f"address:198.51.100.{index}", 5, 60)
    assert len(store) == 50
    clock.advance(61)
    assert store.sweep() == 50
    assert len(store) == 0


def test_expired_subjects_are_swept_during_requests():
    clock = FakeClock()
    store = MemoryRateLimitStore(clock=clock)
    for index in range(20):
        store.hit_now(f"old-{index}", 5, 60)
    clock.advance(61)
    store.hit_now("new", 5, 60)
    assert len(store) == 1


def test_number_of_subjects_is_capped():
    store = MemoryRateLimitStore(max_subjects=100, clock=FakeClock())
    for index in range(1000):
        store.hit_now(f"address:{index}", 5, 60)
    assert len(store) == 100


# Limiter


async def test_limiters_that_share_a_store_share_the_count():
    shared = MemoryRateLimitStore()
    first = RateLimiter(shared, max_requests=3, window_seconds=60)
    second = RateLimiter(shared, max_requests=3, window_seconds=60)
    subject = "address:198.51.100.1"
    results = [
        await first.hit(subject),
        await second.hit(subject),
        await first.hit(subject),
        await second.hit(subject),
    ]
    assert [result.allowed for result in results] == [True, True, True, False]


async def test_limiters_with_their_own_store_count_separately():
    first = RateLimiter(MemoryRateLimitStore(), max_requests=1)
    second = RateLimiter(MemoryRateLimitStore(), max_requests=1)
    assert (await first.hit("s")).allowed
    assert (await second.hit("s")).allowed
    assert not (await first.hit("s")).allowed


def test_subject_names():
    assert principal_subject("tenant-a", "key-1") == "principal:tenant-a:key-1"
    assert address_subject("198.51.100.7") == "address:198.51.100.7"
    assert address_subject("2001:db8:1:2::99") == "address:2001:db8:1:2::/64"


def test_headers_of_a_refused_decision():
    decision = RateLimitDecision(
        allowed=False,
        limit=10,
        remaining=0,
        reset_after=12.5,
        retry_after=13,
        store="memory",
    )
    assert rate_limit_headers(decision, now=1000.0) == {
        "X-RateLimit-Limit": "10",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1012",
        "Retry-After": "13",
    }


async def test_refusals_are_logged_once_per_subject_and_window(monkeypatch):
    from ragbot.api.edge import rate_limiter as limiter_module

    fake_logger = MagicMock()
    monkeypatch.setattr(limiter_module, "logger", fake_logger)
    limiter = RateLimiter(MemoryRateLimitStore(), max_requests=1, window_seconds=60)
    for _ in range(5):
        await limiter.hit("address:198.51.100.1")
    assert fake_logger.warning.call_count == 1


async def test_background_sweep_starts_and_stops():
    closed = []

    class Store(MemoryRateLimitStore):
        async def close(self) -> None:
            closed.append(True)

    limiter = RateLimiter(Store(), window_seconds=60)
    limiter.start_background_sweep()
    task = limiter._sweep_task
    assert task is not None and not task.done()
    await limiter.aclose()
    assert task.done()
    assert closed == [True]


# Shared Redis store and fallback


async def test_redis_store_hashes_subjects_and_reads_decisions():
    client = FakeRedis()
    store = RedisRateLimitStore("redis://cache.example:6379/0", client=client)
    decisions = [await store.hit("address:198.51.100.1", 2, 60) for _ in range(3)]
    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert decisions[2].retry_after >= 1
    assert all(decision.store == "redis" for decision in decisions)
    key = client.script.calls[0][0][0]
    assert key.startswith("ratelimit:v1:")
    assert "198.51.100.1" not in key
    assert client.script.calls[0][1][:2] == [2, 60000]
    await store.close()
    assert client.closed


async def test_fallback_keeps_limiting_and_warns_once(monkeypatch):
    fake_logger = MagicMock()
    monkeypatch.setattr(rate_limit_store, "logger", fake_logger)
    clock = FakeClock()
    client = FakeRedis(fail=ConnectionError("redis is down"))
    primary = RedisRateLimitStore("redis://cache.example:6379/0", client=client)
    store = FallbackRateLimitStore(
        primary, MemoryRateLimitStore(clock=clock), cooldown=30, clock=clock
    )
    decisions = [await store.hit("s", 2, 60) for _ in range(3)]
    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert all(decision.store == "memory" for decision in decisions)
    assert store.degraded
    assert fake_logger.warning.call_count == 1
    assert len(client.script.calls) == 1


async def test_fallback_retries_after_the_cooldown_and_logs_recovery(monkeypatch):
    fake_logger = MagicMock()
    monkeypatch.setattr(rate_limit_store, "logger", fake_logger)
    clock = FakeClock()
    client = FakeRedis(fail=TimeoutError("slow"))
    primary = RedisRateLimitStore("redis://cache.example:6379/0", client=client)
    store = FallbackRateLimitStore(
        primary, MemoryRateLimitStore(clock=clock), cooldown=30, clock=clock
    )
    await store.hit("s", 5, 60)
    assert store.degraded
    client.script.fail = None
    clock.advance(10)
    await store.hit("s", 5, 60)
    assert len(client.script.calls) == 1
    clock.advance(21)
    decision = await store.hit("s", 5, 60)
    assert decision.store == "redis"
    assert not store.degraded
    assert fake_logger.warning.call_count == 1
    assert fake_logger.info.call_count == 1


async def test_slow_shared_store_times_out_and_falls_back():
    class SlowScript:
        async def __call__(self, keys: list[str], args: list[Any]) -> list[int]:
            await asyncio.sleep(5)
            return [1, 0, 0]

    class SlowRedis:
        def register_script(self, source: str) -> SlowScript:
            return SlowScript()

    primary = RedisRateLimitStore(
        "redis://cache.example:6379/0", client=SlowRedis(), timeout=0.05
    )
    store = FallbackRateLimitStore(primary)
    decision = await asyncio.wait_for(store.hit("s", 5, 60), timeout=2)
    assert decision.allowed
    assert decision.store == "memory"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("redis://localhost:6379/0", "redis://localhost:6379/0"),
        ("redis://:secret@redis:6379/1", "redis://:***@redis:6379/1"),
        (
            "rediss://user:secret@cache.example.com:6380/2",
            "rediss://user:***@cache.example.com:6380/2",
        ),
    ],
)
def test_mask_url_hides_passwords(url, expected):
    assert mask_url(url) == expected


# Settings and startup messages


def test_default_settings_are_secure():
    from ragbot.api.edge.config import load_edge_config

    config = load_edge_config({})
    assert config.environment == "production"
    assert not config.trusted_proxies.enabled
    assert config.cors.mode == "disabled"
    assert config.rate_limit_storage_url == ""


def test_invalid_storage_url_is_rejected():
    from ragbot.api.edge.config import load_edge_config

    with pytest.raises(ValueError, match="SECURITY_RATE_LIMIT_STORAGE_URL"):
        load_edge_config({"SECURITY_RATE_LIMIT_STORAGE_URL": "memcached://cache:11211"})


def test_storage_url_builds_a_shared_store_with_fallback():
    from ragbot.api.edge.config import build_rate_limiter, load_edge_config

    limiter = build_rate_limiter(
        load_edge_config({"SECURITY_RATE_LIMIT_STORAGE_URL": "redis://127.0.0.1:1/0"})
    )
    assert isinstance(limiter.store, FallbackRateLimitStore)
    assert isinstance(limiter.store.primary, RedisRateLimitStore)


def test_startup_messages_for_the_default_settings(monkeypatch):
    from ragbot.api.edge import config as edge_config

    fake_logger = MagicMock()
    monkeypatch.setattr(edge_config, "logger", fake_logger)
    modes = edge_config.log_edge_protection_mode(
        edge_config.load_edge_config({}), environ={"WORKERS": "4"}
    )
    assert modes == {
        "trusted_proxies": "none",
        "rate_limit_store": "per-instance",
        "cors": "disabled",
        "upload_limit_mb": modes["upload_limit_mb"],
    }
    infos = " ".join(call.args[0] for call in fake_logger.info.call_args_list)
    warnings = " ".join(call.args[0] for call in fake_logger.warning.call_args_list)
    assert "no trusted proxy is configured" in infos
    assert "counted per instance" in infos
    assert "WORKERS=4" in warnings


def test_startup_messages_warn_about_wide_networks_and_hide_passwords(monkeypatch):
    from ragbot.api.edge import config as edge_config

    fake_logger = MagicMock()
    monkeypatch.setattr(edge_config, "logger", fake_logger)
    config = edge_config.load_edge_config(
        {
            "SECURITY_TRUSTED_PROXIES": "10.0.0.0/8",
            "SECURITY_RATE_LIMIT_STORAGE_URL": "redis://:secret@redis:6379/1",
            "SECURITY_CORS_ALLOWED_ORIGINS": "http://intranet.example",
        }
    )
    modes = edge_config.log_edge_protection_mode(config, environ={})
    assert modes["trusted_proxies"] == "configured"
    assert modes["rate_limit_store"] == "shared"
    assert modes["cors"] == "allowlist"
    messages = " ".join(
        call.args[0]
        for call in fake_logger.info.call_args_list + fake_logger.warning.call_args_list
    )
    assert "10.0.0.0/8 is a wide network" in messages
    assert "plain HTTP outside development" in messages
    assert "secret" not in messages
