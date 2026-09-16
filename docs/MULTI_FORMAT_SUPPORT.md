# 📚 Multi-Format Document Support

## 📋 **Overview**

پشتیبانی کامل از فرمت‌های مختلف اسناد شامل PowerPoint، Excel، HTML، Markdown و OCR برای تصاویر در سیستم RAG Telegram Assistant.

## 🎯 **Supported Formats**

### **Office Documents**

- **PowerPoint (.pptx)**: استخراج متن از اسلایدها، عنوان‌ها و layout
- **Excel (.xlsx)**: پردازش تمام sheet ها و تبدیل داده‌ها به متن
- **Word (.docx)**: پردازش اسناد Word (قبلاً موجود)

### **Web Formats**

- **HTML (.html, .htm)**: پشتیبانی از فایل و URL
- **Markdown (.md)**: پردازش کامل Markdown با front matter

### **Images & OCR**

- **PNG, JPG, JPEG, TIFF, BMP**: OCR با پشتیبانی فارسی و انگلیسی

### **Existing Formats**

- **PDF (.pdf)**: پردازش اسناد PDF (قبلاً موجود)
- **Text (.txt)**: فایل‌های متنی (قبلاً موجود)
- **URLs**: لینک‌های وب (قبلاً موجود)

## 🏗️ **Architecture**

### **File Structure**

```
ragbot/rag/loaders/
├── pptx_loader.py          # بارگذاری PowerPoint
├── xlsx_loader.py          # بارگذاری Excel
├── html_loader.py          # بارگذاری HTML
├── markdown_loader.py      # بارگذاری Markdown
├── ocr_loader.py           # OCR برای تصاویر
├── advanced_loaders.py     # مدیر بارگذاری پیشرفته
└── __init__.py            # به‌روزرسانی شده
```

### **Configuration**

```python
# ragbot/configs/settings.py
class MultiFormatSettings(PydanticBaseSettings):
    supported_formats: List[str] = [
        "pdf", "docx", "txt", "pptx", "xlsx",
        "html", "htm", "md", "png", "jpg", "jpeg", "tiff", "bmp"
    ]

    # OCR settings
    ocr_enabled: bool = True
    ocr_language: str = "fas+eng"  # فارسی + انگلیسی
    ocr_confidence_threshold: float = 0.6

    # Excel settings
    excel_max_rows: int = 1000
    excel_include_headers: bool = True

    # PowerPoint settings
    pptx_extract_images: bool = False
    pptx_extract_notes: bool = True

    # HTML settings
    html_extract_links: bool = True
    html_extract_images: bool = True
    html_clean_content: bool = True

    # Markdown settings
    markdown_extract_code: bool = True
    markdown_extract_tables: bool = True
```

## 🚀 **Usage Examples**

### **Basic Usage**

```python
from ragbot.rag.loaders.advanced_loaders import AdvancedDocumentLoader

# ایجاد loader پیشرفته
loader = AdvancedDocumentLoader()

# بارگذاری سند با تشخیص خودکار فرمت
document = await loader.load_document("example.pptx")

print(f"متن: {document.text}")
print(f"متادیتا: {document.metadata}")
```

### **Format Validation**

```python
# اعتبارسنجی فایل
validation = await loader.validate_file("example.xlsx")

if validation["is_valid"]:
    print(f"فرمت: {validation['format']}")
    print(f"اندازه: {validation['size']} bytes")
else:
    print(f"خطا: {validation['error']}")
```

### **Supported Formats List**

```python
# دریافت فرمت‌های پشتیبانی شده
formats = await loader.get_supported_formats()

for format_ext, description in formats.items():
    print(f"{format_ext}: {description}")
```

## 📊 **Format-Specific Features**

### **PowerPoint (.pptx)**

- استخراج متن از تمام اسلایدها
- استخراج عنوان هر اسلاید
- تشخیص layout اسلایدها
- متادیتای کامل شامل تعداد اسلایدها

### **Excel (.xlsx)**

- پردازش تمام sheet ها
- تبدیل داده‌ها به متن ساختاریافته
- استخراج نام ستون‌ها
- محدود کردن ردیف‌ها (قابل تنظیم)

### **HTML (.html, .htm)**

- پشتیبانی از فایل محلی و URL
- استخراج محتوای اصلی (main, article, content)
- استخراج متادیتای SEO (title, description, keywords)
- تمیز کردن محتوا (حذف script, style, nav)

### **Markdown (.md)**

- پردازش front matter
- استخراج عنوان‌ها با سطح
- استخراج لینک‌ها
- پردازش کدهای inline
- تبدیل به HTML و استخراج متن

### **OCR (Images)**

- پشتیبانی از فرمت‌های تصویری متعدد
- OCR چندزبانه (فارسی + انگلیسی)
- تمیز کردن متن استخراج شده
- استخراج متادیتای تصویر (ابعاد، فرمت، EXIF)

## ⚙️ **Configuration Options**

### **Environment Variables**

```bash
# Multi-Format Settings
MULTI_FORMAT_SUPPORTED_FORMATS="pdf,docx,txt,pptx,xlsx,html,htm,md,png,jpg,jpeg,tiff,bmp"
MULTI_FORMAT_OCR_ENABLED=true
MULTI_FORMAT_OCR_LANGUAGE="fas+eng"
MULTI_FORMAT_OCR_CONFIDENCE_THRESHOLD=0.6
MULTI_FORMAT_EXCEL_MAX_ROWS=1000
MULTI_FORMAT_EXCEL_INCLUDE_HEADERS=true
MULTI_FORMAT_PPTX_EXTRACT_IMAGES=false
MULTI_FORMAT_PPTX_EXTRACT_NOTES=true
MULTI_FORMAT_HTML_EXTRACT_LINKS=true
MULTI_FORMAT_HTML_EXTRACT_IMAGES=true
MULTI_FORMAT_HTML_CLEAN_CONTENT=true
MULTI_FORMAT_MARKDOWN_EXTRACT_CODE=true
MULTI_FORMAT_MARKDOWN_EXTRACT_TABLES=true
```

### **Security Settings**

```python
# فرمت‌های مجاز در تنظیمات امنیتی
allowed_file_types = [
    "pdf", "txt", "docx", "html", "pptx", "xlsx",
    "md", "png", "jpg", "jpeg", "tiff", "bmp"
]
```

## 🧪 **Testing**

### **Unit Tests**

```bash
# اجرای تست‌های Multi-Format
pytest tests/unit/test_multi_format.py -v

# تست‌های خاص
pytest tests/unit/test_multi_format.py::TestPPTXLoader -v
pytest tests/unit/test_multi_format.py::TestXLSXLoader -v
pytest tests/unit/test_multi_format.py::TestHTMLLoader -v
pytest tests/unit/test_multi_format.py::TestMarkdownLoader -v
pytest tests/unit/test_multi_format.py::TestOCRLoader -v
pytest tests/unit/test_multi_format.py::TestAdvancedDocumentLoader -v
```

### **Integration Tests**

```bash
# تست یکپارچگی
pytest tests/unit/test_multi_format.py::test_integration_multi_format_loading -v
```

## 📈 **Performance Metrics**

### **Expected Performance**

- **PowerPoint**: ~2-5 ثانیه برای فایل‌های متوسط
- **Excel**: ~1-3 ثانیه برای فایل‌های متوسط
- **HTML**: ~0.5-2 ثانیه برای فایل‌های متوسط
- **Markdown**: ~0.1-0.5 ثانیه برای فایل‌های متوسط
- **OCR**: ~3-10 ثانیه بسته به اندازه تصویر

### **Memory Usage**

- **PowerPoint**: متوسط (بسته به تعداد اسلایدها)
- **Excel**: بالا (بسته به تعداد ردیف‌ها)
- **HTML**: پایین
- **Markdown**: پایین
- **OCR**: متوسط (بسته به اندازه تصویر)

## 🔧 **Dependencies**

### **New Dependencies**

```txt
python-pptx==0.6.23      # PowerPoint processing
openpyxl==3.1.2          # Excel processing
markdown==3.6            # Markdown processing
Pillow==10.4.0           # Image processing
pytesseract==0.3.10      # OCR processing
```

### **Existing Dependencies**

```txt
beautifulsoup4==4.12.3   # HTML parsing
requests==2.32.3         # URL fetching
pandas==2.2.2           # Excel data processing
```

## 🚨 **Error Handling**

### **Common Errors**

- **Unsupported Format**: فرمت فایل پشتیبانی نمی‌شود
- **File Not Found**: فایل وجود ندارد
- **Permission Denied**: دسترسی به فایل ندارید
- **Corrupted File**: فایل خراب است
- **OCR Failure**: خطا در پردازش OCR

### **Error Recovery**

- اعتبارسنجی قبل از پردازش
- پیام‌های خطای واضح
- fallback برای فرمت‌های مشابه
- logging کامل خطاها

## 🔮 **Future Enhancements**

### **Planned Features**

- پشتیبانی از فرمت‌های بیشتر (CSV, RTF, ODT)
- OCR پیشرفته‌تر با مدل‌های بهتر
- پردازش batch فایل‌ها
- کش کردن نتایج پردازش
- پردازش موازی فرمت‌های مختلف

### **Integration Opportunities**

- ادغام با سیستم کش معنایی
- بهینه‌سازی عملکرد
- نظارت بلادرنگ
- تحلیل رفتار کاربر

## 📞 **Support**

### **Troubleshooting**

1. بررسی فرمت فایل پشتیبانی شده
2. بررسی اندازه فایل (محدودیت امنیتی)
3. بررسی دسترسی به فایل
4. بررسی dependencies نصب شده

### **Getting Help**

- بررسی logs برای جزئیات خطا
- تست با فایل‌های نمونه
- بررسی تنظیمات Multi-Format
- تماس با تیم پشتیبانی

---

**تاریخ آخرین بروزرسانی:** 2024-01-21
**نسخه:** 1.0.0
**وضعیت:** Production Ready
