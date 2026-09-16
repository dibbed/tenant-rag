"""
Unit tests for HTMLLoader covering URL/file loading, headings, metadata,
and custom headers/cookies behavior.
"""

from typing import Dict

import pytest
from aioresponses import CallbackResult, aioresponses

from ragbot.configs.settings import settings
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders.html_loader import HTMLLoader


@pytest.fixture
def html_loader() -> HTMLLoader:
    return HTMLLoader()


@pytest.mark.asyncio
async def test_load_valid_html_url(html_loader: HTMLLoader) -> None:
    test_url = "https://example.com/test"
    test_content = """
    <html>
      <head>
        <title>Test Page</title>
        <meta name="description" content="Test page description" />
        <link rel="canonical" href="https://example.com/test" />
        <meta property="og:title" content="OG Title" />
      </head>
      <body>
        <h1>Main Heading</h1>
        <article><p>Body paragraph</p></article>
        <script>console.log('remove');</script>
        <style>.a{color:red}</style>
        <a href="/rel">Link</a>
        <img src="/img.png" alt="alt" />
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
        doc = await html_loader.load(test_url)

    assert isinstance(doc.text, str)
    assert "Main Heading" in doc.text
    assert "Body paragraph" in doc.text
    assert "console.log" not in doc.text and ".a{" not in doc.text
    assert doc.metadata.get("title") == "Test Page"
    assert doc.metadata.get("description") == "Test page description"
    assert doc.metadata.get("canonical_url") == "https://example.com/test"
    assert doc.metadata.get("og_title") == "OG Title"
    assert doc.metadata.get("link_count", 0) >= 1
    assert doc.metadata.get("image_count", 0) >= 1


@pytest.mark.asyncio
async def test_load_invalid_url_raises(html_loader: HTMLLoader) -> None:
    with pytest.raises(DocumentProcessingError):
        await html_loader.load("")


@pytest.mark.asyncio
async def test_load_html_file(tmp_path, html_loader: HTMLLoader) -> None:
    p = tmp_path / "sample.html"
    p.write_text(
        """
        <html><body>
          <header>ignore</header>
          <h2>Section</h2>
          <div class="content"><p>Inside content</p></div>
        </body></html>
        """,
        encoding="utf-8",
    )
    doc = await html_loader.load(str(p))
    assert "Section" in doc.text
    assert "Inside content" in doc.text
    assert doc.metadata.get("type") == "html"
    assert doc.metadata.get("source_type") == "file"


@pytest.mark.asyncio
async def test_heading_markers_injection(html_loader: HTMLLoader, monkeypatch) -> None:
    # Ensure markers are injected
    monkeypatch.setattr(
        settings.multi_format, "html_enable_structural_extraction", True
    )
    monkeypatch.setattr(settings.multi_format, "html_inject_heading_markers", True)

    url = "https://example.com/markers"
    content = """
    <html><body>
      <h1>Title</h1>
      <h3>Sub</h3>
      <p>Text</p>
    </body></html>
    """
    with aioresponses() as m:
        m.get(url, status=200, body=content, headers={"content-type": "text/html"})
        doc = await html_loader.load(url)

    # Expect markdown-style markers present in flattened text
    assert "# Title" in doc.text
    assert "### Sub" in doc.text
    headings = doc.metadata.get("headings") or []
    assert any(h.get("level") == 1 and h.get("text") == "Title" for h in headings)
    assert any(h.get("level") == 3 and h.get("text") == "Sub" for h in headings)


@pytest.mark.asyncio
async def test_custom_headers_and_cookies(html_loader: HTMLLoader, monkeypatch) -> None:
    # Provide custom UA and cookies via settings
    monkeypatch.setattr(settings.multi_format, "html_user_agent_mode", "fixed")
    monkeypatch.setattr(settings.multi_format, "html_user_agent", "MyAgent/1.0")
    monkeypatch.setattr(settings.multi_format, "html_cookies", "a=1; b=2")
    monkeypatch.setattr(
        settings.multi_format, "html_custom_headers", '{"X-Region":"IR"}'
    )

    test_url = "https://example.com/headers"
    body = "<html><body><h1>OK</h1></body></html>"

    def cb(url, **kwargs):
        headers: Dict[str, str] = kwargs.get("headers", {})
        assert headers.get("User-Agent") == "MyAgent/1.0"
        assert headers.get("Cookie") == "a=1; b=2"
        assert headers.get("X-Region") == "IR"
        return CallbackResult(status=200, body=body)

    with aioresponses() as m:
        m.get(test_url, callback=cb)
        doc = await html_loader.load(test_url)
    assert "OK" in doc.text
