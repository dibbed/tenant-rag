# 🔧 راهنمای عیب‌یابی

## مشکلات رایج و راه‌حل‌ها

### ربات شروع نمی‌شود

**مشکل**: ربات با خطای احراز هویت شروع نمی‌شود
```
ERROR: Unauthorized: bot token is invalid
```

**راه‌حل**:
1. توکن ربات خود را در فایل `.env` بررسی کنید
2. اطمینان حاصل کنید که توکن از [@BotFather](https://t.me/botfather) است
3. فضاهای اضافی یا علامت نقل قول در توکن را بررسی کنید
4. توکن را با درخواست curl ساده تست کنید:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
   ```

### خطاهای OpenAI API

**مشکل**: خطاهای کلید API یا محدودیت نرخ OpenAI
```
ERROR: Incorrect API key provided
ERROR: Rate limit exceeded
```

**راه‌حل‌ها**:

#### کلید API نامعتبر
- کلید OpenAI API خود را در `.env` بررسی کنید
- اطمینان حاصل کنید که کلید با `sk-` شروع می‌شود
- بررسی کنید که حساب OpenAI شما اعتبار کافی دارد

#### محدودیت نرخ
- طرح OpenAI خود را برای محدودیت‌های بالاتر ارتقا دهید
- محدودیت درخواست در استفاده خود اعمال کنید
- استفاده از مدل‌های مختلف را در نظر بگیرید (مثل `gpt-3.5-turbo` به جای `gpt-4`)

### مشکلات حافظه

**مشکل**: استفاده بالای حافظه یا خطاهای کمبود حافظه
```
ERROR: Process killed (OOM)
```

**راه‌حل‌ها**:

#### کاهش اندازه chunk
```env
CHUNK_SIZE=256  # کاهش از پیش‌فرض 512
```

#### محدود کردن اندازه سند
```env
MAX_FILE_SIZE=10485760  # محدودیت 10MB
```

#### استفاده از محدودیت‌های حافظه Docker
```yaml
deploy:
  resources:
    limits:
      memory: 512M
```

### مشکلات Vector Store

**مشکل**: خرابی یا خطاهای بارگذاری ایندکس FAISS
```
ERROR: Could not load FAISS index
```

**راه‌حل‌ها**:

#### ریست vector store
```bash
rm -rf data/vector_store/*
# یا استفاده از دستور /reset در تلگرام
```

#### بررسی مجوزهای فایل
```bash
chmod -R 755 data/
chown -R $USER:$USER data/
```

### مشکلات Docker

**مشکل**: کانتینر شروع نمی‌شود یا crash می‌کند
```
ERROR: Container exited with code 1
```

**راه‌حل‌ها**:

#### بررسی لاگ‌ها
```bash
docker-compose logs ragbot
```

#### بررسی فایل محیط
```bash
docker-compose config  # اعتبارسنجی فایل compose
```

#### بازسازی image
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## نکات عیب‌یابی

### فعال‌سازی لاگ‌گیری debug
```env
LOG_LEVEL=DEBUG
```

### نظارت بر استفاده منابع
```bash
docker stats ragbot
```

### بررسی وضعیت ربات
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## دریافت کمک

اگر با مشکلاتی مواجه شدید که اینجا پوشش داده نشده:

### 1. ابتدا لاگ‌ها را بررسی کنید
```bash
tail -f logs/ragbot.log
# یا برای Docker:
docker-compose logs -f ragbot
```

### 2. مسائل موجود را در GitHub جستجو کنید

### 3. مسئله جدید ایجاد کنید
شامل:
- پیام‌های خطا و لاگ‌ها
- جزئیات محیط شما
- مراحل بازتولید
- پیکربندی (بدون داده‌های حساس)