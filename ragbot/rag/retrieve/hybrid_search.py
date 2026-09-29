"""
ترکیب جستجوی معنایی و کلیدواژه‌ای
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING, TypedDict

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager

if TYPE_CHECKING:
    from ragbot.rag.embeddings.base import Embedder
    from ragbot.rag.store.base import BaseVectorStore, VectorDocument


class _HybridScores(TypedDict):
    document: VectorDocument
    semantic_score: float
    keyword_score: float


class HybridRetriever:
    """ترکیب جستجوی معنایی و کلیدواژه‌ای"""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        keyword_store: SimpleKeywordStore | None = None,
        embedder: Embedder | None = None,
        alpha: float = 0.7,
        keyword_search_enabled: bool = True,
    ) -> None:
        """
        Initialize hybrid retriever

        Args:
            vector_store: ذخیره‌گاه برداری
            keyword_store: ذخیره‌گاه کلیدواژه‌ای (اختیاری)
            embedder: مدل جاسازی
        """
        self.vector_store = vector_store
        self.keyword_store = keyword_store or self._create_keyword_store()
        self.embedder = embedder
        self.alpha = alpha
        self.keyword_search_enabled = keyword_search_enabled

    async def search(
        self,
        query: str,
        alpha: float | None = None,
        top_k: int = 20,
        min_hybrid_score: float = 0.0,
    ) -> list[VectorDocument]:
        """
        جستجوی ترکیبی با وزن‌دهی

        Args:
            query: پرسش کاربر
            alpha: وزن جستجوی معنایی (0-1) - اگر None باشد از تنظیمات کلاس استفاده می‌شود
            top_k: تعداد نتایج

        Returns:
            لیست اسناد مرتبط
        """
        # استفاده از alpha کلاس اگر پارامتر داده نشده باشد (و پویاسازی بر اساس طول پرسش)
        if alpha is None:
            alpha = getattr(
                getattr(settings, "retrieve", object()),
                "hybrid_default_alpha",
                self.alpha,
            )
        # تنظیم حداقل امتیاز از تنظیمات اگر مشخص نشده
        if not min_hybrid_score:
            with contextlib.suppress(Exception):
                min_hybrid_score = float(
                    getattr(
                        getattr(settings, "retrieve", object()), "min_hybrid_score", 0.0
                    )
                )
        try:
            q_len = len((query or "").split())
            if q_len <= 3:
                alpha = max(0.0, min(1.0, alpha - 0.2))  # وزن بیشتر به keyword
            elif q_len >= 15:
                alpha = max(0.0, min(1.0, alpha + 0.1))  # وزن بیشتر به semantic
        except Exception:
            pass

        # جستجوی معنایی
        semantic_results = await self._semantic_search(query, top_k)

        # جستجوی کلیدواژه‌ای (اگر فعال باشد)
        if self.keyword_search_enabled:
            keyword_results = await self._keyword_search(query, top_k)
        else:
            keyword_results = []

        # ثبت لاگ تشخیصی
        with contextlib.suppress(Exception):
            logger.debug(
                "Hybrid search breakdown",
                alpha=alpha,
                top_k=top_k,
                semantic_count=len(semantic_results),
                keyword_enabled=self.keyword_search_enabled,
                keyword_count=len(keyword_results),
            )

        # ترکیب نتایج
        combined_results = await self._combine_results(
            semantic_results, keyword_results, alpha
        )

        # فیلتر حداقل امتیاز ترکیبی (اختیاری)
        if min_hybrid_score > 0:
            with contextlib.suppress(Exception):
                combined_results = [
                    d
                    for d in combined_results
                    if float(
                        (d.metadata.get("hybrid_breakdown") or {}).get(
                            "final_hybrid_score", 0.0
                        )
                    )
                    >= min_hybrid_score
                ]

        final = combined_results[:top_k]
        # متریک ساده
        with contextlib.suppress(Exception):
            metrics_manager.record_query_processing(
                "hybrid_search",
                "success",
                retrieval_duration=0.0,
            )
        return final

    async def _semantic_search(self, query: str, top_k: int) -> list[VectorDocument]:
        """جستجوی معنایی"""
        if not self.embedder:
            logger.warning("Semantic search skipped: embedder is not initialized")
            return []

        # تولید جاسازی پرسش
        query_embedding = await self.embedder.embed_texts([query])

        # جستجو در ذخیره‌گاه برداری (duck-typing امن)
        result = await self.vector_store.search(query_embedding[0], top_k=top_k)
        documents: list[VectorDocument] = result.documents
        return documents

    async def _keyword_search(self, query: str, top_k: int) -> list[VectorDocument]:
        """جستجوی کلیدواژه‌ای"""
        # استخراج کلیدواژه‌ها
        keywords = self._extract_keywords(query)

        # اگر keyword store خالی است، ابتدا اسناد موجود را از vector store بگیریم (غیرمسدودکننده در حد ممکن)
        if not self.keyword_store.documents:
            # در صورت شکست populate، با نتایج موجود ادامه می‌دهیم
            with contextlib.suppress(Exception):
                await self._populate_keyword_store(limit=5000)

        # جستجو در ذخیره‌گاه کلیدواژه‌ای
        results = await self.keyword_store.search(keywords, k=top_k)

        return results

    async def _populate_keyword_store(self, limit: int = 5000) -> None:
        """پر کردن keyword store با اسناد موجود در vector store"""
        try:
            # اگر vector store متد get_all_documents دارد، از آن استفاده کنیم
            if hasattr(self.vector_store, "get_all_documents"):
                documents = await self.vector_store.get_all_documents()
                if documents:
                    # محدودسازی اندازه برای جلوگیری از مصرف زیاد حافظه
                    await self.keyword_store.add_documents(list(documents)[:limit])
            # وگرنه از جستجوی معنایی با query عمومی استفاده کنیم
            elif self.embedder:
                # جستجو با کلمات عمومی برای گرفتن نمونه‌ای از اسناد
                general_query = "document text content"
                query_embedding = await self.embedder.embed_texts([general_query])
                search_result = await self.vector_store.search(
                    query_embedding[0], top_k=min(1000, limit)
                )
                docs = search_result.documents
                if docs:
                    await self.keyword_store.add_documents(docs[:limit])
        except Exception:
            # اگر خطایی رخ داد، keyword search را غیرفعال کنیم
            self.keyword_search_enabled = False

    async def _combine_results(
        self,
        semantic_results: list[VectorDocument],
        keyword_results: list[VectorDocument],
        alpha: float,
    ) -> list[VectorDocument]:
        """ترکیب نتایج جستجو"""
        # ایجاد دیکشنری برای ترکیب امتیازات
        doc_scores: dict[str, _HybridScores] = {}

        # امتیازات جستجوی معنایی
        for i, doc in enumerate(semantic_results):
            doc_id = self._get_doc_id(doc)
            doc_scores[doc_id] = {
                "document": doc,
                "semantic_score": 1.0 - (i / len(semantic_results)),
                "keyword_score": 0.0,
            }

        # امتیازات جستجوی کلیدواژه‌ای
        for i, doc in enumerate(keyword_results):
            doc_id = self._get_doc_id(doc)
            if doc_id in doc_scores:
                doc_scores[doc_id]["keyword_score"] = 1.0 - (i / len(keyword_results))
            else:
                doc_scores[doc_id] = {
                    "document": doc,
                    "semantic_score": 0.0,
                    "keyword_score": 1.0 - (i / len(keyword_results)),
                }

        # محاسبه امتیاز نهایی (و الصاق متادیتای breakdown)
        final_results: list[tuple[VectorDocument, float]] = []
        for scores in doc_scores.values():
            sem = scores["semantic_score"]
            key = scores["keyword_score"]
            final_score = alpha * sem + (1 - alpha) * key
            doc = scores["document"]
            try:
                md = getattr(doc, "metadata", {}) or {}
                md.setdefault("hybrid_breakdown", {})
                md["hybrid_breakdown"].update(
                    {
                        "alpha_used": alpha,
                        "semantic_score_norm": round(sem, 4),
                        "keyword_score_norm": round(key, 4),
                        "final_hybrid_score": round(final_score, 4),
                    }
                )
                doc.metadata = md
                # The final score is persisted in metadata above for optional filtering.
            except Exception:
                pass

            final_results.append((doc, final_score))

        # مرتب‌سازی بر اساس امتیاز نهایی
        final_results.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, score in final_results]

    def _extract_keywords(self, query: str) -> list[str]:
        """استخراج کلیدواژه‌ها از پرسش با نرمال‌سازی یونیکد/فارسی و bigram ساده"""
        import unicodedata

        # حذف اعراب عربی/فارسی
        def _strip_diacritics(s: str) -> str:
            return "".join(
                ch
                for ch in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(ch)
            )

        # نرمال‌سازی یونیکد و حروف کوچک
        q = query or ""
        q = _strip_diacritics(q)
        q = unicodedata.normalize("NFKC", q).lower()
        # حذف علائم نگارشی (انگلیسی/فارسی/CJK)
        q = re.sub(
            r"[\u200c\u061f\u061b\u060c\u3002\uff01\uff1f\.,!?:;\-\(\)\[\]\{\}\|\/\\]",
            " ",
            q,
        )
        q = re.sub(r"\s+", " ", q).strip()

        # حذف کلمات توقف
        stop_words = {"و", "در", "از", "به", "که", "این", "آن", "با", "برای", "است"}

        words = [w for w in q.split(" ") if w and w not in stop_words and len(w) > 2]

        # bigram ساده برای عبارات دوتایی پرتکرار احتمالی
        bigrams: list[str] = []
        for i in range(len(words) - 1):
            pair = f"{words[i]} {words[i + 1]}"
            if len(words[i]) > 2 and len(words[i + 1]) > 2:
                bigrams.append(pair)

        return list(dict.fromkeys(words + bigrams))

    def _get_doc_id(self, doc: VectorDocument) -> str:
        """دریافت شناسه یکتای سند"""
        return f"{doc.metadata.get('source', '')}_{doc.metadata.get('chunk_id', '')}"

    def _create_keyword_store(self) -> SimpleKeywordStore:
        """ایجاد ذخیره‌گاه کلیدواژه‌ای ساده"""
        return SimpleKeywordStore()


class SimpleKeywordStore:
    """ذخیره‌گاه کلیدواژه‌ای ساده"""

    def __init__(self) -> None:
        self.keyword_index: dict[str, list[str]] = {}
        self.documents: dict[str, VectorDocument] = {}

    async def add_documents(self, documents: list[VectorDocument]) -> None:
        """اضافه کردن اسناد به فهرست کلیدواژه‌ها"""
        for doc in documents:
            doc_id = self._get_doc_id(doc)
            self.documents[doc_id] = doc

            # استخراج کلیدواژه‌ها
            keywords = self._extract_keywords(doc.content)

            # اضافه کردن به فهرست
            for keyword in keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                self.keyword_index[keyword].append(doc_id)

    async def search(self, keywords: list[str], k: int = 10) -> list[VectorDocument]:
        """جستجو بر اساس کلیدواژه‌ها"""
        doc_scores: dict[str, int] = {}

        for keyword in keywords:
            if keyword in self.keyword_index:
                for doc_id in self.keyword_index[keyword]:
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = 0
                    doc_scores[doc_id] += 1

        # مرتب‌سازی بر اساس امتیاز
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        # بازگرداندن اسناد
        results: list[VectorDocument] = []
        for doc_id, _ in sorted_docs[:k]:
            if doc_id in self.documents:
                results.append(self.documents[doc_id])

        return results

    def _extract_keywords(self, text: str) -> list[str]:
        """استخراج کلیدواژه‌ها از متن با نرمال‌سازی یونیکد/فارسی"""
        import unicodedata

        def _strip_diacritics(s: str) -> str:
            return "".join(
                ch
                for ch in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(ch)
            )

        t = _strip_diacritics(text or "")
        t = unicodedata.normalize("NFKC", t).lower()
        t = re.sub(
            r"[\u200c\u061f\u061b\u060c\u3002\uff01\uff1f\.,!?:;\-\(\)\[\]\{\}\|\/\\]",
            " ",
            t,
        )
        t = re.sub(r"\s+", " ", t).strip()

        stop_words = {"و", "در", "از", "به", "که", "این", "آن", "با", "برای", "است"}
        words = [w for w in t.split(" ") if w and w not in stop_words and len(w) > 2]
        return list(dict.fromkeys(words))

    def _get_doc_id(self, doc: VectorDocument) -> str:
        """دریافت شناسه یکتای سند"""
        return f"{doc.metadata.get('source', '')}_{doc.metadata.get('chunk_id', '')}"
