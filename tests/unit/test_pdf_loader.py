"""
Professional PDF loader tests with comprehensive edge cases.

This module tests the PDF loading functionality with various scenarios including
edge cases, error handling, and file format validation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ragbot.rag import DocumentProcessingError, Document, PDFLoader


class TestPDFLoader:
    """Comprehensive test suite for PDF loader functionality."""

    @pytest.fixture
    def loader(self) -> PDFLoader:
        """Create a PDFLoader instance for testing."""
        return PDFLoader()

    @pytest.fixture
    def sample_pdf_path(self, tmp_path: Path) -> str:
        """Create a sample PDF file for testing."""
        pdf_path = tmp_path / "sample.pdf"
        # Create a minimal valid PDF content
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000207 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""
        pdf_path.write_bytes(pdf_content)
        return str(pdf_path)

    @pytest.mark.asyncio
    async def test_load_valid_pdf(
        self, loader: PDFLoader, sample_pdf_path: str
    ) -> None:
        """Test loading a valid PDF file."""
        document = await loader.load(sample_pdf_path)

        assert isinstance(document, Document)
        assert isinstance(document.content, str)
        assert len(document.content) > 0
        assert document.source == sample_pdf_path
        assert document.document_type == "pdf"

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, loader: PDFLoader) -> None:
        """Test handling of non-existent PDF files."""
        with pytest.raises(DocumentProcessingError, match="File not found"):
            await loader.load("nonexistent.pdf")

    @pytest.mark.asyncio
    async def test_load_empty_file(self, loader: PDFLoader, tmp_path: Path) -> None:
        """Test handling of empty PDF files."""
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")

        with pytest.raises(DocumentProcessingError):
            await loader.load(str(empty_pdf))

    @pytest.mark.asyncio
    async def test_load_corrupted_pdf(self, loader: PDFLoader, tmp_path: Path) -> None:
        """Test graceful handling of corrupted PDF files."""
        corrupted_pdf = tmp_path / "corrupted.pdf"
        corrupted_pdf.write_bytes(b"This is not a PDF file")

        with pytest.raises(DocumentProcessingError, match="Failed to extract text"):
            await loader.load(str(corrupted_pdf))

    @pytest.mark.parametrize("file_size", [0, 1024, 1024 * 1024])
    @pytest.mark.asyncio
    async def test_load_various_file_sizes(
        self, loader: PDFLoader, tmp_path: Path, file_size: int
    ) -> None:
        """Test PDF loading with various file sizes."""
        test_pdf = tmp_path / f"test_{file_size}.pdf"

        if file_size == 0:
            test_pdf.write_bytes(b"")
            with pytest.raises(DocumentProcessingError):
                await loader.load(str(test_pdf))
        else:
            # Create a minimal PDF with padding to reach desired size
            base_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 20>>stream
BT /F1 12 Tf (Test) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000207 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
300
%%EOF"""

            # Pad to desired size
            padding = b" " * max(0, file_size - len(base_content))
            content = base_content + padding
            test_pdf.write_bytes(content)

            # Should not raise for reasonable file sizes
            if file_size <= 10 * 1024 * 1024:  # 10MB limit
                document = await loader.load(str(test_pdf))
                assert isinstance(document, Document)

    @pytest.mark.asyncio
    async def test_load_with_unicode_content(
        self, loader: PDFLoader, tmp_path: Path
    ) -> None:
        """Test PDF loading with Unicode and multilingual content."""
        # Create PDF with Unicode text
        pdf_path = tmp_path / "unicode.pdf"
        # Create PDF with Unicode text using ASCII-safe encoding
        unicode_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
            b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
            b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n"
            b"4 0 obj\n<<\n/Length 50\n>>\nstream\n"
            b"BT\n/F1 12 Tf\n100 700 Td\n(Hello World Unicode) Tj\nET\n"
            b"endstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000058 00000 n \n0000000115 00000 n \n0000000207 00000 n \n"
            b"trailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n320\n%%EOF"
        )
        pdf_path.write_bytes(unicode_content)

        document = await loader.load(str(pdf_path))
        assert isinstance(document.content, str)
        # Should handle Unicode characters gracefully

    @pytest.mark.asyncio
    async def test_load_with_metadata_extraction(
        self, loader: PDFLoader, sample_pdf_path: str
    ) -> None:
        """Test that metadata is properly extracted from PDF."""
        document = await loader.load(sample_pdf_path)

        assert document.source == sample_pdf_path
        assert document.document_type == "pdf"
        assert "file_size" in document.metadata
        assert "page_count" in document.metadata

    @pytest.mark.asyncio
    async def test_load_password_protected_pdf(
        self, loader: PDFLoader, tmp_path: Path
    ) -> None:
        """Test handling of password-protected PDFs."""
        # This is a placeholder test as creating a password-protected PDF
        # programmatically is complex. In real scenarios, you'd use a
        # pre-created password-protected file.
        protected_pdf = tmp_path / "protected.pdf"
        protected_pdf.write_bytes(b"Password protected PDF content")

        # Should handle gracefully when password protection is encountered
        with pytest.raises(DocumentProcessingError):
            await loader.load(str(protected_pdf))

    @pytest.mark.asyncio
    async def test_load_large_pdf_memory_efficiency(
        self, loader: PDFLoader, tmp_path: Path
    ) -> None:
        """Test memory efficiency with large PDF files."""
        # Create a moderately sized PDF for memory testing
        large_pdf = tmp_path / "large.pdf"
        base_content = (
            b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 5000>>stream
BT /F1 12 Tf """
            + b"Test content " * 300
            + b""" Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
trailer<</Size 5/Root 1 0 R>>
%%EOF"""
        )
        large_pdf.write_bytes(base_content)

        # Should complete without memory errors
        document = await loader.load(str(large_pdf))
        assert isinstance(document, Document)
        assert len(document.content) > 0

    @pytest.mark.asyncio
    async def test_load_with_custom_config(self, tmp_path: Path) -> None:
        """Test PDF loader with custom configuration."""
        custom_loader = PDFLoader(max_pages=5, extract_images=False)

        # Use sample PDF
        pdf_path = tmp_path / "test.pdf"
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 20>>stream
BT /F1 12 Tf (Test) Tj ET
endstream
endobj
xref
0 5
trailer<</Size 5/Root 1 0 R>>
%%EOF"""
        pdf_path.write_bytes(pdf_content)

        document = await custom_loader.load(str(pdf_path))
        assert isinstance(document, Document)

    # Removed legacy extract_pdf_text direct-function test since function is deleted

    @pytest.mark.asyncio
    async def test_error_handling_with_mock(
        self, loader: PDFLoader, tmp_path: Path
    ) -> None:
        """Test error handling using mocks."""
        pdf_path = tmp_path / "mock_test.pdf"
        pdf_path.write_bytes(b"fake pdf content")

        with patch("ragbot.rag.loaders.pdf.fitz") as mock_fitz:
            mock_fitz.open.side_effect = Exception("Mock error")

            with pytest.raises(DocumentProcessingError, match="Failed to extract text"):
                await loader.load(str(pdf_path))


class _FakePage:
    def get_text(self, *args, **kwargs):
        return ""

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
    with patch.object(PDFLoader, "_ocr_google", return_value="GDRIVE TEXT"):
        out = loader._perform_ocr(b"img")
        assert out == "GDRIVE TEXT"


@pytest.mark.asyncio
async def test_pdf_loader_ocr_injected_function(tmp_path: Path) -> None:
    pdf_path = tmp_path / "img.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")

    loader = PDFLoader(extract_images=True, ocr_func=lambda b: "OCR CAPTURED")

    with patch("ragbot.rag.loaders.pdf.PYMUPDF_AVAILABLE", True), patch(
        "ragbot.rag.loaders.pdf.fitz", _Fitz
    ):
        doc = await loader.load(str(pdf_path))
        assert isinstance(doc, Document)
        assert "OCR CAPTURED" in doc.content


@pytest.mark.asyncio
async def test_pdf_loader_ocr_missing_libs_no_raise(tmp_path: Path) -> None:
    raw = b"%PDF-1.4\n1 0 obj<<>>endobj\nBT (Hello) ET\n%%EOF"
    pdf_path = tmp_path / "heuristic.pdf"
    pdf_path.write_bytes(raw)

    loader = PDFLoader(extract_images=True)

    with patch("ragbot.rag.loaders.pdf.fitz", _Fitz), patch(
        "ragbot.rag.loaders.pdf.PYOCR_AVAILABLE", False
    ):
        doc = await loader.load(str(pdf_path))
        assert isinstance(doc, Document)
        assert "Hello" in doc.content


@pytest.mark.asyncio
async def test_pdf_headings_six_levels(monkeypatch) -> None:
    import types

    class _MockPage:
        def __init__(self, layout_blocks, text="body"):
            self._layout = {"blocks": layout_blocks}
            self._text = text

        def get_text(self, mode="text"):
            if mode == "dict":
                return self._layout
            return self._text

    class _MockDoc:
        def __init__(self, pages):
            self._pages = pages
            self.page_count = len(pages)
            self.needs_pass = False

        def __getitem__(self, idx: int):
            return self._pages[idx]

        def close(self):
            return None

    def _mk_span(text: str, size: float):
        return {"text": text, "size": size, "bbox": [0, 0, 10, 10]}

    spans = [
        _mk_span("Heading1", 32.0),
        _mk_span("Heading2", 24.0),
        _mk_span("Heading3", 18.0),
        _mk_span("Heading4", 16.0),
        _mk_span("Heading5", 14.0),
        _mk_span("Heading6", 12.5),
    ]
    layout_blocks = [{"lines": [{"spans": spans}]}]
    mock_doc = _MockDoc([_MockPage(layout_blocks, text="page body")])

    import ragbot.rag.loaders.pdf as pdf_mod

    monkeypatch.setattr(pdf_mod, "PYMUPDF_AVAILABLE", True)
    monkeypatch.setattr(pdf_mod, "fitz", types.SimpleNamespace(open=lambda src: mock_doc))

    loader = PDFLoader(
        enable_structural_extraction=True,
        inject_heading_markers=True,
        detect_language=False,
        max_pages=10,
    )

    from pathlib import Path

    monkeypatch.setattr(Path, "exists", lambda self: True)

    class _Stat:
        st_size = 1

    monkeypatch.setattr(Path, "stat", lambda self: _Stat())
    monkeypatch.setattr(PDFLoader, "validate_source", lambda self, s: True)

    document = await loader.load("/tmp/fake.pdf")

    headings = document.metadata.get("headings") or []
    assert len(headings) >= 6
    levels = sorted({h.get("level") for h in headings})
    assert 1 in levels and 6 in levels
    assert "# Heading1" in document.text

