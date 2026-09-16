# دستیار تلگرامی RAG

ربات تلگرامی پیشرفته برای بازیابی و تولید (RAG) روی PDF، DOCX، لینک‌ها و متن. پشتیبانی کامل از فارسی و انگلیسی. پشتیبانی از حالت‌های آفلاین (مدل‌های محلی) و آنلاین (OpenRouter/OpenAI/Anthropic/Ollama). اکنون با پایگاه‌های داده برداری متعدد (FAISS، Chroma، Qdrant، Weaviate)، قابلیت‌های پرسش پیشرفته، رمزنگاری، پلاگین‌ها، تحلیل‌ها و پشتیبانی چند کاربره.

## شروع سریع

1. نصب وابستگی‌ها:

   python -m venv .venv

   # ویندوز: .\.venv\Scripts\Activate.ps1

   # لینوکس/مک: source .venv/bin/activate

   pip install -U pip
   pip install -r requirements.txt

2. فایل `env.example` را به `.env` (یا `.env_deepseek`) کپی و مقادیر را تنظیم کنید. برای حالت رایگان:

   LLM_PROVIDER=openrouter
   LLM_MODEL=x-ai/grok-4-fast:free
   OPENROUTER_API_KEY=your_key_here
   EMBED_PROVIDER=sentence_transformers
   EMBED_MODEL=intfloat/e5-small-v2

3. اجرا:

   python main.py

دستورات تلگرام:

- `/start` - شروع و خوش‌آمدگویی
- `/add` - افزودن سند (PDF، DOCX، URL یا متن)
- `/ask <سؤال>` - پرسیدن سوال از اسناد
- `/aggregate <پرسش>` - پرسش‌های تجمیعی پیشرفته
- `/filter <پرسش>` - عملیات فیلترینگ پیشرفته
- `/optimize <پرسش>` - پیشنهادات بهینه‌سازی پرسش
- `/score <پرسش>` - الگوریتم‌های امتیازدهی سفارشی
- `/reset` - پاک کردن تمام اسناد
- `/status` - نمایش وضعیت سیستم
- `/help` - نمایش راهنما
- `/config` - نمایش تنظیمات فعلی

## Docker

    docker compose up --build -d

دایرکتوری‌های `./data`، `./logs` و کش `~/.cache/huggingface` برای مدل‌های آفلاین mount می‌شوند. کش مدل‌های امبدینگ محلی در `./cache/sentence_transformers` ذخیره می‌شود.

## حالت‌های پیکربندی

### LLM Providers

- **OpenRouter** (رایگان): `LLM_PROVIDER=openrouter` با `LLM_MODEL=x-ai/grok-4-fast:free`
- **OpenAI**: `LLM_PROVIDER=openai` با `LLM_MODEL=gpt-3.5-turbo`
- **Anthropic**: `LLM_PROVIDER=anthropic` با `LLM_MODEL=claude-3-haiku`
- **Ollama** (محلی): `LLM_PROVIDER=ollama` با `LLM_MODEL=llama2`
- **HuggingFace** (محلی): `LLM_PROVIDER=hf_local` با `LLM_HF_MODEL=aidal/Persian-Mistral-7B`

### Embedding Providers

- **Sentence Transformers** (آفلاین): `EMBED_PROVIDER=sentence_transformers`
- **OpenAI** (آنلاین): `EMBED_PROVIDER=openai`
- **HuggingFace** (آفلاین): `EMBED_PROVIDER=huggingface`

کش امبدینگ از طریق CacheManager (حافظه + Redis اختیاری) فعال است و قبل از محاسبه بررسی می‌شود. همچنین کش معنایی پاسخ‌ها نیز در صورت کافی بودن اعتماد (confidence) قابل‌فعال‌سازی است.

### نصب افزونه آفلاین

برای اجرای حالت آفلاین کامل:

    pip install -e ".[offline]"
    # نصب torch مناسب سیستم (CPU/GPU)
    # مثال CPU: pip install torch --index-url https://download.pytorch.org/whl/cpu

سپس متغیرها را تنظیم کنید:

    LLM_PROVIDER=hf_local
    LLM_HF_MODEL=aidal/Persian-Mistral-7B
    LLM_HF_DEVICE=auto  # یا cuda
    EMBED_PROVIDER=sentence_transformers
    EMBED_MODEL=intfloat/e5-small-v2

---

## ویژگی‌ها

### 📄 پردازش اسناد

- **فرمت‌های پشتیبانی شده**: PDF، DOCX، TXT، URL
- **OCR**: پشتیبانی از `pytesseract`، `easyocr`، `google` برای PDFهای تصویری
- **پاک‌سازی محتوا**: استخراج متن خالص از اسناد پیچیده
- **محدودیت امنیتی**: حداکثر 25MB برای فایل‌ها
- **HTML Loader (async)**: IO غیرمسدودکننده فایل/وب با timeout/retry؛ استخراج ساختاری تیترها (h1–h6) با مارکرگذاری اختیاری؛ متادیتای غنی (title, description, canonical, OpenGraph/Twitter, language, mime)؛ لینک‌ها/تصاویر با URL مطلق و محدودیت‌های قابل تنظیم؛ پاک‌سازی و نرمال‌سازی متن. پیکربندی از طریق `MULTI_FORMAT_HTML_*` در env.

### 🔍 سیستم RAG

- **برش متن**: توکنی، معنایی، سلسله‌مراتبی، تطبیقی + بهینه‌ساز
- **امبدینگ**: OpenAI، Sentence Transformers، HuggingFace با کش
- **ذخیره‌سازی برداری**: FAISS، Chroma، Qdrant، Weaviate با ماندگاری
- **بازیابی**: جست‌وجوی هیبرید، ریرنکینگ، گسترش پرسش
- **پرسش‌های پیشرفته**: تجمیع، فیلترینگ، امتیازدهی سفارشی، بهینه‌سازی
- **تولید پاسخ**: پشتیبانی از 5 پروایدر LLM

### 🌐 چندزبانه و UI

- **زبان‌ها**: فارسی و انگلیسی با تشخیص خودکار
- **رابط کاربری**: پیام‌های دوستانه و راهنماهای کامل
- **دستورات**: 8 دستور اصلی + دستورات مدیریتی

### 🔧 مدیریت و مانیتورینگ

- **کش**: دو سطحی (Memory + Redis)
- **مانیتورینگ**: Prometheus، Grafana، Health checks
- **لاگ‌گیری**: ساخت‌یافته با Loguru
- **محدودیت نرخ**: قابل تنظیم برای جلوگیری از سوءاستفاده
- **امنیت**: رمزنگاری، مدیریت کلید، بکاپ امن
- **تحلیل‌ها**: تحلیل رفتار کاربر، بینش‌های ML
- **پلاگین‌ها**: بارگذاری پویا، تعویض گرم، بازار

## CLI

### دستورات اصلی

```bash
# وضعیت سیستم
python -m ragbot.cli status

# پاک کردن تمام اسناد
python -m ragbot.cli reset

# پرسیدن سوال
python -m ragbot.cli query --question "RAG چیست؟" --lang fa
python -m ragbot.cli query --question "What is RAG?" --lang en --top-k 5
```

### اینجست اسناد

```bash
# اینجست تک‌موردی
python -m ragbot.cli ingest --file ./docs/file.pdf
python -m ragbot.cli ingest --url https://example.com
python -m ragbot.cli ingest --text "یک متن نمونه"

# اینجست گروهی (پیش‌فرض فقط PDF)
python -m ragbot.cli batch-ingest --dir ./knowledge

# شامل TXT و DOCX
python -m ragbot.cli batch-ingest --dir ./knowledge --include-txt --include-docx

# الگوهای دلخواه
python -m ragbot.cli batch-ingest --dir ./knowledge --pattern "*.pdf" --pattern "*.docx"
```

## معماری

```
ragbot/
├── app/                     # روت‌های aiogram و میان‌افزارها
├── configs/                 # تنظیمات پایدانتیک و اعتبارسنجی
├── outputs/                 # لاگ و متریک
├── rag/
│   ├── loaders/             # بارگذارهای pdf/url/text
│   ├── chunkers/            # token/semantic/hierarchical/adaptive + optimizer
│   ├── embeddings/          # openai + sentence-transformers + huggingface
│   ├── store/               # FAISS، Chroma، Qdrant، Weaviate stores
│   ├── query/               # پرسش‌های پیشرفته، تجمیع، فیلترینگ، امتیازدهی
│   ├── retrieve/            # hybrid + reranker + expansion
│   └── qa/                  # پرامپت + LLM
├── services/                # ارکستراتور RAG
├── security/                # رمزنگاری، مدیریت کلید، بکاپ امن
├── plugins/                 # سیستم پلاگین، بازار
├── analytics/               # رفتار کاربر، بینش‌های ML، تحلیل پیش‌بینانه
├── multi_tenant/            # مدیریت tenant، جداسازی، سهمیه‌ها
└── tests/                   # تست‌ها
```

## نیازمندی‌ها

- **Python**: 3.10+ (تست شده روی 3.11/3.12)
- **توکن ربات تلگرام**: از [@BotFather](https://t.me/botfather) دریافت کنید
- **کلید API**: OpenRouter/OpenAI/Anthropic (برای حالت آنلاین)
- **GPU**: اختیاری، برای مدل‌های 7B+ آفلاین توصیه می‌شود

## پیکربندی کلیدی

### تنظیمات LLM

```bash
LLM_PROVIDER=openrouter          # openai|anthropic|ollama|hf_local|openrouter
LLM_MODEL=x-ai/grok-4-fast:free  # مدل مورد نظر
LLM_TEMPERATURE=0.3              # خلاقیت پاسخ (0.0-2.0)
LLM_MAX_TOKENS=2000              # حداکثر توکن پاسخ
```

### تنظیمات Embedding

```bash
EMBED_PROVIDER=sentence_transformers  # openai|sentence_transformers|huggingface
EMBED_MODEL=intfloat/e5-small-v2     # مدل embedding
EMBED_BATCH_SIZE=100                  # اندازه batch
```

### تنظیمات RAG

```bash
RAG_CHUNK_SIZE=400                    # اندازه chunk (توکن)
RAG_CHUNK_OVERLAP=50                 # هم‌پوشانی chunks
RAG_TOP_K=5                          # تعداد chunks بازیابی
RAG_SIMILARITY_THRESHOLD=0.6         # آستانه شباهت (0.0-1.0)
RAG_MAX_CONTEXT_TOKENS=4000          # (اختیاری) سقف توکن کانتکست ارسالی به LLM
```

### تنظیمات امنیتی

```bash
SECURITY_MAX_FILE_SIZE_MB=25         # حداکثر حجم فایل
SECURITY_RATE_LIMIT_REQUESTS=20      # محدودیت درخواست
SECURITY_RATE_LIMIT_WINDOW=60        # پنجره زمانی (ثانیه)
```

## توسعه

```bash
pytest -q          # اجرای تست‌ها
ruff check .       # لینت
mypy ragbot        # تایپ‌چک
```

## رفع اشکال

### مشکلات عملکرد

- **کندی در حالت آفلاین**: از GPU استفاده کنید (`LLM_HF_DEVICE=cuda`) یا مدل کوچک‌تر
- **مصرف حافظه بالا**: `RAG_CHUNK_SIZE` را کاهش دهید یا `RAG_MAX_CHUNKS_PER_DOCUMENT` را محدود کنید

### مشکلات فنی

- **خطای ابعاد FAISS**: فروشگاه در حالت خالی خودکار سازگار می‌شود
- **خطای OpenRouter**: `OPENROUTER_API_KEY` و `LLM_BASE_URL` را بررسی کنید
- **خطای OCR**: موتور OCR را تغییر دهید (`/setocr pytesseract|easyocr|google|none`)

### حالت آفلاین کامل

```bash
# پس از دانلود مدل‌ها
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

### لاگ‌ها و دیباگ

- لاگ‌ها در `./logs/ragbot.log` ذخیره می‌شوند
- سطح لاگ را تغییر دهید: `MONITORING_LOG_LEVEL=DEBUG`
- وضعیت سیستم: `/status` یا `python -m ragbot.cli status`

## مجوز

MIT © 2025 — [dibbed](https://github.com/dibbed)
