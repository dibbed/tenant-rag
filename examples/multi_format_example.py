"""
مثال استفاده از پشتیبانی چندفرمت
"""

import asyncio

from ragbot.configs.settings import settings
from ragbot.rag.loaders.advanced_loaders import AdvancedDocumentLoader


async def main():
    """مثال اصلی استفاده از Multi-Format Support"""

    print("🚀 شروع مثال پشتیبانی چندفرمت")
    print("=" * 50)

    # ایجاد loader پیشرفته
    loader = AdvancedDocumentLoader()

    # دریافت فرمت‌های پشتیبانی شده
    print("📋 فرمت‌های پشتیبانی شده:")
    supported_formats = await loader.get_supported_formats()
    for format_ext, description in supported_formats.items():
        print(f"  {format_ext}: {description}")

    print("\n" + "=" * 50)

    # مثال‌های مختلف بارگذاری
    test_files = [
        "example.pdf",
        "example.docx",
        "example.pptx",
        "example.xlsx",
        "example.html",
        "example.md",
        "example.png",
        "https://example.com",
    ]

    for file_path in test_files:
        print(f"\n📄 پردازش فایل: {file_path}")

        try:
            # اعتبارسنجی فایل
            validation = await loader.validate_file(file_path)

            if validation["is_valid"]:
                print(f"  ✅ فرمت معتبر: {validation['format']}")
                print(f"  📊 اندازه: {validation['size']} bytes")

                # بارگذاری سند (در محیط واقعی)
                # document = await loader.load_document(file_path)
                # print(f"  📝 متن استخراج شده: {len(document.text)} کاراکتر")
                # print(f"  🏷️ متادیتا: {document.metadata}")

            else:
                print(f"  ❌ خطا: {validation['error']}")

        except Exception as e:
            print(f"  ⚠️ خطا در پردازش: {str(e)}")

    print("\n" + "=" * 50)
    print("🎯 تنظیمات Multi-Format:")
    print(f"  فرمت‌های پشتیبانی: {settings.security.allowed_file_types}")
    print(f"  OCR فعال: {settings.multi_format.ocr_enabled}")
    print(f"  زبان OCR: {settings.multi_format.ocr_language}")
    print(f"  حداکثر ردیف Excel: {settings.multi_format.excel_max_rows}")
    print(f"  استخراج لینک HTML: {settings.multi_format.html_extract_links}")

    print("\n✅ مثال تکمیل شد!")


async def test_specific_loaders():
    """تست loader های خاص"""

    print("\n🔧 تست Loader های خاص")
    print("=" * 30)

    # تست PPTX Loader
    from ragbot.rag.loaders.pptx_loader import PPTXLoader

    pptx_loader = PPTXLoader()
    print("✅ PPTXLoader ایجاد شد")

    # تست XLSX Loader
    from ragbot.rag.loaders.xlsx_loader import XLSXLoader

    xlsx_loader = XLSXLoader()
    print("✅ XLSXLoader ایجاد شد")

    # تست HTML Loader
    from ragbot.rag.loaders.html_loader import HTMLLoader

    html_loader = HTMLLoader()
    print("✅ HTMLLoader ایجاد شد")

    # تست Markdown Loader
    from ragbot.rag.loaders.markdown_loader import MarkdownLoader

    md_loader = MarkdownLoader()
    print("✅ MarkdownLoader ایجاد شد")

    # تست OCR Loader
    from ragbot.rag.loaders.ocr_loader import OCRLoader

    ocr_loader = OCRLoader()
    print("✅ OCRLoader ایجاد شد")

    print("✅ تمام Loader ها آماده هستند!")


async def demonstrate_format_processing():
    """نمایش پردازش فرمت‌های مختلف"""

    print("\n📊 نمایش پردازش فرمت‌ها")
    print("=" * 35)

    # مثال پردازش PowerPoint
    print("\n📊 PowerPoint Processing:")
    print("  - استخراج متن از اسلایدها")
    print("  - استخراج عنوان اسلایدها")
    print("  - استخراج layout اسلایدها")
    print("  - ایجاد متادیتای کامل")

    # مثال پردازش Excel
    print("\n📈 Excel Processing:")
    print("  - پردازش تمام sheet ها")
    print("  - تبدیل داده‌ها به متن")
    print("  - استخراج نام ستون‌ها")
    print("  - محدود کردن ردیف‌ها")

    # مثال پردازش HTML
    print("\n🌐 HTML Processing:")
    print("  - پشتیبانی از فایل و URL")
    print("  - استخراج محتوای اصلی")
    print("  - استخراج متادیتای SEO")
    print("  - تمیز کردن محتوا")

    # مثال پردازش Markdown
    print("\n📝 Markdown Processing:")
    print("  - استخراج front matter")
    print("  - پردازش عنوان‌ها")
    print("  - استخراج لینک‌ها")
    print("  - پردازش کدهای inline")

    # مثال پردازش OCR
    print("\n👁️ OCR Processing:")
    print("  - پشتیبانی از فرمت‌های تصویری")
    print("  - OCR چندزبانه (فارسی + انگلیسی)")
    print("  - تمیز کردن متن استخراج شده")
    print("  - استخراج متادیتای تصویر")


if __name__ == "__main__":
    # اجرای مثال‌ها
    asyncio.run(main())
    asyncio.run(test_specific_loaders())
    asyncio.run(demonstrate_format_processing())
