"""
Redis cache implementation for the RAG Telegram bot.

This module provides a Redis-based cache implementation with connection
pooling, serialization, and comprehensive error handling.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

from ragbot.caching.base import BaseCache
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

if TYPE_CHECKING:
    from redis.asyncio import ConnectionPool, Redis


class RedisCache(BaseCache):
    """
    Redis cache implementation with connection pooling and serialization.

    This cache uses Redis as the backend storage with automatic serialization
    and deserialization of Python objects.
    """

    def __init__(self, redis_url: str | None = None, default_ttl: int = 3600,
                 serialization: str = "json"):
        """
        Initialize the Redis cache.

        Args:
            redis_url: Redis connection URL (uses settings if None)
            default_ttl: Default time-to-live in seconds
            serialization: Serialization method. Only versioned JSON is supported.
        """
        super().__init__(default_ttl)
        self.redis_url = redis_url or settings.redis.url
        if serialization != "json":
            raise ValueError(
                "RedisCache only supports safe JSON serialization. "
                "Legacy pickle cache entries must be expired or deleted; they are never deserialized."
            )
        self.serialization = serialization
        self._redis: Redis | None = None
        self._connection_pool: ConnectionPool | None = None

        logger.info(f"RedisCache initialized with URL={self.redis_url}, serialization={serialization}")

    async def _get_redis(self) -> Redis:
        """Get Redis connection, creating it if necessary."""
        if self._redis is None:
            try:
                import redis.asyncio as redis

                # Create and validate a connection before publishing it.
                connection_pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    max_connections=settings.redis.max_connections,
                    socket_timeout=settings.redis.socket_timeout,
                    decode_responses=False,  # We handle serialization ourselves
                )
                client = redis.Redis(connection_pool=connection_pool)

                # Test connection
                await client.ping()
                self._connection_pool = connection_pool
                self._redis = client
                logger.info("Redis connection established successfully")

            except ImportError:
                logger.error("redis package not installed. Install with: pip install redis")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e!s}")
                self._record_error()
                raise

        assert self._redis is not None
        return self._redis

    _SERIALIZATION_VERSION = 1

    @classmethod
    def _validate_json_value(cls, value: Any, *, path: str = "value") -> None:
        """Validate the cache payload against the supported JSON data model."""
        if value is None or isinstance(value, str | bool | int):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(f"{path} contains a non-finite float")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                cls._validate_json_value(item, path=f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{path} contains a non-string object key")
                cls._validate_json_value(item, path=f"{path}.{key}")
            return
        raise TypeError(f"{path} contains unsupported type {type(value).__name__}")

    def _serialize(self, value: Any) -> bytes:
        """Serialize a cache value as a versioned, non-executable JSON payload."""
        try:
            self._validate_json_value(value)
            envelope = {
                "version": self._SERIALIZATION_VERSION,
                "value": value,
            }
            return json.dumps(
                envelope,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except Exception as e:
            logger.error(f"Serialization error: {e!s}")
            raise

    def _deserialize(self, data: bytes) -> Any:
        """Decode and validate a versioned JSON cache payload.

        Legacy pickle bytes are intentionally rejected rather than inspected or
        migrated in-process because deserializing them could execute code.
        """
        try:
            payload = json.loads(data.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Cache payload must be a JSON object")
            if payload.get("version") != self._SERIALIZATION_VERSION:
                raise ValueError("Unsupported cache payload version")
            if set(payload) != {"version", "value"}:
                raise ValueError("Cache payload has an invalid schema")
            value = payload["value"]
            self._validate_json_value(value)
            return value
        except Exception as e:
            logger.error(f"Deserialization error: {e!s}")
            raise

    async def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            redis = await self._get_redis()
            data = await redis.get(key)

            if data is None:
                self._record_miss()
                return None

            value = self._deserialize(data)
            self._record_hit()
            return value

        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e!s}")
            self._record_error()
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            True if successful, False otherwise
        """
        try:
            if ttl is None:
                ttl = self.default_ttl

            redis = await self._get_redis()
            data = self._serialize(value)

            result = await redis.setex(key, ttl, data)

            if result:
                self._record_set()
                return True
            return False

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e!s}")
            self._record_error()
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        try:
            redis = await self._get_redis()
            result = await redis.delete(key)

            if result > 0:
                self._record_delete()
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e!s}")
            self._record_error()
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        try:
            redis = await self._get_redis()
            result = await redis.exists(key)
            return bool(result > 0)

        except Exception as e:
            logger.error(f"Error checking cache key existence {key}: {e!s}")
            self._record_error()
            return False

    async def clear(self) -> bool:
        """
        Clear all cached values.

        Returns:
            True if successful, False otherwise
        """
        try:
            redis = await self._get_redis()
            await redis.flushdb()
            logger.info("Redis cache cleared")
            return True

        except Exception as e:
            logger.error(f"Error clearing cache: {e!s}")
            self._record_error()
            return False

    async def get_ttl(self, key: str) -> int | None:
        """
        Get the time-to-live for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds or None if key doesn't exist
        """
        try:
            redis = await self._get_redis()
            ttl = await redis.ttl(key)

            if ttl == -2:  # Key doesn't exist
                return None
            elif ttl == -1:  # Key exists but has no expiration
                return -1
            else:
                return int(ttl)

        except Exception as e:
            logger.error(f"Error getting TTL for cache key {key}: {e!s}")
            self._record_error()
            return None

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        Get multiple values from the cache efficiently.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values (missing keys are omitted)
        """
        try:
            if not keys:
                return {}

            redis = await self._get_redis()
            data_list = await redis.mget(keys)

            result = {}
            for key, data in zip(keys, data_list, strict=False):
                if data is not None:
                    try:
                        value = self._deserialize(data)
                        result[key] = value
                        self._record_hit()
                    except Exception as e:
                        logger.error(f"Error deserializing key {key}: {e!s}")
                        self._record_error()
                else:
                    self._record_miss()

            return result

        except Exception as e:
            logger.error(f"Error getting multiple cache keys: {e!s}")
            self._record_error()
            return {}

    async def set_many(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """
        Set multiple values in the cache efficiently.

        Args:
            mapping: Dictionary mapping keys to values
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            True if all operations successful, False otherwise
        """
        try:
            if not mapping:
                return True

            if ttl is None:
                ttl = self.default_ttl

            redis = await self._get_redis()

            # Use pipeline for efficiency
            pipe = redis.pipeline()

            try:
                for key, value in mapping.items():
                    data = self._serialize(value)
                    pipe.setex(key, ttl, data)
            except Exception as e:
                logger.error(f"Error serializing key {key}: {e!s}")
                return False

            results = await pipe.execute()

            # Check if all operations succeeded
            success = all(results)
            if success:
                self._stats["sets"] += len(mapping)

            return success

        except Exception as e:
            logger.error(f"Error setting multiple cache keys: {e!s}")
            self._record_error()
            return False

    async def delete_many(self, keys: list[str]) -> bool:
        """
        Delete multiple values from the cache efficiently.

        Args:
            keys: List of cache keys

        Returns:
            True if all operations successful, False otherwise
        """
        try:
            if not keys:
                return True

            redis = await self._get_redis()
            result = await redis.delete(*keys)

            self._stats["deletes"] += result
            return bool(result == len(keys))

        except Exception as e:
            logger.error(f"Error deleting multiple cache keys: {e!s}")
            self._record_error()
            return False

    async def get_cache_info(self) -> dict[str, Any]:
        """
        Get detailed cache information from Redis.

        Returns:
            Dictionary containing cache information
        """
        try:
            redis = await self._get_redis()
            info = await redis.info()

            return {
                "type": "redis",
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "serialization": self.serialization,
                "default_ttl": self.default_ttl,
                **self.get_stats()
            }

        except Exception as e:
            logger.error(f"Error getting cache info: {e!s}")
            self._record_error()
            return {"type": "redis", "error": str(e)}

    async def close(self) -> None:
        """Close the Redis connection and cleanup resources."""
        try:
            if self._redis:
                await self._redis.close()
                self._redis = None

            if self._connection_pool:
                await self._connection_pool.disconnect()
                self._connection_pool = None

            logger.info("Redis cache connection closed")

        except Exception as e:
            logger.error(f"Error closing Redis connection: {e!s}")

    async def ping(self) -> bool:
        """
        Test Redis connection.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            redis = await self._get_redis()
            await redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e!s}")
            return False
