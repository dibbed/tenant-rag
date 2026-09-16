# 🚀 راهنمای نصب و راه‌اندازی

## پیش‌نیازها
- Python 3.10+ (3.11+ توصیه می‌شود)
- Telegram Bot Token از [@BotFather](https://t.me/botfather)
- کلید API OpenAI از [OpenAI Platform](https://platform.openai.com/api-keys)
- Git (برای کلون کردن مخزن)
- Docker و Docker Compose (برای استقرار کانتینری)

## تنظیم محیط توسعه محلی

### 1. کلون و ورود به مخزن
```bash
git clone https://github.com/dibbed/rag-telegram-assistant.git
cd rag-telegram-assistant
```

### 2. ایجاد و فعال‌سازی محیط مجازی
```bash
# استفاده از venv
python -m venv venv
source venv/bin/activate  # در ویندوز: venv\Scripts\activate

# یا استفاده از conda
conda create -n ragbot python=3.11
conda activate ragbot
```

### 3. نصب وابستگی‌ها
```bash
# نصب وابستگی‌های اصلی
pip install -r requirements.txt

# برای توسعه (شامل ابزارهای تست و linting)
pip install -e ".[dev]"

# برای ویژگی‌های کامل (شامل ChromaDB، Redis و...)
pip install -e ".[full]"
```

### 4. پیکربندی محیط
```bash
cp .env.example .env
```

ویرایش `.env` با اعتبارنامه‌های خود:
```env
BOT_TOKEN=توکن_ربات_تلگرام_شما
OPENAI_API_KEY=کلید_api_openai_شما
DEFAULT_LANG=fa
ALLOW_USERS=123456789,987654321  # اختیاری: ID‌های کاربری جدا شده با کاما
```

### 5. مقداردهی اولیه پوشه‌های داده
```bash
mkdir -p data/vector_store logs
```

### 6. اجرای ربات
```bash
python main.py
```

## استقرار Docker

### شروع سریع با Docker Compose

```bash
# کلون مخزن
git clone https://github.com/dibbed/rag-telegram-assistant.git
cd rag-telegram-assistant

# پیکربندی محیط
cp .env.example .env
# ویرایش .env با اعتبارنامه‌های خود

# ساخت و اجرا
docker-compose up --build -d

# مشاهده لاگ‌ها
docker-compose logs -f ragbot

# توقف ربات
docker-compose down
```

### استقرار تولید

برای محیط‌های تولید، از پیکربندی تولید استفاده کنید:

```bash
# استفاده از فایل محیط تولید
cp .env.production .env
# ویرایش با اعتبارنامه‌های تولید

# استقرار با محدودیت‌های منابع
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# نظارت بر سلامت
docker-compose ps
docker-compose logs -f --tail=100 ragbot
```

### ساخت دستی Docker

```bash
# ساخت image
docker build -t ragbot:latest .

# اجرا با فایل محیط
docker run -d \
  --name ragbot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  ragbot:latest
```