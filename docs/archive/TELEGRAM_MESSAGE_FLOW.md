# Archived Documentation

> [!NOTE]
> This document describes the previous Telegram-based architecture, experiments, or historical roadmap.
> The active production system uses the API-first architecture described in [README.md](../../README.md) and [docs/API.md](../API.md).

---

### RAG Telegram Assistant — End-to-End Message Flow (Telegram ➜ Answer)

این سند مسیر کامل دریافت پیام از تلگرام تا تولید پاسخ نهایی را توصیف می‌کند، همراه با اجزای درگیر، ورودی/خروجی هر گام، نقاط پیکربندی مهم، و حالت‌های گوناگون تقسیم‌بندی متن (Chunking). هدف این است که هر توسعه‌دهنده یا اپراتوری با خواندن این فایل، به‌روشنی بداند «چه گزینه‌هایی وجود دارد»، «هر گزینه دقیقاً چه می‌کند»، و «در هر شاخه از مسیر چه اتفاقی می‌افتد».

---

### 1) نقطه ورود و دریافت آپدیت‌ها

- Bot/Dispatcher

  - فایل: `ragbot/app/bot.py`
  - ایجاد `Bot` با `settings.bot_token` و راه‌اندازی `Dispatcher`
  - اضافه‌شدن میان‌افزارها: `AuthMiddleware`, `ContentFilterMiddleware` (بر اساس `settings.security.enable_content_filtering`)
  - ثبت `router` واحد که شامل همه‌ی هندلرها در `ragbot/app/routes/` است
  - اجرای polling: `dp.start_polling(bot)`

- Entry (Console):
  - فایل: `ragbot/main.py`
  - آماده‌سازی سرویس‌ها و مانیتورینگ، سپس اجرای `ragbot.app.bot.main()`

نمودار خطی ساده (جریان دریافت آپدیت):

Telegram ➜ aiogram(Bot, Dispatcher) ➜ Middlewares [Auth, ContentFilter] ➜ Router(handlers)

---

### 2) هندلرهای پیام و فرمان‌ها

#### میان‌افزارها (Middlewares)

- AuthMiddleware: بررسی مجوز کاربر قبل از ورود به هندلرها (وابسته به `settings.allow_users_list`).
- ContentFilterMiddleware: اگر `settings.security.enable_content_filtering` فعال باشد، متن‌ها قبل از پردازش برای محتوای نامناسب/ریسکی پالایش می‌شوند.

- مثال اصلی پرسش/پاسخ: `ragbot/app/routes/qa.py`

  - فرمان: `/ask <question>`
  - مراحل:
    - احراز مجوز کاربر: `is_user_authorized`
    - بررسی نرخ درخواست: `check_rate_limit`
    - نمایش پیام «در حال پردازش»
    - فراخوانی سرویس RAG: `rag_service.query_documents(question, lang)`
    - ثبت تحلیلات کاربری (Analytics) و ویرایش پیام پاسخ با نتیجه

- ابزارهای مشترک هندلرها: `ragbot/app/routes/utils.py`
  - ساخت و بازیابی سرویس‌ها: `get_integration_service`, `get_rag_service`, `get_document_service`
  - متدهای پاسخ ایمن: `safe_reply`, `safe_reply_with_kb`
  - کیبوردهای اینلاین نمونه (مانند Performance)

#### کال‌بک‌ها و کیبوردها

- `ragbot/app/routes/callbacks.py`
  - نمونه: `perf_refresh` برای تازه‌سازی خروجی صفحه Performance.
- ساخت کیبورد نمونه در `routes/utils.py` با `InlineKeyboardMarkup` و کلیدهای استاندارد Refresh/Back/Close.

نمودار درختی (جریان /ask):

`/ask` (Message)
├─ is_user_authorized? ❌ ➜ reply(Unauthorized) ⏹
├─ check_rate_limit? ❌ ➜ reply(Rate limit) ⏹
└─ extract question ➜ show «processing…»
└─ get_rag_service ➜ RAGService.query_documents
├─ (try) SemanticCache.get_similar_answer
│ └─ if hit: build response from cache ⏹
└─ else ➜ Retrieval ➜ Prompt/LLM ➜ Build Answer ➜ Cache-if-high-confidence

خروجی هندلر: یک متن HTML شامل «پاسخ»، «منابع»، «زمان پردازش»، و «Confidence» (در صورت موجود بودن).

---

### 3) سرویس یکپارچه و RAGService

- Integration bootstrap: `ragbot/services/integration_service.py` (ایجاد و اشتراک‌گذاری اجزای اصلی)
- سرویس اصلی: `ragbot/services/rag_service.py`
  - اجزا:
    - Loaders: `pdf`, `text`, `url`, (`docx` اختیاری)
    - Chunker: بر اساس `settings.advanced_chunking.chunking_strategy`
    - Embedder: مطابق `settings.embedding.provider`
    - Vector Store: معمولاً `FAISS` طبق `settings.store`/`settings.vector_db`
    - AdvancedRetriever (اختیاری): جستجوی پیشرفته، Re-ranking، Hybrid، Expansion
    - SemanticCache (اختیاری): پاسخ‌های مشابه معنایی
    - QAChain: ساخت پرامپت و تماس با مدل‌های زبانی

نمودار خطی (Query ↦ Answer):

Question ➜ AdvancedRetriever or BasicRetriever ➜ Context Chunks ➜ QAChain(PromptBuilder + LLM) ➜ Answer

جزئیات `query_documents`:

- ورودی: `question`, `lang`, `top_k?`, `similarity_threshold?`
- گام‌ها:
  1. Semantic Cache (اختیاری)
  2. Retrieval (Advanced یا Basic)
  3. محدودسازی کانتکست با بودجه توکن (در صورت تنظیم)
  4. تولید پاسخ با `QAChain.generate_answer`
  5. ساخت لیست منابع و استنادها
  6. کَش پاسخ در صورت بالا بودن اعتماد
- خروجی: `QueryResult` شامل `answer`, `sources`, `confidence_score`, `processing_time`, `metadata`

نگاشت اجزای `IntegrationService` (سطح بالا):

- `components["rag_service"]`: نمونه `RAGService`
- `components["loaders"]`: نقشه لودرها: pdf/text/url/(docx)
- `components["chunker"]`: `AdaptiveChunker` یا `TokenChunker`
- `components["embedder"]`: OpenAI/ST
- `components["vector_store"]`: FAISS
- `components["cache"]`: در صورت پیکربندی، کش معنایی/سایر کش‌ها

---

### 4) بازیابی (Retrieval)

- Advanced Retriever: `ragbot/rag/retrieve/advanced_retriever.py`

  - قابلیت‌ها: Hybrid Search، Re-ranking، Query Expansion، Thresholdها، Cache گسترش پرسش
  - تنظیمات از `settings.advanced_retrieval` (پیشوند محیطی: `ADVANCED_RETRIEVAL_`)

- Basic Retriever: `ragbot/rag/retrieve/retriever.py`
  - مراحل: Embed پرسش ➜ جستجو در Vector Store ➜ فیلتر آستانه شباهت ➜ بوست سلسله‌مراتبی والد/فرزند ➜ مرتب‌سازی

خروجی هر دو: لیستی از `VectorDocument` ها با `content`, `score`, `metadata` (منبع، صفحه/اسلاید، span و ...)

جزئیات پیشرفته (ماتریس تصمیم ساده):

- اگر `enable_hybrid` فعال: نمره ترکیبی واژه‌کلیدی+برداری با `hybrid_alpha`.
- اگر `enable_reranking` فعال: بازچینش نتایج اولیه با مدل رتبه‌بند و `reranker_threshold`.
- اگر `enable_expansion` فعال: گسترش پرسش با `expansion_type` و سقف `max_expanded_queries`.
- فیلتر اعتماد: اگر `confidence_threshold` تعیین شده باشد، نتایج کم‌اعتماد حذف/کاهش وزن می‌شوند.

---

### 5) استراتژی‌های تقسیم‌بندی (Chunking Strategies)

کلید پیکربندی: `ADV_CHUNK_CHUNKING_STRATEGY`

مقادیر پشتیبانی‌شده (طبق `ragbot/configs/settings.py`):

- `adaptive` (پیش‌فرض)
- `semantic`
- `hierarchical`
- `hybrid`
- `full`
- `token`

نکته ساختاری: در `RAGService` اگر مقدار یکی از {`adaptive`, `semantic`, `hierarchical`, `full`, `hybrid`} باشد، از `AdaptiveChunker` استفاده می‌شود. اگر `token` باشد (یا AdaptiveChunker در دسترس نباشد)، از `TokenChunker` استفاده می‌شود.

نمودار انتخاب چانکر:

strategy = ADV_CHUNK_CHUNKING_STRATEGY
├─ in {adaptive, semantic, hierarchical, full, hybrid} ➜ AdaptiveChunker
└─ else (token or fallback) ➜ TokenChunker

جزئیات AdaptiveChunker (`ragbot/rag/chunkers/adaptive_chunker.py`):

- اگر `chunking_strategy` به‌طور صریح یکی از {`full`, `hybrid`, `semantic`, `hierarchical`, `token`} باشد، همان اعمال می‌شود.
- در غیر این‌صورت تحلیل سبک روی متن انجام می‌شود و بر اساس طول متن، پیچیدگی ساختار، و انسجام معنایی، یکی از راهبردها انتخاب می‌شود.
- خروجی: لیست `TextChunk` با متادیتا (اندیس‌ها، نوع ساختار، توکن‌ها، …)

نمودار درختی رفتار AdaptiveChunker:

AdaptiveChunker.chunk(text)
├─ explicit = settings.advanced_chunking.chunking_strategy in {full, hybrid, semantic, hierarchical, token}?
│ ├─ بله ➜ strategy = explicit
│ └─ خیر ➜ analysis = analyze(text) ➜ strategy = select(analysis)
└─ dispatch(strategy)
├─ semantic ➜ SemanticChunker
├─ hierarchical ➜ HierarchicalChunker
├─ token ➜ TokenChunker
├─ hybrid ➜ ترکیبی (semantic+token یا hierarchical+token بر اساس تحلیل/threshold)
└─ full ➜ اجرای کامل مراحل (semantic ➜ refine by token ➜ optimize)

توضیح حالت‌ها:

- `token`: برش مبتنی بر تعداد توکن (استفاده از `tiktoken` در دسترس؛ در غیر این‌صورت تقریب مبتنی بر کلمه). پارامترهای مهم: `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, و `ADV_CHUNK_TOKEN_FALLBACK_DENSITY_FACTOR`.
- `hierarchical`: تشخیص سطوح ساختاری (عنوان/بخش/پاراگراف/جمله) و تولید چانک‌های هم‌سطح با متادیتای سلسله‌مراتب. پارامترها: `ADV_CHUNK_HIERARCHICAL_MIN/MAX_CHUNK_SIZE`, `HIERARCHICAL_MAX_LEVELS`.
- `semantic`: تقسیم بر اساس شباهت جملات با مدل جمله‌نگار. پارامترها: `ADV_CHUNK_SEMANTIC_MIN/MAX_CHUNK_SIZE`, `SEMANTIC_SIMILARITY_THRESHOLD`, `embedding.model`.
- `hybrid`: جفت‌کردن روش معنایی/سلسله‌مراتبی با ریزسازی توکنی در مرزهای حساس (Thresholdها: `ADV_CHUNK_HYBRID_REFINE_TOKEN_THRESHOLD`).
- `full`: اجرای زنجیره کامل (مثلاً Semantic ➜ Token refine ➜ Optimizer) برای کیفیت بیشتر؛ هزینه محاسباتی بالاتر. Threshold: `ADV_CHUNK_FULL_REFINE_TOKEN_THRESHOLD`.
- `adaptive`: انتخاب خودکار بین موارد بالا با توجه به متن ورودی و آستانه‌ها: `ADAPTIVE_TEXT_LENGTH_THRESHOLD`, `ADAPTIVE_STRUCTURE_COMPLEXITY_THRESHOLD`, `ADAPTIVE_SEMANTIC_COHERENCE_THRESHOLD`.

بهینه‌سازی بعد از چانک (Post-Chunk Optimization):

- اگر `ADV_CHUNK_ENABLE_CHUNK_OPTIMIZATION = true` فعال باشد، بهینه‌ساز چانک‌ها (مثلاً `ChunkOptimizer`) اندازه‌ها را به سمت `ADV_CHUNK_CHUNK_TARGET_SIZE` با تحمل `ADV_CHUNK_CHUNK_SIZE_TOLERANCE` همگرا می‌کند و چانک‌های خیلی کوتاه را با نسبت `ADV_CHUNK_MERGE_SHORT_CHUNK_RATIO` ادغام می‌کند.

ضمیمه‌کردن متادیتا تحلیل:

- اگر `ADV_CHUNK_ATTACH_ANALYSIS_METADATA = true` باشد، خروجی چانک‌ها شامل اطلاعات تحلیل و راهبرد انتخاب‌شده خواهد بود.

نکات عملی پیاده‌سازی چانکینگ:

- TokenChunker در نبود `tiktoken` از تقریب مبتنی بر کلمه استفاده می‌کند و با `ADV_CHUNK_TOKEN_FALLBACK_DENSITY_FACTOR` چگالی را تنظیم می‌کند.
- مرزهای جملات و نواحی محافظت‌شده (سرفصل‌ها/کد بلاک/جداول) هنگام برش حفظ می‌شوند تا برش‌های نامطلوب کاهش یابد.
- اگر ساختار سند (heading/paragraph) از لودرها برسد، مرزهای چانک با آن هم‌تراز می‌شوند.

نگاشت env برای AdvancedChunking (نمونه‌های کلیدی):

- `ADV_CHUNK_CHUNKING_STRATEGY`
- `ADV_CHUNK_SEMANTIC_MIN_CHUNK_SIZE`, `ADV_CHUNK_SEMANTIC_MAX_CHUNK_SIZE`, `ADV_CHUNK_SEMANTIC_SIMILARITY_THRESHOLD`
- `ADV_CHUNK_HIERARCHICAL_MIN_CHUNK_SIZE`, `ADV_CHUNK_HIERARCHICAL_MAX_CHUNK_SIZE`, `ADV_CHUNK_HIERARCHICAL_MAX_LEVELS`
- `ADV_CHUNK_ADAPTIVE_TEXT_LENGTH_THRESHOLD`, `ADV_CHUNK_ADAPTIVE_STRUCTURE_COMPLEXITY_THRESHOLD`, `ADV_CHUNK_ADAPTIVE_SEMANTIC_COHERENCE_THRESHOLD`
- `ADV_CHUNK_CHUNK_TARGET_SIZE`, `ADV_CHUNK_CHUNK_SIZE_TOLERANCE`, `ADV_CHUNK_ENABLE_CHUNK_OPTIMIZATION`, `ADV_CHUNK_MERGE_SHORT_CHUNK_RATIO`, `ADV_CHUNK_ATTACH_ANALYSIS_METADATA`
- `ADV_CHUNK_TOKEN_FALLBACK_DENSITY_FACTOR`, `ADV_CHUNK_HYBRID_REFINE_TOKEN_THRESHOLD`, `ADV_CHUNK_FULL_REFINE_TOKEN_THRESHOLD`

---

### 6) تعبیه (Embedding) و فروشگاه برداری (Vector Store)

- Embedder با توجه به `settings.embedding.provider`:
  - `openai`: `OpenAIEmbedder`
  - `sentence_transformers`/`huggingface`: `STEmbedder`
- Vector Store: پیش‌فرض `FAISS` با مسیر `settings.data_dir / "vector_store"`

---

### 7) زنجیره QA و LLM

- `ragbot/rag/qa/chain.py` و `QAChain`:
  - ساخت پرامپت با `PromptBuilder`
  - تماس با ارائه‌دهنده LLM (`settings.llm.provider`, `settings.llm.model`)
  - محدودسازی کانتکست با بودجه توکن در صورت نیاز
  - تولید پاسخ و متادیتای همراه

نمودار خطی (Answering):

Context Chunks ➜ PromptBuilder ➜ LLM Client ➜ Answer

جزئیات QAChain:

- `PromptBuilder`: ساخت دستورالعمل‌ها و جایگذاری کانتکست/پرسش.
- LLM Client: `settings.llm.provider` (openai/anthropic/…)، مدل و پارامترهایی مانند `temperature`, `max_tokens`.
- بودجه توکن کانتکست: اگر `RAG_MAX_CONTEXT_TOKENS` تنظیم شده باشد، متون زمینه بر اساس توکن محدود می‌شوند.

---

### 8) خطاها، لاگ‌ها، و سلامت سیستم

- لاگ‌ها: از طریق `ragbot/outputs/logger.py` در فایل‌های `logs/`
- هندل خطا در هندلرها: پیام دوزبانه خطا + ثبت در لاگ
- Health & Monitoring: دستورات `/health` و `/monitoring` در `ragbot/app/routes/monitoring.py`

Semantic Cache:

- اگر کش معنایی فعال باشد، ابتدا برای پاسخ‌های مشابه بررسی می‌شود؛ در صورت موفقیت، پاسخ سریع برگردانده می‌شود.
- اگر `confidence_score` پاسخ نهایی > 0.7 باشد، نتیجه برای استفاده‌های بعدی کش می‌شود.

---

### 9) متغیرهای محیطی مهم (نمونه)

- Token bot: `BOT_TOKEN`
- LLM provider/model: `LLM_PROVIDER`, `LLM_MODEL`
- Embedding provider/model: `EMBED_PROVIDER`, `EMBED_MODEL`
- Chunking:
  - `ADV_CHUNK_CHUNKING_STRATEGY` ∈ {adaptive, semantic, hierarchical, hybrid, full, token}
  - `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`
  - `ADV_CHUNK_*` آستانه‌ها و بهینه‌سازی‌ها (مطابق کلاس `AdvancedChunkingSettings`)

---

### 10) چک‌لیست سریع اشکال‌زدایی

- توکن ربات معتبر است؟ (`BOT_TOKEN`)
- سرویس‌ها در `IntegrationService` مقداردهی شده‌اند؟
- استراتژی چانکینگ مناسب محتوا انتخاب شده است؟
- شاخص FAISS وجود دارد و مسیر `data/vector_store/` قابل نوشتن است؟
- محدودیت نرخ/احراز هویت جلوی پردازش را نگرفته است؟
- خطاهای LLM/Embedding در لاگ‌ها مشخص‌اند؟

---

این سند بدون مراجعه به سایر فایل‌های مستندات، تصویر کامل از جریان پیام تا پاسخ را ارائه می‌دهد و برای عملیات و توسعه کافی است.

---

### 11) فلو اینجست اسناد (Ingestion)

مسیر سطح بالا:

Source (pdf/url/text/docx) ➜ Loader ➜ Chunker ➜ Embedder ➜ VectorStore

جزئیات در `RAGService.ingest_document`:

- تشخیص نوع منبع (url/pdf/docx/text)
- بارگذاری محتوا با لودر متناظر
- چانک‌کردن بر اساس استراتژی فعال
- تولید امبدینگ‌ها برای هر چانک
- ذخیره متن/امبدینگ/متادیتا در فروشگاه برداری

خروجی: `IngestResult` شامل شناسه سند، تعداد چانک‌ها، زمان پردازش، و متادیتا.

پشتیبانی فرمت‌ها و متادیتای ساختاری:

- لودرها (pdf/docx/url/text) در صورت امکان سرفصل‌ها، صفحات/اسلایدها و محدوده‌های متنی را در متادیتا قرار می‌دهند تا چانکینگ و ارجاع دقیق‌تر شود.

---

### 12) شرایط و سویچ‌ها (True/False) و حالت‌های اثرگذار

این بخش تمام سوییچ‌ها، حالت‌ها و شرط‌های مهم را لیست می‌کند و می‌گوید اگر فعال/غیرفعال باشند چه تغییری در مسیر رخ می‌دهد.

1. امنیت/فیلتر محتوا

- `SECURITY_ENABLE_CONTENT_FILTERING` (settings.security.enable_content_filtering)
  - True: `ContentFilterMiddleware` فعال؛ پیام‌ها قبل از ورود به هندلر پالایش می‌شوند.
  - False: بدون پالایش محتوا؛ پیام مستقیم به هندلر می‌رسد.

2. احراز مجوز کاربر

- `ALLOW_USERS_LIST` (settings.allow_users_list)
  - خالی یا None: همه مجاز.
  - لیست پر: فقط شناسه‌های داخل لیست مجاز؛ دیگران «Unauthorized» می‌گیرند.

3. OCR در استخراج متن (RAG)

- `RAG_OCR_ENABLED` و `RAG_OCR_ENGINE` ∈ {none, pytesseract, easyocr, google}
  - Enabled (engine≠none): تصاویر در PDF/اسناد تحلیل می‌شوند؛ متن OCR به متن مستند اضافه می‌شود.
  - Disabled (none): هیچ OCR انجام نمی‌شود؛ فقط متن قابل استخراج مستقیم.

4. بودجه توکن کانتکست

- `RAG_MAX_CONTEXT_TOKENS`
  - > 0: متن زمینه قبل از ارسال به LLM بر اساس بودجه توکن کوتاه/تقسیم می‌شود.
  - 0 یا unset: محدودیت اعمال نمی‌شود.

5. چانکینگ (ADV*CHUNK*\*)

- `ADV_CHUNK_CHUNKING_STRATEGY`
  - adaptive/semantic/hierarchical/hybrid/full: `AdaptiveChunker` فعال (با انتخاب مستقیم یا تحلیل).
  - token: `TokenChunker` مستقیم استفاده می‌شود.
- `ADV_CHUNK_ENABLE_CHUNK_OPTIMIZATION`
  - True: پس‌پردازش اندازه چانک‌ها به سمت `ADV_CHUNK_CHUNK_TARGET_SIZE` + ادغام کوتاه‌ها.
  - False: بدون بهینه‌سازی پس‌پردازش.
- `ADV_CHUNK_TOKEN_FALLBACK_DENSITY_FACTOR` (فقط وقتی tiktoken نیست)
  - تعیین نسبت تبدیل کلمه↦توکنِ تقریبی؛ عدد کمتر یعنی چانک‌های کوچک‌تر در fallback.
- `ADV_CHUNK_ATTACH_ANALYSIS_METADATA`
  - True: درج متادیتای «analysis/selected_strategy» در خروجی چانک‌ها.
  - False: بدون این متادیتا.

6. بازیابی پیشرفته (Advanced Retrieval)

- `ADVANCED_RETRIEVAL_ENABLE_HYBRID`
  - True: ترکیب واژه‌کلیدی+برداری با `hybrid_alpha`.
  - False: فقط برداری (یا مسیرهای دیگر فعال).
- `ADVANCED_RETRIEVAL_ENABLE_RERANKING`
  - True: بازچینش با مدل رتبه‌بند؛ نتایج ضعیف زیر `reranker_threshold` حذف/تنزیل.
  - False: بدون ریرنک.
- `ADVANCED_RETRIEVAL_ENABLE_EXPANSION`
  - True: گسترش پرسش (synonym/…)، تولید چند پرسش تا سقف `max_expanded_queries`.
  - False: بدون گسترش پرسش.

7. کش معنایی

- فعال (SemanticCache موجود)
  - ابتدا بررسی مشابهت معنایی؛ در صورت هیت، پاسخ سریع از کش و خاتمه مسیر.
  - پس از تولید پاسخ، اگر `confidence_score > 0.7`، نتیجه در کش ذخیره می‌شود.
- غیرفعال: مسیر همواره Retrieval ➜ QA.

8. LLM Provider

- `LLM_PROVIDER` و `LLM_MODEL`
  - OpenAI/…: انتخاب کلاینت و مدل؛ پارامترها (temperature, max_tokens) رفتار طول/تنوع پاسخ را مشخص می‌کنند.

9. Embed Provider

- `EMBED_PROVIDER`, `EMBED_MODEL`
  - openai: `OpenAIEmbedder`
  - sentence_transformers/huggingface: `STEmbedder` با مدل انتخابی و دستگاه (GPU/CPU) بر اساس تنظیمات.

10. Vector Store

- `STORE_PROVIDER` یا `VECTOR_DB`
  - faiss: ایجاد/استفاده از مسیر `data/vector_store`؛ پارامترهای FAISS مانند `faiss_nlist`, `faiss_nprobe` بر latency/دقت اثر دارند.

11. لودرها و نکات فرمت‌ها

- PDF:
  - در صورت وجود متادیتای صفحه/heading، محدوده‌ها به چانک‌ها الصاق می‌شوند؛ OCR طبق تنظیمات.
- DOCX:
  - توجه به پاراگراف‌ها، headingها، جدول‌ها؛ تلاش برای حفظ مرز پاراگراف/جدول در چانک‌ها.
- URL:
  - استخراج متن با حذف اسکریپت/استایل؛ تلاش برای تشخیص ساختار (سرتیتر/بخش‌ها) اگر قابل استخراج باشد.
- TEXT:
  - ورودی ساده؛ در صورت نبود ساختار، تکیه بر Token/Adaptive.

استانداردسازی متادیتای پایه (مطابق `loaders/base.py`):

- کلیدهای توصیه‌شده در `metadata` برای هم‌خوانی با چانکرها:
  - `source_type`: نوع منبع مثل 'pdf'، 'html'، 'docx'، 'text'
  - `page`: شماره صفحه (اگر وجود داشته باشد)
  - `span`: دیکشنری با `{'start': int, 'end': int}` برای محدوده متن
  - `language`: کد زبان متن (در صورت تشخیص)
  - `mime_type`: نوع MIME استاندارد

AdvancedDocumentLoader (مدیر بارگذاری چندفرمتی):

- فایل: `ragbot/rag/loaders/advanced_loaders.py`
- وظیفه: انتخاب لودر مناسب بر اساس مسیر/URL و تنظیمات امنیتی، ارائه لیست فرمت‌های پشتیبانی‌شده، و اعتبارسنجی فایل (وجود، اندازه، فرمت).
- فرمت‌های متداول: pdf, docx, txt, pptx, xlsx, html/htm, md و تصاویر برای OCR.

جزئیات تکمیلی لودرهای خاص:

- DOCXLoader:

  - استخراج پاراگراف‌ها و جدول‌ها (تا سقف `docx_tables_max`)، حفظ شماره‌گذاری در صورت فعال بودن `docx_preserve_numbering`.
  - استنتاج هدینگ‌ها از Style/OOXML/Delta فونت در صورت فعال بودن `docx_enable_structural_extraction`.
  - استخراج لینک‌ها و امکان تزریق لینک-inline در متن (تا سقف `docx_hyperlinks_max`) اگر `docx_extract_hyperlinks`/`inject_inline` فعال باشد.
  - تشخیص زبان رأی‌گیری و تخمین توکن؛ محافظت در برابر Zip Bomb (`docx_max_zip_entries`, `docx_max_uncompressed_mb`).

- PPTXLoader:

  - تشخیص عنوان اسلاید (H1) و هدینگ‌های بعدی با Delta فونت و سیگنال‌ها، لیست‌های بولت/شماره، جدول‌ها، نوت‌ها، لینک‌ها و متادیتای تصویر/چارت.
  - تشخیص زبان چند-قطعه‌ای و تخمین توکن؛ محافظت ZIP.

- HTMLLoader:

  - استخراج ساختاری سرتیترها و تزریق مارکر در صورت فعال بودن `html_enable_structural_extraction`/`html_inject_heading_markers`.
  - پیکربندی User-Agent (`html_user_agent_mode`، هدرهای سفارشی `html_custom_headers`، و `html_cookies`).
  - سقف لینک/تصویر قابل استخراج: `html_max_links`، `html_max_images`.

- URLLoader:

  - مشابه HTML با BS4؛ در صورت فعال بودن `multi_format.html_enable_structural_extraction`، سرتیترها و ساختار استخراج و در متادیتا درج می‌شود.

- XLSXLoader:
  - تبدیل شیت‌ها به متن خوانا با امکان درج نام شیت و هدر ستون‌ها؛ محدودیت سطر/شیت بر اساس تنظیمات چندفرمتی؛ تشخیص زبان و تخمین توکن؛ متادیتای کامل (sheet_count, total_rows, total_cells,...).

نکات امنیتی/کارایی مشترک:

- سقف اندازه فایل‌ها بر اساس `settings.security.max_file_size_mb` اعمال می‌شود (در اعتبارسنجی لودرها).
- تمامی لودرها در صورت امکان `approx_chars` و `estimated_tokens` را پر می‌کنند تا برای بودجه‌بندی و مانیتورینگ مفید باشد.
