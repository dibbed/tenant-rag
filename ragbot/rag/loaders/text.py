"""
Plain text document loader.

This module provides functionality to load and process plain text content
with proper validation and metadata extraction.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError, ValidationError
from ragbot.rag.loaders.base import BaseLoader, Document


class TextLoader(BaseLoader):
    """
    Plain text document loader.

    This loader handles plain text content from strings, files, or other text sources
    with validation and metadata extraction.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize text loader.

        Args:
            **kwargs: Configuration options including:
                - max_length: Maximum text length to process
                - encoding: Text encoding (default: utf-8)
                - validate_encoding: Whether to validate text encoding
                - extract_stats: Whether to extract text statistics
        """
        super().__init__(**kwargs)

        # Default caps (prefer security file-size for files)
        self.max_length = kwargs.get(
            "max_length", 1_000_000
        )  # 1MB chars for in-memory text
        self.encoding = kwargs.get("encoding", "utf-8")
        self.validate_encoding = kwargs.get("validate_encoding", True)
        self.extract_stats = kwargs.get("extract_stats", True)
        self.detect_language = kwargs.get("detect_language", True)

    def validate_source(self, source: str) -> bool:
        """
        Validate if the source is valid text content.

        Args:
            source: Text content or file path to validate

        Returns:
            bool: True if valid text, False otherwise
        """
        if not isinstance(source, str):
            return False

        # Check length
        if len(source) > self.max_length:
            logger.warning(
                f"Text too long: {len(source)} characters > {self.max_length}",
                text_length=len(source),
                max_length=self.max_length,
            )
            return False

        # Check if it's a file path
        if self._is_file_path(source):
            path = Path(source)
            # Only validate file size if file exists, allow non-existent files to proceed
            if path.exists() and path.is_file():
                try:
                    file_size = path.stat().st_size
                    max_bytes = int(settings.security.max_file_size_mb) * 1024 * 1024
                    if file_size > max_bytes:
                        logger.warning(
                            f"Text file too large: {file_size} bytes > {max_bytes}",
                            file_size=file_size,
                            max_bytes=max_bytes,
                        )
                        return False
                except Exception:
                    # If stat fails, allow validate to pass and let loader handle later
                    pass

        return True

    def _is_file_path(self, source: str) -> bool:
        """
        Check if source appears to be a file path.

        Args:
            source: Source string to check

        Returns:
            bool: True if appears to be a file path
        """
        # Simple heuristic: if it contains path separators, has file extension, or is not too long
        has_path_separators = "/" in source or "\\" in source
        # Check for file extension: dot near the end with reasonable extension length
        has_file_extension = False
        if "." in source:
            parts = source.split(".")
            if len(parts) >= 2:
                extension = parts[-1]
                # Valid file extension: 1-10 chars, alphanumeric, and no spaces
                has_file_extension = (
                    1 <= len(extension) <= 10
                    and extension.isalnum()
                    and " "
                    not in source  # file paths typically don't have spaces (in simple cases)
                )

        is_reasonable_length = len(source) < 500

        return (has_path_separators or has_file_extension) and is_reasonable_length

    def get_supported_extensions(self) -> list[str]:
        """Get supported file extensions."""
        return [".txt", ".md", ".rst", ".log"]

    async def load(self, source: str, **kwargs: Any) -> Document:
        """
        Load text content from string or file.

        Args:
            source: Text content or file path
            **kwargs: Additional options:
                - source_type: 'string' or 'file' to force interpretation
                - encoding: Text encoding override
                - metadata: Additional metadata to include

        Returns:
            Document: Loaded document with text content and metadata

        Raises:
            DocumentProcessingError: If text loading or processing fails
            ValidationError: If text validation fails
        """
        if not self.validate_source(source):
            raise ValidationError(
                "Invalid text source",
                field="source",
                value=source[:100] + "..." if len(source) > 100 else source,
            )

        try:
            logger.debug(f"Loading text content (length: {len(source)})")

            # Determine if source is file path or direct text
            source_type = kwargs.get("source_type")
            encoding = kwargs.get("encoding", self.encoding)

            if source_type == "file" or (
                source_type is None and self._is_file_path(source)
            ):
                # Load from file
                text_content, file_metadata = await self._load_from_file(
                    source, encoding
                )
                source_identifier = source
                doc_type = "text"
                source_type_resolved = "file"
            else:
                # Use source as direct text content
                text_content = source
                file_metadata = {}
                source_identifier = "direct_text"
                doc_type = "text"
                source_type_resolved = "string"

            # Validate text content (allow empty files for file loading)
            if (
                not text_content.strip()
                and source_type != "file"
                and not self._is_file_path(source)
            ):
                raise ValidationError(
                    "Text content is empty or contains only whitespace",
                    field="content",
                    value=text_content[:100],
                )

            # Normalize basic whitespace/newlines (preserve paragraph breaks)
            try:
                text_content = text_content.replace("\r\n", "\n").replace("\r", "\n")
                # Collapse 3+ newlines to 2
                import re as _re

                text_content = _re.sub(r"\n{3,}", "\n\n", text_content)
            except Exception:
                pass

            # Extract metadata
            metadata = self._extract_metadata(
                text_content, file_metadata, source_identifier
            )
            # Standardize keys
            metadata.setdefault("type", "text")
            metadata.setdefault("source_type", source_type_resolved)
            # MIME type based on extension (best-effort)
            mime: str = "text/plain"
            try:
                ext = metadata.get("file_extension", "").lower()
                if ext in {".md", ".markdown"}:
                    mime = "text/markdown"
                elif ext in {".rst"}:
                    mime = "text/x-rst"
                elif ext in {".log"}:
                    mime = "text/plain"
            except Exception:
                pass
            metadata.setdefault("mime_type", mime)

            # Approx size and tokens
            metadata["approx_chars"] = len(text_content)
            metadata["estimated_tokens"] = self._estimate_tokens(text_content)

            # Optional language detection (3-segment voting)
            if self.detect_language:
                lang = self._detect_language_voted(text_content)
                if lang:
                    metadata["language"] = lang

            # Add any additional metadata from kwargs
            additional_metadata = kwargs.get("metadata", {})
            metadata.update(additional_metadata)

            logger.info(
                f"Successfully loaded text content: {len(text_content)} characters",
                source=source_identifier,
                text_length=len(text_content),
                doc_type=doc_type,
            )

            return Document(
                text=text_content,
                metadata=metadata,
                source=source_identifier,
                document_type=doc_type,
            )

        except (ValidationError, DocumentProcessingError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading text: {e}")
            raise DocumentProcessingError(
                f"Failed to load text content: {str(e)}",
                document_type="text",
                source=source[:100] + "..." if len(source) > 100 else source,
                details=str(e),
            ) from e

    async def _load_from_file(
        self, file_path: str, encoding: str
    ) -> tuple[str, Dict[str, Any]]:
        """
        Load text content from file.

        Args:
            file_path: Path to text file
            encoding: Text encoding to use

        Returns:
            tuple[str, Dict[str, Any]]: Text content and file metadata

        Raises:
            DocumentProcessingError: If file loading fails
        """
        try:
            path = Path(file_path)

            # Check file exists and is readable
            if not path.exists():
                raise DocumentProcessingError(
                    f"Failed to load text file: {file_path} does not exist",
                    document_type="text",
                    source=file_path,
                )

            if not path.is_file():
                raise DocumentProcessingError(
                    f"Failed to load text file: {file_path} is not a file",
                    document_type="text",
                    source=file_path,
                )

            # Get file stats
            file_stats = path.stat()

            # Read file content
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
            except UnicodeDecodeError as e:
                # Try with different encodings
                for fallback_encoding in ["utf-8", "latin-1", "cp1252"]:
                    if fallback_encoding != encoding:
                        try:
                            with open(path, "r", encoding=fallback_encoding) as f:
                                content = f.read()
                            logger.warning(
                                f"Used fallback encoding {fallback_encoding} for {file_path}",
                                original_encoding=encoding,
                                fallback_encoding=fallback_encoding,
                            )
                            encoding = fallback_encoding
                            break
                        except UnicodeDecodeError:
                            continue
                else:
                    raise DocumentProcessingError(
                        f"Could not decode file with any supported encoding: {e}",
                        document_type="text_file",
                        source=file_path,
                        details=str(e),
                    )

            # File metadata
            file_metadata = {
                "file_name": path.name,
                "file_path": str(path.absolute()),
                "file_size": file_stats.st_size,
                "file_modified": file_stats.st_mtime,
                "file_extension": path.suffix.lower(),
                "encoding": encoding,
            }

            return content, file_metadata

        except DocumentProcessingError:
            raise
        except Exception as e:
            raise DocumentProcessingError(
                f"Error reading file {file_path}: {str(e)}",
                document_type="text_file",
                source=file_path,
                details=str(e),
            ) from e

    def _extract_metadata(
        self, text_content: str, file_metadata: Dict[str, Any], source_identifier: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from text content.

        Args:
            text_content: The text content
            file_metadata: File-related metadata (if applicable)
            source_identifier: Source identifier

        Returns:
            Dict[str, Any]: Extracted metadata
        """
        metadata = {
            "loader": "TextLoader",
            "loader_version": "1.0.0",
            "source_identifier": source_identifier,
            "source": file_metadata.get("file_path", source_identifier),
            "content_length": len(text_content),
        }

        # Add file metadata if available
        metadata.update(file_metadata)

        # Extract text statistics if enabled
        if self.extract_stats:
            stats = self._extract_text_stats(text_content)
            metadata.update(stats)

        return metadata

    def _extract_text_stats(self, text: str) -> Dict[str, Any]:
        """
        Extract statistical information from text.

        Args:
            text: Text content to analyze

        Returns:
            Dict[str, Any]: Text statistics
        """
        try:
            # Basic statistics
            char_count = len(text)
            word_count = len(text.split())
            line_count = text.count("\n") + 1

            # Character analysis
            alpha_count = sum(1 for c in text if c.isalpha())
            digit_count = sum(1 for c in text if c.isdigit())
            space_count = sum(1 for c in text if c.isspace())

            # Persian character ratio (kept as a feature in stats)
            persian_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
            persian_ratio = persian_chars / char_count if char_count > 0 else 0

            return {
                "char_count": char_count,
                "word_count": word_count,
                "line_count": line_count,
                "alpha_count": alpha_count,
                "digit_count": digit_count,
                "space_count": space_count,
                "persian_char_count": persian_chars,
                "persian_ratio": round(persian_ratio, 3),
                "avg_word_length": round(alpha_count / word_count, 2)
                if word_count > 0
                else 0,
            }

        except Exception as e:
            logger.warning(f"Error extracting text statistics: {e}")
            return {"stats_error": str(e)}

    def _detect_language_voted(self, text: str) -> Optional[str]:
        try:
            from langdetect import detect  # type: ignore
        except Exception:
            return None
        try:
            n = len(text)
            if n == 0:
                return None
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
        except Exception:
            return None

    def _estimate_tokens(self, text: str) -> int:
        try:
            import tiktoken  # type: ignore

            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = tiktoken.get_encoding(tiktoken.list_encoding_names()[0])
            return len(enc.encode(text))
        except Exception:
            return len(text.split())


def load_text_content(content: str, **kwargs: Any) -> Document:
    """
    Convenience function to load text content directly.

    Args:
        content: Text content to load
        **kwargs: Additional options for TextLoader

    Returns:
        Document: Loaded document

    Raises:
        DocumentProcessingError: If loading fails
    """
    loader = TextLoader(**kwargs)
    import asyncio

    try:
        # Run in an event loop; if one is already running, fall back to to_thread
        try:
            loop = asyncio.get_running_loop()
            # If inside an event loop, schedule task and wait
            return loop.run_until_complete(loader.load(content, source_type="string"))
        except RuntimeError:
            return asyncio.run(loader.load(content, source_type="string"))
    except Exception as e:
        raise DocumentProcessingError(
            f"Failed to load text content: {str(e)}",
            document_type="text",
            source=content[:100] + "..." if len(content) > 100 else content,
        ) from e
