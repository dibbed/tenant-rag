# RAGBot - پلتفرم بک‌اند مبتنی بر API برای RAG

[![CI](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)

پلتفرم بک‌اند پرسرعت و بهینه‌سازی‌شده برای تولید تقویت‌شده با بازیابی اطلاعات (**Retrieval-Augmented Generation - RAG**) مبتنی بر **FastAPI REST API**. این سیستم اسناد متنی (PDF، Word، اکسل، پاورپوینت، HTML، مارک‌داون، متن و تصاویر/OCR) و لینک‌های وب را بارگذاری، خردسازی و امبد کرده و پاسخ‌های مبتنی بر اسناد را به همراه منابع و شاخص اعتماد ارائه می‌دهد. دارای پشتیبانی کامل و بومی از زبان‌های فارسی و انگلیسی، کش چند لایه معنایی، مدیریت همزمانی ایمن در پایگاه‌های برداری (FAISS، کروما، کیودرنت و ویویت) و کنترل نرخ درخواست (Rate Limiting).

*مستندات انگلیسی: [README.md](README.md) · معماری: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · راهنمای API: [docs/API.md](docs/API.md)*

---

## 🏛️ معماری سیستم

```text
کلاینت وب / فرانت‌اند / سرویس‌های خارجی
                  ↓
       سرور FastAPI HTTP API
    ├── میان‌افزار محدودیت نرخ درخواست (Sliding Window)
    ├── میان‌افزار CORS
    └── مدیریت متمرکز خطاها و اعتبارسنجی
                  ↓
       لایه سرویس‌های یکپارچه
    ├── IntegrationService (مدیریت چرخه حیات و سلامت اجزا)
    └── RAGService (دریافت اسناد، خط لوله پرسش، بازنشانی مخزن)
                  ↓
       سیستم کش چند سطحی
    ├── SemanticCache (استفاده مجدد از پاسخ‌ها بر پایه شباهت معنایی)
    └── کش عمومی L1/L2 (حافظه و Redis اختیاری)
                  ↓
       هسته پردازش RAG
    ├── لودرها (PDF, DOCX, TXT, HTML, MD, PPTX, XLSX, OCR)
    ├── چانکرها (توکنی، معنایی، سلسله‌مراتبی، تطبیقی)
    ├── امبدینگ‌ها (SentenceTransformers, OpenAI, HuggingFace)
    ├── پایگاه‌های برداری (FAISS با async_lock، Chroma، Qdrant، Weaviate)
    └── زنجیره پاسخ‌دهی QAChain (OpenAI, Anthropic Claude, Ollama, HuggingFace)
```

---

## 🚀 شروع سریع

### ۱. راه‌اندازی محیط

```bash
git clone https://github.com/dibbed/rag-telegram-assistant.git
cd rag-telegram-assistant

# ایجاد محیط مجازی
python -m venv venv

# فعال‌سازی محیط مجازی
# در ویندوز (PowerShell):
.\venv\Scripts\Activate.ps1
# در لینوکس یا مک:
source venv/bin/activate

# نصب پکیج‌ها
pip install -U pip
pip install -r requirements.txt
```

### ۲. تنظیم متغیرهای محیطی

فایل نمونه را کپی کرده و تنظیمات را مشخص کنید:

```bash
cp env.example .env
```

تنظیمات حداقلی برای تست رایگان محلی در `.env`:
```env
# سرور
HOST=0.0.0.0
PORT=8000

# ارائه‌دهنده مدل زبانی (openrouter, openai, anthropic, ollama, hf_local)
LLM_PROVIDER=openrouter
LLM_MODEL=x-ai/grok-4-fast:free
OPENROUTER_API_KEY=your_key_here

# امبدینگ (Sentence Transformers محلی روی CPU اجرا می‌شود)
EMBED_PROVIDER=sentence_transformers
EMBED_MODEL=intfloat/e5-small-v2

# پایگاه داده برداری پیش‌فرض (faiss, chroma, qdrant, weaviate)
VECTOR_STORE_DEFAULT_STORE=faiss
```

### ۳. اجرای سرور API

```bash
# از طریق فایل اصلی پروژه:
python main.py

# یا مستقیماً از طریق Uvicorn:
uvicorn ragbot.api.app:app --host 0.0.0.0 --port 8000 --reload
```

مستندات تعاملی Swagger بلافاصله در آدرس‌های زیر در دسترس است:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 📡 نقاط پایانی اصلی API

| متد | مسیر (Endpoint) | توضیحات |
|:---|:---|:---|
| `GET` | `/health` یا `/api/v1/health` | بررسی وضعیت سلامت بخش‌های مخزن برداری، امبدینگ، کش و مدل‌ها |
| `POST` | `/api/v1/query` | ارسال پرسش و دریافت پاسخ به همراه استنادها و درصد اطمینان |
| `POST` | `/api/v1/documents/upload` | آپلود و پردازش فایل‌های سندی (PDF، DOCX، TXT، HTML و غیره) |
| `POST` | `/api/v1/documents/text` | درج مستقیم محتوای متنی در پایگاه دانش |
| `POST` | `/api/v1/documents/url` | استخراج و پردازش محتوا از یک پیوند وب (URL) |
| `POST` | `/api/v1/documents/reset` | پاکسازی کامل اسناد پایگاه برداری و خالی کردن کش‌های معنایی مرتبط |

### نمونه پرسش از پایگاه دانش

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "معماری این سیستم چگونه کار می‌کند؟",
    "language": "fa",
    "top_k": 3,
    "similarity_threshold": 0.5
  }'
```

---

## 🛡️ امنیت و محدودیت نرخ درخواست

- **محدودیت درخواست (Rate Limiting)**: پیاده‌سازی پنجره لغزان درون حافظه به ازای هر IP با متغیرهای `SECURITY_RATE_LIMIT_REQUESTS=60` و `SECURITY_RATE_LIMIT_WINDOW=60`. در صورت عبور، کد خطای `HTTP 429` همراه با هدرهای استاندارد صادر می‌شود.
- **ایمن‌سازی مسیرها**: جلوگیری از حملات Directory Traversal در فایل‌های ورودی و متادیتا.
- **سقف حجم فایل‌ها**: محدودیت اندازه ورودی‌های متنی و فایل‌ها با متغیر `SECURITY_MAX_FILE_SIZE_MB=50` (کد خطای `HTTP 413` در صورت تجاوز).

---

## 🧪 تست و اعتبارسنجی

اجرای تست‌ها باید با ایزولاسیون پردازنده مرکزی (CPU) صورت گیرد تا از خطای تداخل حافظه گرافیکی جلوگیری شود:

```powershell
# در ویندوز (PowerShell):
$env:CUDA_VISIBLE_DEVICES = ""
$env:TORCH_DEVICE = "cpu"
.\venv\Scripts\pytest.exe -o addopts='' -q

# در لینوکس / مک:
export CUDA_VISIBLE_DEVICES=""
export TORCH_DEVICE="cpu"
pytest -o addopts='' -q
```

---

## 🐳 استقرار با Docker

```bash
docker compose up --build -d
```

---

## 📚 فهرست مستندات

- [راهنمای جامع معماری](docs/ARCHITECTURE.md)
- [مستندات فنی API](docs/API.md)
- [راهنمای متغیرهای پیکربندی](docs/configuration.md)
- [راهنمای استقرار](docs/DEPLOYMENT.md)
- [راهنمای تست و ارزیابی](docs/testing.md)
- [پایگاه‌های داده برداری](docs/VECTOR_STORES.md)
- [آرشیو مستندات قدیمی](docs/archive/)

---

## 📄 لایسنس

مجوز MIT © 2025–2026 [dibbed](https://github.com/dibbed).
