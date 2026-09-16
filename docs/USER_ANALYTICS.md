# 📊 User Analytics & Behavior Analysis

## 📋 Overview

سیستم تحلیل رفتار کاربران و آمار استفاده برای بهینه‌سازی تجربه کاربری و بهبود عملکرد سیستم.

## 🏗️ Architecture

### Components

- **UserBehaviorAnalyzer**: تحلیل رفتار کاربران و تولید پروفایل
- **UsagePatternsAnalyzer**: تحلیل الگوهای استفاده و روندها
- **SatisfactionTracker**: ردیابی رضایت کاربران
- **AnalyticsDashboard**: داشبورد جامع تحلیل

### Integration

```python
from ragbot.analytics.analytics_dashboard import AnalyticsDashboard
from ragbot.configs.settings import Settings

# Initialize
settings = Settings()
dashboard = AnalyticsDashboard(settings)
await dashboard.initialize()
```

## 🔧 Configuration

### Environment Variables

```bash
# Analytics Settings
ANALYTICS_ENABLE_USER_ANALYTICS=true
ANALYTICS_TRACK_USER_SESSIONS=true
ANALYTICS_TRACK_QUERY_PATTERNS=true
ANALYTICS_TRACK_DOCUMENT_PREFERENCES=true
ANALYTICS_ENABLE_SATISFACTION_TRACKING=true
ANALYTICS_SATISFACTION_PROMPT_FREQUENCY=5
ANALYTICS_SATISFACTION_RATING_SCALE=5
ANALYTICS_ANONYMIZE_USER_DATA=false
ANALYTICS_DATA_RETENTION_DAYS=90
ANALYTICS_EXPORT_USER_DATA=true
ANALYTICS_SESSION_TIMEOUT_HOURS=1
ANALYTICS_MAX_SESSION_HISTORY=1000
ANALYTICS_ANALYTICS_UPDATE_INTERVAL=300
```

## 📊 Features

### 1. User Behavior Tracking

#### Session Management

- ردیابی جلسات کاربران
- محاسبه مدت جلسات
- تشخیص الگوهای استفاده

#### Query Analysis

- استخراج کلمات کلیدی
- تحلیل ترجیحات موضوعی
- ردیابی فرکانس پرسش‌ها

#### User Profiling

- تولید پروفایل کاربر
- طبقه‌بندی الگوهای استفاده:
  - `light_user`: کاربر کم‌استفاده
  - `casual_user`: کاربر معمولی
  - `regular_user`: کاربر منظم
  - `power_user`: کاربر فعال

### 2. Usage Patterns Analysis

#### Time-based Analysis

- تحلیل ساعات پیک استفاده
- روندهای روزانه و هفتگی
- الگوهای فصلی

#### Content Analysis

- ترجیحات نوع اسناد
- الگوهای پرسش‌ها
- تنوع محتوا

#### Engagement Metrics

- سطح درگیری کاربران
- مدت جلسات
- فرکانس استفاده

### 3. Satisfaction Tracking

#### Rating System

- مقیاس 1-5 برای رضایت
- بازخورد متنی اختیاری
- تحلیل روند رضایت

#### Quality Metrics

- میانگین رضایت کلی
- توزیع امتیازها
- شناسایی زمینه‌های بهبود

#### User-specific Analysis

- پروفایل رضایت کاربر
- روند تغییرات
- توصیه‌های شخصی‌سازی

## 🚀 Usage

### Basic Tracking

```python
# Track user actions
await dashboard.track_user_action("user123", "query", {
    "query": "What is AI?",
    "processing_time": 2.5,
    "confidence_score": 0.8
})

# Record satisfaction feedback
await dashboard.record_satisfaction_feedback(
    "user123", "What is AI?", "AI is...", 5, "Great answer!"
)

# Record session length
await dashboard.record_session_length(300)  # 5 minutes

# Record document type
await dashboard.record_document_type("pdf")
```

### Analytics Retrieval

```python
# Get user analytics
user_analytics = await dashboard.get_user_analytics("user123")

# Get comprehensive report
report = await dashboard.get_analytics_report(days=30)

# Get dashboard data
dashboard_data = await dashboard.get_comprehensive_dashboard()
```

## 📈 Metrics

### User Behavior Metrics

- **Total Sessions**: تعداد کل جلسات
- **Total Queries**: تعداد کل پرسش‌ها
- **Usage Pattern**: الگوی استفاده
- **Satisfaction Average**: میانگین رضایت
- **Last Active**: آخرین فعالیت

### Usage Pattern Metrics

- **Peak Hours**: ساعات پیک استفاده
- **Usage Distribution**: توزیع استفاده
- **Query Patterns**: الگوهای پرسش
- **Document Preferences**: ترجیحات اسناد
- **Session Characteristics**: ویژگی‌های جلسه

### Satisfaction Metrics

- **Overall Satisfaction**: رضایت کلی
- **Rating Distribution**: توزیع امتیازها
- **User Satisfaction**: رضایت کاربران
- **Satisfaction Trend**: روند رضایت
- **Satisfaction Levels**: سطوح رضایت

## 🎯 Commands

### Telegram Bot Commands

- `/analytics` - نمایش تحلیل رفتار کاربر
- `/report` - نمایش گزارش جامع تحلیل

### Example Output

```
📊 تحلیل رفتار کاربر

👤 پروفایل کاربر:
🔢 تعداد جلسات: 5
❓ تعداد پرسش‌ها: 12
📈 الگوی استفاده: regular_user
⭐ میانگین رضایت: 4.2

📅 فعالیت اخیر:
🕐 آخرین جلسه: 3 پرسش
📊 جلسات هفته: 2
❓ پرسش‌های هفته: 8

💡 توصیه‌ها:
• سعی کنید بیشتر از بات استفاده کنید تا پاسخ‌های بهتری دریافت کنید
• شما علاقه‌مند به موضوعات AI, machine learning هستید

😊 رضایت:
⭐ میانگین امتیاز: 4.2/5
📊 تعداد بازخورد: 3
```

## 🔍 Insights

### System Health Assessment

سیستم سلامت کلی را بر اساس:

- تعداد کاربران فعال
- سطح رضایت
- میزان استفاده
- تنوع کاربران

ارزیابی می‌کند.

### Recommendations

توصیه‌های بهبود بر اساس:

- الگوهای استفاده
- سطح رضایت
- ترجیحات موضوعی
- روندهای زمانی

تولید می‌شوند.

### Trend Analysis

تحلیل روندها شامل:

- روند استفاده
- روند رضایت
- تغییرات فصلی
- الگوهای رشد

## 🧪 Testing

### Unit Tests

```bash
python -m pytest tests/unit/test_user_analytics.py -v
```

### Example Usage

```bash
python examples/user_analytics_example.py
```

## 📊 Performance

### Optimization Features

- **Lazy Loading**: بارگذاری تنبل داده‌ها
- **Caching**: کش کردن نتایج تحلیل
- **Batch Processing**: پردازش دسته‌ای
- **Memory Management**: مدیریت حافظه

### Scalability

- **Horizontal Scaling**: مقیاس‌پذیری افقی
- **Data Partitioning**: تقسیم داده‌ها
- **Async Processing**: پردازش ناهمزمان
- **Resource Optimization**: بهینه‌سازی منابع

## 🔒 Privacy & Security

### Data Protection

- **Anonymization**: ناشناس‌سازی داده‌ها
- **Data Retention**: نگهداری محدود داده‌ها
- **Access Control**: کنترل دسترسی
- **Encryption**: رمزگذاری داده‌ها

### Compliance

- **GDPR Compliance**: سازگاری با GDPR
- **Data Export**: امکان صادرات داده‌ها
- **User Consent**: رضایت کاربر
- **Audit Trail**: ردپای حسابرسی

## 🚀 Future Enhancements

### Planned Features

- **Real-time Analytics**: تحلیل بلادرنگ
- **Predictive Analytics**: تحلیل پیش‌بینی‌کننده
- **Advanced Visualizations**: تجسم‌های پیشرفته
- **Machine Learning Integration**: ادغام یادگیری ماشین

### Integration Opportunities

- **External Analytics Tools**: ابزارهای تحلیل خارجی
- **Business Intelligence**: هوش تجاری
- **Customer Relationship Management**: مدیریت روابط مشتری
- **Marketing Automation**: اتوماسیون بازاریابی

## 📞 Support

برای سوالات و پشتیبانی:

- بررسی فایل‌های تست
- مطالعه مثال‌های استفاده
- مراجعه به مستندات API
- بررسی لاگ‌های سیستم

---

**تاریخ آخرین بروزرسانی:** 2024-01-21
**نسخه:** 1.0.0
**وضعیت:** Production Ready
