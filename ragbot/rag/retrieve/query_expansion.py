"""
گسترش پرسش با مترادف و کلمات مرتبط - بهبود یافته
"""

import asyncio
import time
from typing import Dict, List, Optional

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.exceptions import DocumentProcessingError

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None


class QueryExpander:
    """گسترش پرسش با مترادف و کلمات مرتبط - بهبود یافته"""

    def __init__(
        self,
        synonym_model: Optional[str] = None,
        max_expanded_queries: Optional[int] = None,
        enable_ai_expansion: Optional[bool] = None,
        **kwargs,
    ):
        """
        Initialize query expander with settings integration

        Args:
            synonym_model: مدل تولید مترادف (از تنظیمات خوانده می‌شود)
            max_expanded_queries: حداکثر تعداد پرسش‌های گسترش یافته (از تنظیمات خوانده می‌شود)
            enable_ai_expansion: فعال‌سازی گسترش با AI (از تنظیمات خوانده می‌شود)
        """
        # خواندن تنظیمات از settings
        adv_settings = getattr(settings, "advanced_retrieval", object())

        self.synonym_model_name = synonym_model or getattr(
            adv_settings,
            "synonym_model",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        self.max_expanded_queries = max_expanded_queries or getattr(
            adv_settings, "max_expanded_queries", 3
        )
        self.enable_ai_expansion = (
            enable_ai_expansion
            if enable_ai_expansion is not None
            else getattr(adv_settings, "enable_ai_expansion", False)
        )

        # تنظیمات اضافی
        self.expansion_timeout = getattr(adv_settings, "expansion_timeout", 10.0)
        self.cache_size = getattr(adv_settings, "expansion_cache_size", 100)
        self.min_query_length = getattr(adv_settings, "min_query_length", 3)

        # Initialize AI model if available and enabled
        self.ai_model = None
        if self.enable_ai_expansion and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                cache_dir = getattr(
                    getattr(settings, "embedding", object()),
                    "cache_folder",
                    "./cache/sentence_transformers",
                )
                self.ai_model = SentenceTransformer(
                    self.synonym_model_name, cache_folder=cache_dir
                )
                logger.info(f"AI expansion model loaded: {self.synonym_model_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to load AI model: {e}, falling back to rule-based expansion"
                )
                self.ai_model = None
                self.enable_ai_expansion = False

        # Cache برای expanded queries
        self._expansion_cache: Dict[str, List[str]] = {}

        # دیکشنری‌های مترادف و کلمات مرتبط بهبود یافته
        self._synonym_dict = self._build_synonym_dict()
        self._related_dict = self._build_related_dict()

        logger.info(
            "Query expander initialized",
            synonym_model=self.synonym_model_name,
            max_expanded_queries=self.max_expanded_queries,
            enable_ai_expansion=self.enable_ai_expansion,
            ai_model_available=self.ai_model is not None,
        )

    async def expand_query(
        self, query: str, expansion_type: str = "synonym"
    ) -> List[str]:
        """
        گسترش پرسش با مترادف و کلمات مرتبط - بهبود یافته

        Args:
            query: پرسش اصلی
            expansion_type: نوع گسترش (synonym, related, context, hybrid)

        Returns:
            لیست پرسش‌های گسترش یافته

        Raises:
            DocumentProcessingError: اگر گسترش با خطا مواجه شود
        """
        if not isinstance(query, str) or not query.strip():
            return [query]

        # بررسی حداقل طول پرسش
        if len(query.strip()) < self.min_query_length:
            logger.debug(f"Query too short for expansion: {query}")
            return [query]

        start_time = time.time()
        cache_key = f"{query}_{expansion_type}"

        try:
            # بررسی cache
            if cache_key in self._expansion_cache:
                logger.debug(f"Using cached expansion for: {query}")
                return self._expansion_cache[cache_key]

            # Timeout برای expansion
            expanded_queries = await asyncio.wait_for(
                self._perform_expansion(query, expansion_type),
                timeout=self.expansion_timeout,
            )

            # ذخیره در cache
            if len(self._expansion_cache) >= self.cache_size:
                # حذف قدیمی‌ترین
                oldest_key = next(iter(self._expansion_cache))
                del self._expansion_cache[oldest_key]
            self._expansion_cache[cache_key] = expanded_queries

            # ثبت متریک
            duration = time.time() - start_time
            try:
                metrics_manager.record_query_processing(
                    "query_expansion",
                    "success",
                    retrieval_duration=duration,
                )
            except Exception:
                pass

            logger.debug(
                "Query expansion completed",
                original_query=query,
                expansion_type=expansion_type,
                expanded_count=len(expanded_queries),
                duration=duration,
            )

            return expanded_queries

        except asyncio.TimeoutError:
            logger.warning(
                f"Query expansion timeout after {self.expansion_timeout}s for: {query}"
            )
            try:
                metrics_manager.record_error("query_expansion", "timeout")
            except Exception:
                pass
            return [query]

        except Exception as e:
            logger.error(f"Query expansion failed: {e} for query: {query}")
            try:
                metrics_manager.record_error("query_expansion", "error")
            except Exception:
                pass
            raise DocumentProcessingError(
                f"Failed to expand query: {str(e)}",
                document_type="query_expansion",
                source=query,
            ) from e

    async def _perform_expansion(self, query: str, expansion_type: str) -> List[str]:
        """انجام گسترش پرسش بر اساس نوع"""
        if expansion_type == "synonym":
            return await self._expand_with_synonyms(query)
        elif expansion_type == "related":
            return await self._expand_with_related_terms(query)
        elif expansion_type == "context":
            return await self._expand_with_context(query)
        elif expansion_type == "hybrid":
            return await self._expand_with_hybrid(query)
        else:
            logger.warning(f"Unknown expansion type: {expansion_type}")
            return [query]

    async def _expand_with_synonyms(self, query: str) -> List[str]:
        """گسترش با مترادف - بهبود یافته"""
        try:
            # تولید مترادف با AI اگر فعال باشد
            if self.enable_ai_expansion and self.ai_model:
                synonyms = await self._generate_synonyms_ai(query)
            else:
                synonyms = self._generate_synonyms_rule_based(query)

            # ترکیب پرسش اصلی با مترادف (بدون تکرار)
            expanded_queries = [query]
            for synonym in synonyms:
                if synonym != query and synonym not in expanded_queries:
                    expanded_queries.append(synonym)

            return expanded_queries[: self.max_expanded_queries + 1]

        except Exception as e:
            logger.warning(f"Synonym expansion failed: {e}, using fallback")
            return [query]

    async def _expand_with_related_terms(self, query: str) -> List[str]:
        """گسترش با کلمات مرتبط - بهبود یافته"""
        try:
            # استخراج کلمات کلیدی بهبود یافته
            keywords = self._extract_keywords_enhanced(query)

            if not keywords:
                return [query]

            # تولید کلمات مرتبط
            related_terms = []
            for keyword in keywords:
                related = self._generate_related_terms(keyword)
                related_terms.extend(related)

            # حذف تکراری و محدود کردن
            related_terms = list(dict.fromkeys(related_terms))[
                : self.max_expanded_queries
            ]

            # ایجاد پرسش‌های جدید با جایگزینی هوشمند
            expanded_queries = [query]
            for term in related_terms:
                # جایگزینی همه کلمات کلیدی، نه فقط اولی
                expanded_query = query
                for keyword in keywords:
                    if keyword in expanded_query:
                        expanded_query = expanded_query.replace(keyword, term, 1)
                        break

                if expanded_query != query and expanded_query not in expanded_queries:
                    expanded_queries.append(expanded_query)

            return expanded_queries[: self.max_expanded_queries + 1]

        except Exception as e:
            logger.warning(f"Related terms expansion failed: {e}, using fallback")
            return [query]

    async def _expand_with_context(self, query: str) -> List[str]:
        """گسترش با زمینه - بهبود یافته"""
        try:
            # تشخیص نوع پرسش بهبود یافته
            question_type = self._detect_question_type_enhanced(query)

            # تولید پرسش‌های زمینه‌ای بر اساس نوع
            context_queries = []

            if question_type == "what":
                context_queries.extend(
                    [f"تعریف {query}", f"معنی {query}", f"مفهوم {query}"]
                )
            elif question_type == "how":
                context_queries.extend(
                    [f"روش {query}", f"نحوه {query}", f"راه‌حل {query}"]
                )
            elif question_type == "why":
                context_queries.extend(
                    [f"دلیل {query}", f"علت {query}", f"چرا {query}"]
                )
            elif question_type == "where":
                context_queries.extend(
                    [f"مکان {query}", f"موقعیت {query}", f"کجا {query}"]
                )
            elif question_type == "when":
                context_queries.extend(
                    [f"زمان {query}", f"چه وقت {query}", f"کی {query}"]
                )
            else:
                # برای پرسش‌های عمومی، اضافه کردن کلمات پرسشی
                context_queries.extend(
                    [f"چیست {query}", f"چطور {query}", f"چرا {query}"]
                )

            # حذف تکراری و محدود کردن
            context_queries = list(dict.fromkeys(context_queries))[
                : self.max_expanded_queries
            ]

            return [query] + context_queries

        except Exception as e:
            logger.warning(f"Context expansion failed: {e}, using fallback")
            return [query]

    async def _expand_with_hybrid(self, query: str) -> List[str]:
        """گسترش ترکیبی - ترکیب همه روش‌ها"""
        try:
            # ترکیب همه روش‌های گسترش
            synonym_queries = await self._expand_with_synonyms(query)
            related_queries = await self._expand_with_related_terms(query)
            context_queries = await self._expand_with_context(query)

            # ادغام و حذف تکراری
            all_queries = synonym_queries + related_queries + context_queries
            unique_queries = list(dict.fromkeys(all_queries))

            # محدود کردن تعداد
            return unique_queries[: self.max_expanded_queries + 1]

        except Exception as e:
            logger.warning(f"Hybrid expansion failed: {e}, using fallback")
            return [query]

    async def _generate_synonyms_ai(self, query: str) -> List[str]:
        """تولید مترادف با AI model"""
        try:
            # استفاده از SentenceTransformer برای تولید مترادف
            # این یک پیاده‌سازی ساده است - می‌تواند بهبود یابد
            import numpy as np

            # تولید embedding برای query
            query_embedding = self.ai_model.encode([query])

            # تولید چندین variation از query
            variations = [
                query.replace("چیست", "چیه"),
                query.replace("چطور", "چگونه"),
                query.replace("چرا", "دلیل"),
                query.replace("کجا", "کجاست"),
                query.replace("کی", "چه وقت"),
            ]

            # حذف variations تکراری
            variations = [v for v in variations if v != query]

            if not variations:
                return []

            # محاسبه شباهت
            variation_embeddings = self.ai_model.encode(variations)
            similarities = np.dot(query_embedding, variation_embeddings.T)[0]

            # انتخاب بهترین variations
            best_indices = np.argsort(similarities)[::-1][: self.max_expanded_queries]
            synonyms = [variations[i] for i in best_indices if similarities[i] > 0.7]

            return synonyms

        except Exception as e:
            logger.warning(
                f"AI synonym generation failed: {e}, falling back to rule-based"
            )
            return self._generate_synonyms_rule_based(query)

    def _generate_synonyms_rule_based(self, query: str) -> List[str]:
        """تولید مترادف با قوانین از پیش تعریف شده"""
        synonyms = []
        for word, syns in self._synonym_dict.items():
            if word in query:
                for syn in syns:
                    synonym_query = query.replace(word, syn)
                    if synonym_query != query:
                        synonyms.append(synonym_query)

        return synonyms[: self.max_expanded_queries]

    def _generate_related_terms(self, keyword: str) -> List[str]:
        """تولید کلمات مرتبط بهبود یافته"""
        return self._related_dict.get(keyword, [])

    def _extract_keywords_enhanced(self, query: str) -> List[str]:
        """استخراج کلمات کلیدی بهبود یافته"""
        # کلمات توقف گسترش یافته
        stop_words = {
            "چیست",
            "چطور",
            "چرا",
            "کجا",
            "کی",
            "چی",
            "کدوم",
            "چگونه",
            "نحوه",
            "دلیل",
            "علت",
            "کجاست",
            "چه",
            "وقت",
            "زمان",
            "مقدار",
            "و",
            "در",
            "از",
            "به",
            "که",
            "این",
            "آن",
            "با",
            "برای",
            "است",
            "بود",
            "باشد",
            "می",
            "خواهد",
            "کرد",
            "کرده",
            "کنم",
            "کنی",
            "کند",
            "کنیم",
            "کنید",
            "کنند",
        }

        # تقسیم به کلمات و حذف کلمات توقف
        words = query.split()
        keywords = [
            word.strip()
            for word in words
            if word.strip() not in stop_words and len(word.strip()) > 1
        ]

        return keywords

    def _detect_question_type_enhanced(self, query: str) -> str:
        """تشخیص نوع پرسش بهبود یافته"""
        query_lower = query.lower()

        if any(
            word in query_lower
            for word in ["چیست", "چیه", "چی", "تعریف", "معنی", "مفهوم"]
        ):
            return "what"
        elif any(
            word in query_lower for word in ["چطور", "چگونه", "نحوه", "روش", "راه‌حل"]
        ):
            return "how"
        elif any(word in query_lower for word in ["چرا", "دلیل", "علت"]):
            return "why"
        elif any(word in query_lower for word in ["کجا", "کجاست", "مکان", "موقعیت"]):
            return "where"
        elif any(word in query_lower for word in ["کی", "چه وقت", "زمان"]):
            return "when"
        elif any(word in query_lower for word in ["چقدر", "مقدار", "تعداد", "چند"]):
            return "how_much"
        elif any(word in query_lower for word in ["کدام", "کدوم", "کیه"]):
            return "which"
        else:
            return "general"

    def _build_synonym_dict(self) -> Dict[str, List[str]]:
        """ساخت دیکشنری مترادف بهبود یافته"""
        return {
            "چیست": ["چیه", "چی", "کدوم", "تعریف", "معنی"],
            "چطور": ["چگونه", "نحوه", "روش", "راه‌حل"],
            "چرا": ["دلیل", "علت", "چرا"],
            "کجا": ["کجاست", "کدام", "کدوم", "مکان", "موقعیت"],
            "کی": ["چه وقت", "زمان", "مقدار", "چه زمانی"],
            "چقدر": ["مقدار", "تعداد", "چند", "چه مقدار"],
            "کدام": ["کدوم", "کیه", "کدامیک"],
            "یادگیری": ["آموزش", "تحصیل", "مطالعه", "فراگیری"],
            "برنامه": ["کد", "نرم‌افزار", "اپلیکیشن", "پروژه"],
            "داده": ["اطلاعات", "معلومات", "دیتا", "اطلاع"],
            "سیستم": ["سامانه", "پلتفرم", "نظام", "ساختار"],
            "مشکل": ["مسئله", "خطا", "ایراد", "اشکال"],
            "راه‌حل": ["حل", "جواب", "پاسخ", "راهکار"],
            "تکنولوژی": ["فناوری", "تکنیک", "روش", "ابزار"],
            "کامپیوتر": ["رایانه", "سیستم", "ماشین", "دستگاه"],
        }

    def _build_related_dict(self) -> Dict[str, List[str]]:
        """ساخت دیکشنری کلمات مرتبط بهبود یافته"""
        return {
            "یادگیری": ["آموزش", "تحصیل", "مطالعه", "فراگیری", "یاددهی"],
            "برنامه": ["کد", "نرم‌افزار", "اپلیکیشن", "پروژه", "توسعه"],
            "داده": ["اطلاعات", "معلومات", "دیتا", "اطلاع", "آمار"],
            "سیستم": ["سامانه", "پلتفرم", "نظام", "ساختار", "معماری"],
            "مشکل": ["مسئله", "خطا", "ایراد", "اشکال", "باز"],
            "راه‌حل": ["حل", "جواب", "پاسخ", "راهکار", "راه‌اندازی"],
            "تکنولوژی": ["فناوری", "تکنیک", "روش", "ابزار", "تجهیزات"],
            "کامپیوتر": ["رایانه", "سیستم", "ماشین", "دستگاه", "سخت‌افزار"],
            "اینترنت": ["وب", "شبکه", "آنلاین", "دیجیتال", "مجازی"],
            "امنیت": ["حفاظت", "محافظت", "ایمنی", "کنترل", "دسترسی"],
            "پایگاه": ["دیتابیس", "ذخیره", "انبار", "نگهداری", "ذخیره‌سازی"],
            "کاربر": ["مستخدم", "استفاده‌کننده", "کاربری", "شخص", "فرد"],
            "مدیریت": ["کنترل", "نظارت", "هدایت", "رهبری", "سازماندهی"],
            "عملکرد": ["کارایی", "بازدهی", "نتیجه", "خروجی", "تولید"],
            "کیفیت": ["مرغوبیت", "مطلوبیت", "بهبود", "بهینه", "عالی"],
        }

    def get_expander_info(self) -> Dict[str, any]:
        """دریافت اطلاعات تنظیمات expander"""
        return {
            "synonym_model": self.synonym_model_name,
            "max_expanded_queries": self.max_expanded_queries,
            "enable_ai_expansion": self.enable_ai_expansion,
            "ai_model_available": self.ai_model is not None,
            "expansion_timeout": self.expansion_timeout,
            "cache_size": len(self._expansion_cache),
            "cache_max_size": self.cache_size,
            "min_query_length": self.min_query_length,
            "synonym_dict_size": len(self._synonym_dict),
            "related_dict_size": len(self._related_dict),
        }

    async def health_check(self) -> Dict[str, any]:
        """بررسی سلامت expander"""
        try:
            # تست expansion ساده
            test_query = "چیست یادگیری ماشین"
            test_result = await self.expand_query(test_query, "synonym")

            return {
                "status": "healthy",
                "expander_type": "QueryExpander",
                "ai_model_status": "available" if self.ai_model else "disabled",
                "test_successful": len(test_result) > 0,
                "test_results": len(test_result),
                "cache_size": len(self._expansion_cache),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "expander_type": "QueryExpander",
                "error": str(e),
                "test_successful": False,
            }
