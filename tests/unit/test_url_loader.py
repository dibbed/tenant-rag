"""
Professional URL loader tests with comprehensive edge cases.

This module tests the URL loading functionality with various scenarios including
different content types, error handling, and network conditions.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from ragbot.rag import URLLoader, Document, DocumentProcessingError


class TestURLLoader:
    """Comprehensive test suite for URL loader functionality."""

    @pytest.fixture
    def loader(self) -> URLLoader:
        """Create a URLLoader instance for testing."""
        return URLLoader()

    @pytest.mark.asyncio
    async def test_load_valid_html_url(self, loader: URLLoader) -> None:
        """Test loading a valid HTML URL."""
        test_url = "https://example.com/test"
        test_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Test Content</h1>
                <p>This is a test paragraph with useful content.</p>
                <script>console.log('This should be removed');</script>
                <style>.test { color: red; }</style>
            </body>
        </html>
        """

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={"content-type": "text/html; charset=utf-8"},
            )

            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert isinstance(document.content, str)
            assert len(document.content) > 0
            assert "Test Content" in document.content
            assert "test paragraph" in document.content
            # Should remove script and style tags
            assert "console.log" not in document.content
            assert "color: red" not in document.content
            assert document.source == test_url
            assert document.document_type == "url"

    @pytest.mark.asyncio
    async def test_load_plain_text_url(self, loader: URLLoader) -> None:
        """Test loading a plain text URL."""
        test_url = "https://example.com/test.txt"
        test_content = "This is plain text content without HTML tags."

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={"content-type": "text/plain; charset=utf-8"},
            )

            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert document.content == test_content
            assert document.source == test_url
            assert "content-type" in document.metadata

    @pytest.mark.asyncio
    async def test_load_json_url(self, loader: URLLoader) -> None:
        """Test loading a JSON URL."""
        test_url = "https://api.example.com/data.json"
        test_content = '{"title": "Test Data", "content": "JSON content here"}'

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={"content-type": "application/json"},
            )

            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert "Test Data" in document.content
            assert "JSON content" in document.content

    @pytest.mark.asyncio
    async def test_load_url_with_redirects(self, loader: URLLoader) -> None:
        """Test handling of URL redirects."""
        original_url = "https://example.com/redirect"
        final_url = "https://example.com/final"
        test_content = "<html><body><h1>Final Content</h1></body></html>"

        with aioresponses() as m:
            m.get(original_url, status=301, headers={"Location": final_url})
            m.get(
                final_url,
                status=200,
                body=test_content,
                headers={"content-type": "text/html"},
            )

            document = await loader.load(original_url)

            assert isinstance(document, Document)
            assert "Final Content" in document.content
            assert document.metadata["source"] == original_url  # Original URL preserved

    @pytest.mark.asyncio
    async def test_load_url_404_error(self, loader: URLLoader) -> None:
        """Test handling of 404 errors."""
        test_url = "https://example.com/notfound"

        with aioresponses() as m:
            m.get(test_url, status=404)

            with pytest.raises(DocumentProcessingError, match="HTTP 404"):
                await loader.load(test_url)

    @pytest.mark.asyncio
    async def test_load_url_500_error(self, loader: URLLoader) -> None:
        """Test handling of server errors."""
        test_url = "https://example.com/servererror"

        with aioresponses() as m:
            m.get(test_url, status=500)

            with pytest.raises(DocumentProcessingError, match="HTTP 500"):
                await loader.load(test_url)

    @pytest.mark.asyncio
    async def test_load_url_timeout(self, loader: URLLoader) -> None:
        """Test handling of request timeouts."""
        test_url = "https://example.com/timeout"

        with aioresponses() as m:
            m.get(test_url, exception=asyncio.TimeoutError())

            with pytest.raises(DocumentProcessingError, match="timeout"):
                await loader.load(test_url)

    @pytest.mark.asyncio
    async def test_load_invalid_url(self, loader: URLLoader) -> None:
        """Test handling of invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # Unsupported protocol
            "http://",  # Incomplete URL
            "",  # Empty string
        ]

        for invalid_url in invalid_urls:
            with pytest.raises(DocumentProcessingError):
                await loader.load(invalid_url)

    @pytest.mark.asyncio
    async def test_load_url_with_unicode_content(self, loader: URLLoader) -> None:
        """Test loading URLs with Unicode and multilingual content."""
        test_url = "https://example.com/unicode"
        test_content = """
        <html>
            <head><meta charset="utf-8"><title>Unicode Test</title></head>
            <body>
                <h1>English Title</h1>
                <p>عنوان فارسی - Persian content here</p>
                <p>中文内容 - Chinese content</p>
                <p>العربية - Arabic content</p>
                <p>Русский - Russian content</p>
            </body>
        </html>
        """

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={"content-type": "text/html; charset=utf-8"},
            )

            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert "English Title" in document.content
            assert "فارسی" in document.content
            assert "中文" in document.content
            assert "العربية" in document.content
            assert "Русский" in document.content

    @pytest.mark.asyncio
    async def test_load_url_large_content(self, loader: URLLoader) -> None:
        """Test loading URLs with large content."""
        test_url = "https://example.com/large"
        # Create large content (simulate a large article)
        test_content = f"""
        <html>
            <body>
                <h1>Large Content Test</h1>
                {"<p>This is a large paragraph with lots of text. " * 1000}</p>
            </body>
        </html>
        """

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={"content-type": "text/html"},
            )

            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert len(document.content) > 10000  # Should handle large content
            assert "Large Content Test" in document.content

    @pytest.mark.asyncio
    async def test_load_url_with_malformed_html(self, loader: URLLoader) -> None:
        """Test handling of malformed HTML."""
        test_url = "https://example.com/malformed"
        test_content = """
        <html>
            <body>
                <h1>Malformed HTML Test
                <p>Missing closing tags
                <div>Unclosed div
                <p>Another paragraph</p>
            </body>
        """

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={"content-type": "text/html"},
            )

            # Should handle malformed HTML gracefully
            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert "Malformed HTML Test" in document.content
            assert "Another paragraph" in document.content

    @pytest.mark.asyncio
    async def test_load_url_with_custom_headers(self, loader: URLLoader) -> None:
        """Test loading with custom headers."""
        test_url = "https://example.com/headers"
        test_content = "<html><body><h1>Content with headers</h1></body></html>"

        with aioresponses() as m:

            def callback(url, **kwargs):
                headers = kwargs.get("headers", {})
                assert "User-Agent" in headers
                return aioresponses.CallbackResult(status=200, body=test_content)

            m.get(test_url, callback=callback)

            document = await loader.load(test_url)
            assert isinstance(document, Document)

    @pytest.mark.asyncio
    async def test_load_url_empty_content(self, loader: URLLoader) -> None:
        """Test handling of URLs with empty content."""
        test_url = "https://example.com/empty"

        with aioresponses() as m:
            m.get(test_url, status=200, body="", headers={"content-type": "text/html"})

            with pytest.raises(DocumentProcessingError, match="Empty content"):
                await loader.load(test_url)

    @pytest.mark.asyncio
    async def test_load_url_with_metadata_extraction(self, loader: URLLoader) -> None:
        """Test metadata extraction from URLs."""
        test_url = "https://example.com/metadata"
        test_content = """
        <html>
            <head>
                <title>Test Page Title</title>
                <meta name="description" content="Test page description">
                <meta name="author" content="Test Author">
            </head>
            <body><h1>Content</h1></body>
        </html>
        """

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=test_content,
                headers={
                    "content-type": "text/html; charset=utf-8",
                    "content-length": str(len(test_content)),
                },
            )

            document = await loader.load(test_url)

            assert document.metadata["source"] == test_url
            assert document.metadata["source_type"] == "url"
            assert "content-type" in document.metadata
            # Check if title is extracted
            if "title" in document.metadata:
                assert document.metadata["title"] == "Test Page Title"

    @pytest.mark.parametrize(
        "content_type,expected_processing",
        [
            ("text/html", "html_processing"),
            ("text/plain", "text_processing"),
            ("application/json", "json_processing"),
            ("application/xml", "xml_processing"),
        ],
    )
    @pytest.mark.asyncio
    async def test_load_different_content_types(
        self, loader: URLLoader, content_type: str, expected_processing: str
    ) -> None:
        """Test handling of different content types."""
        test_url = "https://example.com/content-type-test"

        if content_type == "text/html":
            content = "<html><body><h1>HTML Content</h1></body></html>"
            expected_text = "HTML Content"
        elif content_type == "text/plain":
            content = "Plain text content"
            expected_text = content
        elif content_type == "application/json":
            content = '{"message": "JSON content"}'
            expected_text = "JSON content"
        elif content_type == "application/xml":
            content = "<root><message>XML content</message></root>"
            expected_text = "XML content"

        with aioresponses() as m:
            m.get(
                test_url,
                status=200,
                body=content,
                headers={"content-type": content_type},
            )

            document = await loader.load(test_url)

            assert isinstance(document, Document)
            assert expected_text in document.content

    @pytest.mark.asyncio
    async def test_load_url_connection_error(self, loader: URLLoader) -> None:
        """Test handling of connection errors."""
        test_url = "https://nonexistent-domain-12345.com"

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = Exception("Connection error")

            with pytest.raises(DocumentProcessingError, match="Failed to fetch"):
                await loader.load(test_url)

    @pytest.mark.asyncio
    async def test_load_url_with_retries(self, loader: URLLoader) -> None:
        """Test retry mechanism on temporary failures."""
        test_url = "https://example.com/retry-test"
        test_content = "<html><body><h1>Success after retry</h1></body></html>"

        with aioresponses() as m:
            # First request fails, second succeeds
            m.get(test_url, status=503)  # Service unavailable
            m.get(test_url, status=200, body=test_content)

            # Configure loader with retries if supported
            retry_loader = URLLoader(max_retries=1)
            document = await retry_loader.load(test_url)

            assert isinstance(document, Document)
            assert "Success after retry" in document.content
