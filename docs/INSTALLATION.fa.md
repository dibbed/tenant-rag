# 🚀 راهنمای نصب و راه‌اندازی TenantRAG

این راهنما مراحل نصب وابستگی‌ها، تنظیم متغیرهای محیطی و اجرای سرور API را شرح می‌دهد.

---

## ۱. پیش‌نیازها
- پایتون نسخه 3.10، 3.11 یا 3.12
- ابزار Git
- کلید دسترسی یکی از ارائه‌دهندگان مدل زبانی (OpenRouter، OpenAI یا Anthropic) یا نصب محلی Ollama
- داکر و Docker Compose (اختیاری، برای استقرار کانتینری)

---

## ۲. راه‌اندازی محیط محلی

### گام اول: کلون کردن مخزن
```bash
git clone https://github.com/dibbed/tenant-rag.git
cd tenant-rag
```

### گام دوم: ساخت و فعال‌سازی محیط مجازی
```bash
# ایجاد محیط مجازی
python -m venv venv

# فعال‌سازی در ویندوز (PowerShell):
.\venv\Scripts\Activate.ps1

# فعال‌سازی در لینوکس یا مک:
source venv/bin/activate
```

### گام سوم: نصب پکیج‌ها
```bash
# به‌روزرسانی pip
pip install -U pip

# نصب پیش‌نیازهای اصلی
pip install -r requirements.txt

# نصب وابستگی‌های توسعه و تست (اختیاری)
pip install -e ".[dev]"
```

---

## ۳. تنظیم متغیرهای محیطی (`.env`)

فایل نمونه را کپی کنید:
```bash
cp env.example .env
```

نمونه تنظیمات کاربردی برای تست سریع و رایگان در `.env`:
```env
HOST=0.0.0.0
PORT=8000

# ارائه‌دهنده مدل زبانی
LLM_PROVIDER=openrouter
LLM_MODEL=x-ai/grok-4-fast:free
OPENROUTER_API_KEY=کلید_openrouter_شما

# مدل امبدینگ
EMBED_PROVIDER=sentence_transformers
EMBED_MODEL=intfloat/e5-small-v2

# پایگاه داده برداری
VECTOR_STORE_DEFAULT_STORE=faiss
```

---

## ۴. اجرای سرور API

```bash
# از طریق فایل اصلی:
python main.py

# یا از طریق Uvicorn با قابلیت reload:
uvicorn ragbot.api.app:app --host 0.0.0.0 --port 8000 --reload
```

پس از اجرا، مستندات تعاملی Swagger در آدرس زیر در دسترس خواهد بود:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## ۵. استقرار با Docker

```bash
# ساخت ایمیج و اجرای کانتینر
docker compose up --build -d

# مشاهده لاگ‌ها
docker compose logs -f
```