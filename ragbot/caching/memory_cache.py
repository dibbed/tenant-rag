"""In-memory cache implementation used by the RAG Telegram bot."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ragbot.caching.base import BaseCache
from ragbot.outputs.logger import logger


@dataclass
class CacheEntry:
    """Container for cache entry metadata.

    Attributes:
        value: Stored payload.
        expires_at: UNIX timestamp indicating when the entry expires.
        created_at: UNIX timestamp indicating when the entry was created.
    """
    value: Any
    expires_at: float
    created_at: float


class MemoryCache(BaseCache):
    """In-memory cache implementation with TTL support."""
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 10000, cleanup_interval: int = 300):
        """Initialise the memory cache.

        Args:
            default_ttl: Default time-to-live for entries, expressed in seconds.
            max_size: Maximum number of entries to store in memory.
            cleanup_interval: Interval, in seconds, between cleanup runs.
        """
        super().__init__(default_ttl)
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self._cache: Dict[str, CacheEntry] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
        
        logger.info(f"MemoryCache initialized with max_size={max_size}, default_ttl={default_ttl}")
    
    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {str(e)}")
                self._record_error()
    
    async def _cleanup_expired(self) -> None:
        """Remove expired entries from the cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.expires_at <= current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _evict_if_needed(self) -> None:
        """Evict the oldest entries when the cache reaches capacity."""
        if len(self._cache) >= self.max_size:
            # Sort by creation time and remove oldest entries
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1].created_at
            )
            
            # Remove 10% of entries to make room
            num_to_remove = max(1, self.max_size // 10)
            for key, _ in sorted_items[:num_to_remove]:
                del self._cache[key]
            
            logger.debug(f"Evicted {num_to_remove} cache entries due to size limit")
    
    async def get(self, key: str) -> Optional[Any]:
        """Return a value from the cache if present and not expired.

        Args:
            key: Cache key.

        Returns:
            Optional[Any]: Cached value, or ``None`` when missing/expired.
        """
        try:
            entry = self._cache.get(key)
            if entry is None:
                self._record_miss()
                return None
            
            current_time = time.time()
            if entry.expires_at <= current_time:
                # Entry has expired, remove it
                del self._cache[key]
                self._record_miss()
                return None
            
            self._record_hit()
            return entry.value
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            self._record_error()
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Optional time-to-live override in seconds.

        Returns:
            bool: ``True`` if the value was cached successfully.
        """
        try:
            if ttl is None:
                ttl = self.default_ttl
            
            current_time = time.time()
            expires_at = current_time + ttl
            
            # Evict entries if needed
            self._evict_if_needed()
            
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at,
                created_at=current_time
            )
            
            self._record_set()
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            self._record_error()
            return False
    
    async def delete(self, key: str) -> bool:
        """Remove a value from the cache.

        Args:
            key: Cache key.

        Returns:
            bool: ``True`` if the entry existed and was removed.
        """
        try:
            if key in self._cache:
                del self._cache[key]
                self._record_delete()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            self._record_error()
            return False
    
    async def exists(self, key: str) -> bool:
        """Check whether a key exists and is still valid.

        Args:
            key: Cache key to check.

        Returns:
            bool: ``True`` when the key exists and has not expired.
        """
        try:
            entry = self._cache.get(key)
            if entry is None:
                return False
            
            current_time = time.time()
            if entry.expires_at <= current_time:
                # Entry has expired, remove it
                del self._cache[key]
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking cache key existence {key}: {str(e)}")
            self._record_error()
            return False
    
    async def clear(self) -> bool:
        """Remove every cached entry.

        Returns:
            bool: ``True`` when the cache was cleared successfully.
        """
        try:
            self._cache.clear()
            logger.info("Memory cache cleared")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            self._record_error()
            return False
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """Return the remaining TTL for a key.

        Args:
            key: Cache key.

        Returns:
            Optional[int]: TTL in seconds, or ``None`` when the key is missing
            or expired.
        """
        try:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            current_time = time.time()
            if entry.expires_at <= current_time:
                # Entry has expired, remove it
                del self._cache[key]
                return None
            
            return int(entry.expires_at - current_time)
            
        except Exception as e:
            logger.error(f"Error getting TTL for cache key {key}: {str(e)}")
            self._record_error()
            return None
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Return diagnostic information about the cache."""
        current_time = time.time()
        expired_count = 0
        
        for entry in self._cache.values():
            if entry.expires_at <= current_time:
                expired_count += 1
        
        return {
            "type": "memory",
            "size": len(self._cache),
            "max_size": self.max_size,
            "expired_entries": expired_count,
            "default_ttl": self.default_ttl,
            "cleanup_interval": self.cleanup_interval,
            **self.get_stats()
        }
    
    async def close(self) -> None:
        """Close the cache and release resources."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._cache.clear()
        logger.info("Memory cache closed")
    
    def __del__(self):
        """Cancel the cleanup task when the cache is garbage collected."""

    async def trim(self, percent: float = 0.25) -> int:
        """Remove a fraction of the oldest entries from the cache.

        Args:
            percent: Fraction of entries to evict (value clamped between 0 and 1).

        Returns:
            int: Number of entries evicted.
        """

        if percent <= 0 or not self._cache:
            return 0

        percent = min(1.0, percent)
        sorted_items = sorted(
            self._cache.items(),
            key=lambda item: item[1].created_at,
        )
        to_remove = max(0, int(len(sorted_items) * percent))
        removed = 0
        for key, _ in sorted_items[:to_remove]:
            del self._cache[key]
            removed += 1
        if removed:
            logger.debug("Trimmed %d entries from memory cache", removed)
        return removed
        if hasattr(self, '_cleanup_task') and self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
