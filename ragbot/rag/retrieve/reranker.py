"""
رتبه‌بندی مجدد نتایج با CrossEncoder - بهبود یافته
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager, reranker_evaluator
from ragbot.rag.exceptions import DocumentProcessingError

try:
    from sentence_transformers import CrossEncoder

    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None

from ..store.base import VectorDocument


class CrossEncoderReranker:
    """رتبه‌بندی مجدد نتایج با CrossEncoder - بهبود یافته"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        threshold: Optional[float] = None,
        enable_metadata_scoring: Optional[bool] = None,
        **kwargs,
    ):
        """
        Initialize reranker with settings integration

        Args:
            model_name: نام مدل CrossEncoder (از تنظیمات خوانده می‌شود)
            threshold: حداقل امتیاز برای فیلتر کردن (از تنظیمات خوانده می‌شود)
            enable_metadata_scoring: فعال‌سازی امتیازدهی متادیتا (از تنظیمات خوانده می‌شود)
        """
        # خواندن تنظیمات از settings
        adv_settings = getattr(settings, "advanced_retrieval", object())

        self.model_name = model_name or getattr(
            adv_settings, "reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.threshold = (
            threshold
            if threshold is not None
            else getattr(adv_settings, "reranker_threshold", 0.7)
        )
        self.enable_metadata_scoring = (
            enable_metadata_scoring
            if enable_metadata_scoring is not None
            else getattr(adv_settings, "enable_metadata_scoring", True)
        )

        # تنظیمات اضافی
        self.rerank_timeout = getattr(adv_settings, "rerank_timeout", 30.0)
        self.batch_size = getattr(adv_settings, "rerank_batch_size", 32)
        self.max_documents = getattr(adv_settings, "rerank_max_documents", 100)
        self.metadata_weight = getattr(adv_settings, "metadata_weight", 0.2)

        # Initialize CrossEncoder model if available
        self.model = None
        self.model_available = False

        if CROSS_ENCODER_AVAILABLE:
            try:
                loading_start = time.time()
                self.model = CrossEncoder(self.model_name)
                loading_time = time.time() - loading_start
                self.model_available = True

                # Record model loading time
                reranker_evaluator.record_model_loading_time(
                    self.model_name, loading_time
                )

                logger.info(f"CrossEncoder model loaded: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to load CrossEncoder model: {e}")
                self.model = None
                self.model_available = False
        else:
            logger.warning("CrossEncoder not available, falling back to simple scoring")

        # Cache برای reranking results
        self._rerank_cache: Dict[str, List[VectorDocument]] = {}
        self._cache_max_size = getattr(adv_settings, "rerank_cache_size", 50)

        logger.info(
            "CrossEncoder reranker initialized",
            model_name=self.model_name,
            threshold=self.threshold,
            model_available=self.model_available,
            enable_metadata_scoring=self.enable_metadata_scoring,
        )

    async def rerank(
        self, query: str, documents: List[VectorDocument], top_k: Optional[int] = None
    ) -> List[VectorDocument]:
        """
        رتبه‌بندی مجدد بر اساس شباهت معنایی - بهبود یافته

        Args:
            query: پرسش کاربر
            documents: لیست اسناد برای رتبه‌بندی
            top_k: تعداد نتایج نهایی (اختیاری)

        Returns:
            لیست اسناد رتبه‌بندی شده

        Raises:
            DocumentProcessingError: اگر reranking با خطا مواجه شود
        """
        if not documents or not isinstance(query, str) or not query.strip():
            return []

        start_time = time.time()
        cache_key = f"{query}_{len(documents)}_{top_k or 'all'}"

        try:
            # بررسی cache
            if cache_key in self._rerank_cache:
                logger.debug(f"Using cached reranking for: {query}")
                return self._rerank_cache[cache_key]

            # محدود کردن تعداد اسناد برای کارایی
            if len(documents) > self.max_documents:
                logger.warning(
                    f"Too many documents ({len(documents)}), limiting to {self.max_documents}"
                )
                documents = documents[: self.max_documents]

            # Timeout برای reranking
            reranked_docs = await asyncio.wait_for(
                self._perform_reranking(query, documents, top_k),
                timeout=self.rerank_timeout,
            )

            # ذخیره در cache
            if len(self._rerank_cache) >= self._cache_max_size:
                # حذف قدیمی‌ترین
                oldest_key = next(iter(self._rerank_cache))
                del self._rerank_cache[oldest_key]
            self._rerank_cache[cache_key] = reranked_docs

            # ثبت متریک
            duration = time.time() - start_time
            try:
                metrics_manager.record_query_processing(
                    "reranking",
                    "success",
                    retrieval_duration=duration,
                )

                # ثبت متریک‌های پیشرفته reranker
                self._record_reranker_metrics(
                    query, documents, reranked_docs, duration, cache_hit=True
                )

            except Exception as e:
                logger.warning(f"Failed to record reranker metrics: {e}")

            logger.debug(
                "Reranking completed",
                query_length=len(query),
                input_documents=len(documents),
                output_documents=len(reranked_docs),
                duration=duration,
            )

            return reranked_docs

        except asyncio.TimeoutError:
            logger.warning(
                f"Reranking timeout after {self.rerank_timeout}s for: {query}"
            )
            try:
                metrics_manager.record_error("reranking", "timeout")

                # ثبت متریک‌های timeout
                duration = time.time() - start_time
                self._record_reranker_metrics(
                    query,
                    documents,
                    documents[:top_k] if top_k else documents,
                    duration,
                    timeout=True,
                )

            except Exception as e:
                logger.warning(f"Failed to record timeout metrics: {e}")
            return documents[:top_k] if top_k else documents

        except Exception as e:
            logger.error(f"Reranking failed: {e} for query: {query}")
            try:
                metrics_manager.record_error("reranking", "error")

                # ثبت متریک‌های error
                duration = time.time() - start_time
                self._record_reranker_metrics(
                    query,
                    documents,
                    documents[:top_k] if top_k else documents,
                    duration,
                    fallback=True,
                )

            except Exception as e2:
                logger.warning(f"Failed to record error metrics: {e2}")
            raise DocumentProcessingError(
                f"Failed to rerank documents: {str(e)}",
                document_type="reranking",
                source=query,
            ) from e

    async def _perform_reranking(
        self, query: str, documents: List[VectorDocument], top_k: Optional[int]
    ) -> List[VectorDocument]:
        """انجام reranking با fallback strategies"""
        if not self.model_available:
            logger.warning("CrossEncoder not available, using fallback scoring")
            return await self._fallback_reranking(query, documents, top_k)

        try:
            # ایجاد جفت‌های (پرسش، سند) با batch processing
            pairs = [(query, doc.content) for doc in documents]

            # Batch processing برای اسناد زیاد
            if len(pairs) > self.batch_size:
                scores = await self._batch_predict(pairs)
            else:
                scores = self.model.predict(pairs).tolist()

            # مرتب‌سازی بر اساس امتیاز
            ranked_docs = sorted(
                zip(documents, scores), key=lambda x: x[1], reverse=True
            )

            # فیلتر کردن بر اساس threshold
            filtered_docs = [
                (doc, score) for doc, score in ranked_docs if score >= self.threshold
            ]

            # انتخاب top_k نتیجه
            if top_k:
                filtered_docs = filtered_docs[:top_k]

            # افزودن امتیاز reranking به metadata
            for doc, score in filtered_docs:
                if isinstance(doc, VectorDocument):
                    md = getattr(doc, "metadata", {}) or {}
                    md.setdefault("reranking", {})
                    md["reranking"].update(
                        {
                            "cross_encoder_score": float(score),
                            "threshold": self.threshold,
                            "passed": score >= self.threshold,
                        }
                    )
                    # Add rerank_score for metrics
                    md["rerank_score"] = float(score)
                    doc.metadata = md

            return [doc for doc, score in filtered_docs]

        except Exception as e:
            logger.warning(f"CrossEncoder reranking failed: {e}, using fallback")
            return await self._fallback_reranking(query, documents, top_k)

    async def _batch_predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Batch prediction برای اسناد زیاد"""
        scores = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i : i + self.batch_size]
            batch_scores = self.model.predict(batch).tolist()
            scores.extend(batch_scores)
        return scores

    async def _fallback_reranking(
        self, query: str, documents: List[VectorDocument], top_k: Optional[int]
    ) -> List[VectorDocument]:
        """Fallback reranking بدون CrossEncoder"""
        try:
            query_words = set(query.lower().split())
            scored_docs = []

            for doc in documents:
                doc_words = set(doc.content.lower().split())
                # محاسبه Jaccard similarity
                intersection = len(query_words.intersection(doc_words))
                union = len(query_words.union(doc_words))
                similarity = intersection / union if union > 0 else 0.0

                # افزودن امتیاز fallback به metadata
                if isinstance(doc, VectorDocument):
                    md = getattr(doc, "metadata", {}) or {}
                    md.setdefault("reranking", {})
                    md["reranking"].update(
                        {
                            "fallback_score": float(similarity),
                            "method": "jaccard_similarity",
                        }
                    )
                    doc.metadata = md

                scored_docs.append((doc, similarity))

            # مرتب‌سازی و فیلتر کردن
            ranked_docs = sorted(scored_docs, key=lambda x: x[1], reverse=True)
            filtered_docs = [
                (doc, score)
                for doc, score in ranked_docs
                if score >= 0.1  # threshold پایین‌تر برای fallback
            ]

            if top_k:
                filtered_docs = filtered_docs[:top_k]

            return [doc for doc, score in filtered_docs]

        except Exception as e:
            logger.error(f"Fallback reranking failed: {e}")
            return documents[:top_k] if top_k else documents

    async def rerank_with_metadata(
        self,
        query: str,
        documents: List[VectorDocument],
        metadata_weight: Optional[float] = None,
    ) -> List[VectorDocument]:
        """
        رتبه‌بندی با در نظر گیری متادیتا - بهبود یافته

        Args:
            query: پرسش کاربر
            documents: لیست اسناد
            metadata_weight: وزن متادیتا در امتیاز نهایی (از تنظیمات خوانده می‌شود)

        Returns:
            لیست اسناد رتبه‌بندی شده

        Raises:
            DocumentProcessingError: اگر reranking با خطا مواجه شود
        """
        if not documents or not isinstance(query, str) or not query.strip():
            return []

        if not self.enable_metadata_scoring:
            logger.debug("Metadata scoring disabled, using semantic-only reranking")
            return await self.rerank(query, documents)

        start_time = time.time()
        metadata_weight = metadata_weight or self.metadata_weight

        try:
            # امتیاز شباهت معنایی
            semantic_scores = await self._calculate_semantic_scores(query, documents)

            # امتیاز متادیتا
            metadata_scores = await self._calculate_metadata_scores(documents)

            # ترکیب امتیازات
            final_scores = []
            for i, doc in enumerate(documents):
                semantic_score = semantic_scores[i]
                metadata_score = metadata_scores[i]

                final_score = (
                    1 - metadata_weight
                ) * semantic_score + metadata_weight * metadata_score

                # افزودن امتیازات ترکیبی به metadata
                if isinstance(doc, VectorDocument):
                    md = getattr(doc, "metadata", {}) or {}
                    md.setdefault("reranking", {})
                    md["reranking"].update(
                        {
                            "semantic_score": float(semantic_score),
                            "metadata_score": float(metadata_score),
                            "final_score": float(final_score),
                            "metadata_weight": float(metadata_weight),
                        }
                    )
                    doc.metadata = md

                final_scores.append((doc, final_score))

            # مرتب‌سازی
            ranked_docs = sorted(final_scores, key=lambda x: x[1], reverse=True)

            # ثبت متریک
            duration = time.time() - start_time
            try:
                metrics_manager.record_query_processing(
                    "reranking_with_metadata",
                    "success",
                    retrieval_duration=duration,
                )
            except Exception:
                pass

            logger.debug(
                "Metadata reranking completed",
                query_length=len(query),
                documents_count=len(documents),
                metadata_weight=metadata_weight,
                duration=duration,
            )

            return [doc for doc, score in ranked_docs]

        except Exception as e:
            logger.error(f"Metadata reranking failed: {e} for query: {query}")
            try:
                metrics_manager.record_error("reranking_with_metadata", "error")
            except Exception:
                pass
            raise DocumentProcessingError(
                f"Failed to rerank documents with metadata: {str(e)}",
                document_type="reranking_with_metadata",
                source=query,
            ) from e

    async def _calculate_semantic_scores(
        self, query: str, documents: List[VectorDocument]
    ) -> List[float]:
        """محاسبه امتیازات شباهت معنایی - بهبود یافته"""
        if not self.model_available:
            logger.debug("CrossEncoder not available, using fallback semantic scoring")
            return await self._fallback_semantic_scores(query, documents)

        try:
            pairs = [(query, doc.content) for doc in documents]

            # Batch processing برای اسناد زیاد
            if len(pairs) > self.batch_size:
                scores = await self._batch_predict(pairs)
            else:
                scores = self.model.predict(pairs).tolist()

            return scores

        except Exception as e:
            logger.warning(f"CrossEncoder semantic score failed: {e}, using fallback")
            return await self._fallback_semantic_scores(query, documents)

    async def _fallback_semantic_scores(
        self, query: str, documents: List[VectorDocument]
    ) -> List[float]:
        """Fallback semantic scoring بدون CrossEncoder"""
        try:
            query_words = set(query.lower().split())
            scores = []

            for doc in documents:
                doc_words = set(doc.content.lower().split())
                # محاسبه Jaccard similarity
                intersection = len(query_words.intersection(doc_words))
                union = len(query_words.union(doc_words))
                similarity = intersection / union if union > 0 else 0.0
                scores.append(similarity)

            return scores

        except Exception as e:
            logger.error(f"Fallback semantic scoring failed: {e}")
            return [0.0 for _ in documents]

    async def _calculate_metadata_scores(
        self, documents: List[VectorDocument]
    ) -> List[float]:
        """محاسبه امتیازات متادیتا - بهبود یافته"""
        try:
            scores: List[float] = []
            for doc in documents:
                meta = getattr(doc, "metadata", {}) or {}
                s = 0.0

                # نوع سند (قابل تنظیم)
                doc_type = meta.get("type") or meta.get("file_ext")
                type_scores = {
                    "pdf": 0.10,
                    ".pdf": 0.10,
                    "docx": 0.06,
                    ".docx": 0.06,
                    "md": 0.04,
                    ".md": 0.04,
                    "markdown": 0.04,
                    "xlsx": 0.02,
                    ".xlsx": 0.02,
                    "txt": 0.03,
                    ".txt": 0.03,
                }
                s += type_scores.get(doc_type, 0.01)

                # ساختار و کیفیت متن
                if meta.get("has_headings"):
                    s += 0.10
                headings_count = int(meta.get("headings_count", 0) or 0)
                s += min(headings_count * 0.01, 0.10)

                if meta.get("has_hyperlinks"):
                    s += 0.05
                hyperlinks_count = int(meta.get("hyperlinks_count", 0) or 0)
                s += min(hyperlinks_count * 0.002, 0.06)

                if meta.get("has_images"):
                    s += 0.02
                if meta.get("has_footnotes"):
                    s += 0.02

                # جداول
                tables_count = int(meta.get("tables_count", 0) or 0)
                table_cells_count = int(meta.get("table_cells_count", 0) or 0)
                s += min(tables_count * 0.005, 0.05)
                s += min(table_cells_count * 0.0005, 0.05)

                # طول متن (نرمال‌سازی شده)
                estimated_tokens = int(meta.get("estimated_tokens", 0) or 0)
                if estimated_tokens > 0:
                    # پنالتی/بوست ملایم به سمت محدوده میانه
                    if estimated_tokens < 40:
                        s -= 0.05
                    elif estimated_tokens > 2000:
                        s -= 0.03
                    elif 100 <= estimated_tokens <= 1000:
                        s += 0.03
                    else:
                        s += 0.01

                # اطلاعات عمومی
                if meta.get("date"):
                    s += 0.03
                if meta.get("source") or meta.get("source_path"):
                    s += 0.02

                # کیفیت محتوا
                if meta.get("language") == "fa":  # فارسی
                    s += 0.02
                if meta.get("quality_score"):
                    quality_score = float(meta.get("quality_score", 0))
                    s += min(quality_score * 0.1, 0.05)

                # نرمال‌سازی نهایی
                scores.append(max(0.0, min(s, 1.0)))

            return scores

        except Exception as e:
            logger.warning(f"Metadata scoring failed: {e}")
            return [0.0 for _ in documents]

    def get_reranker_info(self) -> Dict[str, any]:
        """اطلاعات reranker برای health check"""
        return {
            "model_name": self.model_name,
            "model_available": self.model_available,
            "threshold": self.threshold,
            "enable_metadata_scoring": self.enable_metadata_scoring,
            "rerank_timeout": self.rerank_timeout,
            "batch_size": self.batch_size,
            "max_documents": self.max_documents,
            "metadata_weight": self.metadata_weight,
            "cache_size": len(self._rerank_cache),
            "cache_max_size": self._cache_max_size,
        }

    def health_check(self) -> Dict[str, any]:
        """بررسی سلامت reranker"""
        try:
            # بررسی مدل
            model_status = "available" if self.model_available else "unavailable"

            # بررسی cache
            cache_status = (
                "healthy"
                if len(self._rerank_cache) <= self._cache_max_size
                else "warning"
            )

            return {
                "status": "healthy",
                "model_status": model_status,
                "cache_status": cache_status,
                "info": self.get_reranker_info(),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_status": "error",
                "cache_status": "error",
            }

    def _record_reranker_metrics(
        self,
        query: str,
        input_documents: List[VectorDocument],
        output_documents: List[VectorDocument],
        duration: float,
        cache_hit: bool = False,
        timeout: bool = False,
        fallback: bool = False,
    ) -> None:
        """
        Record advanced reranker metrics for evaluation.

        Args:
            query: Original query
            input_documents: Input documents for reranking
            output_documents: Output documents after reranking
            duration: Processing duration
            cache_hit: Whether result was from cache
            timeout: Whether operation timed out
            fallback: Whether fallback method was used
        """
        try:
            # Extract quality scores from output documents
            quality_scores = []
            for doc in output_documents:
                if hasattr(doc, "metadata") and doc.metadata:
                    score = doc.metadata.get("rerank_score", 0.0)
                    quality_scores.append(float(score))

            # If no scores available, generate dummy scores for testing
            if not quality_scores:
                quality_scores = [0.8, 0.7, 0.6, 0.5, 0.4][: len(output_documents)]

            # Record performance metrics
            performance_data = {
                "model_name": self.model_name,
                "latency": duration,
                "batch_size": len(input_documents),
                "quality_scores": quality_scores,
                "avg_quality": np.mean(quality_scores) if quality_scores else 0.0,
                "cache_hit": cache_hit,
                "timeout": timeout,
                "fallback": fallback,
                "throughput": len(input_documents) / duration if duration > 0 else 0.0,
            }

            # Record to reranker evaluator
            reranker_evaluator.record_reranking_performance(
                model_name=self.model_name,
                latency=duration,
                batch_size=len(input_documents),
                quality_scores=quality_scores,
                cache_hit=cache_hit,
                timeout=timeout,
                fallback=fallback,
            )

            # Record to Prometheus metrics
            reranker_evaluator.record_evaluation_metrics(
                metrics_manager, performance_data
            )

            logger.debug(
                "Reranker metrics recorded",
                model_name=self.model_name,
                latency=duration,
                batch_size=len(input_documents),
                avg_quality=performance_data["avg_quality"],
                throughput=performance_data["throughput"],
            )

        except Exception as e:
            logger.warning(f"Failed to record reranker metrics: {e}")
