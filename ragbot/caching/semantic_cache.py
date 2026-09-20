"""
کش معنایی بر اساس شباهت پرسش‌ها

این ماژول شامل پیاده‌سازی کش معنایی است که بر اساس شباهت پرسش‌ها
پاسخ‌های مشابه را ذخیره و بازیابی می‌کند.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import cache_analytics, metrics_manager

from ..rag.embeddings.base import Embedder


@dataclass
class CacheEntry:
    """ورودی کش معنایی.

    Attributes:
        query: پرسش اصلی کاربر
        query_embedding: جاسازی پرسش
        answer: پاسخ تولید شده
        context: زمینه استفاده شده برای تولید پاسخ
        metadata: متادیتای اضافی
        timestamp: زمان ایجاد ورودی
        access_count: تعداد دسترسی‌ها
        last_access: زمان آخرین دسترسی
        confidence_score: امتیاز اطمینان پاسخ
    """

    query: str
    query_embedding: List[float]
    answer: str
    context: List[str]
    metadata: Dict[str, Any]
    timestamp: float
    access_count: int
    last_access: float
    confidence_score: float


class SemanticCache:
    """کش بر اساس شباهت معنایی.

    این کلاس کش معنایی را پیاده‌سازی می‌کند که بر اساس شباهت
    پرسش‌ها پاسخ‌های مشابه را ذخیره و بازیابی می‌کند.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        embedder: Optional[Embedder] = None,
    ):
        """مقداردهی اولیه کش معنایی.

        Args:
            similarity_threshold: آستانه شباهت برای تطبیق (0.0 تا 1.0)
            max_size: حداکثر تعداد ورودی‌های کش
            ttl_seconds: زمان انقضای ورودی‌ها به ثانیه
            embedder: مدل جاسازی برای تولید embedding
        """
        self.similarity_threshold = similarity_threshold
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.embedder = embedder

        # Cache storage
        self.cache: Dict[str, CacheEntry] = {}
        self.embedding_cache: Dict[str, List[float]] = {}

        # Statistics
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0

        # Background tasks
        self._cleanup_task = None
        self._start_cleanup_task()

    async def get_similar_answer(self, query: str) -> Optional[CacheEntry]:
        """جستجوی پاسخ مشابه در کش.

        Args:
            query: پرسش کاربر

        Returns:
            ورودی کش مشابه یا None اگر مشابهی پیدا نشود
        """
        # پاک‌سازی ورودی‌های منقضی شده
        await self._cleanup_expired()

        # تولید جاسازی پرسش
        query_embedding = await self._get_query_embedding(query)

        # جستجوی مشابه
        best_match = await self._find_best_match(query_embedding)

        if best_match:
            # به‌روزرسانی آمار دسترسی
            best_match.access_count += 1
            best_match.last_access = time.time()
            self.hit_count += 1

            # ثبت متریک‌های cache hit
            similarity_score = self._cosine_similarity(
                query_embedding, best_match.query_embedding
            )
            cache_analytics.record_cache_hit(
                query, similarity_score, best_match.confidence_score
            )

            # ثبت متریک‌های Prometheus
            self._record_cache_metrics()

            return best_match
        else:
            self.miss_count += 1

            # ثبت متریک‌های cache miss
            cache_analytics.record_cache_miss(query)

            # ثبت متریک‌های Prometheus
            self._record_cache_metrics()

            return None

    async def cache_answer(
        self,
        query: str,
        answer: str,
        context: List[str],
        metadata: Dict[str, Any],
        confidence_score: float = 1.0,
    ) -> None:
        """ذخیره پاسخ در کش.

        Args:
            query: پرسش کاربر
            answer: پاسخ تولید شده
            context: زمینه استفاده شده
            metadata: متادیتای اضافی
            confidence_score: امتیاز اطمینان پاسخ (0.0 تا 1.0)
        """
        # تولید جاسازی پرسش
        query_embedding = await self._get_query_embedding(query)

        # ایجاد ورودی کش
        cache_entry = CacheEntry(
            query=query,
            query_embedding=query_embedding,
            answer=answer,
            context=context,
            metadata=metadata,
            timestamp=time.time(),
            access_count=0,
            last_access=time.time(),
            confidence_score=confidence_score,
        )

        # تولید کلید یکتا
        cache_key = self._generate_cache_key(query, query_embedding)

        # بررسی محدودیت اندازه
        if len(self.cache) >= self.max_size:
            await self._evict_least_used()

        # ذخیره در کش
        self.cache[cache_key] = cache_entry

    async def _get_query_embedding(self, query: str) -> List[float]:
        """دریافت جاسازی پرسش.

        Args:
            query: پرسش کاربر

        Returns:
            لیست اعداد float که جاسازی پرسش را نشان می‌دهد
        """
        # بررسی کش جاسازی
        query_hash = hashlib.md5(query.encode()).hexdigest()
        if query_hash in self.embedding_cache:
            return self.embedding_cache[query_hash]

        # تولید جاسازی جدید
        embedding_start_time = time.time()

        if self.embedder:
            embedding = await self.embedder.embed_texts([query])
            query_embedding = embedding[0]
        else:
            # استفاده از امبدری که در settings تعیین شده است
            provider = getattr(
                getattr(settings, "embedding", object()),
                "provider",
                "sentence_transformers",
            )
            try:
                if provider in ("sentence_transformers", "huggingface"):
                    # مسیر محلی: STEmbedder (cache_folder در خود embedder رعایت می‌شود)
                    from ragbot.rag.embeddings.st_embedder import (
                        STEmbedder,  # lazy import
                    )

                    model_name = getattr(
                        getattr(settings, "embedding", object()),
                        "model",
                        "sentence-transformers/all-MiniLM-L6-v2",
                    )
                    device = getattr(
                        getattr(settings, "llm", object()), "hf_device", None
                    )
                    _emb = STEmbedder(model_name=model_name, device=device)
                    _vecs = await _emb.embed_texts([query])
                    query_embedding = _vecs[0]
                elif provider == "openai" and getattr(settings, "openai_api_key", None):
                    # مسیر آنلاین: OpenAIEmbedder
                    from ragbot.rag.embeddings.openai_embedder import (
                        OpenAIEmbedder,  # lazy import
                    )

                    _emb = OpenAIEmbedder(api_key=settings.openai_api_key)
                    _vecs = await _emb.embed_texts([query])
                    query_embedding = _vecs[0]
                else:
                    # تلاش برای SentenceTransformer با مدل پیکربندی‌شده (fallback محلی)
                    cache_dir = getattr(
                        getattr(settings, "embedding", object()),
                        "cache_folder",
                        "./cache/sentence_transformers",
                    )
                    model_name = getattr(
                        getattr(settings, "embedding", object()),
                        "model",
                        "all-MiniLM-L6-v2",
                    )
                    _model = SentenceTransformer(model_name, cache_folder=cache_dir)
                    query_embedding = _model.encode([query])[0].tolist()
            except Exception:
                # fallback نهایی: بردار شبه‌تصادفیِ قطعی تا مسیر از کار نیفتد
                import numpy as _np  # type: ignore

                h = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
                _np.random.seed(h)
                query_embedding = _np.random.rand(384).astype(float).tolist()

        # ذخیره در کش جاسازی
        self.embedding_cache[query_hash] = query_embedding

        # ثبت زمان تولید embedding
        embedding_duration = time.time() - embedding_start_time
        cache_analytics.record_embedding_generation_time(embedding_duration)

        return query_embedding

    async def _find_best_match(
        self, query_embedding: List[float]
    ) -> Optional[CacheEntry]:
        """یافتن بهترین تطبیق در کش.

        Args:
            query_embedding: جاسازی پرسش

        Returns:
            بهترین ورودی کش یا None
        """
        similarity_start_time = time.time()

        best_match = None
        best_similarity = 0.0

        for cache_entry in self.cache.values():
            # محاسبه شباهت کسینوسی
            similarity = self._cosine_similarity(
                query_embedding, cache_entry.query_embedding
            )

            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_match = cache_entry
                best_similarity = similarity

        # ثبت زمان محاسبه شباهت
        similarity_duration = time.time() - similarity_start_time
        cache_analytics.record_similarity_computation_time(similarity_duration)

        return best_match

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """محاسبه شباهت کسینوسی بین دو بردار.

        Args:
            vec1: بردار اول
            vec2: بردار دوم

        Returns:
            مقدار شباهت کسینوسی (0.0 تا 1.0)
        """
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _generate_cache_key(self, query: str, embedding: List[float]) -> str:
        """تولید کلید یکتای کش.

        Args:
            query: پرسش کاربر
            embedding: جاسازی پرسش

        Returns:
            کلید یکتای کش
        """
        # استفاده از هش جاسازی برای کلید
        embedding_str = json.dumps(embedding, sort_keys=True)
        key_data = f"{query}_{embedding_str}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    async def _evict_least_used(self) -> None:
        """حذف کم‌استفاده‌ترین ورودی‌ها."""
        if not self.cache:
            return

        # محاسبه امتیاز استفاده
        usage_scores = {}
        current_time = time.time()

        for key, entry in self.cache.items():
            # امتیاز بر اساس تعداد دسترسی و زمان آخرین دسترسی
            time_factor = 1.0 / (current_time - entry.last_access + 1)
            usage_score = entry.access_count * time_factor
            usage_scores[key] = usage_score

        # حذف کم‌امتیازترین ورودی
        least_used_key = min(usage_scores.keys(), key=lambda k: usage_scores[k])
        evicted_entry = self.cache[least_used_key]
        del self.cache[least_used_key]
        self.eviction_count += 1

        # ثبت متریک‌های eviction
        cache_analytics.record_cache_eviction(evicted_entry.query, "size_limit")

    async def _cleanup_expired(self) -> None:
        """پاک‌سازی ورودی‌های منقضی شده."""
        current_time = time.time()
        expired_keys = []

        for key, entry in self.cache.items():
            if current_time - entry.timestamp > self.ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            expired_entry = self.cache[key]
            del self.cache[key]

            # ثبت متریک‌های TTL expiration
            cache_analytics.record_ttl_expiration(expired_entry.query)

    def _start_cleanup_task(self) -> None:
        """شروع کار پاک‌سازی پس‌زمینه."""

        async def cleanup_loop():
            while True:
                await asyncio.sleep(300)  # هر 5 دقیقه
                await self._cleanup_expired()

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def get_cache_stats(self) -> Dict[str, Any]:
        """دریافت آمار کش.

        Returns:
            دیکشنری شامل آمار کش
        """
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "eviction_count": self.eviction_count,
            "similarity_threshold": self.similarity_threshold,
            "ttl_seconds": self.ttl_seconds,
        }

    async def clear_cache(self) -> None:
        """پاک‌سازی کامل کش."""
        self.cache.clear()
        self.embedding_cache.clear()
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0

    clear = clear_cache

    async def export_cache(self) -> Dict[str, Any]:
        """صادرات کش.

        Returns:
            دیکشنری شامل داده‌های کش
        """
        return {
            "cache_entries": {key: asdict(entry) for key, entry in self.cache.items()},
            "stats": await self.get_cache_stats(),
        }

    async def import_cache(self, cache_data: Dict[str, Any]) -> None:
        """واردات کش.

        Args:
            cache_data: داده‌های کش برای وارد کردن
        """
        if "cache_entries" in cache_data:
            for key, entry_data in cache_data["cache_entries"].items():
                self.cache[key] = CacheEntry(**entry_data)

        if "stats" in cache_data:
            stats = cache_data["stats"]
            self.hit_count = stats.get("hit_count", 0)
            self.miss_count = stats.get("miss_count", 0)
            self.eviction_count = stats.get("eviction_count", 0)

    def _record_cache_metrics(self) -> None:
        """Record cache metrics to Prometheus."""
        try:
            # Calculate memory usage (approximate)
            memory_usage = len(self.cache) * 1024  # Rough estimate: 1KB per entry

            # Record cache size
            cache_analytics.record_cache_size(len(self.cache))

            # Prepare cache data for metrics
            cache_data = {
                "size": len(self.cache),
                "memory_usage": memory_usage,
                "similarity_threshold": self.similarity_threshold,
                "hit_rate": self.hit_count / (self.hit_count + self.miss_count)
                if (self.hit_count + self.miss_count) > 0
                else 0.0,
                "miss_rate": self.miss_count / (self.hit_count + self.miss_count)
                if (self.hit_count + self.miss_count) > 0
                else 0.0,
                "eviction_rate": self.eviction_count
                / (self.hit_count + self.miss_count)
                if (self.hit_count + self.miss_count) > 0
                else 0.0,
                "ttl_expired": 0,  # Will be updated by cleanup task
                "access_frequency": sum(
                    entry.access_count for entry in self.cache.values()
                )
                if self.cache
                else 0,
                "embedding_generation_time": 0.0,  # Will be updated by embedding generation
                "similarity_computation_time": 0.0,  # Will be updated by similarity computation
            }

            # Record to Prometheus
            cache_analytics.record_evaluation_metrics(metrics_manager, cache_data)

        except Exception as e:
            logger.warning(f"Failed to record cache metrics: {e}")
