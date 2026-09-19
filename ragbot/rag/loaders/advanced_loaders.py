"""
مدیر بارگذاری پیشرفته
"""

from pathlib import Path
from typing import Any, Dict

from ragbot.configs.settings import settings

from .base import Document
from .docx import DOCXLoader
from .html_loader import HTMLLoader
from .markdown_loader import MarkdownLoader
from .ocr_loader import OCRLoader
from .pdf import PDFLoader
from .pptx_loader import PPTXLoader
from .text import TextLoader
from .url import URLLoader
from .xlsx_loader import XLSXLoader


class AdvancedDocumentLoader:
    """مدیر بارگذاری پیشرفته اسناد"""

    def __init__(self):
        """Initialize advanced document loader"""
        # Initialize loaders based on allowed file types from settings
        self.loaders = {}

        # PDF
        if "pdf" in settings.security.allowed_file_types:
            self.loaders[".pdf"] = PDFLoader()

        # Word
        if "docx" in settings.security.allowed_file_types:
            self.loaders[".docx"] = DOCXLoader()

        # Text
        if "txt" in settings.security.allowed_file_types:
            self.loaders[".txt"] = TextLoader()

        # PowerPoint
        if "pptx" in settings.security.allowed_file_types:
            self.loaders[".pptx"] = PPTXLoader()

        # Excel
        if "xlsx" in settings.security.allowed_file_types:
            self.loaders[".xlsx"] = XLSXLoader()

        # HTML
        if "html" in settings.security.allowed_file_types:
            self.loaders[".html"] = HTMLLoader()
            self.loaders[".htm"] = HTMLLoader()

        # Markdown
        if "md" in settings.security.allowed_file_types:
            self.loaders[".md"] = MarkdownLoader()

        # Images (OCR)
        image_formats = ["png", "jpg", "jpeg", "tiff", "bmp"]
        if any(fmt in settings.security.allowed_file_types for fmt in image_formats):
            ocr_loader = OCRLoader()
            for fmt in image_formats:
                if fmt in settings.security.allowed_file_types:
                    self.loaders[f".{fmt}"] = ocr_loader

        # URL loader برای لینک‌ها
        self.url_loader = URLLoader()

    async def load_document(self, file_path: str) -> Document:
        """
        بارگذاری سند با تشخیص خودکار فرمت

        Args:
            file_path: مسیر فایل یا URL

        Returns:
            سند بارگذاری شده
        """
        # تشخیص نوع منبع
        if file_path.startswith(("http://", "https://")):
            return await self.url_loader.load(file_path)

        # تشخیص فرمت فایل
        suffix = Path(file_path).suffix
        file_ext = str(suffix() if callable(suffix) else suffix).lower()

        if file_ext in self.loaders:
            loader = self.loaders[file_ext]
            return await loader.load(file_path)
        else:
            raise ValueError(f"فرمت فایل {file_ext} پشتیبانی نمی‌شود")

    async def get_supported_formats(self) -> Dict[str, str]:
        """دریافت فرمت‌های پشتیبانی شده"""
        format_descriptions = {
            ".pdf": "PDF documents",
            ".docx": "Word documents",
            ".txt": "Text files",
            ".pptx": "PowerPoint presentations",
            ".xlsx": "Excel spreadsheets",
            ".html": "HTML files",
            ".htm": "HTML files",
            ".md": "Markdown files",
            ".png": "PNG images (OCR)",
            ".jpg": "JPEG images (OCR)",
            ".jpeg": "JPEG images (OCR)",
            ".tiff": "TIFF images (OCR)",
            ".bmp": "BMP images (OCR)",
            "url": "Web URLs",
        }

        # فقط فرمت‌های مجاز رو برگردون
        allowed_formats = {}
        for fmt_ext, description in format_descriptions.items():
            if fmt_ext == "url":
                allowed_formats[fmt_ext] = description
            else:
                fmt_name = fmt_ext[1:]  # حذف نقطه
                if fmt_name in settings.security.allowed_file_types:
                    allowed_formats[fmt_ext] = description

        return allowed_formats

    async def validate_file(self, file_path: str) -> Dict[str, Any]:
        """اعتبارسنجی فایل"""
        validation_result = {
            "is_valid": False,
            "format": None,
            "size": 0,
            "error": None,
        }

        try:
            # بررسی وجود فایل
            if not Path(file_path).exists():
                validation_result["error"] = "فایل وجود ندارد"
                return validation_result

            # بررسی اندازه فایل
            file_size = Path(file_path).stat().st_size
            validation_result["size"] = file_size

            # بررسی فرمت
            suffix = Path(file_path).suffix
            file_ext = str(suffix() if callable(suffix) else suffix).lower()
            if file_ext in self.loaders:
                validation_result["format"] = file_ext
                validation_result["is_valid"] = True
            else:
                validation_result["error"] = f"فرمت {file_ext} پشتیبانی نمی‌شود"

        except Exception as e:
            validation_result["error"] = str(e)

        return validation_result
