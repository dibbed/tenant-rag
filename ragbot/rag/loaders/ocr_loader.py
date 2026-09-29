"""
بارگذاری اسناد با OCR با متادیتای استاندارد و نرمال‌سازی متن.
"""

import contextlib
from typing import Any

import pytesseract
from PIL import Image

from ragbot.configs.settings import settings
from ragbot.rag.exceptions import DocumentProcessingError

from .base import Document, DocumentLoader


class OCRLoader(DocumentLoader):
    """بارگذاری اسناد با OCR"""

    def __init__(self, language: str | None = None):
        """
        Initialize OCR loader

        Args:
            language: زبان OCR (فارسی + انگلیسی) - اگر None باشد از settings استفاده می‌شود
        """
        self.language = language or settings.multi_format.ocr_language
        self.supported_formats = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

    async def load(
        self, source: str | None = None, **kwargs: Any
    ) -> Document:
        """بارگذاری فایل تصویری با OCR."""
        file_path = source if source is not None else kwargs.pop("file_path", None)
        if not isinstance(file_path, str):
            raise TypeError("load() requires a source path")
        try:
            # بررسی فرمت فایل
            ext = "." + file_path.lower().split(".")[-1]
            if ext not in self.supported_formats:
                clean_ext = ext.lstrip(".")
                raise ValueError(f"فرمت فایل {clean_ext} پشتیبانی نمی‌شود")

            # بررسی اندازه فایل (ایمن)
            try:
                from pathlib import Path

                p = Path(file_path)
                max_bytes = int(settings.security.max_file_size_mb) * 1024 * 1024
                if p.exists() and p.is_file() and p.stat().st_size > max_bytes:
                    raise DocumentProcessingError(
                        "Image file too large", document_type="image", source=file_path
                    )
            except Exception:
                pass

            # بارگذاری تصویر
            image = Image.open(file_path)

            # استخراج متن با OCR
            extracted_text = await self._extract_text_with_ocr(image)
            normalized = self._normalize_text(extracted_text)

            # استخراج متادیتا
            metadata = await self._extract_image_metadata(image, file_path)
            # استانداردسازی متادیتا
            metadata.update(
                {
                    "file_name": getattr(image, "filename", None)
                    or file_path.split("/")[-1],
                    "file_ext": ext,
                    "loader": "OCRLoader",
                    "mime_type": self._guess_mime(ext, image),
                    "type": "image",
                    "source_type": "file",
                    "approx_chars": len(normalized),
                    "estimated_tokens": self._estimate_tokens(normalized),
                }
            )

            # تشخیص زبان (اختیاری - سه قطعه)
            lang = self._detect_language_voted(normalized)
            if lang:
                metadata["language"] = lang

            # ایجاد سند
            document = Document(
                text=normalized,
                metadata=metadata,
                source=file_path,
                document_type="image",
            )

            return document

        except (DocumentProcessingError, ValueError):
            raise
        except Exception as e:
            raise DocumentProcessingError(
                f"Failed to load OCR image: {e!s}",
                document_type="image",
                source=file_path,
            ) from e

    async def _extract_text_with_ocr(self, image: Image.Image) -> str:
        """استخراج متن با OCR"""
        # تنظیمات OCR
        config = f"--oem 3 --psm 6 -l {self.language}"

        # استخراج متن
        text = pytesseract.image_to_string(image, config=config)

        # تمیز کردن متن
        cleaned_text = self._clean_ocr_text(text)

        return cleaned_text

    def _clean_ocr_text(self, text: str) -> str:
        """تمیز کردن متن OCR"""
        # حذف خطوط خالی
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # حذف کاراکترهای غیرضروری / خطوط کوتاه (احتمالاً خطا)
        cleaned_lines = [line for line in lines if len(line) > 5]

        return "\n".join(cleaned_lines)

    def _normalize_text(self, text: str) -> str:
        try:
            import re as _re
            import unicodedata as _ud

            norm = _ud.normalize("NFC", text or "")
            norm = _re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", norm)
            norm = _re.sub(r"[ \t]+", " ", norm)
            norm = _re.sub(r"\n{3,}", "\n\n", norm)
            norm = _re.sub(r"\s*\n\s*", "\n", norm).strip()
            return norm
        except Exception:
            return text or ""

    async def _extract_image_metadata(
        self, image: Image.Image, file_path: str
    ) -> dict[str, Any]:
        """استخراج متادیتای تصویر"""
        metadata = {
            "source": file_path,
            "type": "image",
            "ocr_language": self.language,
            "image_width": image.width,
            "image_height": image.height,
            "image_mode": image.mode,
            "image_format": image.format,
        }

        # اضافه کردن EXIF data اگر موجود باشد
        if hasattr(image, "_getexif") and image._getexif():
            exif_data = image._getexif()
            metadata["exif_data"] = exif_data

        return metadata

    def _guess_mime(self, ext: str, image: Image.Image | None) -> str:
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp",
        }
        return mapping.get(
            ext, f"image/{(image.format or '').lower()}" if image else "image/unknown"
        )

    def _estimate_tokens(self, text: str) -> int:
        try:
            import tiktoken

            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = tiktoken.get_encoding(tiktoken.list_encoding_names()[0])
            return len(enc.encode(text))
        except Exception:
            return len(text.split())

    def _detect_language_voted(self, text: str) -> str | None:
        try:
            from langdetect import detect
        except Exception:
            return None
        try:
            n = len(text)
            if n == 0:
                return None
            chunks = [
                text[: min(2000, n)],
                text[max(0, n // 2 - 1000) : min(n, n // 2 + 1000)],
                text[max(0, n - 2000) :],
            ]
            votes: list[str] = []
            for ch in chunks:
                with contextlib.suppress(Exception):
                    if ch.strip():
                        votes.append(detect(ch))
            if not votes:
                return None
            from collections import Counter

            return Counter(votes).most_common(1)[0][0]
        except Exception:
            return None
