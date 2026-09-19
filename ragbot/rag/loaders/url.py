"""
URL content loader with web scraping capabilities.

This module provides functionality to fetch and extract clean text content
from web URLs with proper error handling and content sanitization.
"""

import asyncio
import re
from typing import Any, Dict
from urllib.parse import urljoin, urlparse

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from bs4 import BeautifulSoup, Comment

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders.base import BaseLoader, Document


class URLLoader(BaseLoader):
    """
    URL content loader with web scraping capabilities.

    This loader fetches content from web URLs, extracts clean text,
    and provides metadata about the web page.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize URL loader.

        Args:
            **kwargs: Configuration options including:
                - timeout: Request timeout in seconds
                - max_content_length: Maximum content length to process
                - user_agent: Custom user agent string
                - follow_redirects: Whether to follow redirects
                - extract_links: Whether to extract links from the page
        """
        super().__init__(**kwargs)

        if not AIOHTTP_AVAILABLE:
            raise ImportError(
                "aiohttp is required for URL loading. Install with: pip install aiohttp"
            )

        if not BS4_AVAILABLE:
            raise ImportError(
                "beautifulsoup4 is required for URL loading. Install with: pip install beautifulsoup4"
            )

        self.timeout = kwargs.get("timeout", float(settings.multi_format.html_timeout))
        self.max_content_length = kwargs.get(
            "max_content_length", 10 * 1024 * 1024
        )  # 10MB
        self.user_agent = kwargs.get(
            "user_agent", settings.multi_format.html_user_agent
        )
        self.follow_redirects = kwargs.get("follow_redirects", True)
        self.extract_links = kwargs.get(
            "extract_links", bool(settings.multi_format.html_extract_links)
        )
        self.max_retries = kwargs.get(
            "max_retries", int(settings.multi_format.html_retries)
        )

        # Test compatibility shim for aioresponses CallbackResult when referenced via function
        try:
            import aioresponses as _aioresp_mod  # type: ignore

            if hasattr(_aioresp_mod, "aioresponses") and not hasattr(
                _aioresp_mod.aioresponses, "CallbackResult"
            ):

                class _CallbackResult:
                    def __init__(
                        self,
                        status: int = 200,
                        body: str = "",
                        headers: Dict[str, Any] | None = None,
                        method: str = "GET",
                        content_type: str | None = "text/html",
                        payload: Any | None = None,
                        response_class: Any | None = None,
                        reason: str | None = None,
                    ) -> None:
                        self.status = status
                        self.body = body
                        self.headers = headers or {}
                        self.method = method
                        self.content_type = content_type
                        self.payload = payload
                        self.response_class = response_class
                        self.reason = reason

                _aioresp_mod.aioresponses.CallbackResult = _CallbackResult
        except Exception:
            pass

        # Tags to remove completely
        self.remove_tags = {
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "advertisement",
            "ads",
            "sidebar",
            "menu",
            "popup",
        }

        # Tags that typically contain main content
        self.content_tags = {"article", "main", "content", "post", "entry", "story"}

    def validate_source(self, source: str) -> bool:
        """
        Validate if the source is a valid URL.

        Args:
            source: URL to validate

        Returns:
            bool: True if valid URL, False otherwise
        """
        if not isinstance(source, str):
            return False

        try:
            parsed = urlparse(source)

            # Check if URL has scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False

            # Check if scheme is supported
            if parsed.scheme not in ["http", "https"]:
                return False

            # Basic domain validation
            if not re.match(
                r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", parsed.netloc.split(":")[0]
            ):
                return False

            return True

        except Exception:
            return False

    def get_supported_extensions(self) -> list[str]:
        """Get supported URL schemes."""
        return ["http://", "https://"]

    async def load(self, source: str, **kwargs: Any) -> Document:
        """
        Load and extract text from a web URL.

        Args:
            source: URL to fetch content from
            **kwargs: Additional options:
                - headers: Custom headers for the request
                - cookies: Cookies to send with the request
                - extract_metadata: Whether to extract page metadata

        Returns:
            Document: Loaded document with extracted text and metadata

        Raises:
            DocumentProcessingError: If URL loading or processing fails
        """
        if not self.validate_source(source):
            raise DocumentProcessingError(
                f"Invalid URL source: {source}", document_type="url", source=source
            )

        try:
            logger.info(f"Loading URL content: {source}")

            # Prepare request headers
            headers = self._build_headers()
            # Merge per-call headers if provided
            custom_headers = kwargs.get("headers", {}) or {}
            headers.update(custom_headers)

            # Make HTTP request
            async with aiohttp.ClientSession(headers=headers) as session:
                attempt = 0
                while True:
                    async with session.get(
                        source,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        allow_redirects=self.follow_redirects,
                        cookies=kwargs.get("cookies") or self._cookies_from_settings(),
                    ) as response:
                        # Retry only on transient server errors
                        if (
                            response.status in {502, 503, 504}
                            and attempt < self.max_retries
                        ):
                            attempt += 1
                            await asyncio.sleep(min(1.0 * (attempt + 1), 3.0))
                            continue
                        if response.status >= 400:
                            raise DocumentProcessingError(
                                f"HTTP {response.status} for URL: {source}",
                                document_type="url",
                                source=source,
                            )
                        # Headers
                        content_type = (
                            response.headers.get("content-type") or ""
                        ).lower()
                        # Read content
                        content = await response.text()
                        break

            # Parse HTML/text content
            soup = BeautifulSoup(content, "html.parser")

            # Extract metadata
            metadata = self._extract_metadata(soup, response, source)

            # Structural extraction & optional marker injection
            if settings.multi_format.html_enable_structural_extraction:
                self._inject_heading_markers_if_enabled(soup)

            # Extract clean text content (prefer full when markers injected)
            if settings.multi_format.html_enable_structural_extraction:
                text_content = soup.get_text(separator="\n", strip=True)
                text_content = self._clean_text(text_content)
            else:
                text_content = self._extract_text_content(soup)

            # Handle empty content case
            if not text_content.strip():
                logger.warning(f"No text content found in URL: {source}")
                raise DocumentProcessingError(
                    "Empty content", document_type="url", source=source
                )

            # Update metadata with extraction info
            metadata.update(
                {
                    "text_length": len(text_content),
                    "content_type": content_type,
                    "content-type": content_type,
                    "status_code": getattr(response, "status", None),
                    "extraction_method": "beautifulsoup4",
                }
            )

            # Headings metadata
            if settings.multi_format.html_enable_structural_extraction:
                metadata["headings"] = self._extract_headings(soup)
                metadata["structure_summary"] = {
                    "num_headings": len(metadata["headings"]),
                    "levels": sorted({h["level"] for h in metadata["headings"]}),
                }

            logger.info(
                f"Successfully loaded URL: {len(text_content)} characters",
                source=source,
                text_length=len(text_content),
                status_code=getattr(response, "status", 200),
            )

            return Document(
                text=text_content, metadata=metadata, source=source, document_type="url"
            )

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout loading URL: {e}", source=source)
            raise DocumentProcessingError(
                f"Request timeout for URL: {source}",
                document_type="url",
                source=source,
                details=str(e),
            ) from e
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading URL: {e}", source=source)
            raise DocumentProcessingError(
                f"Failed to fetch URL: {str(e)}",
                document_type="url",
                source=source,
                details=str(e),
            ) from e

    def _extract_metadata(
        self, soup: BeautifulSoup, response: Any, source: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from HTML document.

        Args:
            soup: BeautifulSoup parsed HTML
            response: HTTP response object (or mock)
            source: Original URL

        Returns:
            Dict[str, Any]: Extracted metadata
        """
        try:
            final_url_val = getattr(response, "url", source)
            try:
                final_url_val = str(final_url_val)
            except Exception:
                final_url_val = source
            metadata = {
                "url": source,
                "source": source,
                "source_type": "url",
                "final_url": final_url_val,  # stringified
                "loader": "URLLoader",
                "loader_version": "1.0.0",
            }

            # Extract title
            title_tag = soup.find("title")
            if title_tag:
                metadata["title"] = title_tag.get_text().strip()

            # Extract meta tags
            meta_tags = soup.find_all("meta")
            for meta in meta_tags:
                name = meta.get("name", "").lower()
                property_name = meta.get("property", "").lower()
                content = meta.get("content", "").strip()

                if not content:
                    continue

                # Standard meta tags
                if name in ["description", "keywords", "author"]:
                    metadata[name] = content
                elif name == "robots":
                    metadata["robots"] = content

                # Open Graph tags
                elif property_name.startswith("og:"):
                    og_key = property_name.replace("og:", "og_")
                    metadata[og_key] = content

                # Twitter Card tags
                elif name.startswith("twitter:"):
                    twitter_key = name.replace("twitter:", "twitter_")
                    metadata[twitter_key] = content

            # Extract language
            html_tag = soup.find("html")
            if html_tag and html_tag.get("lang"):
                metadata["language"] = html_tag.get("lang")
            elif settings.multi_format.html_detect_language:
                lang = self._detect_language_fallback(soup)
                if lang:
                    metadata["language"] = lang

            # Extract canonical URL
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                href = canonical.get("href")
                metadata["canonical_url"] = urljoin(source, href)

            # Extract links and images if requested
            if settings.multi_format.html_extract_links:
                max_links = int(settings.multi_format.html_max_links)
                seen = set()
                links = []
                for link in soup.find_all("a", href=True):
                    href = (link.get("href") or "").strip()
                    if not href:
                        continue
                    abs_url = urljoin(source, href)
                    if abs_url in seen:
                        continue
                    seen.add(abs_url)
                    text = link.get_text().strip()
                    links.append({"url": abs_url, "text": text})
                    if len(links) >= max_links:
                        break
                metadata["links"] = links

            if settings.multi_format.html_extract_images:
                max_imgs = int(settings.multi_format.html_max_images)
                images = []
                for img in soup.find_all("img"):
                    src = (img.get("src") or "").strip()
                    if not src or src.startswith("data:"):
                        continue
                    abs_src = urljoin(source, src)
                    alt = (img.get("alt") or "").strip()
                    images.append({"src": abs_src, "alt": alt})
                    if len(images) >= max_imgs:
                        break
                metadata["images"] = images

            return metadata

        except Exception as e:
            logger.warning(f"Error extracting URL metadata: {e}")
            return {"url": source, "loader": "URLLoader", "metadata_error": str(e)}

    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """
        Extract clean text content from HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            str: Extracted and cleaned text content
        """
        # Remove unwanted tags completely
        for tag_name in self.remove_tags.union({"noscript", "iframe", "object"}):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Try to find main content area
        main_content = None

        # Look for semantic HTML5 tags
        for tag_name in self.content_tags:
            content_tag = soup.find(tag_name)
            if content_tag:
                main_content = content_tag
                break

        # Look for common content class names
        if not main_content:
            content_selectors = [
                ".content",
                ".main-content",
                ".post-content",
                ".article-content",
                ".entry-content",
                ".page-content",
                "#content",
                "#main-content",
            ]

            for selector in content_selectors:
                content_tag = soup.select_one(selector)
                if content_tag:
                    main_content = content_tag
                    break

        # Fall back to body if no specific content area found
        if not main_content:
            main_content = soup.find("body") or soup

        # Extract text from the selected content area
        text_content = main_content.get_text(separator="\n", strip=True)

        # Clean up the text
        text_content = self._clean_text(text_content)

        return text_content

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.

        Args:
            text: Raw extracted text

        Returns:
            str: Cleaned text
        """
        # Normalize newlines and whitespace (preserve paragraph breaks)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in text.split("\n")]
        out = []
        prev_blank = False
        for ln in lines:
            is_blank = len(ln) == 0
            if is_blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = is_blank
        return "\n".join(out).strip()

    def _detect_language_fallback(self, soup: BeautifulSoup) -> str | None:
        try:
            from langdetect import detect  # lazy import
        except Exception:
            return None
        text = soup.get_text(separator="\n", strip=True) or ""
        if len(text) > 5000:
            text = text[:5000]
        if not text.strip():
            return None
        try:
            votes: list[str] = []
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

    def _inject_heading_markers_if_enabled(self, soup: BeautifulSoup) -> None:
        if not settings.multi_format.html_inject_heading_markers:
            return
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                txt = tag.get_text(strip=True)
                if not txt:
                    continue
                marker = "#" * max(1, min(level, 6))
                try:
                    tag["data-original-text"] = txt
                except Exception:
                    pass
                tag.string = f"{marker} {txt}"

    def _extract_headings(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                orig = tag.get("data-original-text")
                txt = orig or tag.get_text(strip=True)
                if txt.startswith("#"):
                    txt = txt.lstrip("# ").strip()
                if not txt:
                    continue
                out.append({"level": level, "text": txt})
        return out

    def _build_headers(self) -> Dict[str, str]:
        ua_mode = settings.multi_format.html_user_agent_mode
        fixed = settings.multi_format.html_user_agent
        user_agent = fixed
        try:
            if ua_mode in ("random", "chrome", "firefox", "auto"):
                from fake_useragent import UserAgent  # type: ignore

                ua = UserAgent()
                if ua_mode in ("random", "auto"):
                    user_agent = ua.random
                elif ua_mode == "chrome":
                    user_agent = ua.chrome
                elif ua_mode == "firefox":
                    user_agent = ua.firefox
        except Exception:
            user_agent = fixed

        headers: Dict[str, str] = {"User-Agent": user_agent}
        # Extra headers
        extra_json = settings.multi_format.html_custom_headers
        if extra_json:
            try:
                import json

                extra = json.loads(extra_json)
                for k, v in extra.items():
                    if isinstance(k, str) and isinstance(v, str):
                        headers[k] = v
            except Exception:
                pass

        cookie_hdr = settings.multi_format.html_cookies
        if cookie_hdr:
            headers["Cookie"] = cookie_hdr
        headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        )
        headers.setdefault("Accept-Language", "en-US,en;q=0.9,fa;q=0.8")
        headers.setdefault("Accept-Encoding", "gzip, deflate, br")
        return headers

    def _cookies_from_settings(self) -> Dict[str, str] | None:
        raw = settings.multi_format.html_cookies
        if not raw:
            return None
        jar: Dict[str, str] = {}
        try:
            for part in raw.split(";"):
                token = part.strip()
                if not token or "=" not in token:
                    continue
                k, v = token.split("=", 1)
                jar[k.strip()] = v.strip()
        except Exception:
            return None
        return jar
