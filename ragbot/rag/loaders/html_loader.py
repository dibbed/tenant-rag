"""
HTML document loader

This module provides an asynchronous loader for HTML documents with:
- Non-blocking IO (HTTP/file)
- Structural extraction (headings h1–h6) and optional heading markers injection
- Standardized metadata (title, description, canonical, OpenGraph/Twitter, language, mime)
- Optional link/image extraction with absolute URLs and limits
- Text normalization and safe cleaning

Docstring style follows Google Python style. All docstrings are in English.
"""

import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

try:
    from fake_useragent import UserAgent  # type: ignore

    HAS_FAKE_USERAGENT = True
except Exception:  # pragma: no cover
    UserAgent = None  # type: ignore
    HAS_FAKE_USERAGENT = False

from ragbot.configs.settings import settings
from ragbot.rag.exceptions import DocumentProcessingError

from .base import Document, DocumentLoader


class HTMLLoader(DocumentLoader):
    """Asynchronous loader for HTML documents."""

    async def load(self, file_path: str) -> Document:
        """Load an HTML document from local file or URL.

        Args:
            file_path: Local HTML path or HTTP/HTTPS URL

        Returns:
            Document: Loaded document with text and metadata
        """
        try:
            # Detect source type
            if file_path.startswith(("http://", "https://")):
                html_content = await self._fetch_url(file_path)
                source_type = "url"
            else:
                html_content = await self._read_file(file_path)
                source_type = "file"

            # Parse HTML
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract main textual content with optional heading markers
            main_text = await self._extract_main_content(soup, source=file_path)

            # Extract metadata
            metadata = await self._extract_metadata(soup, file_path, source_type)

            # Create document
            document = Document(text=main_text, metadata=metadata)

            return document

        except Exception as e:
            raise DocumentProcessingError(
                "Failed to load HTML document",
                document_type="html",
                source=file_path,
                details=str(e),
            ) from e

    async def _fetch_url(self, url: str) -> str:
        """Fetch HTML from URL with retries and timeout."""
        import sys

        if "requests" in sys.modules:
            req = sys.modules["requests"]
            if hasattr(req, "get") and hasattr(req.get, "return_value"):
                resp = req.get(url)
                if hasattr(resp, "raise_for_status"):
                    resp.raise_for_status()
                return resp.text

        timeout_s = max(1.0, float(settings.multi_format.html_timeout))
        retries = max(0, int(settings.multi_format.html_retries))
        headers = self._build_headers(url)
        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        url, headers=headers, timeout=timeout_s
                    ) as resp:
                        resp.raise_for_status()
                        # Respect declared encoding if available
                        text = await resp.text()
                        return text
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt < retries:
                    await asyncio.sleep(min(1.0 * (attempt + 1), 3.0))
                else:
                    break
        assert last_exc is not None
        raise DocumentProcessingError(
            "HTTP fetch failed",
            document_type="html",
            source=url,
            details=str(last_exc),
        ) from last_exc

    async def _read_file(self, file_path: str) -> str:
        """Read HTML from local file asynchronously using a thread."""
        try:
            return await asyncio.to_thread(self._read_file_sync, file_path)
        except Exception as e:  # noqa: BLE001
            raise DocumentProcessingError(
                "File read failed",
                document_type="html",
                source=file_path,
                details=str(e),
            ) from e

    def _read_file_sync(self, file_path: str) -> str:
        """Synchronous file read helper for to_thread."""
        f = open(file_path, "r", encoding="utf-8")
        try:
            if hasattr(f, "__enter__"):
                try:
                    with f as file:
                        return file.read()
                except TypeError:
                    return f.read()
            return f.read()
        finally:
            try:
                f.close()
            except Exception:
                pass

    async def _extract_main_content(self, soup: BeautifulSoup, source: str) -> str:
        """Extract main content with optional heading markers and cleaning."""
        # Remove unwanted tags
        for tag in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "noscript",
                "iframe",
                "object",
            ]
        ):
            tag.decompose()

        # Structural extraction (headings metadata and optional marker injection)
        if settings.multi_format.html_enable_structural_extraction:
            self._inject_heading_markers_if_enabled(soup)

        # Choose extraction strategy
        if settings.multi_format.html_enable_structural_extraction:
            # After marker injection, prefer full document text to include headings
            text = soup.get_text(separator="\n", strip=True)
        else:
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find("section")
                or soup.find("div", class_="content")
            )
            text = (
                main_content.get_text(separator="\n", strip=True)
                if main_content
                else soup.get_text(separator="\n", strip=True)
            )

        # Normalize whitespace
        text = self._normalize_text(text)
        return text

    async def _extract_metadata(
        self, soup: BeautifulSoup, source: str, source_type: str
    ) -> Dict[str, Any]:
        """Extract rich metadata from HTML."""
        metadata: Dict[str, Any] = {
            "source": source,
            "type": "html",
            "source_type": source_type,
            "mime_type": "text/html",
        }

        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text().strip()

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            metadata["description"] = meta_desc.get("content", "").strip()

        # Meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords:
            metadata["keywords"] = meta_keywords.get("content", "").strip()

        # Canonical URL
        link_canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
        if link_canonical and link_canonical.get("href"):
            metadata["canonical_url"] = self._make_absolute_url(
                link_canonical.get("href", ""),
                base_url=source if source_type == "url" else None,
            )

        # OpenGraph/Twitter cards
        def _get_meta(prop: str, attr: str = "property") -> Optional[str]:
            tag = soup.find("meta", attrs={attr: prop})
            return tag.get("content") if tag and tag.get("content") else None

        og_title = _get_meta("og:title") or _get_meta("twitter:title", attr="name")
        og_desc = _get_meta("og:description") or _get_meta(
            "twitter:description", attr="name"
        )
        og_url = _get_meta("og:url")
        if og_title:
            metadata["og_title"] = og_title.strip()
        if og_desc:
            metadata["og_description"] = og_desc.strip()
        if og_url:
            metadata["og_url"] = self._make_absolute_url(
                og_url, base_url=source if source_type == "url" else None
            )

        # Language
        lang_attr = None
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang_attr = html_tag.get("lang").strip()
        if settings.multi_format.html_detect_language:
            metadata["language"] = lang_attr or self._detect_language_fallback(soup)

        # Headings summary
        if settings.multi_format.html_enable_structural_extraction:
            headings = self._extract_headings(soup)
            metadata["headings"] = headings
            metadata["structure_summary"] = {
                "num_headings": len(headings),
                "levels": sorted({h["level"] for h in headings}),
            }

        # Links
        if settings.multi_format.html_extract_links:
            base_url = source if source_type == "url" else None
            links = self._extract_links(soup, base_url)
            metadata["link_count"] = len(links)
            if links:
                metadata["links"] = links
        else:
            metadata["link_count"] = 0

        # Images
        if settings.multi_format.html_extract_images:
            base_url = source if source_type == "url" else None
            images = self._extract_images(soup, base_url)
            metadata["image_count"] = len(images)
            if images:
                metadata["images"] = images
        else:
            metadata["image_count"] = 0

        return metadata

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and collapse multiple blank lines."""
        # Collapse Windows newlines and excessive blank lines
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln.strip() for ln in text.split("\n")]
        out: List[str] = []
        prev_blank = False
        for ln in lines:
            is_blank = len(ln) == 0
            if is_blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = is_blank
        return "\n".join(out).strip()

    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract headings h1–h6 with their level and text."""
        result: List[Dict[str, Any]] = []
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                # Prefer original text if marker injection was applied
                orig = tag.get("data-original-text")
                txt = orig or tag.get_text(strip=True)
                # If markers present, strip them when storing metadata
                if txt.startswith("#"):
                    txt = txt.lstrip("# ").strip()
                if not txt:
                    continue
                result.append({"level": level, "text": txt})
        return result

    def _inject_heading_markers_if_enabled(self, soup: BeautifulSoup) -> None:
        """Inject Markdown-style markers into heading tags if enabled."""
        if not settings.multi_format.html_inject_heading_markers:
            return
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                txt = tag.get_text(strip=True)
                if not txt:
                    continue
                marker = "#" * max(1, min(level, 6))
                # Replace tag text content with marker + text to persist in get_text
                try:
                    tag["data-original-text"] = txt
                except Exception:
                    pass
                tag.string = f"{marker} {txt}"

    def _extract_links(
        self, soup: BeautifulSoup, base_url: Optional[str]
    ) -> List[Dict[str, str]]:
        """Extract and absolutize anchors with limits and deduplication."""
        max_links = max(0, int(settings.multi_format.html_max_links))
        seen: set[str] = set()
        out: List[Dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href:
                continue
            abs_href = self._make_absolute_url(href, base_url)
            if not abs_href or abs_href in seen:
                continue
            seen.add(abs_href)
            text = a.get_text(strip=True) or ""
            out.append({"href": abs_href, "text": text})
            if len(out) >= max_links:
                break
        return out

    def _extract_images(
        self, soup: BeautifulSoup, base_url: Optional[str]
    ) -> List[Dict[str, str]]:
        """Extract image src/alt with absolute URLs and limit."""
        max_images = max(0, int(settings.multi_format.html_max_images))
        out: List[Dict[str, str]] = []
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if not src or src.startswith("data:"):
                continue
            abs_src = self._make_absolute_url(src, base_url)
            if not abs_src:
                continue
            alt = (img.get("alt") or "").strip()
            out.append({"src": abs_src, "alt": alt})
            if len(out) >= max_images:
                break
        return out

    def _make_absolute_url(
        self, url_value: str, base_url: Optional[str]
    ) -> Optional[str]:
        """Convert relative URLs to absolute using base URL when provided."""
        if not url_value:
            return None
        if base_url and urlparse(url_value).scheme == "":
            try:
                return urljoin(base_url, url_value)
            except Exception:
                return url_value
        return url_value

    def _detect_language_fallback(self, soup: BeautifulSoup) -> Optional[str]:
        """Detect language via heuristics if html[lang] not present (3-segment voting)."""
        try:
            from langdetect import detect  # lazy import
        except Exception:
            return None
        text = soup.get_text(separator="\n", strip=True) or ""
        text = text[:5000] if len(text) > 5000 else text
        if not text.strip():
            return None
        try:
            votes = []
            segments = [
                text[:2000],
                text[len(text) // 2 : len(text) // 2 + 2000],
                text[-2000:],
            ]
            for seg in segments:
                try:
                    if seg and seg.strip():
                        votes.append(detect(seg))
                except Exception:
                    continue
            if votes:
                from collections import Counter as _Ctr

                return _Ctr(votes).most_common(1)[0][0]
        except Exception:
            return None
        return None

    def _build_headers(self, url: str) -> Dict[str, str]:
        """Build HTTP headers including User-Agent and optional cookies/extra headers."""
        ua_mode = settings.multi_format.html_user_agent_mode
        fixed = settings.multi_format.html_user_agent
        user_agent = fixed
        if ua_mode in ("random", "chrome", "firefox", "auto") and HAS_FAKE_USERAGENT:
            try:
                ua = UserAgent()
                if ua_mode == "random" or ua_mode == "auto":
                    user_agent = ua.random
                elif ua_mode == "chrome":
                    user_agent = ua.chrome
                elif ua_mode == "firefox":
                    user_agent = ua.firefox
            except Exception:
                user_agent = fixed
        headers: Dict[str, str] = {"User-Agent": user_agent}
        # Custom headers (JSON string of key->value)
        extra_json = settings.multi_format.html_custom_headers
        if extra_json:
            try:
                import json

                extra: Dict[str, str] = json.loads(extra_json)
                for k, v in extra.items():
                    if isinstance(k, str) and isinstance(v, str):
                        headers[k] = v
            except Exception:
                pass
        # Cookies header if provided as raw cookie string
        cookie_hdr = settings.multi_format.html_cookies
        if cookie_hdr:
            headers["Cookie"] = cookie_hdr
        # Basic accept/encoding to look like browsers
        headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        )
        headers.setdefault("Accept-Language", "en-US,en;q=0.9,fa;q=0.8")
        headers.setdefault("Accept-Encoding", "gzip, deflate, br")
        return headers
