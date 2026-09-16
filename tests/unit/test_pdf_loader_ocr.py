"""
OCR-related tests for PDFLoader.

These tests verify that when OCR is enabled, PDFLoader can incorporate
text extracted from images. The OCR function is injected to avoid
external Tesseract dependencies.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ragbot.rag.loaders.pdf import PDFLoader
from ragbot.rag.loaders.base import Document


class _FakePage:
    def get_text(self):
        return ""  # Force OCR/heuristic paths

    def get_images(self):
        # Return a list of tuples where first item is xref
        return [(123,)]


class _FakeDoc:
    def __init__(self):
        self.needs_pass = False
        self.metadata = {}
        self.page_count = 1

    def __getitem__(self, idx: int):
        return _FakePage()

    def extract_image(self, xref: int):
        return {"image": b"fake-image-bytes"}

    def close(self):
        return None


class _FakeFitz:
    @staticmethod
    def open(path: str):
        return _FakeDoc()


@pytest.mark.asyncio
async def test_pdf_loader_ocr_injected_function(tmp_path: Path) -> None:
    # Create a minimal PDF so file exists for validation
    pdf_path = tmp_path / "img.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")

    loader = PDFLoader(extract_images=True, ocr_func=lambda b: "OCR CAPTURED")

    with patch("ragbot.rag.loaders.pdf.PYMUPDF_AVAILABLE", True):
        with patch("ragbot.rag.loaders.pdf.fitz", _FakeFitz):
            doc = await loader.load(str(pdf_path))
            assert isinstance(doc, Document)
            assert "OCR CAPTURED" in doc.content


@pytest.mark.asyncio
async def test_pdf_loader_ocr_missing_libs_no_raise(tmp_path: Path) -> None:
    # PDF with a parenthesized string so heuristic fallback can find text
    raw = b"%PDF-1.4\n1 0 obj<<>>endobj\nBT (Hello) ET\n%%EOF"
    pdf_path = tmp_path / "heuristic.pdf"
    pdf_path.write_bytes(raw)

    loader = PDFLoader(extract_images=True)  # no ocr_func provided

    with patch("ragbot.rag.loaders.pdf.fitz", _FakeFitz):
        # Force OCR lib marker off in module scope
        with patch("ragbot.rag.loaders.pdf.PYOCR_AVAILABLE", False):
            doc = await loader.load(str(pdf_path))
            assert isinstance(doc, Document)
            # Heuristic extraction should pick up 'Hello'
            assert "Hello" in doc.content
