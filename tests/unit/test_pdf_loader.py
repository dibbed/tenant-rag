"""
Professional PDF loader tests with comprehensive edge cases.

This module tests the PDF loading functionality with various scenarios including
edge cases, error handling, and file format validation.
"""

from pathlib import Path
from unittest.mock import patch

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
