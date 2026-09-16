"""
Tests for OCR engine selection in PDFLoader.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ragbot.rag.loaders.pdf import PDFLoader
from ragbot.rag.loaders.base import Document


class _FakePage:
    def get_text(self):
        return ""  # Force OCR to be used

    def get_images(self):
        return [(1,)]


class _FakeDoc:
    def __init__(self):
        self.needs_pass = False
        self.metadata = {}
        self.page_count = 1

    def __getitem__(self, idx: int):
        return _FakePage()

    def extract_image(self, xref: int):
        return {"image": b"image-bytes"}

    def close(self):
        return None


class _Fitz:
    @staticmethod
    def open(path: str):
        return _FakeDoc()


@pytest.mark.asyncio
async def test_engine_custom_func(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF")
    loader = PDFLoader(extract_images=True, ocr_engine="pytesseract", ocr_func=lambda b: "CUSTOM")
    with patch("ragbot.rag.loaders.pdf.PYMUPDF_AVAILABLE", True), patch(
        "ragbot.rag.loaders.pdf.fitz", _Fitz
    ):
        doc = await loader.load(str(path))
        assert isinstance(doc, Document)
        assert "CUSTOM" in doc.content


def test_engine_pytesseract_perform_ocr() -> None:
    loader = PDFLoader(extract_images=True, ocr_engine="pytesseract")
    fake_pyt = MagicMock()
    fake_pyt.image_to_string.return_value = "TESS TEXT"
    with patch("ragbot.rag.loaders.pdf.PYOCR_AVAILABLE", True), patch(
        "ragbot.rag.loaders.pdf.pytesseract", fake_pyt, create=True
    ), patch("ragbot.rag.loaders.pdf.Image", MagicMock(), create=True) as mock_image:
        mock_image.open.return_value.__enter__.return_value = MagicMock()
        out = loader._perform_ocr(b"img")
        assert out == "TESS TEXT"


def test_engine_easyocr_perform_ocr() -> None:
    loader = PDFLoader(extract_images=True, ocr_engine="easyocr")

    class _Reader:
        def __init__(self, langs, gpu=False):
            pass

        def readtext(self, inp):
            return [([0, 0, 1, 1], "EASY", 0.9)]

    fake_easyocr = MagicMock()
    fake_easyocr.Reader = _Reader

    with patch("importlib.import_module", return_value=fake_easyocr):
        out = loader._perform_ocr(b"img")
        assert out == "EASY"


def test_engine_google_perform_ocr() -> None:
    loader = PDFLoader(extract_images=True, ocr_engine="google", google_token_path="token.json")

    class _FakeFiles:
        def __init__(self):
            self._id = {"id": "123"}

        def create(self, media_body=None, body=None, fields=None):
            class _Exec:
                def execute(self):
                    return {"id": "123"}

            return _Exec()

        def export(self, fileId=None, mimeType=None):
            class _Exec:
                def execute(self):
                    return b"GDRIVE TEXT"

            return _Exec()

    class _Drive:
        def files(self):
            return _FakeFiles()

    class _Creds:
        @staticmethod
        def from_authorized_user_file(path, scopes):
            return object()

    with patch.object(PDFLoader, "_ocr_google", return_value="GDRIVE TEXT"):
        out = loader._perform_ocr(b"img")
        assert out == "GDRIVE TEXT"
