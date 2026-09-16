# 🔑 Redis Keys Documentation

This document outlines all Redis keys used by the RAG Telegram bot system for caching, sessions, and performance optimization.

## Key Naming Convention

All Redis keys follow this pattern:
```
[namespace]:[resource_id]:[operation]:[version]
```

Where:
- **namespace**: Module or service (e.g., `user`, `query`, `embed`)
- **resource_id**: Unique identifier (user_id, query_hash, etc.)
- **operation**: Type of operation (session, response, rate, etc.)
- **version**: Optional version for backward compatibility

## User Management Keys

### User Sessions
```
user:{user_id}:session
```
- **TTL**: 86400 (24 hours)
- **Value**: JSON containing user session data
- **Example**:
```json
{
  "user_id": 123456789,
  "default_lang": "fa",
  "current_context": "ai_ml",
  "last_activity": "2024-01-15T10:30:00Z",
  "preferences": {
    "max_results": 4,
    "response_format": "detailed"
  }
}
```

### User Authentication
```
user:{user_id}:auth
```
- **TTL**: 3600 (1 hour)
- **Value**: Boolean string ("true"/"false")
- **Usage**: Track authenticated status

### User Rate Limiting
```
user:{user_id}:rate:{window}
```
- **TTL**: Window duration (60 for per-minute rates)
- **Value**: Integer counter of requests
- **Example**:
  - `user:123456789:rate:60` → "15"
  - `user:123456789:rate:3600` → "150"

## Query Caching Keys

### Query Responses
```
query:{query_hash}:response:{model}:{version}
```
- **TTL**: 3600 (1 hour for generic queries), 86400 (24 hours for specific/factual)
- **Value**: JSON response with metadata
- **Example**:
```json
{
  "response": "RAG stands for Retrieval-Augmented Generation...",
  "model": "gpt-3.5-turbo",
  "language": "fa",
  "created_at": "2024-01-15T10:30:00Z",
  "confidence": 0.85
}
```

### Query Metadata
```
query:{query_hash}:metadata
```
- **TTL**: 86400 (24 hours)
- **Value**: JSON with query analytics
- **Example**:
```json
{
  "original_query": "What is RAG?",
  "processed_query": "RAG چیست?",
  "language": "fa",
  "timestamp": "2024-01-15T10:30:00Z",
  "response_length": 287,
  "documents_retrieved": 3,
  "processing_time": 0.85
}
```

## Embedding Cache Keys

### Text Embeddings
```
embed:{content_hash}:{model}
```
- **TTL**: 604800 (7 days)
- **Value**: JSON array of embedding vectors
- **Example**: `[0.123, 0.456, -0.789, ...]`

### Chunk Embeddings
```
embed:chunk:{chunk_id}:{model}
```
- **TTL**: 2592000 (30 days)
- **Value**: JSON array of chunk embedding
- **Usage**: Cache embeddings for frequently used document chunks

## Document Management Keys

### Document Metadata
```
doc:{doc_hash}:metadata
```
- **TTL**: ∞ (persistent)
- **Value**: JSON with document information
- **Example**:
```json
{
  "original_name": "ai_paper.pdf",
  "content_type": "application/pdf",
  "size_bytes": 2048576,
  "total_chunks": 15,
  "language": "en",
  "upload_timestamp": "2024-01-15T09:15:00Z",
  "user_id": 123456789
}
```

### Document Access Log
```
doc:{doc_hash}:access:{date}
```
- **TTL**: 7776000 (90 days)
- **Value**: JSON array of access logs
- **Example**:
```json
[
  {
    "user_id": 123456789,
    "timestamp": "2024-01-15T10:30:00Z",
    "query": "What is machine learning?",
    "chunks_retrieved": [1, 3, 5]
  }
]
```

## System Monitoring Keys

### Performance Metrics
```
metrics:{service}:{operation}:{period}
```
- **TTL**: Period-dependent (300 for 5min, 3600 for 1hour, 86400 for 1day)
- **Value**: JSON metrics data
- **Examples**:
  - `metrics:query:response:5min` → `{"count": 150, "avg_time": 0.8, "errors": 2}`
  - `metrics:embed:process:1hour` → `{"count": 850, "success_rate": 0.98}`

### Health Check Status
```
health:{service}:status
```
- **TTL**: 60 (1 minute)
- **Value**: JSON health status
- **Example**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "uptime": 345675
}
```

## Cache Management Utilities

### Key Expiration Patterns
```python
import redis

class RedisManager:
    def __init__(self):
        self.redis = redis.Redis(decode_responses=True)

    def bulk_expire_keys(self, pattern: str, ttl: int):
        """Expire keys matching pattern."""
        keys = self.redis.keys(pattern)
        for key in keys:
            self.redis.expire(key, ttl)

    def cleanup_old_keys(self):
        """Remove keys older than cleanup threshold."""
        # User sessions older than 7 days
        self.bulk_expire_keys("user:*:session", 604800)
        # Query responses older than 24 hours
        self.bulk_expire_keys("query:*:response:*", 86400)

    def get_cache_stats(self):
        """Get comprehensive cache statistics."""
        info = {}
        info["total_user_sessions"] = len(self.redis.keys("user:*:session"))
        info["total_cached_queries"] = len(self.redis.keys("query:*:response:*"))
        info["total_embeddings"] = len(self.redis.keys("embed:*"))
        info["total_documents"] = len(self.redis.keys("doc:*"))

        return info
```

### Lua Scripts for Atomic Operations

```lua
-- Atomic rate limiting script
local key = KEYS[1]
local max_requests = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call("GET", key)
if not current then
    redis.call("SETEX", key, window, "1")
    return 1
end

local count = tonumber(current)
if count >= max_requests then
    return -1
else
    redis.call("INCR", key)
    return count + 1
end
```

## Memory Management Strategies

### Efficient Serialization
```python
import pickle

class RedisCaching:
    def __init__(self):
        self.redis = redis.Redis()

    def cache_large_object(self, key: str, obj: Any, compression: bool = True):
        """Cache large objects with optional compression."""
        data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

        if compression and len(data) > 1024:  # Compress if >1KB
            import lz4.frame
            data = lz4.frame.compress(data)

        self.redis.set(key, data)

    def get_cached_object(self, key: str, compression: bool = True):
        """Retrieve cached large object."""
        data = self.redis.get(key)
        if not data:
            return None

        if compression:
            import lz4.frame
            try:
                data = lz4.frame.decompress(data)
            except:
                pass  # Not compressed

        return pickle.loads(data)
```

## Monitoring & Alerting

### Cache Hit/Miss Tracking
```
cache:{operation}:hits:counter    → Hit counter with 1-hour TTL
cache:{operation}:misses:counter  → Miss counter with 1-hour TTL
cache:{operation}:hit_ratio        → Calculated hit ratio with 1-hour TTL
```

### Alert Conditions
```python
def check_cache_health():
    """Alert conditions for cache monitoring."""
    alerts = []

    # Check hit ratio
    hit_ratio = cache_manager.get_hit_ratio()
    if hit_ratio < 0.7:  # Below 70% hit rate
        alerts.append(f"Low cache hit ratio: {hit_ratio:.2%}")

    # Check memory usage
    memory_usage = cache_manager.get_memory_usage()
    if memory_usage > 0.8:  # Above 80% memory usage
        alerts.append(f"High memory usage: {memory_usage:.2%}")

    # Check stale data
    stale_count = cache_manager.get_stale_keys_count()
    if stale_count > 1000:
        alerts.append(f"High stale data count: {stale_count}")

    return alerts
```

## Best Practices

1. **Key Expiration**: Always set appropriate TTL values
2. **Namespace Separation**: Use clear namespaces to avoid conflicts
3. **Memory Monitoring**: Regularly monitor memory usage
4. **Backup Strategy**: Backup critical keys periodically
5. **Versioning**: Include version numbers for API changes
6. **Performance Profiling**: Profile slow Redis operations
7. **Batch Operations**: Use pipelines for bulk operations
