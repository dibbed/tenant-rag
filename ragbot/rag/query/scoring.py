"""
Custom Scoring Algorithms

This module provides advanced scoring algorithms for ranking search results,
including weighted scoring, time decay, popularity-based scoring, and hybrid approaches.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import math
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ScoringStrategy(Enum):
    """استراتژی‌های امتیازدهی"""

    WEIGHTED = "weighted"
    TIME_DECAY = "time_decay"
    POPULARITY = "popularity"
    SEMANTIC_BOOST = "semantic_boost"
    HYBRID = "hybrid"
    CUSTOM = "custom"


@dataclass
class ScoredDocument:
    """سند با امتیاز"""

    document_id: str
    content: str
    metadata: Dict[str, Any]
    base_score: float
    final_score: float
    scoring_components: Dict[str, float]
    timestamp: datetime


class CustomScorer:
    """الگوریتم‌های امتیازدهی سفارشی"""

    def __init__(self, vector_store):
        """Initialize custom scorer"""
        self.vector_store = vector_store
        self.scoring_cache = {}
        self.cache_ttl = 600  # 10 minutes

    async def weighted_scoring(
        self, documents: List[Any], weights: Dict[str, float]
    ) -> List[ScoredDocument]:
        """امتیازدهی وزنی بر اساس فاکتورهای مختلف"""
        scored_docs = []

        for doc in documents:
            base_score = getattr(doc, "score", 0.0)

            # محاسبه فاکتورهای مختلف
            content_length = len(doc.content) if hasattr(doc, "content") else 0
            length_score = self._calculate_length_score(content_length)
            metadata_score = self._calculate_metadata_score(doc.metadata)
            recency_score = self._calculate_recency_score(doc.metadata)

            # محاسبه امتیاز نهایی
            final_score = (
                base_score * weights.get("semantic_similarity", 0.5)
                + length_score * weights.get("content_length", 0.1)
                + metadata_score * weights.get("metadata_quality", 0.1)
                + recency_score * weights.get("recency", 0.2)
            )

            final_score = min(max(final_score, 0.0), 1.0)

            scored_doc = ScoredDocument(
                document_id=doc.id,
                content=getattr(doc, "content", ""),
                metadata=doc.metadata,
                base_score=base_score,
                final_score=final_score,
                scoring_components={
                    "semantic_similarity": base_score,
                    "content_length": length_score,
                    "metadata_quality": metadata_score,
                    "recency": recency_score,
                },
                timestamp=datetime.now(),
            )

            scored_docs.append(scored_doc)

        scored_docs.sort(key=lambda x: x.final_score, reverse=True)
        return scored_docs

    async def time_decay_scoring(
        self, documents: List[Any], decay_factor: float = 0.1
    ) -> List[ScoredDocument]:
        """امتیازدهی با کاهش تدریجی بر اساس زمان"""
        scored_docs = []
        current_time = datetime.now()

        for doc in documents:
            base_score = getattr(doc, "score", 0.0)

            # محاسبه سن سند
            doc_time = self._extract_document_time(doc.metadata)
            if doc_time:
                age_days = (current_time - doc_time).days
                decay_multiplier = math.exp(-decay_factor * age_days)
            else:
                decay_multiplier = 1.0

            final_score = base_score * decay_multiplier

            scored_doc = ScoredDocument(
                document_id=doc.id,
                content=getattr(doc, "content", ""),
                metadata=doc.metadata,
                base_score=base_score,
                final_score=final_score,
                scoring_components={
                    "semantic_similarity": base_score,
                    "time_decay": decay_multiplier,
                },
                timestamp=current_time,
            )

            scored_docs.append(scored_doc)

        scored_docs.sort(key=lambda x: x.final_score, reverse=True)
        return scored_docs

    async def popularity_scoring(
        self,
        documents: List[Any],
        popularity_weights: Optional[Dict[str, float]] = None,
    ) -> List[ScoredDocument]:
        """امتیازدهی بر اساس محبوبیت"""
        if popularity_weights is None:
            popularity_weights = {
                "view_count": 0.3,
                "like_count": 0.4,
                "share_count": 0.2,
                "comment_count": 0.1,
            }

        scored_docs = []

        for doc in documents:
            base_score = getattr(doc, "score", 0.0)

            # محاسبه امتیاز محبوبیت
            popularity_score = 0.0
            for metric, weight in popularity_weights.items():
                if hasattr(doc, "metadata") and metric in doc.metadata:
                    try:
                        value = float(doc.metadata[metric])
                        # نرمال‌سازی بر اساس حداکثر مقدار
                        normalized_value = min(value / 1000.0, 1.0)  # فرض: حداکثر 1000
                        popularity_score += normalized_value * weight
                    except (ValueError, TypeError):
                        continue

            # ترکیب امتیاز semantic و محبوبیت
            final_score = (base_score * 0.7) + (popularity_score * 0.3)
            final_score = min(max(final_score, 0.0), 1.0)

            scored_doc = ScoredDocument(
                document_id=doc.id,
                content=getattr(doc, "content", ""),
                metadata=doc.metadata,
                base_score=base_score,
                final_score=final_score,
                scoring_components={
                    "semantic_similarity": base_score,
                    "popularity": popularity_score,
                },
                timestamp=datetime.now(),
            )

            scored_docs.append(scored_doc)

        scored_docs.sort(key=lambda x: x.final_score, reverse=True)
        return scored_docs

    async def semantic_boost_scoring(
        self, documents: List[Any], boost_factors: Optional[Dict[str, float]] = None
    ) -> List[ScoredDocument]:
        """امتیازدهی با تقویت معنایی"""
        if boost_factors is None:
            boost_factors = {
                "title_match": 1.5,
                "category_match": 1.3,
                "tag_match": 1.2,
                "author_match": 1.1,
            }

        scored_docs = []

        for doc in documents:
            base_score = getattr(doc, "score", 0.0)

            # محاسبه boost factors
            boost_multiplier = 1.0
            for factor, boost_value in boost_factors.items():
                if hasattr(doc, "metadata") and factor in doc.metadata:
                    # فرض: وجود فیلد به معنای تطابق است
                    boost_multiplier *= boost_value

            final_score = base_score * boost_multiplier
            final_score = min(max(final_score, 0.0), 1.0)

            scored_doc = ScoredDocument(
                document_id=doc.id,
                content=getattr(doc, "content", ""),
                metadata=doc.metadata,
                base_score=base_score,
                final_score=final_score,
                scoring_components={
                    "semantic_similarity": base_score,
                    "boost_multiplier": boost_multiplier,
                },
                timestamp=datetime.now(),
            )

            scored_docs.append(scored_doc)

        scored_docs.sort(key=lambda x: x.final_score, reverse=True)
        return scored_docs

    async def hybrid_scoring(
        self, documents: List[Any], strategy_weights: Optional[Dict[str, float]] = None
    ) -> List[ScoredDocument]:
        """امتیازدهی ترکیبی با چندین استراتژی"""
        if strategy_weights is None:
            strategy_weights = {
                "semantic": 0.4,
                "time_decay": 0.2,
                "popularity": 0.2,
                "metadata_quality": 0.2,
            }

        # محاسبه امتیازات با استراتژی‌های مختلف
        weighted_scores = await self.weighted_scoring(
            documents,
            {
                "semantic_similarity": 1.0,
                "content_length": 0.0,
                "metadata_quality": 0.0,
                "recency": 0.0,
            },
        )

        time_decay_scores = await self.time_decay_scoring(documents)
        popularity_scores = await self.popularity_scoring(documents)

        # ترکیب امتیازات
        hybrid_docs = []
        for i, doc in enumerate(documents):
            weighted_score = (
                weighted_scores[i].final_score if i < len(weighted_scores) else 0.0
            )
            time_score = (
                time_decay_scores[i].final_score if i < len(time_decay_scores) else 0.0
            )
            popularity_score = (
                popularity_scores[i].final_score if i < len(popularity_scores) else 0.0
            )
            metadata_score = self._calculate_metadata_score(doc.metadata)

            final_score = (
                weighted_score * strategy_weights["semantic"]
                + time_score * strategy_weights["time_decay"]
                + popularity_score * strategy_weights["popularity"]
                + metadata_score * strategy_weights["metadata_quality"]
            )

            final_score = min(max(final_score, 0.0), 1.0)

            hybrid_doc = ScoredDocument(
                document_id=doc.id,
                content=getattr(doc, "content", ""),
                metadata=doc.metadata,
                base_score=getattr(doc, "score", 0.0),
                final_score=final_score,
                scoring_components={
                    "semantic": weighted_score,
                    "time_decay": time_score,
                    "popularity": popularity_score,
                    "metadata_quality": metadata_score,
                },
                timestamp=datetime.now(),
            )

            hybrid_docs.append(hybrid_doc)

        hybrid_docs.sort(key=lambda x: x.final_score, reverse=True)
        return hybrid_docs

    async def custom_scoring(
        self, documents: List[Any], scoring_function: Callable[[Any], float]
    ) -> List[ScoredDocument]:
        """امتیازدهی سفارشی با تابع کاربر"""
        scored_docs = []

        for doc in documents:
            base_score = getattr(doc, "score", 0.0)
            custom_score = scoring_function(doc)
            final_score = min(max(custom_score, 0.0), 1.0)

            scored_doc = ScoredDocument(
                document_id=doc.id,
                content=getattr(doc, "content", ""),
                metadata=doc.metadata,
                base_score=base_score,
                final_score=final_score,
                scoring_components={
                    "semantic_similarity": base_score,
                    "custom_score": custom_score,
                },
                timestamp=datetime.now(),
            )

            scored_docs.append(scored_doc)

        scored_docs.sort(key=lambda x: x.final_score, reverse=True)
        return scored_docs

    def _calculate_length_score(self, content_length: int) -> float:
        """محاسبه امتیاز بر اساس طول محتوا"""
        if 500 <= content_length <= 2000:
            return 1.0
        elif content_length < 500:
            return content_length / 500.0
        else:
            return max(0.5, 1.0 - (content_length - 2000) / 10000.0)

    def _calculate_metadata_score(self, metadata: Dict[str, Any]) -> float:
        """محاسبه امتیاز کیفیت metadata"""
        if not metadata:
            return 0.0

        important_fields = ["title", "author", "category", "tags", "created_at"]
        score = sum(
            1.0 for field in important_fields if field in metadata and metadata[field]
        )

        return min(score / len(important_fields), 1.0)

    def _calculate_recency_score(self, metadata: Dict[str, Any]) -> float:
        """محاسبه امتیاز تازگی"""
        doc_time = self._extract_document_time(metadata)
        if not doc_time:
            return 0.5

        current_time = datetime.now()
        age_days = (current_time - doc_time).days

        if age_days <= 7:
            return 1.0
        elif age_days <= 30:
            return 0.8
        elif age_days <= 90:
            return 0.6
        elif age_days <= 365:
            return 0.4
        else:
            return 0.2

    def _extract_document_time(self, metadata: Dict[str, Any]) -> Optional[datetime]:
        """استخراج زمان سند از metadata"""
        time_fields = ["created_at", "updated_at", "published_at", "date"]

        for field in time_fields:
            if field in metadata:
                try:
                    time_value = metadata[field]
                    if isinstance(time_value, str):
                        for fmt in [
                            "%Y-%m-%d",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%dT%H:%M:%S",
                        ]:
                            try:
                                return datetime.strptime(time_value, fmt)
                            except ValueError:
                                continue
                    elif isinstance(time_value, datetime):
                        return time_value
                except Exception:
                    continue

        return None

    async def get_scoring_statistics(self) -> Dict[str, Any]:
        """دریافت آمار امتیازدهی"""
        return {
            "cached_scores": len(self.scoring_cache),
            "cache_ttl": self.cache_ttl,
            "available_strategies": [strategy.value for strategy in ScoringStrategy],
        }

    async def clear_scoring_cache(self):
        """پاک کردن cache امتیازات"""
        self.scoring_cache.clear()

    async def benchmark_scoring_strategies(
        self, documents: List[Any], sample_size: int = 100
    ) -> Dict[str, Dict[str, float]]:
        """مقایسه عملکرد استراتژی‌های مختلف امتیازدهی"""
        if len(documents) > sample_size:
            import random

            sample_docs = random.sample(documents, sample_size)
        else:
            sample_docs = documents

        results = {}
        strategies = [
            (
                "weighted",
                lambda: self.weighted_scoring(
                    sample_docs,
                    {
                        "semantic_similarity": 0.5,
                        "content_length": 0.1,
                        "metadata_quality": 0.1,
                        "recency": 0.2,
                    },
                ),
            ),
            ("time_decay", lambda: self.time_decay_scoring(sample_docs)),
            ("popularity", lambda: self.popularity_scoring(sample_docs)),
            ("hybrid", lambda: self.hybrid_scoring(sample_docs)),
        ]

        for strategy_name, strategy_func in strategies:
            start_time = time.time()
            scored_docs = await strategy_func()
            execution_time = time.time() - start_time

            # محاسبه آمار
            scores = [doc.final_score for doc in scored_docs]
            results[strategy_name] = {
                "execution_time": execution_time,
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
                "min_score": min(scores) if scores else 0,
                "score_std": math.sqrt(
                    sum((s - sum(scores) / len(scores)) ** 2 for s in scores)
                    / len(scores)
                )
                if len(scores) > 1
                else 0,
            }

        return results
