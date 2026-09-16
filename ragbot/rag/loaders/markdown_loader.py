"""
Markdown document loader - Advanced.

Features:
- Front matter parsing (YAML/JSON-like)
- Heading extraction with levels (H1-H6)
- Lists, blockquotes, code blocks, tables
- Links and images metadata
- Language detection (multi-chunk voting)
- Token estimation (tiktoken)
"""

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

import markdown
from bs4 import BeautifulSoup

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders.base import Document, DocumentLoader


class MarkdownLoader(DocumentLoader):
    """Load and parse Markdown documents with advanced metadata."""

    def __init__(self, **kwargs: Any) -> None:
        self.md = markdown.Markdown(
            extensions=["toc", "codehilite", "tables", "fenced_code", "nl2br"]
        )
        self.detect_language: bool = bool(
            getattr(settings.multi_format, "markdown_detect_language", False)
        )

    async def load(self, file_path: str) -> Document:
        path = Path(file_path)
        if not path.exists() or path.suffix.lower() not in [".md", ".markdown"]:
            raise DocumentProcessingError(
                "Invalid Markdown path", document_type="markdown", source=str(path)
            )

        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")

            metadata = await self._extract_metadata(raw, str(path))
            # Standard keys
            metadata.setdefault("file_name", path.name)
            metadata.setdefault("file_ext", path.suffix.lower())
            metadata.setdefault("loader", "MarkdownLoader")
            metadata.setdefault("type", "markdown")
            metadata.setdefault("source_type", "file")
            metadata.setdefault("mime_type", "text/markdown")

            html = self.md.convert(raw)
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)

            normalized = self._normalize_text(text_content)

            metadata["approx_chars"] = len(normalized)
            metadata["estimated_tokens"] = self._estimate_tokens(normalized)

            # Language detection (optional)
            if self.detect_language:
                lang = self._detect_language_voted(normalized)
                if lang:
                    metadata["language"] = lang

            return Document(
                text=normalized,
                metadata=metadata,
                source=str(path),
                document_type="markdown",
            )

        except Exception as e:
            logger.error(f"Markdown load error: {e} | path={file_path}")
            raise DocumentProcessingError(
                str(e), document_type="markdown", source=str(path)
            ) from e

    # ---------------------------
    # Metadata extraction
    # ---------------------------
    async def _extract_metadata(self, content: str, file_path: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "source": file_path,
            "type": "markdown",
        }

        # Front matter (YAML style)
        if content.startswith("---"):
            try:
                fm_end = content.find("---", 3)
                if fm_end != -1:
                    fm_block = content[3:fm_end]
                    for line in fm_block.splitlines():
                        if ":" in line:
                            key, val = line.split(":", 1)
                            metadata[key.strip()] = val.strip()
            except Exception as e:
                logger.warning(f"Front matter parse failed: {e}")

        # Headings
        headings = []
        for line in content.splitlines():
            if line.strip().startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                if title:
                    headings.append({"level": level, "title": title})
        metadata["headers"] = headings
        metadata["header_count"] = len(headings)
        metadata["has_headings"] = bool(headings)
        # Uniform key with other loaders
        try:
            metadata["headings"] = [
                {"level": h["level"], "text": h["title"]} for h in headings
            ]
        except Exception:
            pass

        # Links
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        metadata["links"] = [{"text": t, "url": u} for t, u in links]
        metadata["link_count"] = len(links)
        metadata["has_links"] = bool(links)

        # Images
        images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)
        metadata["images"] = [{"alt": alt, "url": url} for alt, url in images]
        metadata["images_count"] = len(images)
        metadata["has_images"] = bool(images)

        # Lists
        bullets = re.findall(r"^\s*[-*+] .+", content, re.MULTILINE)
        numbers = re.findall(r"^\s*\d+\..+", content, re.MULTILINE)
        metadata["bullet_list_count"] = len(bullets)
        metadata["numbered_list_count"] = len(numbers)

        # Blockquotes
        blockquotes = re.findall(r"^\s*> .+", content, re.MULTILINE)
        metadata["blockquote_count"] = len(blockquotes)

        # Code blocks
        code_blocks = re.findall(r"```(\w+)?([\s\S]*?)```", content, re.DOTALL)
        metadata["code_blocks"] = [
            {"lang": lang.strip() or None, "length": len(body.strip())}
            for lang, body in code_blocks
        ]
        metadata["code_blocks_count"] = len(code_blocks)

        # Tables
        tables = re.findall(r"\|.*\|", content)
        metadata["tables_count"] = len(tables)

        return metadata

    # ---------------------------
    # Utils
    # ---------------------------
    def _normalize_text(self, text: str) -> str:
        norm = unicodedata.normalize("NFC", text)
        norm = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", norm)
        norm = re.sub(r"[ \t]+", " ", norm)
        norm = re.sub(r"\s*\n\s*", "\n", norm).strip()
        return norm

    def _estimate_tokens(self, text: str) -> int:
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text.split())

    def _detect_language_voted(self, text: str) -> Optional[str]:
        try:
            from langdetect import detect
        except Exception:
            return None
        n = len(text)
        chunks = [
            text[: min(2000, n)],
            text[max(0, n // 2 - 1000) : min(n, n // 2 + 1000)],
            text[max(0, n - 2000) :],
        ]
        votes = []
        for ch in chunks:
            try:
                if ch.strip():
                    votes.append(detect(ch))
            except Exception:
                continue
        if not votes:
            return None
        from collections import Counter

        return Counter(votes).most_common(1)[0][0]
