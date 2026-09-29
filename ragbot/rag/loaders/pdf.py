"""
PDF document loader using PyMuPDF.

This module provides functionality to extract text content from PDF files
with proper error handling and metadata extraction.
"""

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

    # Create a dummy fitz module for type annotations
    class _DummyFitz:
        class Document:
            pass

    fitz = _DummyFitz()

import contextlib

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders.base import BaseLoader, Document

if TYPE_CHECKING:
    from collections.abc import Callable

# Optional OCR dependencies
try:
    import pytesseract
    from PIL import Image

    PYOCR_AVAILABLE = True
except Exception:  # pragma: no cover - import guarded
    PYOCR_AVAILABLE = False


class PDFLoader(BaseLoader):
    """
    PDF document loader using PyMuPDF.

    This loader extracts text content from PDF files and provides
    metadata about the document structure and properties.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize PDF loader.

        Args:
            **kwargs: Configuration options including:
                - max_pages: Maximum number of pages to process
                - extract_images: Whether to extract image text (OCR)
                - password: PDF password if encrypted
                - ocr_engine: one of {"none","pytesseract","easyocr","google"}
                - ocr_lang: OCR language code (default: 'eng')
                - ocr_func: custom OCR function (bytes -> str)
                - google_token_path: path to OAuth token.json for Google OCR
        """
        super().__init__(**kwargs)

        # Allow operation in environments without PyMuPDF; we'll use a fallback if available

        self.max_pages = kwargs.get("max_pages", 1000)
        # Default to env-configured OCR settings if not provided
        self.extract_images = kwargs.get("extract_images", settings.rag.ocr_enabled)
        self.password = kwargs.get("password")
        # Optional OCR configuration
        self.ocr_lang: str = kwargs.get("ocr_lang", settings.rag.ocr_lang)
        # Injectable OCR function: Callable[[bytes], str]
        self.ocr_func: Callable[[bytes], str] | None = kwargs.get("ocr_func")
        self.ocr_engine: str = kwargs.get("ocr_engine", settings.rag.ocr_engine)
        self.google_token_path: str | None = kwargs.get(
            "google_token_path", settings.rag.google_token_path
        )

        # Structural extraction toggles (defaults from multi_format for consistency)
        try:
            self.enable_structural_extraction: bool = bool(
                kwargs.get(
                    "enable_structural_extraction",
                    getattr(
                        settings.multi_format, "html_enable_structural_extraction", True
                    ),
                )
            )
        except Exception:
            self.enable_structural_extraction = bool(
                kwargs.get("enable_structural_extraction", False)
            )
        try:
            self.inject_heading_markers: bool = bool(
                kwargs.get(
                    "inject_heading_markers",
                    getattr(settings.multi_format, "html_inject_heading_markers", True),
                )
            )
        except Exception:
            self.inject_heading_markers = bool(
                kwargs.get("inject_heading_markers", True)
            )
        try:
            self.detect_language_toggle: bool = bool(
                kwargs.get(
                    "detect_language",
                    getattr(settings.multi_format, "html_detect_language", True),
                )
            )
        except Exception:
            self.detect_language_toggle = bool(kwargs.get("detect_language", False))

    def validate_source(self, source: str) -> bool:
        """
        Validate if the source is a valid PDF file.

        Args:
            source: File path to validate

        Returns:
            bool: True if valid PDF file, False otherwise
        """
        if not isinstance(source, str):
            return False

        path = Path(source)

        # Check if file exists and has PDF extension
        if not path.exists() or not path.is_file():
            return False

        if path.suffix.lower() != ".pdf":
            return False

        # Check file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > settings.security.max_file_size_mb:
            logger.warning(
                f"PDF file too large: {file_size_mb:.1f}MB > {settings.security.max_file_size_mb}MB",
                file_path=source,
                file_size_mb=file_size_mb,
            )
            return False

        return True

    def get_supported_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return [".pdf"]

    async def load(self, source: str, **kwargs: Any) -> Document:
        """
        Load and extract text from a PDF file.

        Args:
            source: Path to the PDF file
            **kwargs: Additional options:
                - page_range: Tuple of (start, end) pages to extract
                - password: PDF password override

        Returns:
            Document: Loaded document with extracted text and metadata

        Raises:
            DocumentProcessingError: If PDF loading or processing fails
        """
        path = Path(source)
        if not path.exists():
            raise DocumentProcessingError(
                "File not found", document_type="pdf", source=source
            )
        if not self.validate_source(source):
            raise DocumentProcessingError(
                f"Invalid PDF source: {source}", document_type="pdf", source=source
            )
        # Reject empty files explicitly
        if path.stat().st_size == 0:
            raise DocumentProcessingError(
                "Failed to extract text: empty file", document_type="pdf", source=source
            )

        try:
            logger.info(f"Loading PDF document: {source}")

            # Extract password from kwargs or use default
            password = kwargs.get("password", self.password)
            page_range = kwargs.get("page_range")

            # Open PDF document (prefer PyMuPDF; fallback to pypdf if unavailable)
            doc = None
            if PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(source)
                except Exception as e:  # Normalize open failures
                    raise DocumentProcessingError(
                        f"Failed to extract text: {e!s}",
                        document_type="pdf",
                        source=source,
                        details=str(e),
                    ) from e
            else:
                try:
                    from pypdf import PdfReader

                    reader = PdfReader(source)
                    # Handle encryption with pypdf if needed
                    try:
                        if getattr(reader, "is_encrypted", False):
                            if not password:
                                raise DocumentProcessingError(
                                    "PDF is encrypted but no password provided",
                                    document_type="pdf",
                                    source=source,
                                )
                            ok = reader.decrypt(password)
                            if ok == 0:
                                raise DocumentProcessingError(
                                    "Invalid PDF password",
                                    document_type="pdf",
                                    source=source,
                                )
                    except Exception as dec_err:
                        raise DocumentProcessingError(
                            f"Failed to decrypt PDF: {dec_err}",
                            document_type="pdf",
                            source=source,
                            details=str(dec_err),
                        ) from dec_err

                    # Minimal metadata shim
                    class _DocShim:
                        def __init__(self, reader: PdfReader):
                            self.reader = reader
                            self.needs_pass = False
                            self.metadata: dict[str, Any] = {}
                            self.page_count = len(reader.pages)

                        def __getitem__(self, idx: int) -> Any:
                            return reader.pages[idx]

                        def close(self) -> None:
                            return None

                    doc = _DocShim(reader)
                except ModuleNotFoundError:
                    # Fallback without external libs: heuristic text extraction
                    raw_bytes = path.read_bytes()
                    import re

                    # Prefer text in parentheses (PDF string literals)
                    parts = re.findall(rb"\((.*?)\)", raw_bytes, flags=re.DOTALL)
                    decoded = [p.decode("latin1", errors="ignore") for p in parts]
                    full_text = "\n".join([t for t in decoded if t.strip()])
                    # If none found, try capturing BT...ET text blocks
                    if not full_text.strip():
                        blocks = re.findall(rb"BT(.*?)ET", raw_bytes, flags=re.DOTALL)
                        block_texts = [
                            b.decode("latin1", errors="ignore") for b in blocks
                        ]
                        full_text = "\n".join(
                            [t.strip() for t in block_texts if t.strip()]
                        )
                    if not full_text.strip():
                        raise DocumentProcessingError(
                            "Failed to extract text: unsupported or corrupted PDF",
                            document_type="pdf",
                            source=source,
                        ) from None
                    metadata = self._extract_fallback_metadata(source, len(full_text))
                    return Document(
                        text=full_text,
                        metadata=metadata,
                        source=source,
                        document_type="pdf",
                    )
                except Exception as e:
                    raise DocumentProcessingError(
                        f"Failed to extract text: {e!s}",
                        document_type="pdf",
                        source=source,
                        details=str(e),
                    ) from e

            # Handle encrypted PDFs
            if doc.needs_pass:
                if not password:
                    raise DocumentProcessingError(
                        "PDF is encrypted but no password provided",
                        document_type="pdf",
                        source=source,
                    )

                if not doc.authenticate(password):
                    raise DocumentProcessingError(
                        "Invalid PDF password", document_type="pdf", source=source
                    )

            # Extract metadata
            metadata = self._extract_metadata(doc, source)

            # Determine page range
            total_pages = doc.page_count
            if page_range:
                try:
                    start_page, end_page = int(page_range[0]), int(page_range[1])
                except Exception as e:
                    raise DocumentProcessingError(
                        f"Invalid page_range: {page_range}",
                        document_type="pdf",
                        source=source,
                        details=str(e),
                    ) from e
                start_page = max(0, min(start_page, total_pages - 1))
                end_page = min(end_page, total_pages)
                if end_page < start_page:
                    start_page, end_page = 0, min(total_pages, self.max_pages)
            else:
                start_page = 0
                end_page = min(total_pages, self.max_pages)

            # Optional processing timeout (seconds)
            timeout_sec = float(self.config.get("processing_timeout_sec", 0) or 0)
            start_time = None
            if timeout_sec > 0:
                import time as _t

                start_time = _t.time()

            # Extract text from pages
            text_content: list[str] = []
            # Track per-page text offsets to build precise page ranges
            page_offsets: list[dict[str, int]] = []
            cumulative_len = 0
            enable_struct = self.enable_structural_extraction and PYMUPDF_AVAILABLE
            inject_markers = bool(self.inject_heading_markers)
            headings: list[dict[str, Any]] = []
            for page_num in range(start_page, end_page):
                if start_time is not None:
                    import time as _t

                    if _t.time() - start_time > timeout_sec:
                        logger.warning(
                            "Processing timeout reached; aborting further pages",
                            page=page_num + 1,
                        )
                        break
                try:
                    page = doc[page_num]
                    if PYMUPDF_AVAILABLE:
                        # Allow override via config: text|blocks|raw (default: text)
                        mode = str(self.config.get("text_mode", "text")).lower()
                        if mode not in {"text", "blocks", "raw"}:
                            mode = "text"
                        page_text = page.get_text(mode)
                        if enable_struct:
                            try:
                                layout = page.get_text("dict") or {}
                                sizes: list[float] = []
                                spans_by_size: dict[float, list[dict[str, Any]]] = {}
                                for blk in layout.get("blocks", []) or []:
                                    for ln in blk.get("lines", []) or []:
                                        for sp in ln.get("spans", []) or []:
                                            s = float(sp.get("size", 0))
                                            if s > 0:
                                                sizes.append(s)
                                                spans_by_size.setdefault(s, []).append(
                                                    sp
                                                )
                                if sizes:
                                    # Dynamic body font estimation (median of spans)
                                    try:
                                        from statistics import median as _median

                                        body_pt = float(_median(sizes))
                                    except Exception:
                                        body_pt = float(sorted(sizes)[len(sizes) // 2])

                                    dynamic_headings: list[tuple[int, str]] = []

                                    def _span_level(
                                        sz: float,
                                        sp: dict[str, Any],
                                        body_pt: float = body_pt,
                                    ) -> int:
                                        # delta-based levels with simple boosters (bold/position)
                                        delta = float(sz) - body_pt
                                        flags = int(sp.get("flags", 0) or 0)
                                        is_bold = bool(flags)
                                        bbox = sp.get("bbox") or [0, 0, 0, 0]
                                        try:
                                            y_top = (
                                                float(bbox[1])
                                                if isinstance(bbox, list | tuple)
                                                and len(bbox) >= 2
                                                else 0.0
                                            )
                                        except Exception:
                                            y_top = 0.0
                                        # Heuristic boosts
                                        if is_bold:
                                            delta += 0.5
                                        if y_top <= 100.0:
                                            delta += 0.5
                                        if delta >= 8.0:
                                            return 1
                                        if delta >= 6.0:
                                            return 2
                                        if delta >= 4.0:
                                            return 3
                                        if delta >= 3.0:
                                            return 4
                                        return 0

                                    # First try dynamic scoring
                                    for sz, sps in spans_by_size.items():
                                        for sp in sps:
                                            lvl = _span_level(sz, sp)
                                            if lvl:
                                                txt = (sp.get("text") or "").strip()
                                                if not txt or len(txt) < 3:
                                                    continue
                                                headings.append(
                                                    {
                                                        "level": lvl,
                                                        "text": txt,
                                                        "page": page_num + 1,
                                                        "bbox": sp.get("bbox"),
                                                    }
                                                )
                                                dynamic_headings.append((lvl, txt))

                                    page_headings: list[tuple[int, str]] = (
                                        dynamic_headings
                                    )

                                    # Fallback/supplement: ensure up to 6 levels by distinct-size mapping
                                    if not page_headings or len(page_headings) < 6:
                                        uniq_sizes = sorted(set(sizes), reverse=True)
                                        level_map: dict[float, int] = {
                                            sz: idx
                                            for idx, sz in enumerate(
                                                uniq_sizes[:6], start=1
                                            )
                                        }
                                        existing = set(page_headings)
                                        for sz, level in level_map.items():
                                            for sp in spans_by_size.get(sz, []):
                                                txt = (sp.get("text") or "").strip()
                                                if not txt or len(txt) < 3:
                                                    continue
                                                key = (level, txt)
                                                if key in existing:
                                                    continue
                                                headings.append(
                                                    {
                                                        "level": level,
                                                        "text": txt,
                                                        "page": page_num + 1,
                                                        "bbox": sp.get("bbox"),
                                                    }
                                                )
                                                page_headings.append(key)
                                                existing.add(key)
                                                if len(page_headings) >= 6:
                                                    break
                                            if len(page_headings) >= 6:
                                                break
                                    if inject_markers and page_headings:
                                        marker_lines = []
                                        for lvl, txt in page_headings[:10]:
                                            prefix = "#" * min(max(lvl, 1), 6)
                                            marker_lines.append(f"{prefix} {txt}")
                                        page_text = (
                                            page_text + "\n\n" + "\n".join(marker_lines)
                                        )
                            except Exception as struct_err:
                                logger.debug(
                                    "PDF structural extraction failed",
                                    page=page_num + 1,
                                    error=str(struct_err),
                                )
                    else:
                        # pypdf fallback
                        page_text = page.extract_text() or ""

                    if page_text.strip():
                        # record start offset for this page before appending
                        page_offsets.append(
                            {"page": page_num + 1, "start": cumulative_len}
                        )
                        text_content.append(page_text)
                        cumulative_len += len(page_text)
                        # account for the separator that will be added later (\n\n)
                        cumulative_len += 2

                    # Extract image text if enabled (basic OCR placeholder)
                    if self.extract_images and PYMUPDF_AVAILABLE:
                        image_list = page.get_images() or []
                        if image_list:
                            logger.debug(
                                f"Found {len(image_list)} images on page {page_num + 1}",
                                page=page_num + 1,
                                image_count=len(image_list),
                            )
                            # Try OCR if configured
                            max_ocr_images = int(
                                self.config.get("max_ocr_images_per_page", 3)
                            )
                            min_w = int(self.config.get("min_ocr_image_width", 0))
                            min_h = int(self.config.get("min_ocr_image_height", 0))
                            for im in image_list[:max_ocr_images]:
                                try:
                                    xref = im[0]
                                    img_info = doc.extract_image(xref)
                                    img_bytes = img_info.get("image", b"")
                                    if not img_bytes:
                                        continue
                                    # Filter by minimal dimensions if provided
                                    try:
                                        w = int(img_info.get("width", 0))
                                        h = int(img_info.get("height", 0))
                                        if (min_w and w < min_w) or (
                                            min_h and h < min_h
                                        ):
                                            continue
                                    except Exception:
                                        pass
                                    ocr_text = self._perform_ocr(img_bytes)
                                    if ocr_text and ocr_text.strip():
                                        text_content.append(ocr_text.strip())
                                except Exception as ocr_err:
                                    logger.debug(
                                        "OCR extraction failed",
                                        page=page_num + 1,
                                        error=str(ocr_err),
                                    )

                except Exception as e:
                    logger.warning(
                        f"Error processing page {page_num + 1}: {e}",
                        page=page_num + 1,
                        error=str(e),
                    )
                    continue

            with contextlib.suppress(Exception):
                doc.close()

            # Combine all text
            full_text = "\n\n".join(text_content)
            # Fix last separator accounting
            if page_offsets:
                try:
                    # end = length of full_text for last page
                    page_offsets[-1]["end"] = len(full_text)
                    # compute end for intermediate pages based on next start
                    for i in range(len(page_offsets) - 1):
                        page_offsets[i]["end"] = (
                            page_offsets[i + 1]["start"] - 2
                        )  # subtract separator length
                except Exception:
                    pass

            # Handle empty PDF case - try heuristic then raise
            if not full_text.strip():
                # Try a minimal heuristic extraction for simple PDFs
                try:
                    raw_bytes = path.read_bytes()
                    # Very naive extraction of strings between parentheses in content streams
                    import re

                    candidates = re.findall(rb"\((.*?)\)", raw_bytes, flags=re.DOTALL)

                    def _decode_pdf_candidate(candidate: bytes) -> str:
                        """Decode a PDF string literal using deterministic fallbacks."""
                        try:
                            return candidate.decode("utf-8")
                        except UnicodeDecodeError:
                            try:
                                return candidate.decode("utf-16")
                            except UnicodeDecodeError:
                                return candidate.decode("latin1", errors="ignore")

                    decoded = [_decode_pdf_candidate(c) for c in candidates]
                    heuristic_text = "\n".join(s for s in decoded if s.strip())
                    # Also try capturing between BT ... ET blocks if parentheses not found
                    if not heuristic_text.strip():
                        blocks = re.findall(rb"BT(.*?)ET", raw_bytes, flags=re.DOTALL)
                        block_texts = [
                            b.decode("latin1", errors="ignore") for b in blocks
                        ]
                        heuristic_text = "\n".join(
                            [t.strip() for t in block_texts if t.strip()]
                        )
                    if heuristic_text.strip():
                        full_text = heuristic_text
                        extraction_method = "heuristic"
                    else:
                        raise DocumentProcessingError(
                            "Failed to extract text: no content",
                            document_type="pdf",
                            source=source,
                        )
                except Exception as e:
                    raise DocumentProcessingError(
                        "Failed to extract text: unreadable content",
                        document_type="pdf",
                        source=source,
                        details=str(e),
                    ) from e
            else:
                extraction_method = "pymupdf" if PYMUPDF_AVAILABLE else "pypdf"

            # Optional language detection (majority vote over three segments)
            lang = None
            try:
                if self.detect_language_toggle:
                    try:
                        from langdetect import detect

                        votes = []
                        segments = [
                            full_text[:2000],
                            full_text[len(full_text) // 2 : len(full_text) // 2 + 2000],
                            full_text[-2000:],
                        ]
                        for seg in segments:
                            with contextlib.suppress(Exception):
                                if seg and seg.strip():
                                    votes.append(detect(seg))
                        if votes:
                            from collections import Counter as _Ctr

                            lang = _Ctr(votes).most_common(1)[0][0]
                    except Exception:
                        lang = None
            except Exception:
                lang = None

            # Update metadata with extraction info
            metadata.update(
                {
                    "pages_processed": end_page - start_page,
                    "total_pages": total_pages,
                    "text_length": len(full_text),
                    "extraction_method": extraction_method,
                    # Standardized keys for downstream components
                    "source_type": "pdf",
                    "mime_type": "application/pdf",
                    "language": lang if lang else metadata.get("language"),
                    "pdf_version": getattr(self, "_pdf_header_version", None),
                    "source_dir": str(Path(source).parent),
                    "absolute_path": str(Path(source).resolve()),
                    "headings": headings,
                    "structure_summary": {"heading_count": len(headings)},
                    # precise page ranges for chunkers
                    "page_ranges": page_offsets,
                }
            )

            logger.info(
                f"Successfully loaded PDF: {len(full_text)} characters from {end_page - start_page} pages",
                source=source,
                pages_processed=end_page - start_page,
                text_length=len(full_text),
            )

            return Document(
                text=full_text, metadata=metadata, source=source, document_type="pdf"
            )

        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading PDF: {e}", source=source)
            raise DocumentProcessingError(
                f"Failed to extract text: {e!s}",
                document_type="pdf",
                source=source,
                details=str(e),
            ) from e

    def _extract_metadata(self, doc: fitz.Document, source: str) -> dict[str, Any]:
        """
        Extract metadata from PDF document.

        Args:
            doc: PyMuPDF document object
            source: Source file path

        Returns:
            Dict[str, Any]: Extracted metadata
        """
        try:
            # Get PDF metadata
            pdf_metadata = doc.metadata

            # Get file stats
            file_path = Path(source)
            file_stats = file_path.stat()

            metadata = {
                # PDF-specific metadata
                "title": pdf_metadata.get("title", ""),
                "author": pdf_metadata.get("author", ""),
                "subject": pdf_metadata.get("subject", ""),
                "creator": pdf_metadata.get("creator", ""),
                "producer": pdf_metadata.get("producer", ""),
                "creation_date": pdf_metadata.get("creationDate", ""),
                "modification_date": pdf_metadata.get("modDate", ""),
                # File metadata
                "file_name": file_path.name,
                "file_size": file_stats.st_size,
                "file_modified": file_stats.st_mtime,
                # Document structure
                "page_count": doc.page_count,
                "is_encrypted": doc.needs_pass,
                "is_pdf": True,
                # Processing metadata
                "loader": "PDFLoader",
                "loader_version": "1.0.0",
            }

            # Clean up empty string values
            metadata = {k: v for k, v in metadata.items() if v != ""}

            return metadata

        except Exception as e:
            logger.warning(f"Error extracting PDF metadata: {e}")
            return {
                "file_name": Path(source).name,
                "loader": "PDFLoader",
                "metadata_error": str(e),
            }

    def _extract_fallback_metadata(
        self, source: str, text_length: int
    ) -> dict[str, Any]:
        """Provide minimal metadata when no PDF parser is available."""
        file_path = Path(source)
        file_stats = file_path.stat()
        return {
            "file_name": file_path.name,
            "file_size": file_stats.st_size,
            "file_modified": file_stats.st_mtime,
            "page_count": 1,
            "is_encrypted": False,
            "is_pdf": True,
            "loader": "PDFLoader",
            "loader_version": "1.0.0",
            "pages_processed": 1,
            "total_pages": 1,
            "text_length": text_length,
            "extraction_method": "heuristic",
        }

    def _perform_ocr(self, img_bytes: bytes) -> str:
        """Perform OCR on image bytes based on configured engine.

        Order of precedence:
        - Custom ocr_func if provided
        - ocr_engine selection: pytesseract, easyocr, google
        - Otherwise returns empty string
        """
        # Custom OCR function has highest priority
        if self.ocr_func:
            try:
                return self.ocr_func(img_bytes) or ""
            except Exception as e:  # pragma: no cover - safety net
                logger.debug("Custom OCR failed", error=str(e))
                return ""

        engine = (self.ocr_engine or "none").lower()
        if engine == "pytesseract":
            if not PYOCR_AVAILABLE:
                return ""
            try:
                with Image.open(io.BytesIO(img_bytes)) as pil_img:
                    return (
                        pytesseract.image_to_string(pil_img, lang=self.ocr_lang) or ""
                    )
            except Exception as e:  # pragma: no cover - robustness
                logger.debug("pytesseract OCR failed", error=str(e))
                return ""
        elif engine == "easyocr":
            try:  # Guard import and call
                import importlib

                easyocr = importlib.import_module("easyocr")
                # Cache reader instance on self to avoid heavy re-init
                cached_reader = getattr(self, "_easyocr_reader", None)
                if cached_reader is None:
                    cached_reader = easyocr.Reader([self.ocr_lang], gpu=False)
                    self._easyocr_reader = cached_reader
                reader = cached_reader
                # Most easyocr usages accept a file path or numpy array; in tests we mock readtext
                results = reader.readtext(img_bytes)
                # Results often are [(bbox, text, conf), ...]
                texts = []
                for item in results or []:
                    if isinstance(item, list | tuple) and len(item) >= 2:
                        texts.append(str(item[1]))
                    else:
                        texts.append(str(item))
                return "\n".join([t for t in texts if t])
            except Exception as e:  # pragma: no cover - robustness
                logger.debug("easyocr OCR failed", error=str(e))
                return ""
        elif engine == "google":
            try:
                return self._ocr_google(img_bytes)
            except Exception as e:  # pragma: no cover - robustness
                logger.debug("google OCR failed", error=str(e))
                return ""
        return ""

    def _ocr_google(self, img_bytes: bytes) -> str:
        """OCR using Google Drive via googleapiclient.

        Requires a valid OAuth user token at google_token_path with Drive scope.
        """
        from tempfile import NamedTemporaryFile

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except Exception as e:  # pragma: no cover - import guard
            logger.debug("googleapiclient not available", error=str(e))
            return ""

        token_path = self.google_token_path or "token.json"
        creds = Credentials.from_authorized_user_file(
            token_path, ["https://www.googleapis.com/auth/drive"]
        )
        drive = build("drive", "v3", credentials=creds)

        with NamedTemporaryFile(suffix=".jpg", delete=True) as tmp:
            tmp.write(img_bytes)
            tmp.flush()
            media = MediaFileUpload(tmp.name, mimetype="image/jpeg")
            file = (
                drive.files()
                .create(
                    media_body=media,
                    body={
                        "name": "ocr-doc",
                        "mimeType": "application/vnd.google-apps.document",
                    },
                    fields="id",
                )
                .execute()
            )
            doc_id = file.get("id")
            if not doc_id:
                return ""
            txt = (
                drive.files()
                .export(fileId=doc_id, mimeType="text/plain")
                .execute()
                .decode("utf-8")
            )
            # Cleanup: best-effort delete created doc
            with contextlib.suppress(Exception):
                drive.files().delete(fileId=doc_id).execute()
            return txt or ""
