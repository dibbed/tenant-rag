# Archived Documentation

> [!NOTE]
> This document describes the previous Telegram-based architecture, experiments, or historical roadmap.
> The active production system uses the API-first architecture described in [README.md](../../README.md) and [docs/API.md](../API.md).

---

# راهنمای نصب RAG Telegram Assistant

## پیش‌نیازها

- Python 3.10 یا بالاتر
- Redis Server (برای caching)
- Git

## نصب سریع

### 1. کلون کردن پروژه

```bash
git clone https://github.com/your-repo/rag-telegram-assistant.git
cd rag-telegram-assistant
```

### 2. ایجاد محیط مجازی

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# یا
venv\Scripts\activate  # Windows
```

### 3. نصب وابستگی‌ها

#### گزینه 1: نصب با نسخه‌های سازگار (توصیه شده)

```bash
pip install -r requirements-stable.txt
```

#### گزینه 2: نصب با نسخه‌های جدید (ممکن است مشکل داشته باشد)

```bash
pip install -r requirements.txt
```

#### گزینه 3: نصب با pip

```bash
pip install -e .
```

### 4. تنظیم محیط

```bash
cp env.example .env
# فایل .env را ویرایش کنید
```

### 5. راه‌اندازی Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Windows
# Redis را از https://redis.io/download دانلود کنید
```

### 6. اجرای پروژه

```bash
python main.py
```

## حل مشکلات رایج

### مشکل سازگاری Pydantic و OpenAI

اگر خطای `__pydantic_extra__` دریافت کردید:

```bash
# کاهش نسخه pydantic
pip install "pydantic>=2.6.4,<2.7.0"

# کاهش نسخه openai
pip install "openai>=1.39.0,<1.100.0"
```

### مشکل uvloop در Windows

```bash
# نصب بدون uvloop در Windows
pip install -r requirements-stable.txt --no-deps
pip install uvloop  # فقط در Linux/Mac
```

### مشکل Redis

اگر Redis در دسترس نیست:

```bash
# در .env فایل
ENABLE_REDIS=false
```

## تست نصب

```bash
# تست سریع
python -c "from ragbot.services.integration_service import IntegrationService; print('✅ نصب موفق!')"

# تست کامل
python complete_rag_test.py
```

## نسخه‌های سازگار

| کتابخانه  | نسخه سازگار     | توضیح                    |
| --------- | --------------- | ------------------------ |
| pydantic  | 2.6.4           | نسخه پایدار              |
| openai    | 1.39.0 - 1.99.9 | سازگار با pydantic 2.6.4 |
| aiogram   | 3.7.0+          | فریمورک تلگرام           |
| langchain | 0.3.10+         | فریمورک RAG              |

## پشتیبانی

اگر مشکلی دارید:

1. ابتدا `requirements-stable.txt` را امتحان کنید
2. لاگ‌ها را بررسی کنید
3. نسخه‌های سازگار را نصب کنید
4. Issue در GitHub ایجاد کنید
