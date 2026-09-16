"""
Base chunker interface for text splitting.

This module defines the base interface that all text chunkers must implement,
providing a consistent API for splitting text into chunks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional


@dataclass
class TextChunk:
    """
    Represents a chunk of text with metadata.

    Attributes:
        content: The text content of the chunk
        metadata: Additional metadata about the chunk
        start_index: Starting character index in the original text
        end_index: Ending character index in the original text
        chunk_id: Unique identifier for the chunk
    """

    content: str
    metadata: Dict[str, Any]
    start_index: int = 0
    end_index: int = 0
    chunk_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Post-initialization validation."""
        if not isinstance(self.content, str):
            raise ValueError("Chunk content must be a string")
        if not isinstance(self.metadata, dict):
            raise ValueError("Chunk metadata must be a dictionary")
        if self.start_index < 0:
            raise ValueError("Start index must be non-negative")
        if self.end_index < self.start_index:
            raise ValueError("End index must be >= start index")

    @property
    def length(self) -> int:
        """Get the length of the chunk content."""
        return len(self.content)

    def __len__(self) -> int:
        """Get the length of the chunk content."""
        return len(self.content)

    @property
    def word_count(self) -> int:
        """Get the word count of the chunk content."""
        return len(self.content.split())


if TYPE_CHECKING:
    from ragbot.rag.loaders.base import Document


class BaseChunker(ABC):
    """
    Abstract base class for text chunkers.

    All text chunkers must inherit from this class and implement
    the chunk method to provide consistent text chunking interface.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the chunker with configuration options.

        Args:
            **kwargs: Chunker-specific configuration options
        """
        self.config = kwargs

    @abstractmethod
    def chunk(self, text: str, **kwargs: Any) -> List[TextChunk]:
        """
        Split text into chunks.

        Args:
            text: Text to be chunked
            **kwargs: Additional chunking options

        Returns:
            List[TextChunk]: List of text chunks with metadata

        Raises:
            DocumentProcessingError: If chunking fails
        """
        pass

    async def chunk_document(self, document: "Document") -> List["Document"]:
        """
        Chunk a document into smaller documents.

        This is a default implementation that extracts text from the document
        and uses the chunk method. Subclasses can override for specialized behavior.

        Args:
            document: Document to be chunked

        Returns:
            List[Document]: List of chunked documents

        Raises:
            DocumentProcessingError: If chunking fails
        """
        from ragbot.rag.loaders.base import Document

        try:
            # Extract text from document
            text = document.text
            if not text or not text.strip():
                return [document]  # Return original if no content

            # Chunk the text, passing through loader metadata for structural awareness
            chunks = self.chunk(
                text,
                document_id=document.source or "unknown",
                metadata=document.metadata or {},
            )

            # Convert TextChunks to Documents
            chunk_documents = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    **document.metadata,  # Copy original metadata
                    **chunk.metadata,  # Add chunk-specific metadata
                    "original_source": document.source,
                    "chunk_id": chunk.chunk_id,
                    "parent_document": document.source or "unknown",
                }

                chunk_doc = Document(
                    text=chunk.content,
                    metadata=chunk_metadata,
                    source=f"{document.source}_chunk_{i}"
                    if document.source
                    else f"chunk_{i}",
                    document_type=document.document_type,
                )
                chunk_documents.append(chunk_doc)

            return chunk_documents

        except Exception as e:
            from ragbot.rag.exceptions import DocumentProcessingError

            raise DocumentProcessingError(f"Failed to chunk document: {str(e)}") from e

    def validate_text(self, text: str) -> bool:
        """
        Validate if the text can be chunked by this chunker.

        Args:
            text: Text to validate

        Returns:
            bool: True if text can be chunked, False otherwise
        """
        return isinstance(text, str) and len(text.strip()) > 0

    def get_chunker_info(self) -> Dict[str, Any]:
        """
        Get information about this chunker.

        Returns:
            Dict[str, Any]: Chunker information including name, config, etc.
        """
        return {
            "name": self.__class__.__name__,
            "config": self.config,
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the chunker.

        Returns:
            Dict[str, Any]: Health status information
        """
        import time

        try:
            # Basic health check - verify chunker is properly initialized
            chunker_info = self.get_chunker_info()

            # Test chunking with a simple text
            test_text = "This is a test text for health check."
            test_chunks = self.chunk(test_text)

            return {
                "status": "healthy",
                "chunker_name": chunker_info["name"],
                "config_loaded": bool(self.config),
                "test_chunking_successful": len(test_chunks) > 0,
                "test_chunks_count": len(test_chunks),
                "last_check": time.time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "chunker_name": self.__class__.__name__,
                "error": str(e),
                "last_check": time.time(),
            }

    def estimate_chunks(self, text: str) -> int:
        """
        Estimate the number of chunks that will be created.

        Args:
            text: Text to estimate chunks for

        Returns:
            int: Estimated number of chunks
        """
        # Default implementation - subclasses should override for better estimates
        return max(1, len(text) // 1000)

    def get_chunk_overlap_info(self) -> Dict[str, Any]:
        """
        Get information about chunk overlap settings.

        Returns:
            Dict[str, Any]: Overlap information
        """
        return {"has_overlap": False, "overlap_size": 0, "overlap_strategy": "none"}

    # ---------- shared helpers for all chunkers ----------
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Collapse excessive whitespace while preserving newlines and tabs."""
        import re as _re

        if not isinstance(text, str):
            return ""
        # Remove control chars except tab/newline
        txt = _re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)
        # Collapse spaces but keep tabs/newlines
        txt = _re.sub(r"[ ]{2,}", " ", txt)
        # Trim trailing spaces on lines
        txt = _re.sub(r"[ \t]+\n", "\n", txt)
        return txt.strip()

    @staticmethod
    def enforce_span(
        original_text: str, content: str, start: int | None, end: int | None
    ) -> tuple[int, int]:
        """Return a safe (start, end) span of content within original_text."""
        if start is None or end is None or start < 0 or end <= start:
            at = original_text.find(content)
            if at < 0:
                at = 0
            return at, at + len(content)
        return start, end

    def clamp_chunk_size_by_tokens(self, content: str, max_tokens: int) -> str:
        """Clamp content by approximate tokens using naive split if tokenizer not available."""
        if max_tokens <= 0 or not content:
            return content
        try:
            # Prefer token counter from TokenChunker if importable
            from ragbot.rag.chunkers.token_chunker import TokenChunker  # local import

            tc = TokenChunker()
            tok = tc.count_tokens(content)
            if tok <= max_tokens:
                return content
            # Fallback: trim by words proportionally
            words = content.split()
            if not words:
                return content
            keep = max(1, int(len(words) * (max_tokens / max(tok, 1))))
            return " ".join(words[:keep])
        except Exception:
            words = content.split()
            if not words:
                return content
            return " ".join(words[:max_tokens])

    # ---------- page/slide annotation helper ----------
    def _annotate_page_slide(
        self,
        chunks: List["TextChunk"],
        original_text: str,
        headings: Any,
        page_ranges: Any = None,
    ) -> None:
        """
        Best-effort annotation of page/slide for chunks using headings metadata.

        Strategy:
        - For each heading with a non-empty text, locate its position in original_text
          (progressively to disambiguate duplicates).
        - Capture associated "page" or "slide" from heading entry.
        - For each chunk, find the nearest heading occurrence whose position is <= chunk.start_index
          and assign its page/slide to the chunk metadata.
        """
        try:
            if not isinstance(headings, list) or not chunks:
                return
            # Build positional index of headings
            occurrences: List[tuple[int, Optional[int], Optional[int]]] = []
            cursor = 0
            for h in headings:
                try:
                    txt = (h.get("text") or "").strip()
                    if not txt:
                        continue
                    page = h.get("page") if isinstance(h.get("page"), int) else None
                    slide = h.get("slide") if isinstance(h.get("slide"), int) else None
                    pos = original_text.find(txt, cursor)
                    if pos < 0:
                        pos = original_text.find(txt)
                        if pos < 0:
                            continue
                    occurrences.append((pos, page, slide))
                    cursor = pos + len(txt)
                except Exception:
                    continue
            # Include page_ranges as coarse boundaries even if no heading match
            ranges: List[tuple[int, int, int]] = []  # (start, end, page)
            if isinstance(page_ranges, list):
                for pr in page_ranges:
                    try:
                        p = int(pr.get("page"))
                        s = int(pr.get("start", 0))
                        e = int(pr.get("end", 0))
                        if e <= 0:
                            continue
                        ranges.append((s, e, p))
                    except Exception:
                        continue
            if not occurrences:
                # Fallback: annotate via page_ranges only
                if not ranges:
                    return
                for ch in chunks:
                    try:
                        s = int(getattr(ch, "start_index", 0))
                        e = int(getattr(ch, "end_index", 0) or s)
                    except Exception:
                        s, e = 0, 0
                    for rs, re, pg in ranges:
                        if s < re and e > rs:
                            ch.metadata.setdefault("page", pg)
                            break
                return
            occurrences.sort(key=lambda x: x[0])
            # Annotate chunks
            for ch in chunks:
                try:
                    start = int(
                        getattr(ch, "start_index", 0)
                        or ch.metadata.get("start_index", 0)
                    )
                except Exception:
                    start = 0
                last_page: Optional[int] = None
                last_slide: Optional[int] = None
                for pos, pg, sl in occurrences:
                    if pos <= start:
                        if pg is not None:
                            last_page = pg
                        if sl is not None:
                            last_slide = sl
                    else:
                        break
                if last_page is not None:
                    ch.metadata.setdefault("page", last_page)
                if last_slide is not None:
                    ch.metadata.setdefault("slide", last_slide)
                # If still no page and page_ranges provided, infer by start/end span
                if last_page is None and isinstance(page_ranges, list):
                    try:
                        s = int(getattr(ch, "start_index", 0))
                        e = int(getattr(ch, "end_index", 0) or s)
                    except Exception:
                        s, e = 0, 0
                    for rs, re, pg in ranges:
                        if s < re and e > rs:
                            ch.metadata.setdefault("page", pg)
                            break
        except Exception:
            return


class TextChunker(ABC):
    """
    Abstract base class for text chunkers.

    All text chunkers must implement the chunk method to split text
    into manageable pieces for processing.
    """

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the chunker.

        Args:
            **kwargs: Configuration options for the chunker
        """
        pass

    @abstractmethod
    def chunk(self, text: str) -> List[str]:
        """
        Split text into chunks.

        Args:
            text: The input text to split

        Returns:
            List of text chunks

        Raises:
            ValueError: If text is invalid
        """
        pass

    def chunk_with_metadata(self, text: str) -> List[TextChunk]:
        """
        Split text into chunks with metadata.

        Args:
            text: The input text to split

        Returns:
            List of TextChunk objects with metadata
        """
        chunks = self.chunk(text)
        result = []

        current_index = 0
        for i, chunk_content in enumerate(chunks):
            start_index = text.find(chunk_content, current_index)
            if start_index == -1:
                start_index = current_index

            end_index = start_index + len(chunk_content)

            chunk = TextChunk(
                content=chunk_content,
                metadata={"chunk_index": i, "total_chunks": len(chunks)},
                start_index=start_index,
                end_index=end_index,
                chunk_id=f"chunk_{i}",
            )
            result.append(chunk)
            current_index = end_index

        return result

    def validate_text(self, text: str) -> None:
        """
        Validate input text.

        Args:
            text: Text to validate

        Raises:
            ValueError: If text is invalid
        """
        if not isinstance(text, str):
            raise ValueError("Input must be a string")
        if not text.strip():
            raise ValueError("Input text cannot be empty or whitespace only")
