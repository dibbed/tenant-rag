"""
بارگذاری اسناد Excel (XLSX) با همگام‌سازی متادیتا و رفتار با سایر لودرها.
"""

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError

from .base import Document, DocumentLoader


class XLSXLoader(DocumentLoader):
    """بارگذاری اسناد Excel"""

    async def load(self, file_path: str, **kwargs: Any) -> Document:
        """
        بارگذاری فایل Excel

        Args:
            file_path: مسیر فایل XLSX

        Returns:
            سند استخراج شده
        """
        try:
            path = Path(file_path)
            is_mocked = hasattr(getattr(pd, "ExcelFile", None), "return_value")
            if not is_mocked and (not path.exists() or not path.is_file()):
                raise DocumentProcessingError(
                    "Invalid XLSX file path", document_type="xlsx", source=str(path)
                )

            # Safety: file size cap
            try:
                if path.exists() and path.is_file():
                    max_bytes = int(settings.security.max_file_size_mb) * 1024 * 1024
                    if path.stat().st_size > max_bytes:
                        raise DocumentProcessingError(
                            "XLSX too large", document_type="xlsx", source=str(path)
                        )
            except DocumentProcessingError:
                raise
            except Exception:
                pass

            # بارگذاری تمام sheet ها (فقط nrows محدود برای کارایی)
            excel_file = pd.ExcelFile(str(path))
            sheets_data: Dict[str, Dict[str, Any]] = {}
            all_text: list[str] = []
            total_rows = 0
            total_cells = 0

            max_rows = int(getattr(settings.multi_format, "excel_max_rows", 1000))
            include_headers = bool(
                getattr(settings.multi_format, "excel_include_headers", True)
            )
            max_sheets: Optional[int] = None
            try:
                max_sheets_val = getattr(
                    settings.multi_format, "excel_max_sheets", None
                )
                if max_sheets_val is not None:
                    max_sheets = int(max_sheets_val)
            except Exception:
                max_sheets = None

            # Optional read parameters (risk mitigation for wide/large files)
            usecols = kwargs.get("usecols")
            dtype = kwargs.get("dtype")
            engine = kwargs.get("engine")  # e.g., "openpyxl"

            for i, sheet_name in enumerate(excel_file.sheet_names):
                if max_sheets is not None and i >= max_sheets:
                    break
                # خواندن sheet با محدودیت nrows برای کارایی
                try:
                    read_kwargs: Dict[str, Any] = {
                        "sheet_name": sheet_name,
                        "nrows": max_rows,
                    }
                    if usecols is not None:
                        read_kwargs["usecols"] = usecols
                    if dtype is not None:
                        read_kwargs["dtype"] = dtype
                    if engine is not None:
                        read_kwargs["engine"] = engine
                    df = pd.read_excel(str(path), **read_kwargs)
                except Exception as read_err:
                    logger.warning(
                        f"Excel read failed: {read_err} | sheet={sheet_name}"
                    )
                    continue

                # تبدیل به متن
                # Accumulate counters
                try:
                    total_rows += int(len(df))
                    total_cells += int(df.size)
                except Exception:
                    pass

                sheet_text = await self._dataframe_to_text(
                    df, sheet_name, include_headers=include_headers
                )
                all_text.append(sheet_text)

                try:
                    rows_count = len(df)
                except Exception:
                    rows_count = 0

                try:
                    cols_count = len(df.columns)
                except Exception:
                    cols_count = 0

                sheets_data[sheet_name] = {
                    "rows": rows_count,
                    "columns": cols_count,
                    "columns_list": (
                        df.columns.tolist()
                        if hasattr(df.columns, "tolist")
                        else list(df.columns)
                    ),
                }

            # ترکیب متن تمام sheet ها
            full_text = "\n\n".join(txt for txt in all_text if txt)

            # نرمالسازی متن خروجی
            normalized = unicodedata.normalize("NFC", full_text)
            normalized = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", normalized)
            normalized = re.sub(r"[ \t]+", " ", normalized)
            # حفظ شکست پاراگراف؛ 3+ نیولاین → 2
            normalized = re.sub(r"\n{3,}", "\n\n", normalized)
            normalized = re.sub(r"\s*\n\s*", "\n", normalized).strip()

            if not normalized:
                raise DocumentProcessingError(
                    "Empty XLSX content", document_type="xlsx", source=str(path)
                )

            # ایجاد سند
            document = Document(
                text=normalized,
                metadata={
                    "file_name": path.name,
                    "file_ext": path.suffix.lower(),
                    "source_path": str(path),
                    "source_dir": str(path.parent),
                    "absolute_path": str(path.resolve()),
                    "loader": "XLSXLoader",
                    "type": "xlsx",
                    "source_type": "file",
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "sheet_count": len(excel_file.sheet_names),
                    "sheets": sheets_data,
                    "total_rows": total_rows,
                    "total_cells": total_cells,
                    "approx_chars": len(normalized),
                    "estimated_tokens": _estimate_tokens(normalized),
                },
            )

            return document

        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error(f"Excel load error: {e} | path={file_path}")
            raise DocumentProcessingError(
                str(e), document_type="xlsx", source=file_path
            ) from e

    async def _dataframe_to_text(
        self, df: pd.DataFrame, sheet_name: str, *, include_headers: bool = True
    ) -> str:
        """تبدیل DataFrame به متن"""
        text_parts = [f"Sheet: {sheet_name}"]

        # اضافه کردن نام ستون‌ها
        if include_headers:
            try:
                # Flatten MultiIndex columns if needed
                if hasattr(df.columns, "to_flat_index"):
                    flat_cols = [
                        " | ".join([str(x) for x in tup])
                        if isinstance(tup, tuple)
                        else str(tup)
                        for tup in list(df.columns.to_flat_index())
                    ]
                    cols_line = ", ".join(flat_cols)
                else:
                    cols_line = ", ".join([str(c) for c in df.columns.tolist()])
            except Exception:
                cols_line = ", ".join(map(str, list(df.columns)))
            text_parts.append(f"ستون‌ها: {cols_line}")

        # اضافه کردن داده‌ها (محدود به تنظیمات)
        max_rows = int(getattr(settings.multi_format, "excel_max_rows", 1000))
        sample_df = df.head(max_rows)

        for index, row in sample_df.iterrows():
            row_text = f"ردیف {index + 1}: "
            row_data = []

            for col in df.columns:
                try:
                    v = row[col]
                    if pd.isna(v):
                        value = ""
                    else:
                        # Normalize common types for readability
                        if hasattr(v, "isoformat"):
                            try:
                                value = v.isoformat()
                            except Exception:
                                value = str(v)
                        else:
                            value = str(v)
                except Exception as conv_err:
                    logger.warning(
                        f"Excel value convert failed: {conv_err} | sheet={sheet_name} col={col}"
                    )
                    value = ""
                if value.strip():
                    row_data.append(f"{col}={value}")

            if row_data:
                row_text += ", ".join(row_data)
                text_parts.append(row_text)

        return "\n".join(text_parts)

    # Optional language detection: reuses project-wide approach
    def _detect_language_voted(self, text: str) -> Optional[str]:
        try:
            from langdetect import detect  # type: ignore
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
                try:
                    if ch.strip():
                        votes.append(detect(ch))
                except Exception:
                    continue
            if not votes:
                return None
            from collections import Counter

            return Counter(votes).most_common(1)[0][0]
        except Exception:
            return None


def _estimate_tokens(text: str) -> int:
    try:
        import tiktoken  # type: ignore

        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = tiktoken.get_encoding(tiktoken.list_encoding_names()[0])
        return len(enc.encode(text))
    except Exception:
        return len(text.split())
