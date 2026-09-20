# 🏗️ معماری سیستم RAGBot

سیستم RAGBot یک پلتفرم بک‌اند مدرن و مبتنی بر **FastAPI** برای تولید پاسخ با بازیابی اطلاعات (RAG) است که برای عملکرد بالا، مقیاس‌پذیری و دقت در بازیابی اسناد طراحی شده است.

---

## 🔄 نمای کلی جریان داده‌ها

```mermaid
flowchart TD
    Client["کلاینت (وب، موبایل، سرویس خارجی)"]

    subgraph APILayer ["۱. لایه ارتباطی و API (FastAPI)"]
        RL["میان‌افزار Rate Limiting"]
        CORS["میان‌افزار CORS"]
        Router["مسیریاب اصلی (/api/v1)"]
        HealthRoute["مسیرهای سلامت (/health)"]
        QueryRoute["مسیر پرسش (/api/v1/query)"]
        DocRoute["مسیرهای اسناد (/api/v1/documents/*)"]
    end

    subgraph ServiceLayer ["۲. لایه سرویس‌ها و هماهنگی"]
        Lifespan["مدیریت چرخه حیات Lifespan"]
        IntService["IntegrationService"]
        RAGService["RAGService"]
    end

    subgraph CacheLayer ["۳. سیستم کش چند لایه"]
        CacheMgr["مدیر کش CacheManager"]
        SemCache["کش معنایی SemanticCache"]
        MemCache["کش حافظه L1"]
        RedisCache["کش توزیع‌شده Redis L2 (اختیاری)"]
    end

    subgraph RAGCore ["۴. موتور اصلی RAG"]
        Loaders["لودرها (PDF, Word, TXT, HTML, MD, OCR)"]
        Chunkers["چانکرها (توکنی، معنایی، تطبیقی)"]
        Embedder["مدل‌های امبدینگ (SentenceTransformers, OpenAI)"]
        VectorStore["پایگاه برداری (FAISS با async_lock، Chroma، Qdrant)"]
        QAChain["زنجیره تولید پاسخ QAChain"]
    end

    subgraph ModelProviders ["۵. ارائه‌دهندگان مدل‌های زبانی"]
        OpenAI["OpenAI API"]
        Anthropic["Anthropic Claude API"]
        OpenRouter["OpenRouter API"]
        Ollama["مدل‌های محلی Ollama"]
        HFLocal["مدل‌های محلی HuggingFace"]
    end

    Client --> RL --> CORS --> Router
    Router --> HealthRoute
    Router --> QueryRoute
    Router --> DocRoute

    HealthRoute --> IntService
    DocRoute --> RAGService
    QueryRoute --> RAGService

    Lifespan --> IntService
    IntService --> RAGService
    IntService --> CacheMgr

    RAGService --> Loaders --> Chunkers --> Embedder --> VectorStore
    RAGService --> SemCache
    RAGService --> VectorStore
    RAGService --> QAChain

    QAChain --> ModelProviders
    Embedder --> ModelProviders
    CacheMgr --> SemCache
    CacheMgr --> MemCache
    CacheMgr --> RedisCache
```

---

## 🏛️ تشریح لایه‌های معماری

### ۱. لایه انتقال و ارتباطی (`ragbot/api/`)
- **فریم‌ورک FastAPI**: فریم‌ورک ناهمگام (async) برای ارائه مسیرهای RESTful به همراه اعتبارسنجی خودکار Pydantic و مستندات تعاملی Swagger.
- **چرخه حیات (Lifespan Context)**: بارگذاری اولیه و یکباره سرویس‌های سنگین (`IntegrationService`، مدل‌های امبدینگ و پایگاه داده برداری) در زمان استارت سرور، اتصال آن‌ها به `app.state` و آزادسازی منابع هنگام خاموش شدن.
- **میان‌افزار محدودسازی درخواست (`RateLimitMiddleware`)**: شمارنده لغزان بر پایه زمان به ازای هر IP برای جلوگیری از حملات منع سرویس (DoS).

### ۲. لایه سرویس‌ها (`ragbot/services/`)
- **`IntegrationService`**: هماهنگ‌کننده کلان اجزا، بررسی سلامت سیستم (`health_check`)، ردیابی رفتارهای کاربران و تخریب تدریجی مطمئن (Graceful Degradation).
- **`RAGService`**: هدایت‌کننده خطوط پردازش اسناد (بارگذاری، استخراج متن، امبدینگ، ذخیره‌سازی) و اجرای جستجوی معنایی و تجمیع پاسخ‌ها. همچنین این سرویس بازنشانی اتمیک مخزن برداری و کش‌ها را مدیریت می‌کند.

### ۳. لایه کش معنایی و عمومی (`ragbot/caching/`)
- **`SemanticCache`**: بررسی شباهت کسینوسی امبدینگ سوال با پرسش‌های قبلی. اگر شباهت از آستانه معین بیشتر باشد، پاسخ بلافاصله از کش بازگردانده شده و نیازی به فراخوانی مجدد LLM نیست.
- **`CacheManager`**: مدیریت کش دوسطحی در حافظه و Redis برای ذخیره امبدینگ‌ها و متادیتا.

### ۴. موتور هسته RAG (`ragbot/rag/`)
- **بارگذارها (Loaders)**: استخراج بهینه متن از انواع قالب‌ها (PDF از طریق PyMuPDF، صفحات وب HTML با حفظ ساختار تیترها، فایل‌های Word، اکسل و OCR).
- **خردسازها (Chunkers)**: تقسیم هوشمند متن با متدهای توکنی، معنایی و تطبیقی همراه با حفظ متادیتای صفحات.
- **پایگاه‌های برداری (Vector Stores)**:
  - `FAISSVectorStore`: ذخیره و جستجوی پرسرعت بردارها، مجهز به قفل ناهمگام `async_lock` جهت جلوگیری از تداخل عملیات نوشتن و خطای اشتراک فایل در ویندوز.
  - پشتیبانی از Chroma، Qdrant و Weaviate.
- **زنجیره پاسخ‌دهی (`QAChain`)**: ساخت پرامپت با قالب‌های استاندارد دوزبانه و فراخوانی API مدل‌های زبانی (OpenAI, Anthropic Claude, OpenRouter, Ollama).
