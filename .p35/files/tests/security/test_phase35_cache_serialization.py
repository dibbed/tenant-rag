"""Phase 3.5 regression tests: the Redis cache stores JSON and never unpickles.

Bandit B301 (docs/security/PHASE3_5_SECURITY_HARDENING.md).

Vulnerability: RedisCache used pickle by default. Anyone who could write to the
Redis database (a shared or exposed Redis, another service with the same
credentials) could store a crafted value and run code in the application on
the next cache read.

Expected: values are stored as versioned JSON (ragbot/caching/cache_codec.py).
Legacy pickle entries, other formats and malformed data are cache misses and
are never unpickled.
"""

from __future__ import annotations

import ast
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ragbot.caching import redis_cache as redis_cache_module
from ragbot.caching.redis_cache import RedisCache

ROOT = Path(__file__).resolve().parents[2]


class _FakeRedis:
    """In-memory stand-in for redis.asyncio.Redis (the commands that RedisCache uses)."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    async def setex(self, key: str, ttl: int, value: bytes) -> bool:
        self.data[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        return sum(self.data.pop(key, None) is not None for key in keys)

    async def mget(self, keys: list[str]) -> list[bytes | None]:
        return [self.data.get(key) for key in keys]

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis: _FakeRedis) -> None:
        self.redis = redis
        self.commands: list[tuple[str, bytes]] = []

    def setex(self, key: str, ttl: int, value: bytes) -> _FakePipeline:
        self.commands.append((key, value))
        return self

    async def execute(self) -> list[bool]:
        for key, value in self.commands:
            self.redis.data[key] = value
        return [True] * len(self.commands)


class _Payload:
    """When it is unpickled, this object creates a marker file."""

    def __init__(self, marker: Path) -> None:
        self.marker = marker

    def __reduce__(self) -> Any:
        return (Path.touch, (self.marker,))


@pytest.fixture
def cache() -> RedisCache:
    cache = RedisCache(redis_url="redis://localhost:6379/15")
    cache._redis = _FakeRedis()
    return cache


@pytest.mark.parametrize(
    "value",
    [
        {"answer": "ok", "sources": ["a.txt"], "confidence": 0.5, "nested": {"list": [1, 2, None, True]}},
        [0.125, -1.5, 3.0],
        "text with unicode: \u0633\u0644\u0627\u0645",
        42,
        True,
    ],
    ids=["object", "embedding", "text", "int", "bool"],
)
async def test_json_values_round_trip(cache: RedisCache, value: Any) -> None:
    assert await cache.set("key", value) is True
    assert await cache.get("key") == value


async def test_tuples_and_numpy_values_are_stored_as_lists_and_numbers(cache: RedisCache) -> None:
    value = {"tuple": (1, 2), "array": np.array([0.5, 1.5]), "scalar": np.float32(2.5)}
    assert await cache.set("key", value) is True
    assert await cache.get("key") == {"tuple": [1, 2], "array": [0.5, 1.5], "scalar": 2.5}


async def test_many_values_round_trip(cache: RedisCache) -> None:
    assert await cache.set_many({"a": [1.0], "b": {"x": "y"}}) is True
    assert await cache.get_many(["a", "b", "missing"]) == {"a": [1.0], "b": {"x": "y"}}


async def test_an_entry_is_versioned_json(cache: RedisCache) -> None:
    await cache.set("key", {"a": 1})
    assert json.loads(cache._redis.data["key"].decode("utf-8")) == {
        "format": "tenant-rag/cache",
        "version": 1,
        "value": {"a": 1},
    }


@pytest.mark.parametrize(
    "value",
    [{1, 2}, object(), b"raw bytes", float("nan"), {"k": float("inf")}, {1: "int key"}, datetime(2026, 1, 1)],
    ids=["set", "object", "bytes", "nan", "infinity", "int-key", "datetime"],
)
async def test_a_value_without_a_json_form_is_not_cached(cache: RedisCache, value: Any) -> None:
    assert await cache.set("key", value) is False
    assert "key" not in cache._redis.data


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b"\xff\xfe\x00",
        b"{}",
        b"[1, 2]",
        b'"text"',
        b'{"format": "tenant-rag/cache", "version": 2, "value": 1}',
        b'{"format": "tenant-rag/cache", "version": true, "value": 1}',
        b'{"format": "tenant-rag/cache", "version": "1", "value": 1}',
        b'{"format": "other", "version": 1, "value": 1}',
        b'{"format": "tenant-rag/cache", "version": 1}',
        b'{"format": "tenant-rag/cache", "version": 1, "value": 1, "extra": 2}',
        b'{"format": "tenant-rag/cache", "version": 1, "value": NaN}',
    ],
    ids=[
        "not-json",
        "not-utf8",
        "empty-object",
        "list",
        "string",
        "future-version",
        "boolean-version",
        "string-version",
        "other-format",
        "no-value",
        "extra-field",
        "nan",
    ],
)
async def test_a_malformed_or_foreign_entry_is_a_miss(cache: RedisCache, raw: bytes) -> None:
    cache._redis.data["key"] = raw
    assert await cache.get("key") is None
    assert await cache.get_many(["key"]) == {}
    assert cache.get_stats()["errors"] >= 1


async def test_a_legacy_pickle_entry_is_never_unpickled(cache: RedisCache, tmp_path: Path) -> None:
    marker = tmp_path / "p35-cache-marker"
    cache._redis.data["key"] = pickle.dumps(_Payload(marker))
    assert await cache.get("key") is None
    assert await cache.get_many(["key"]) == {}
    assert not marker.exists()


async def test_a_benign_legacy_pickle_entry_is_a_miss(cache: RedisCache) -> None:
    cache._redis.data["key"] = pickle.dumps({"answer": "cached by an earlier version"})
    assert await cache.get("key") is None


def test_pickle_serialization_is_refused() -> None:
    with pytest.raises(ValueError, match="pickle"):
        RedisCache(redis_url="redis://localhost:6379/15", serialization="pickle")


def test_the_redis_password_is_not_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    real = redis_cache_module.logger

    class _RecordingLogger:
        def __getattr__(self, name: str) -> Any:
            return getattr(real, name)

        def info(self, message: str, *args: Any, **kwargs: Any) -> None:
            messages.append(message)

    monkeypatch.setattr(redis_cache_module, "logger", _RecordingLogger())
    RedisCache(redis_url="redis://cache-user:s3cr3t-value@cache.internal:6380/2")
    assert messages
    assert all("s3cr3t-value" not in message for message in messages)
    assert any("cache.internal:6380" in message for message in messages)


def test_the_cache_modules_do_not_import_pickle() -> None:
    unsafe = {"pickle", "cPickle", "dill", "cloudpickle", "shelve", "jsonpickle"}
    for relative in ("ragbot/caching/redis_cache.py", "ragbot/caching/cache_codec.py"):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not imported & unsafe, relative
