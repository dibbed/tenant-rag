"""Utilities for orchestrating multi-level caching in the RAG Telegram bot."""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ragbot.caching.base import CacheKey
from ragbot.caching.cache_metrics import CacheMetricsCollector
from ragbot.caching.memory_cache import MemoryCache
from ragbot.caching.redis_cache import RedisCache
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


@dataclass
class CacheConfig:
    """Configuration schema for cache layers."""

    l1_enabled: bool = True  # Memory cache (L1)
    l2_enabled: bool = True  # Redis cache (L2)
    semantic_enabled: bool = True  # Semantic cache (L3)
    l1_ttl: int = 300  # L1 TTL (5 minutes)
    l2_ttl: int = 3600  # L2 TTL (1 hour)
    l1_max_size: int = 1000  # L1 max entries
    embedding_ttl: int = 86400  # Embedding cache TTL (24 hours)
    query_ttl: int = 1800  # Query result TTL (30 minutes)


class CacheManager:
    """Multi-level cache manager with intelligent caching strategies.

    The manager controls the following tiers:

    * L1: Fast in-memory cache for frequently accessed data.
    * L2: Redis cache for persistent and shared caching.
    * L3: Semantic cache for similarity-based reuse of responses.

    It also offers dedicated caching flows for embeddings and generated
    answers, plus bookkeeping utilities for trimming and statistics.
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialise the cache manager.

        Args:
            config: Optional cache configuration; defaults are used when ``None``.
        """
        self.config = config or CacheConfig()
        self._l1_cache: Optional[MemoryCache] = None
        self._l2_cache: Optional[RedisCache] = None
        self._semantic_cache: Optional[Any] = None
        self._cache_metrics: Optional[CacheMetricsCollector] = None
        self._initialized = False
        cache_settings = settings.semantic_cache
        self.query_cache_enabled = cache_settings.enable_query_cache
        self.query_cache_ttl = cache_settings.ttl_seconds
        self.query_cache_max_size = cache_settings.max_size
        self._query_cache_prefix = "qc::"
        self._query_cache_index: List[str] = []
        self._query_cache_lock: asyncio.Lock = asyncio.Lock()

        # Only log initialization if this is the first instance
        if not hasattr(CacheManager, '_instance_created'):
            logger.info("CacheManager initialized")
            CacheManager._instance_created = True

    async def initialize(self) -> None:
        """Initialize cache backends."""
        if self._initialized:
            return

        try:
            # Initialize L1 cache (memory)
            if self.config.l1_enabled:
                self._l1_cache = MemoryCache(
                    default_ttl=self.config.l1_ttl, max_size=self.config.l1_max_size
                )
                logger.info("L1 cache (memory) initialized")

            # Initialize L2 cache (Redis)
            if self.config.l2_enabled and settings.enable_redis:
                try:
                    self._l2_cache = RedisCache(default_ttl=self.config.l2_ttl)
                    # Test Redis connection
                    if await self._l2_cache.ping():
                        logger.info("L2 cache (Redis) initialized")
                    else:
                        logger.warning("Redis connection failed, disabling L2 cache")
                        self._l2_cache = None
                except Exception as e:
                    logger.warning(f"Failed to initialize Redis cache: {str(e)}")
                    self._l2_cache = None

            # Initialize L3 cache (Semantic)
            if (
                self.config.semantic_enabled
                and settings.semantic_cache.enable_semantic_cache
            ):
                try:
                    from ragbot.caching.adaptive_cache import AdaptiveCache

                    self._semantic_cache = AdaptiveCache(
                        similarity_threshold=settings.semantic_cache.similarity_threshold,
                        max_size=settings.semantic_cache.max_size,
                        ttl_seconds=settings.semantic_cache.ttl_seconds,
                        eviction_strategy=settings.semantic_cache.eviction_strategy,
                    )
                    logger.info("L3 cache (semantic) initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize semantic cache: {str(e)}")
                    self._semantic_cache = None

            # Initialize cache metrics
            if settings.semantic_cache.enable_cache_metrics:
                self._cache_metrics = CacheMetricsCollector()
                logger.info("Cache metrics collector initialized")

            self._initialized = True
            logger.info("CacheManager initialization completed")

        except Exception as e:
            logger.error(f"Failed to initialize CacheManager: {str(e)}")
            raise

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache (checks L1 then L2).

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self._initialized:
            await self.initialize()

        # Try L1 cache first
        if self._l1_cache:
            value = await self._l1_cache.get(key)
            if value is not None:
                return value

        # Try L2 cache
        if self._l2_cache:
            value = await self._l2_cache.get(key)
            if value is not None:
                # Populate L1 cache for faster future access
                if self._l1_cache:
                    await self._l1_cache.set(key, value, self.config.l1_ttl)
                return value

        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in the cache (sets in both L1 and L2).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            bool: True if at least one cache succeeded, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        success = False

        # Set in L1 cache
        if self._l1_cache:
            l1_ttl = min(ttl or self.config.l1_ttl, self.config.l1_ttl)
            if await self._l1_cache.set(key, value, l1_ttl):
                success = True

        # Set in L2 cache
        if self._l2_cache:
            l2_ttl = ttl or self.config.l2_ttl
            if await self._l2_cache.set(key, value, l2_ttl):
                success = True

        return success

    async def delete(self, key: str) -> bool:
        """
        Delete a value from all cache levels.

        Args:
            key: Cache key

        Returns:
            bool: True if at least one cache succeeded, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        success = False

        # Delete from L1 cache
        if self._l1_cache:
            if await self._l1_cache.delete(key):
                success = True

        # Delete from L2 cache
        if self._l2_cache:
            if await self._l2_cache.delete(key):
                success = True

        return success

    def _build_query_cache_key(
        self,
        question: str,
        language: str,
        provider: str,
        top_k: Optional[int] = None,
        store_type: Optional[str] = None,
    ) -> str:
        """Build a deterministic cache key for exact query caching.

        Args:
            question: User question.
            language: Target language code.
            provider: Identifier of the LLM provider.
            top_k: Optional number of retrieved chunks requested.
            store_type: Optional vector store label.

        Returns:
            str: Namespaced cache key.
        """

        normalized_question = question.strip().lower()
        hasher = hashlib.sha256()
        hasher.update(normalized_question.encode("utf-8"))
        hasher.update(f"|lang={language}|provider={provider}".encode("utf-8"))
        if top_k is not None:
            hasher.update(f"|top_k={top_k}".encode("utf-8"))
        if store_type:
            hasher.update(f"|store={store_type}".encode("utf-8"))
        digest = hasher.hexdigest()
        return f"{self._query_cache_prefix}{digest}"

    async def get_cached_query_result(
        self,
        question: str,
        language: str,
        provider: str,
        *,
        top_k: Optional[int] = None,
        store_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a cached query result when query caching is enabled.

        Args:
            question: User question.
            language: Target language code.
            provider: Identifier of the LLM provider.
            top_k: Optional number of retrieved chunks requested.
            store_type: Optional vector store label.

        Returns:
            Optional[Dict[str, Any]]: Cached payload, if present.
        """

        if not self.query_cache_enabled:
            return None

        cache_key = self._build_query_cache_key(
            question, language, provider, top_k, store_type
        )
        cached = await self.get(cache_key)
        return cached

    async def cache_query_result(
        self,
        question: str,
        language: str,
        provider: str,
        payload: Dict[str, Any],
        *,
        top_k: Optional[int] = None,
        store_type: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Persist a query result snapshot for future reuse.

        Args:
            question: User question.
            language: Target language code.
            provider: Identifier of the LLM provider.
            payload: Serializable payload describing the generated answer.
            top_k: Optional number of retrieved chunks requested.
            store_type: Optional vector store label.
            ttl: Optional override for the cache TTL in seconds.
        """

        if not self.query_cache_enabled:
            return

        cache_key = self._build_query_cache_key(
            question, language, provider, top_k, store_type
        )
        ttl_to_use = ttl or self.query_cache_ttl

        async with self._query_cache_lock:
            # Enforce upper bound of cached entries
            if (
                cache_key not in self._query_cache_index
                and len(self._query_cache_index) >= self.query_cache_max_size
            ):
                # Evict the oldest entry in the index
                oldest_key = self._query_cache_index.pop(0)
                await self.delete(oldest_key)

            await self.set(cache_key, payload, ttl=ttl_to_use)

            if cache_key not in self._query_cache_index:
                self._query_cache_index.append(cache_key)

    async def trim_caches(self, aggressive: bool = False) -> Dict[str, int]:
        """Trim in-memory and Redis caches to reclaim memory.

        Args:
            aggressive: Whether to evict a larger portion of cached entries.

        Returns:
            Dict[str, int]: Number of entries removed per cache layer.
        """

        removed_l1 = 0
        removed_l2 = 0

        percent = 0.5 if aggressive else 0.25

        if self._l1_cache and hasattr(self._l1_cache, "trim"):
            removed_l1 = await self._l1_cache.trim(percent=percent)

        if self._l2_cache and hasattr(self._l2_cache, "trim"):
            removed_l2 = await self._l2_cache.trim(percent=percent)

        async with self._query_cache_lock:
            if aggressive:
                # Clear bookkeeping indexes entirely when aggressive
                self._query_cache_index.clear()
            else:
                # Keep index in sync with existing keys by dropping oldest portion
                to_remove = int(len(self._query_cache_index) * percent)
                if to_remove > 0:
                    del self._query_cache_index[:to_remove]

        return {"l1": removed_l1, "l2": removed_l2}

    async def clear(self) -> bool:
        """
        Clear all cache levels.

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        success = True

        # Clear L1 cache
        if self._l1_cache:
            if not await self._l1_cache.clear():
                success = False

        # Clear L2 cache
        if self._l2_cache:
            if not await self._l2_cache.clear():
                success = False

        return success

    # Specialized caching methods

    async def cache_embedding(
        self, text: str, model: str, embedding: List[float]
    ) -> bool:
        """
        Cache an embedding with optimized TTL.

        Args:
            text: Original text
            model: Embedding model name
            embedding: Embedding vector

        Returns:
            True if successful, False otherwise
        """
        key = CacheKey.embedding(text, model)
        return await self.set(key, embedding, self.config.embedding_ttl)

    async def get_cached_embedding(
        self, text: str, model: str
    ) -> Optional[List[float]]:
        """
        Get a cached embedding.

        Args:
            text: Original text
            model: Embedding model name

        Returns:
            Cached embedding or None if not found
        """
        key = CacheKey.embedding(text, model)
        return await self.get(key)

    async def cache_document_chunks(
        self, source: str, chunks: List[str], chunk_size: int, overlap: int
    ) -> bool:
        """
        Cache document chunks.

        Args:
            source: Document source
            chunks: Text chunks
            chunk_size: Chunk size used
            overlap: Overlap used

        Returns:
            True if successful, False otherwise
        """
        key = CacheKey.document_chunks(source, chunk_size, overlap)

        cache_data = {
            "chunks": chunks,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "timestamp": time.time(),
        }

        return await self.set(key, cache_data, self.config.l2_ttl)

    async def get_cached_document_chunks(
        self, source: str, chunk_size: int, overlap: int
    ) -> Optional[List[str]]:
        """
        Get cached document chunks.

        Args:
            source: Document source
            chunk_size: Chunk size used
            overlap: Overlap used

        Returns:
            Cached chunks or None if not found
        """
        key = CacheKey.document_chunks(source, chunk_size, overlap)
        cache_data = await self.get(key)

        if cache_data and isinstance(cache_data, dict):
            return cache_data.get("chunks")

        return None

    # Semantic cache methods

    async def get_semantic_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get a semantically similar answer from the cache.

        Args:
            query: User query

        Returns:
            Cached answer with metadata or None if not found
        """
        if not self._initialized:
            await self.initialize()

        if not self._semantic_cache:
            return None

        try:
            cached_entry = await self._semantic_cache.get_similar_answer(query)
            if cached_entry:
                # Record metrics
                if self._cache_metrics:
                    self._cache_metrics.record_cache_hit()

                return {
                    "answer": cached_entry.answer,
                    "context": cached_entry.context,
                    "confidence": cached_entry.confidence_score,
                    "metadata": cached_entry.metadata,
                    "cached": True,
                }
            else:
                # Record metrics
                if self._cache_metrics:
                    self._cache_metrics.record_cache_miss()

                return None

        except Exception as e:
            logger.error(f"Error getting semantic answer: {str(e)}")
            return None

    async def cache_semantic_answer(
        self,
        query: str,
        answer: str,
        context: List[str],
        metadata: Dict[str, Any],
        confidence_score: float = 1.0,
    ) -> bool:
        """
        Cache a semantic answer.

        Args:
            query: User query
            answer: Generated answer
            context: Context chunks used
            metadata: Additional metadata
            confidence_score: Confidence score of the answer

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        if not self._semantic_cache:
            return False

        try:
            await self._semantic_cache.cache_answer(
                query=query,
                answer=answer,
                context=context,
                metadata=metadata,
                confidence_score=confidence_score,
            )

            # Update metrics
            if self._cache_metrics:
                self._cache_metrics.update_cache_size(len(self._semantic_cache.cache))

            return True

        except Exception as e:
            logger.error(f"Error caching semantic answer: {str(e)}")
            return False

    async def get_semantic_cache_stats(self) -> Dict[str, Any]:
        """
        Get semantic cache statistics.

        Returns:
            Dictionary containing semantic cache statistics
        """
        if not self._initialized:
            await self.initialize()

        if not self._semantic_cache:
            return {"error": "Semantic cache not initialized"}

        try:
            stats = await self._semantic_cache.get_cache_stats()

            # Add metrics if available
            if self._cache_metrics:
                metrics_summary = self._cache_metrics.get_metrics_summary()
                stats.update(metrics_summary)

            return stats

        except Exception as e:
            logger.error(f"Error getting semantic cache stats: {str(e)}")
            return {"error": str(e)}

    async def clear_semantic_cache(self) -> bool:
        """
        Clear the semantic cache.

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        if not self._semantic_cache:
            return False

        try:
            await self._semantic_cache.clear_cache()

            # Reset metrics
            if self._cache_metrics:
                self._cache_metrics.update_cache_size(0)

            return True

        except Exception as e:
            logger.error(f"Error clearing semantic cache: {str(e)}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Pattern to match (supports wildcards)

        Returns:
            Number of keys invalidated
        """
        if not self._initialized:
            await self.initialize()

        invalidated = 0

        # For Redis, we can use pattern matching
        if self._l2_cache:
            try:
                redis = await self._l2_cache._get_redis()
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
                    invalidated += len(keys)
            except Exception as e:
                logger.error(f"Error invalidating Redis pattern {pattern}: {str(e)}")

        # For memory cache, we need to iterate (less efficient)
        if self._l1_cache:
            try:
                import fnmatch

                keys_to_delete = []

                for key in self._l1_cache._cache.keys():
                    if fnmatch.fnmatch(key, pattern):
                        keys_to_delete.append(key)

                for key in keys_to_delete:
                    await self._l1_cache.delete(key)
                    invalidated += 1

            except Exception as e:
                logger.error(
                    f"Error invalidating memory cache pattern {pattern}: {str(e)}"
                )

        logger.info(
            f"Invalidated {invalidated} cache entries matching pattern: {pattern}"
        )
        return invalidated

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        if not self._initialized:
            await self.initialize()

        stats = {
            "config": {
                "l1_enabled": self.config.l1_enabled,
                "l2_enabled": self.config.l2_enabled,
                "l1_ttl": self.config.l1_ttl,
                "l2_ttl": self.config.l2_ttl,
                "embedding_ttl": self.config.embedding_ttl,
                "query_ttl": self.config.query_ttl,
            }
        }

        # L1 cache stats
        if self._l1_cache:
            stats["l1_cache"] = self._l1_cache.get_cache_info()

        # L2 cache stats
        if self._l2_cache:
            stats["l2_cache"] = await self._l2_cache.get_cache_info()

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all cache backends.

        Returns:
            Health check results
        """
        if not self._initialized:
            await self.initialize()

        health = {"overall_status": "healthy", "checks": {}}

        # Check L1 cache
        if self._l1_cache:
            try:
                test_key = "health_check_l1"
                test_value = "test"

                await self._l1_cache.set(test_key, test_value, 10)
                retrieved = await self._l1_cache.get(test_key)
                await self._l1_cache.delete(test_key)

                if retrieved == test_value:
                    health["checks"]["l1_cache"] = "healthy"
                else:
                    health["checks"]["l1_cache"] = "unhealthy"
                    health["overall_status"] = "degraded"

            except Exception as e:
                health["checks"]["l1_cache"] = f"error: {str(e)}"
                health["overall_status"] = "degraded"

        # Check L2 cache
        if self._l2_cache:
            try:
                if await self._l2_cache.ping():
                    health["checks"]["l2_cache"] = "healthy"
                else:
                    health["checks"]["l2_cache"] = "unhealthy"
                    health["overall_status"] = "degraded"

            except Exception as e:
                health["checks"]["l2_cache"] = f"error: {str(e)}"
                health["overall_status"] = "degraded"

        return health

    async def close(self) -> None:
        """Close all cache connections and cleanup resources."""
        try:
            if self._l1_cache:
                await self._l1_cache.close()
                self._l1_cache = None

            if self._l2_cache:
                await self._l2_cache.close()
                self._l2_cache = None

            if self._semantic_cache:
                # Semantic cache doesn't need explicit closing
                self._semantic_cache = None

            if self._cache_metrics:
                self._cache_metrics = None

            self._initialized = False
            logger.info("CacheManager closed")

        except Exception as e:
            logger.error(f"Error closing CacheManager: {str(e)}")


# Global cache manager instance
cache_manager = CacheManager()
