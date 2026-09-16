"""
تست‌های پشتیبانی چندفرمت
"""

from unittest.mock import Mock, patch

import pytest

from ragbot.rag.loaders.advanced_loaders import AdvancedDocumentLoader
from ragbot.rag.loaders.html_loader import HTMLLoader
from ragbot.rag.loaders.markdown_loader import MarkdownLoader
from ragbot.rag.loaders.ocr_loader import OCRLoader
from ragbot.rag.loaders.pptx_loader import PPTXLoader
from ragbot.rag.loaders.xlsx_loader import XLSXLoader


class TestPPTXLoader:
    """تست بارگذاری PowerPoint"""

    @pytest.mark.asyncio
    async def test_pptx_loading(self):
        """تست بارگذاری فایل PowerPoint"""
        loader = PPTXLoader()

        # Mock presentation
        with patch("pptx.Presentation") as mock_presentation:
            mock_slide = Mock()
            mock_slide.shapes = [Mock(text="Test slide content")]
            mock_slide.slide_layout = Mock(name="Title Slide")
            mock_slide.slide_id = 1
            mock_presentation.return_value.slides = [mock_slide]

            # Test loading
            document = await loader.load("test.pptx")

            # Assertions
            assert document.text == "Test slide content"
            assert document.metadata["type"] == "pptx"
            assert document.metadata["slide_count"] == 1

    @pytest.mark.asyncio
    async def test_pptx_extract_slide_title(self):
        """تست استخراج عنوان اسلاید"""
        loader = PPTXLoader()

        # Mock slide with title
        mock_slide = Mock()
        mock_shape = Mock()
        mock_shape.text = "Test Title"
        mock_slide.shapes = [mock_shape]

        title = await loader._extract_slide_title(mock_slide)
        assert title == "Test Title"

    @pytest.mark.asyncio
    async def test_pptx_extract_slide_text(self):
        """تست استخراج متن اسلاید"""
        loader = PPTXLoader()

        # Mock slide with multiple shapes
        mock_slide = Mock()
        mock_shape1 = Mock()
        mock_shape1.text = "First text"
        mock_shape2 = Mock()
        mock_shape2.text = "Second text"
        mock_slide.shapes = [mock_shape1, mock_shape2]

        text = await loader._extract_slide_text(mock_slide)
        assert "First text" in text
        assert "Second text" in text


class TestXLSXLoader:
    """تست بارگذاری Excel"""

    @pytest.mark.asyncio
    async def test_xlsx_loading(self):
        """تست بارگذاری فایل Excel"""
        loader = XLSXLoader()

        # Mock pandas
        with patch("pandas.ExcelFile") as mock_excel:
            mock_excel.return_value.sheet_names = ["Sheet1"]

            with patch("pandas.read_excel") as mock_read:
                mock_df = Mock()
                mock_df.columns = ["A", "B"]
                mock_df.head.return_value = mock_df
                mock_df.iterrows.return_value = [(0, {"A": "1", "B": "2"})]
                mock_read.return_value = mock_df

                # Test loading
                document = await loader.load("test.xlsx")

                # Assertions
                assert "Sheet: Sheet1" in document.text
                assert document.metadata["type"] == "xlsx"
                assert document.metadata["sheet_count"] == 1

    @pytest.mark.asyncio
    async def test_xlsx_dataframe_to_text(self):
        """تست تبدیل DataFrame به متن"""
        loader = XLSXLoader()

        # Mock DataFrame
        mock_df = Mock()
        mock_df.columns = ["Name", "Age"]
        mock_df.head.return_value = mock_df
        mock_df.iterrows.return_value = [(0, {"Name": "John", "Age": "25"})]

        text = await loader._dataframe_to_text(mock_df, "TestSheet")
        assert "Sheet: TestSheet" in text
        assert "ستون‌ها: Name, Age" in text


class TestHTMLLoader:
    """تست بارگذاری HTML"""

    @pytest.mark.asyncio
    async def test_html_loading_from_file(self):
        """تست بارگذاری فایل HTML"""
        loader = HTMLLoader()

        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Test Content</h1>
                <p>This is a test paragraph.</p>
            </body>
        </html>
        """

        with patch(
            "builtins.open",
            Mock(return_value=Mock(read=Mock(return_value=html_content))),
        ):
            document = await loader.load("test.html")

            # Assertions
            assert "Test Content" in document.text
            assert document.metadata["type"] == "html"
            assert document.metadata["title"] == "Test Page"
            assert document.metadata["source_type"] == "file"

    @pytest.mark.asyncio
    async def test_html_loading_from_url(self):
        """تست بارگذاری HTML از URL"""
        loader = HTMLLoader()

        html_content = """
        <html>
            <head><title>Test URL Page</title></head>
            <body><h1>URL Content</h1></body>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            document = await loader.load("https://example.com/test.html")

            # Assertions
            assert "URL Content" in document.text
            assert document.metadata["source_type"] == "url"

    @pytest.mark.asyncio
    async def test_html_extract_metadata(self):
        """تست استخراج متادیتای HTML"""
        loader = HTMLLoader()

        html_content = """
        <html>
            <head>
                <title>Test Title</title>
                <meta name="description" content="Test description">
                <meta name="keywords" content="test, keywords">
            </head>
            <body>
                <a href="https://example.com">Link</a>
                <img src="image.jpg" alt="Test image">
            </body>
        </html>
        """

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")

        metadata = await loader._extract_metadata(soup, "test.html", "file")

        assert metadata["title"] == "Test Title"
        assert metadata["description"] == "Test description"
        assert metadata["keywords"] == "test, keywords"
        assert metadata["link_count"] == 1
        assert metadata["image_count"] == 1


class TestMarkdownLoader:
    """تست بارگذاری Markdown"""

    @pytest.mark.asyncio
    async def test_markdown_loading(self):
        """تست بارگذاری فایل Markdown"""
        loader = MarkdownLoader()

        markdown_content = """
        # Test Title

        This is a test paragraph.

        ## Subtitle

        Another paragraph.

        [Link text](https://example.com)
        """

        with patch(
            "builtins.open",
            Mock(return_value=Mock(read=Mock(return_value=markdown_content))),
        ):
            document = await loader.load("test.md")

            # Assertions
            assert "Test Title" in document.text
            assert document.metadata["type"] == "markdown"
            assert len(document.metadata["headers"]) == 2
            assert document.metadata["link_count"] == 1

    @pytest.mark.asyncio
    async def test_markdown_extract_metadata(self):
        """تست استخراج متادیتای Markdown"""
        loader = MarkdownLoader()

        markdown_content = """
        ---
        title: Test Document
        author: Test Author
        ---

        # Main Title
        ## Subtitle

        [Link](https://example.com)
        """

        metadata = await loader._extract_markdown_metadata(markdown_content, "test.md")

        assert metadata["title"] == "Test Document"
        assert metadata["author"] == "Test Author"
        assert len(metadata["headers"]) == 2
        assert metadata["link_count"] == 1


class TestOCRLoader:
    """تست بارگذاری OCR"""

    @pytest.mark.asyncio
    async def test_ocr_loading(self):
        """تست بارگذاری فایل تصویری"""
        loader = OCRLoader()

        # Mock PIL Image
        with patch("PIL.Image.open") as mock_image:
            mock_image.return_value.width = 100
            mock_image.return_value.height = 100
            mock_image.return_value.mode = "RGB"
            mock_image.return_value.format = "PNG"

            # Mock pytesseract
            with patch("pytesseract.image_to_string", return_value="Test OCR text"):
                document = await loader.load("test.png")

                # Assertions
                assert document.text == "Test OCR text"
                assert document.metadata["type"] == "image"
                assert document.metadata["image_width"] == 100
                assert document.metadata["image_height"] == 100

    @pytest.mark.asyncio
    async def test_ocr_clean_text(self):
        """تست تمیز کردن متن OCR"""
        loader = OCRLoader()

        dirty_text = "Line 1\n\n\nLine 2\n\nShort\nLine 3"
        cleaned_text = loader._clean_ocr_text(dirty_text)

        lines = cleaned_text.split("\n")
        assert len(lines) == 3
        assert "Short" not in cleaned_text

    @pytest.mark.asyncio
    async def test_ocr_unsupported_format(self):
        """تست فرمت پشتیبانی نشده"""
        loader = OCRLoader()

        with pytest.raises(ValueError, match="فرمت فایل gif پشتیبانی نمی‌شود"):
            await loader.load("test.gif")


class TestAdvancedDocumentLoader:
    """تست مدیر بارگذاری پیشرفته"""

    @pytest.mark.asyncio
    async def test_load_document_pdf(self):
        """تست بارگذاری سند PDF"""
        loader = AdvancedDocumentLoader()

        with patch("ragbot.rag.loaders.pdf.PDFLoader.load") as mock_load:
            mock_document = Mock()
            mock_document.text = "PDF content"
            mock_load.return_value = mock_document

            document = await loader.load_document("test.pdf")

            assert document.text == "PDF content"
            mock_load.assert_called_once_with("test.pdf")

    @pytest.mark.asyncio
    async def test_load_document_url(self):
        """تست بارگذاری URL"""
        loader = AdvancedDocumentLoader()

        with patch("ragbot.rag.loaders.url.URLLoader.load") as mock_load:
            mock_document = Mock()
            mock_document.text = "URL content"
            mock_load.return_value = mock_document

            document = await loader.load_document("https://example.com")

            assert document.text == "URL content"
            mock_load.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_load_document_unsupported_format(self):
        """تست فرمت پشتیبانی نشده"""
        loader = AdvancedDocumentLoader()

        with pytest.raises(ValueError, match="فرمت فایل .xyz پشتیبانی نمی‌شود"):
            await loader.load_document("test.xyz")

    @pytest.mark.asyncio
    async def test_get_supported_formats(self):
        """تست دریافت فرمت‌های پشتیبانی شده"""
        loader = AdvancedDocumentLoader()

        formats = await loader.get_supported_formats()

        assert ".pdf" in formats
        assert ".docx" in formats
        assert ".pptx" in formats
        assert ".xlsx" in formats
        assert ".html" in formats
        assert ".md" in formats
        assert ".png" in formats
        assert "url" in formats

    @pytest.mark.asyncio
    async def test_validate_file_valid(self):
        """تست اعتبارسنجی فایل معتبر"""
        loader = AdvancedDocumentLoader()

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", return_value=".pdf"),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 1024

            result = await loader.validate_file("test.pdf")

            assert result["is_valid"] is True
            assert result["format"] == ".pdf"
            assert result["size"] == 1024
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_validate_file_not_exists(self):
        """تست اعتبارسنجی فایل موجود نباشد"""
        loader = AdvancedDocumentLoader()

        with patch("pathlib.Path.exists", return_value=False):
            result = await loader.validate_file("nonexistent.pdf")

            assert result["is_valid"] is False
            assert result["error"] == "فایل وجود ندارد"

    @pytest.mark.asyncio
    async def test_validate_file_unsupported_format(self):
        """تست اعتبارسنجی فرمت پشتیبانی نشده"""
        loader = AdvancedDocumentLoader()

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", return_value=".xyz"),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 1024

            result = await loader.validate_file("test.xyz")

            assert result["is_valid"] is False
            assert result["error"] == "فرمت .xyz پشتیبانی نمی‌شود"


@pytest.mark.asyncio
async def test_integration_multi_format_loading():
    """تست یکپارچگی بارگذاری چندفرمت"""
    loader = AdvancedDocumentLoader()

    # Test different formats
    test_cases = [
        ("test.pdf", ".pdf"),
        ("test.docx", ".docx"),
        ("test.txt", ".txt"),
        ("test.pptx", ".pptx"),
        ("test.xlsx", ".xlsx"),
        ("test.html", ".html"),
        ("test.md", ".md"),
        ("test.png", ".png"),
    ]

    for file_path, expected_format in test_cases:
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.suffix", return_value=expected_format),
        ):
            # Mock the appropriate loader
            loader_name = expected_format[1:].upper() + "Loader"
            if expected_format == ".png":
                loader_name = "OCRLoader"

            with patch(
                f"ragbot.rag.loaders.{loader_name.lower()}.{loader_name}.load"
            ) as mock_load:
                mock_document = Mock()
                mock_document.text = f"Content from {expected_format}"
                mock_load.return_value = mock_document

                document = await loader.load_document(file_path)
                assert document.text == f"Content from {expected_format}"
