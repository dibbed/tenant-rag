"""
Base cache interface for the RAG Telegram bot.

This module defines the base cache interface that all cache implementations
must follow, providing a consistent API for caching operations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseCache(ABC):
    """
    Abstract base class for cache implementations.
    
    This class defines the interface that all cache implementations must follow,
    ensuring consistency across different caching backends.
    """
    
    def __init__(self, default_ttl: int = 3600):
        """
        Initialize the base cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
        """
        self.default_ttl = default_ttl
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """
        Clear all cached values.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get the time-to-live for a key.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds or None if key doesn't exist
        """
        pass
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from the cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary mapping keys to values (missing keys are omitted)
        """
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in the cache.
        
        Args:
            mapping: Dictionary mapping keys to values
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if all operations successful, False otherwise
        """
        success = True
        for key, value in mapping.items():
            if not await self.set(key, value, ttl):
                success = False
        return success
    
    async def delete_many(self, keys: List[str]) -> bool:
        """
        Delete multiple values from the cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            True if all operations successful, False otherwise
        """
        success = True
        for key in keys:
            if not await self.delete(key):
                success = False
        return success
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "miss_rate": 1.0 - hit_rate
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    def _record_hit(self) -> None:
        """Record a cache hit."""
        self._stats["hits"] += 1
    
    def _record_miss(self) -> None:
        """Record a cache miss."""
        self._stats["misses"] += 1
    
    def _record_set(self) -> None:
        """Record a cache set operation."""
        self._stats["sets"] += 1
    
    def _record_delete(self) -> None:
        """Record a cache delete operation."""
        self._stats["deletes"] += 1
    
    def _record_error(self) -> None:
        """Record a cache error."""
        self._stats["errors"] += 1


class CacheKey:
    """Utility class for generating consistent cache keys."""
    
    @staticmethod
    def embedding(text: str, model: str) -> str:
        """
        Generate cache key for embeddings.
        
        Args:
            text: Text to embed
            model: Embedding model name
            
        Returns:
            Cache key
        """
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"embedding:{model}:{text_hash}"
    
    @staticmethod
    def query_result(question: str, context_hash: str, model: str, lang: str) -> str:
        """
        Generate cache key for query results.
        
        Args:
            question: User question
            context_hash: Hash of retrieved context
            model: LLM model name
            lang: Response language
            
        Returns:
            Cache key
        """
        import hashlib
        question_hash = hashlib.md5(question.encode()).hexdigest()
        return f"query:{model}:{lang}:{question_hash}:{context_hash}"
    
    @staticmethod
    def document_chunks(source: str, chunk_size: int, overlap: int) -> str:
        """
        Generate cache key for document chunks.
        
        Args:
            source: Document source
            chunk_size: Chunk size
            overlap: Chunk overlap
            
        Returns:
            Cache key
        """
        import hashlib
        source_hash = hashlib.md5(source.encode()).hexdigest()
        return f"chunks:{chunk_size}:{overlap}:{source_hash}"
    
    @staticmethod
    def health_check(component: str) -> str:
        """
        Generate cache key for health check results.
        
        Args:
            component: Component name
            
        Returns:
            Cache key
        """
        return f"health:{component}"
    
    @staticmethod
    def user_rate_limit(user_id: int) -> str:
        """
        Generate cache key for user rate limiting.
        
        Args:
            user_id: User ID
            
        Returns:
            Cache key
        """
        return f"rate_limit:user:{user_id}"
