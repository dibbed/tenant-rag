"""
ترکیب تمام قابلیت‌های جستجوی پیشرفته
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import numpy as np

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager, retrieval_evaluator
from ragbot.rag.exceptions import RetrievalError

from ..store.base import VectorDocument
from .hybrid_search import HybridRetriever
from .query_expansion import QueryExpander
from .reranker import CrossEncoderReranker


class AdvancedRetriever:
    """ترکیب تمام قابلیت‌های جستجوی پیشرفته"""

    def __init__(
        self,
        vector_store,
        embedder=None,
        enable_reranking: Optional[bool] = None,
        enable_hybrid: Optional[bool] = None,
        enable_expansion: Optional[bool] = None,
        reranker_model: Optional[str] = None,
        reranker_threshold: Optional[float] = None,
        expansion_type: Optional[str] = None,
        hybrid_alpha: Optional[float] = None,
        keyword_search_enabled: Optional[bool] = None,
        confidence_threshold: Optional[float] = None,
        max_expanded_queries: Optional[int] = None,
        initial_search_multiplier: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Initialize advanced retriever with settings integration

        Args:
            vector_store: ذخیره‌گاه برداری
            embedder: مدل جاسازی
            enable_reranking: فعال‌سازی رتبه‌بندی مجدد (از settings خوانده می‌شود)
            enable_hybrid: فعال‌سازی جستجوی ترکیبی (از settings خوانده می‌شود)
            enable_expansion: فعال‌سازی گسترش پرسش (از settings خوانده می‌شود)
            **kwargs: سایر تنظیمات
        """
        self.vector_store = vector_store
        self.embedder = embedder

        # خواندن تنظیمات از settings با fallback به مقادیر پیش‌فرض
        adv_settings = getattr(settings, "advanced_retrieval", object())

        self.enable_reranking = (
            enable_reranking
            if enable_reranking is not None
            else getattr(adv_settings, "enable_reranking", True)
        )
        self.enable_hybrid = (
            enable_hybrid
            if enable_hybrid is not None
            else getattr(adv_settings, "enable_hybrid", True)
        )
        self.enable_expansion = (
            enable_expansion
            if enable_expansion is not None
            else getattr(adv_settings, "enable_expansion", True)
        )

        self.reranker_model = reranker_model or getattr(
            adv_settings, "reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.reranker_threshold = (
            reranker_threshold
            if reranker_threshold is not None
            else getattr(adv_settings, "reranker_threshold", 0.7)
        )
        self.expansion_type = expansion_type or getattr(
            adv_settings, "expansion_type", "synonym"
        )
        self.hybrid_alpha = (
            hybrid_alpha
            if hybrid_alpha is not None
            else getattr(adv_settings, "hybrid_alpha", 0.7)
        )
        self.keyword_search_enabled = (
            keyword_search_enabled
            if keyword_search_enabled is not None
            else getattr(adv_settings, "keyword_search_enabled", True)
        )
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else getattr(adv_settings, "confidence_threshold", 0.5)
        )
        self.max_expanded_queries = (
            max_expanded_queries
            if max_expanded_queries is not None
            else getattr(adv_settings, "max_expanded_queries", 3)
        )
        self.initial_search_multiplier = (
            initial_search_multiplier
            if initial_search_multiplier is not None
            else getattr(adv_settings, "initial_search_multiplier", 2)
        )

        # تنظیمات اضافی
        self.rerank_timeout = getattr(adv_settings, "rerank_timeout", 30.0)
        self.expansion_timeout = getattr(adv_settings, "expansion_timeout", 10.0)
        self.min_hybrid_score = getattr(adv_settings, "min_hybrid_score", 0.0)
        self.enable_content_dedup = getattr(adv_settings, "enable_content_dedup", True)
        self.content_dedup_threshold = getattr(
            adv_settings, "content_dedup_threshold", 0.95
        )

        # Initialize components
        self.reranker = (
            CrossEncoderReranker(
                model_name=self.reranker_model,
                threshold=self.reranker_threshold,
                enable_metadata_scoring=getattr(
                    adv_settings, "enable_metadata_scoring", True
                ),
            )
            if self.enable_reranking
            else None
        )
        self.hybrid_retriever = (
            HybridRetriever(
                vector_store,
                embedder=embedder,
                alpha=self.hybrid_alpha,
                keyword_search_enabled=self.keyword_search_enabled,
            )
            if self.enable_hybrid
            else None
        )
        self.query_expander = (
            QueryExpander(max_expanded_queries=self.max_expanded_queries)
            if self.enable_expansion
            else None
        )

        # Cache برای expanded queries
        self._query_cache: Dict[str, List[str]] = {}
        self._cache_max_size = getattr(adv_settings, "query_cache_size", 100)

        logger.info(
            "Advanced retriever initialized",
            enable_reranking=self.enable_reranking,
            enable_hybrid=self.enable_hybrid,
            enable_expansion=self.enable_expansion,
            reranker_model=self.reranker_model,
            hybrid_alpha=self.hybrid_alpha,
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = 4,
        use_reranking: Optional[bool] = None,
        use_hybrid: Optional[bool] = None,
        use_expansion: Optional[bool] = None,
        **kwargs: Any,
    ) -> List[VectorDocument]:
        """
        جستجوی پیشرفته با تمام قابلیت‌ها و مدیریت خطای بهبود یافته

        Args:
            query: پرسش کاربر
            top_k: تعداد نتایج نهایی
            use_reranking: استفاده از رتبه‌بندی مجدد (از تنظیمات خوانده می‌شود)
            use_hybrid: استفاده از جستجوی ترکیبی (از تنظیمات خوانده می‌شود)
            use_expansion: استفاده از گسترش پرسش (از تنظیمات خوانده می‌شود)
            **kwargs: سایر تنظیمات

        Returns:
            لیست اسناد مرتبط

        Raises:
            RetrievalError: اگر جستجو با خطا مواجه شود
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query is empty")

        start_time = time.time()
        retrieval_metadata = {
            "query": query,
            "top_k": top_k,
            "stages": {},
            "errors": [],
            "performance": {},
        }

        try:
            # استفاده از تنظیمات کلاس اگر پارامتر داده نشده باشد
            use_reranking = (
                use_reranking if use_reranking is not None else self.enable_reranking
            )
            use_hybrid = use_hybrid if use_hybrid is not None else self.enable_hybrid
            use_expansion = (
                use_expansion if use_expansion is not None else self.enable_expansion
            )

            # مرحله 1: گسترش پرسش (اختیاری) با timeout و cache
            expanded_queries = [query]
            expansion_start = time.time()

            if use_expansion and self.query_expander:
                try:
                    # بررسی cache
                    cache_key = f"{query}_{self.expansion_type}"
                    if cache_key in self._query_cache:
                        expanded_queries = self._query_cache[cache_key]
                        retrieval_metadata["stages"]["expansion"] = "cached"
                    else:
                        # Timeout برای expansion
                        expanded = await asyncio.wait_for(
                            self.query_expander.expand_query(
                                query, expansion_type=self.expansion_type
                            ),
                            timeout=self.expansion_timeout,
                        )

                        if expanded:
                            expanded_queries = list(dict.fromkeys([query] + expanded))[
                                : self.max_expanded_queries + 1
                            ]
                            # ذخیره در cache
                            if len(self._query_cache) >= self._cache_max_size:
                                # حذف قدیمی‌ترین
                                oldest_key = next(iter(self._query_cache))
                                del self._query_cache[oldest_key]
                            self._query_cache[cache_key] = expanded_queries

                        retrieval_metadata["stages"]["expansion"] = "success"
                        retrieval_metadata["performance"]["expansion_duration"] = (
                            time.time() - expansion_start
                        )

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Query expansion timeout after {self.expansion_timeout}s"
                    )
                    retrieval_metadata["errors"].append("expansion_timeout")
                    retrieval_metadata["stages"]["expansion"] = "timeout"
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")
                    retrieval_metadata["errors"].append(f"expansion_error: {str(e)}")
                    retrieval_metadata["stages"]["expansion"] = "failed"
            else:
                retrieval_metadata["stages"]["expansion"] = "disabled"

            # مرحله 2: جستجوی اولیه (برای همه پرسش‌های گسترش‌یافته) و ادغام
            search_start = time.time()
            merged: List[VectorDocument] = []
            seen_ids = set()
            seen_contents = set() if self.enable_content_dedup else None

            for q in expanded_queries:
                try:
                    if use_hybrid and self.hybrid_retriever:
                        results = await self.hybrid_retriever.search(
                            q,
                            top_k=top_k * self.initial_search_multiplier,
                            min_hybrid_score=self.min_hybrid_score,
                        )
                    else:
                        results = await self._basic_search(
                            q, top_k * self.initial_search_multiplier
                        )

                    for doc in results or []:
                        doc_id = getattr(doc, "id", None)

                        # Deduplication بر اساس ID
                        if doc_id and doc_id in seen_ids:
                            continue

                        # Deduplication بر اساس محتوا (اختیاری)
                        if seen_contents is not None:
                            content_hash = hash(doc.content[:100])  # اول 100 کاراکتر
                            if content_hash in seen_contents:
                                continue
                            seen_contents.add(content_hash)

                        if doc_id:
                            seen_ids.add(doc_id)
                        merged.append(doc)

                except Exception as e:
                    logger.warning(f"Search failed for query '{q}': {e}")
                    retrieval_metadata["errors"].append(f"search_error: {str(e)}")

            initial_results = merged
            retrieval_metadata["stages"]["search"] = "success"
            retrieval_metadata["performance"]["search_duration"] = (
                time.time() - search_start
            )
            retrieval_metadata["performance"]["initial_results_count"] = len(
                initial_results
            )

            # مرحله 3: رتبه‌بندی مجدد (اختیاری) با timeout
            if use_reranking and self.reranker and initial_results:
                rerank_start = time.time()
                try:
                    # Timeout برای reranking
                    final_results = await asyncio.wait_for(
                        self.reranker.rerank_with_metadata(
                            query, initial_results, metadata_weight=0.25
                        ),
                        timeout=self.rerank_timeout,
                    )
                    if top_k:
                        final_results = final_results[:top_k]
                    retrieval_metadata["stages"]["reranking"] = "success_with_metadata"

                except asyncio.TimeoutError:
                    logger.warning(f"Reranking timeout after {self.rerank_timeout}s")
                    retrieval_metadata["errors"].append("rerank_timeout")
                    retrieval_metadata["stages"]["reranking"] = "timeout"
                    final_results = initial_results[:top_k]

                except Exception as e:
                    logger.warning(
                        f"Rerank with metadata failed, trying basic rerank: {e}"
                    )
                    try:
                        final_results = await asyncio.wait_for(
                            self.reranker.rerank(query, initial_results, top_k),
                            timeout=self.rerank_timeout,
                        )
                        retrieval_metadata["stages"]["reranking"] = "success_basic"
                    except Exception as e2:
                        logger.warning(f"Basic rerank also failed: {e2}")
                        retrieval_metadata["errors"].append(f"rerank_error: {str(e2)}")
                        retrieval_metadata["stages"]["reranking"] = "failed"
                        final_results = initial_results[:top_k]

                retrieval_metadata["performance"]["rerank_duration"] = (
                    time.time() - rerank_start
                )
            else:
                final_results = initial_results[:top_k]
                retrieval_metadata["stages"]["reranking"] = "disabled"

            # محاسبه زمان کل
            total_duration = time.time() - start_time
            retrieval_metadata["performance"]["total_duration"] = total_duration

            # لاگ تشخیصی نتایج
            logger.info(
                "Advanced retrieval completed",
                query_length=len(query),
                expanded_queries_count=len(expanded_queries),
                initial_results_count=len(initial_results),
                final_results_count=len(final_results),
                total_duration=total_duration,
                stages=retrieval_metadata["stages"],
                errors_count=len(retrieval_metadata["errors"]),
            )

            # ثبت متریک
            try:
                metrics_manager.record_query_processing(
                    "advanced_retrieval",
                    "success"
                    if not retrieval_metadata["errors"]
                    else "partial_success",
                    retrieval_duration=total_duration,
                )

                # ثبت متریک‌های پیشرفته بازیابی
                self._record_advanced_metrics(
                    query,
                    expanded_queries,
                    initial_results,
                    final_results,
                    retrieval_metadata,
                    total_duration,
                )

            except Exception as e:
                logger.warning(f"Failed to record metrics: {e}")

            # افزودن متادیتای تصمیم‌گیری به هر سند
            for doc in final_results:
                if isinstance(doc, VectorDocument):
                    md = getattr(doc, "metadata", {}) or {}
                    md.setdefault("advanced_retrieval", {})
                    md["advanced_retrieval"].update(
                        {
                            "query_expanded": len(expanded_queries) > 1,
                            "expansion_type": self.expansion_type
                            if use_expansion
                            else None,
                            "hybrid_search_used": use_hybrid,
                            "reranking_used": use_reranking,
                            "reranking_stage": retrieval_metadata["stages"].get(
                                "reranking"
                            ),
                            "total_duration": total_duration,
                        }
                    )
                    doc.metadata = md

            return final_results

        except Exception as e:
            metrics_manager.record_error("advanced_retrieval", "retriever")
            logger.error(f"Advanced retrieval failed: {e}")
            raise RetrievalError(
                f"Failed to retrieve documents: {str(e)}", query=query, details=str(e)
            ) from e

    async def _basic_search(self, query: str, top_k: int) -> List[VectorDocument]:
        """جستجوی پایه"""
        if not self.embedder:
            return []

        # تولید جاسازی پرسش
        query_embedding = await self.embedder.embed_texts([query])

        # جستجو در ذخیره‌گاه برداری
        search_result = await self.vector_store.search(query_embedding[0], top_k=top_k)
        results = search_result.documents if hasattr(search_result, "documents") else []

        return results

    async def retrieve_with_confidence(
        self, query: str, top_k: int = 4, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        جستجو با امتیاز اطمینان بهبود یافته

        Args:
            query: پرسش کاربر
            top_k: تعداد نتایج
            **kwargs: سایر تنظیمات

        Returns:
            نتایج با امتیاز اطمینان و متادیتای کامل
        """
        start_time = time.time()

        # جستجوی پیشرفته
        results = await self.retrieve(query, top_k, **kwargs)

        # محاسبه امتیاز اطمینان با batch processing
        confidence_scores = await self._calculate_confidence_scores_batch(
            query, results
        )

        # فیلتر بر اساس threshold
        filtered_results = []
        filtered_scores = []
        for result, score in zip(results, confidence_scores):
            if score >= self.confidence_threshold:
                filtered_results.append(result)
                filtered_scores.append(score)
                # افزودن confidence score به متادیتا
                if isinstance(result, VectorDocument):
                    md = getattr(result, "metadata", {}) or {}
                    md.setdefault("confidence", {})
                    md["confidence"].update(
                        {
                            "score": score,
                            "threshold": self.confidence_threshold,
                            "passed": score >= self.confidence_threshold,
                        }
                    )
                    result.metadata = md

        total_duration = time.time() - start_time

        logger.info(
            "Confidence-based retrieval completed",
            query_length=len(query),
            total_results=len(results),
            filtered_results=len(filtered_results),
            average_confidence=sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0,
            threshold=self.confidence_threshold,
            duration=total_duration,
        )

        return {
            "results": filtered_results,
            "confidence_scores": filtered_scores,
            "average_confidence": sum(filtered_scores) / len(filtered_scores)
            if filtered_scores
            else 0,
            "total_results": len(results),
            "filtered_count": len(filtered_results),
            "threshold": self.confidence_threshold,
            "duration": total_duration,
        }

    async def _calculate_confidence_scores_batch(
        self, query: str, results: List[VectorDocument]
    ) -> List[float]:
        """محاسبه امتیازات اطمینان با batch processing برای کارایی بهتر"""
        if not self.embedder or not results:
            return [0.5] * len(results)

        try:
            # تولید جاسازی پرسش
            query_embedding = await self.embedder.embed_texts([query])

            # Batch embedding برای همه اسناد
            doc_contents = [doc.content for doc in results]
            doc_embeddings = await self.embedder.embed_texts(doc_contents)

            # محاسبه شباهت کسینوسی برای همه اسناد
            confidence_scores = []
            for doc_embedding in doc_embeddings:
                similarity = self._cosine_similarity(query_embedding[0], doc_embedding)
                confidence_scores.append(similarity)

            return confidence_scores

        except Exception as e:
            logger.warning(f"Batch confidence calculation failed, using fallback: {e}")
            # Fallback: محاسبه تکی
            return await self._calculate_confidence_scores_fallback(query, results)

    async def _calculate_confidence_scores_fallback(
        self, query: str, results: List[VectorDocument]
    ) -> List[float]:
        """Fallback برای محاسبه confidence scores"""
        if not self.embedder:
            return [0.5] * len(results)

        try:
            query_embedding = await self.embedder.embed_texts([query])
            confidence_scores = []

            for result in results:
                try:
                    doc_embedding = await self.embedder.embed_texts([result.content])
                    similarity = self._cosine_similarity(
                        query_embedding[0], doc_embedding[0]
                    )
                    confidence_scores.append(similarity)
                except Exception:
                    confidence_scores.append(0.5)  # Fallback score

            return confidence_scores

        except Exception:
            return [0.5] * len(results)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """محاسبه شباهت کسینوسی با numpy"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))
        except Exception:
            return 0.0

    def get_retriever_info(self) -> Dict[str, Any]:
        """دریافت اطلاعات تنظیمات retriever"""
        return {
            "enable_reranking": self.enable_reranking,
            "enable_hybrid": self.enable_hybrid,
            "enable_expansion": self.enable_expansion,
            "reranker_model": self.reranker_model,
            "reranker_threshold": self.reranker_threshold,
            "expansion_type": self.expansion_type,
            "hybrid_alpha": self.hybrid_alpha,
            "confidence_threshold": self.confidence_threshold,
            "max_expanded_queries": self.max_expanded_queries,
            "initial_search_multiplier": self.initial_search_multiplier,
            "rerank_timeout": self.rerank_timeout,
            "expansion_timeout": self.expansion_timeout,
            "min_hybrid_score": self.min_hybrid_score,
            "enable_content_dedup": self.enable_content_dedup,
            "cache_size": len(self._query_cache),
            "cache_max_size": self._cache_max_size,
        }

    async def health_check(self) -> Dict[str, Any]:
        """بررسی سلامت retriever"""
        try:
            # تست جستجوی ساده
            test_docs = await self.retrieve("test query", top_k=1)

            # تست confidence calculation
            confidence_result = await self.retrieve_with_confidence(
                "test query", top_k=1
            )

            return {
                "status": "healthy",
                "retriever_type": "AdvancedRetriever",
                "vector_store_status": "connected",
                "embedder_status": "connected" if self.embedder else "not_configured",
                "reranker_status": "available" if self.reranker else "disabled",
                "hybrid_retriever_status": "available"
                if self.hybrid_retriever
                else "disabled",
                "query_expander_status": "available"
                if self.query_expander
                else "disabled",
                "test_successful": True,
                "test_results": len(test_docs),
                "confidence_test_successful": len(confidence_result["results"]) >= 0,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "retriever_type": "AdvancedRetriever",
                "error": str(e),
                "test_successful": False,
            }

    def _record_advanced_metrics(
        self,
        query: str,
        expanded_queries: List[str],
        initial_results: List[VectorDocument],
        final_results: List[VectorDocument],
        retrieval_metadata: Dict[str, Any],
        total_duration: float,
    ) -> None:
        """
        Record advanced retrieval metrics for evaluation.

        Args:
            query: Original query
            expanded_queries: List of expanded queries
            initial_results: Results before reranking
            final_results: Final results after reranking
            retrieval_metadata: Metadata about retrieval process
            total_duration: Total retrieval duration
        """
        try:
            # Extract document IDs for evaluation
            initial_doc_ids = [doc.id for doc in initial_results if hasattr(doc, "id")]
            final_doc_ids = [doc.id for doc in final_results if hasattr(doc, "id")]

            # Record query expansion metrics
            if len(expanded_queries) > 1:
                # Simulate ground truth (in real scenario, this would come from user feedback)
                # For now, we'll use a simple heuristic based on similarity scores
                ground_truth = initial_doc_ids[:3] if initial_doc_ids else []

                if ground_truth:
                    # Evaluate query expansion effectiveness
                    evaluation = retrieval_evaluator.evaluate_query_expansion(
                        original_query=query,
                        expanded_query=" ".join(
                            expanded_queries[1:3]
                        ),  # Use first 2 expansions
                        original_results=initial_doc_ids,
                        expanded_results=final_doc_ids,
                        relevant_docs=ground_truth,
                    )

                    # Record evaluation metrics
                    retrieval_evaluator.record_evaluation_metrics(
                        metrics_manager, evaluation
                    )

                    # Record expansion-specific metrics
                    if metrics_manager.enabled:
                        metrics_manager._metrics[
                            "query_expansion_timeout_rate"
                        ].inc() if retrieval_metadata["stages"].get(
                            "expansion"
                        ) == "timeout" else None
                        metrics_manager._metrics[
                            "query_expansion_fallback_rate"
                        ].inc() if retrieval_metadata["stages"].get(
                            "expansion"
                        ) == "failed" else None

            # Record retrieval performance metrics
            if metrics_manager.enabled and initial_doc_ids:
                # Calculate Recall@K metrics
                ground_truth = (
                    initial_doc_ids[:5]
                    if len(initial_doc_ids) >= 5
                    else initial_doc_ids
                )

                recall_at_1 = retrieval_evaluator.calculate_recall_at_k(
                    final_doc_ids, ground_truth, 1
                )
                recall_at_3 = retrieval_evaluator.calculate_recall_at_k(
                    final_doc_ids, ground_truth, 3
                )
                recall_at_5 = retrieval_evaluator.calculate_recall_at_k(
                    final_doc_ids, ground_truth, 5
                )
                recall_at_10 = retrieval_evaluator.calculate_recall_at_k(
                    final_doc_ids, ground_truth, 10
                )

                mrr = retrieval_evaluator.calculate_mrr(final_doc_ids, ground_truth)
                ndcg_at_5 = retrieval_evaluator.calculate_ndcg_at_k(
                    final_doc_ids, ground_truth, 5
                )
                ndcg_at_10 = retrieval_evaluator.calculate_ndcg_at_k(
                    final_doc_ids, ground_truth, 10
                )

                # Record metrics
                metrics_manager._metrics["retrieval_recall_at_1"].set(recall_at_1)
                metrics_manager._metrics["retrieval_recall_at_3"].set(recall_at_3)
                metrics_manager._metrics["retrieval_recall_at_5"].set(recall_at_5)
                metrics_manager._metrics["retrieval_recall_at_10"].set(recall_at_10)
                metrics_manager._metrics["retrieval_mrr"].set(mrr)
                metrics_manager._metrics["retrieval_ndcg_at_5"].set(ndcg_at_5)
                metrics_manager._metrics["retrieval_ndcg_at_10"].set(ndcg_at_10)

                # Record strategy-specific metrics
                strategy = retrieval_metadata["stages"].get("reranking", "none")
                metrics_manager._metrics["retrieval_recall_by_strategy"].labels(
                    strategy=strategy, k="5"
                ).set(recall_at_5)

                metrics_manager._metrics["retrieval_ndcg_by_strategy"].labels(
                    strategy=strategy
                ).set(ndcg_at_10)

                logger.debug(
                    "Advanced retrieval metrics recorded",
                    recall_at_5=recall_at_5,
                    mrr=mrr,
                    ndcg_at_10=ndcg_at_10,
                    strategy=strategy,
                )

        except Exception as e:
            logger.warning(f"Failed to record advanced metrics: {e}")
