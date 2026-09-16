"""
Token-based text chunker using tiktoken.

This module provides functionality to split text into chunks based on token count
using OpenAI's tiktoken library for accurate token counting.
"""

import hashlib
from typing import TYPE_CHECKING, Any, Dict, List

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.chunkers.base import BaseChunker, TextChunk
from ragbot.rag.exceptions import DocumentProcessingError

if TYPE_CHECKING:
    from ragbot.rag.loaders.base import Document


class TokenChunker(BaseChunker):
    """
    Token-based text chunker using tiktoken.

    This chunker splits text into chunks based on token count, ensuring
    that each chunk stays within the specified token limit while
    maintaining semantic coherence where possible.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize token chunker.

        Args:
            **kwargs: Configuration options including:
                - chunk_size: Maximum tokens per chunk
                - chunk_overlap: Number of overlapping tokens between chunks
                - encoding_name: Tiktoken encoding name
                - preserve_sentences: Whether to try to preserve sentence boundaries
                - min_chunk_size: Minimum tokens per chunk
        """
        super().__init__(**kwargs)

        # Allow fallback when tiktoken isn't available (tests may run without it)
        self._fallback_encoding = not TIKTOKEN_AVAILABLE

        self.chunk_size = kwargs.get("chunk_size", settings.rag.chunk_size)
        # Support both 'chunk_overlap' and 'overlap' for compatibility
        self.chunk_overlap = kwargs.get(
            "chunk_overlap", kwargs.get("overlap", settings.rag.chunk_overlap)
        )
        self.encoding_name = kwargs.get(
            "encoding_name", "cl100k_base"
        )  # GPT-3.5/4 encoding
        self.preserve_sentences = kwargs.get("preserve_sentences", True)
        self.min_chunk_size = kwargs.get("min_chunk_size", 50)

        # Initialize tokenizer
        if not self._fallback_encoding:
            try:
                self.encoding = tiktoken.get_encoding(self.encoding_name)
            except Exception as e:
                logger.warning(
                    f"Failed to load encoding {self.encoding_name}, using default: {e}"
                )
                self.encoding = tiktoken.get_encoding("cl100k_base")
        else:
            self.encoding = None

        # Sentence boundary markers for better chunking
        self.sentence_endings = {
            ".",
            "!",
            "?",
            "。",
            "！",
            "？",
            "\u061f",  # Persian question mark
            "\u061b",  # Persian semicolon
            "\u060c",  # Persian comma
        }  # English, CJK, and Persian marks

        logger.debug(
            "TokenChunker initialized",
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            encoding=self.encoding_name,
            preserve_sentences=self.preserve_sentences,
        )

    # Compatibility properties for tests
    @property
    def overlap(self) -> int:
        """Compatibility property for overlap."""
        return self.chunk_overlap

    async def chunk_text(self, text: str, **kwargs: Any) -> List[TextChunk]:
        """Async compatibility method for chunk_text."""
        return self.chunk(text, **kwargs)

    async def chunk_texts(self, texts: List[str], **kwargs: Any) -> List[str]:
        """Chunk multiple texts and return flattened list of string chunks.

        Args:
            texts: List of texts to chunk
            **kwargs: Additional chunking options

        Returns:
            List[str]: Flattened list of text chunks as strings
        """
        all_chunks = []
        for text in texts:
            chunks = self.chunk(text, **kwargs)
            all_chunks.extend([chunk.content for chunk in chunks])
        return all_chunks

    async def chunk_document(self, document: "Document") -> List["Document"]:
        """Chunk a document into smaller documents.

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
                return []  # Return empty list for empty content

            # Chunk the text
            chunks = self.chunk(text, document_id=document.source or "unknown")

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

    def _count_tokens(self, text: str) -> int:
        """Compatibility method that delegates to unified count_tokens."""
        return self.count_tokens(text)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or robust fallbacks."""
        if not text:
            return 0
        if self._fallback_encoding or self.encoding is None:
            # Fallback strategy: word-count as proxy
            # Optionally could be calibrated; keep simple and fast
            return len(text.split())
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return len(text.split())

    def chunk(self, text: str, **kwargs: Any) -> List[TextChunk]:
        """
        Split text into token-based chunks.

        Args:
            text: Text to be chunked
            **kwargs: Additional options:
                - chunk_size: Override default chunk size
                - chunk_overlap: Override default overlap
                - document_id: Document identifier for chunk IDs

        Returns:
            List[TextChunk]: List of text chunks with metadata

        Raises:
            DocumentProcessingError: If chunking fails
        """
        # Handle empty text gracefully
        if not text or not text.strip():
            return []

        if not self.validate_text(text):
            raise DocumentProcessingError(
                "Invalid text for chunking", details="Text must be a non-empty string"
            )

        try:
            logger.debug(f"Chunking text: {len(text)} characters")

            # Override settings if provided
            chunk_size = kwargs.get("chunk_size", self.chunk_size)
            chunk_overlap = kwargs.get("chunk_overlap", self.chunk_overlap)
            document_id = kwargs.get("document_id", "unknown")

            # Structural hints from loaders (docx/pdf/html/markdown)
            metadata_in: Dict[str, Any] = kwargs.get("metadata", {}) or {}
            headings = metadata_in.get("headings") or []
            protected_spans: List[tuple[int, int]] = []
            # Protect headings text occurrences
            try:
                cursor = 0
                for h in headings:
                    txt = (h.get("text") or "").strip()
                    if not txt:
                        continue
                    pos = text.find(txt, cursor)
                    if pos < 0:
                        pos = text.find(txt)
                        if pos < 0:
                            continue
                    protected_spans.append((pos, pos + len(txt)))
                    cursor = pos + len(txt)
            except Exception:
                pass
            # Protect tables and fenced code blocks and tab-lines
            import re as _re

            for m in _re.finditer(
                r"(^\s*\[Table\].*$)|(^\s*```[\s\S]*?```)|(^.*\t.*$)",
                text,
                _re.MULTILINE,
            ):
                protected_spans.append((m.start(), m.end()))
            if protected_spans:
                protected_spans.sort(key=lambda x: x[0])
                merged: List[tuple[int, int]] = []
                for s, e in protected_spans:
                    if not merged or s > merged[-1][1]:
                        merged.append((s, e))
                    else:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                protected_spans = merged

            # Tokenize the entire text
            if self._fallback_encoding:
                tokens = None
                # Position-aware fallback: precompute word offsets
                words = text.split()
                word_offsets = []
                idx = 0
                for w in words:
                    # find next occurrence from idx to handle repeated words
                    at = text.find(w, idx)
                    if at < 0:
                        at = idx
                    word_offsets.append(at)
                    idx = at + len(w)
                total_tokens = len(words)
            else:
                tokens = self.encoding.encode(text)
                total_tokens = len(tokens)

            if total_tokens <= chunk_size:
                # Text fits in a single chunk
                chunk_id = self._generate_chunk_id(document_id, 0)
                return [
                    TextChunk(
                        content=text,
                        metadata={
                            "chunk_index": 0,
                            "total_chunks": 1,
                            "token_count": total_tokens,
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                            "encoding": self.encoding_name,
                            "document_id": document_id,
                            "start_index": 0,
                            "end_index": len(text),
                        },
                        start_index=0,
                        end_index=len(text),
                        chunk_id=chunk_id,
                    )
                ]

            # Split into multiple chunks
            chunks = []
            chunk_index = 0
            start_token_idx = 0

            # Adjust effective sizes in fallback to approximate tokenization density
            eff_chunk_size = chunk_size
            eff_overlap = chunk_overlap
            if self._fallback_encoding:
                density = getattr(
                    getattr(settings, "advanced_chunking", object()),
                    "token_fallback_density_factor",
                    0.7,
                )
                try:
                    density = float(density)
                except Exception:
                    density = 0.7
                density = min(1.0, max(0.1, density))
                eff_chunk_size = max(1, int(chunk_size * density))
                eff_overlap = min(chunk_overlap, max(0, eff_chunk_size - 1))

            while start_token_idx < total_tokens:
                # Calculate end token index
                end_token_idx = min(
                    start_token_idx
                    + (eff_chunk_size if self._fallback_encoding else chunk_size),
                    total_tokens,
                )

                # Extract tokens for this chunk
                if self._fallback_encoding:
                    chunk_tokens = None
                    chunk_words = words[start_token_idx:end_token_idx]
                    chunk_text = " ".join(chunk_words)
                else:
                    chunk_tokens = tokens[start_token_idx:end_token_idx]
                    # Decode tokens back to text
                    chunk_text = self.encoding.decode(chunk_tokens)

                # Try to preserve sentence boundaries if enabled
                if self.preserve_sentences and end_token_idx < total_tokens:
                    chunk_text = self._adjust_chunk_boundary(
                        chunk_text, text, start_token_idx, end_token_idx
                    )

                # Calculate character indices in original text
                if self._fallback_encoding:
                    # Use precomputed offsets for better alignment
                    if start_token_idx < len(word_offsets):
                        start_char_idx = word_offsets[start_token_idx]
                    else:
                        start_char_idx = len(text)
                    end_char_idx = min(len(text), start_char_idx + len(chunk_text))
                else:
                    start_char_idx = len(self.encoding.decode(tokens[:start_token_idx]))
                    end_char_idx = start_char_idx + len(chunk_text)

                # Adjust boundaries to avoid cutting inside protected spans
                if protected_spans and start_char_idx < end_char_idx:
                    safe_end = end_char_idx
                    for ps, pe in protected_spans:
                        if start_char_idx < pe and end_char_idx > ps:
                            safe_end = min(safe_end, ps)
                    if safe_end < end_char_idx and safe_end > start_char_idx + 10:
                        chunk_text = text[start_char_idx:safe_end]
                        end_char_idx = safe_end

                # Prefer ending at a heading/paragraph boundary when near
                if headings and end_char_idx - start_char_idx > 20:
                    boundary_candidates: List[int] = []
                    try:
                        # paragraph break
                        prev_para = text.rfind("\n\n", start_char_idx, end_char_idx)
                        if prev_para != -1:
                            boundary_candidates.append(prev_para)
                        # nearest heading start inside window
                        for ps, _pe in protected_spans:
                            if start_char_idx < ps < end_char_idx:
                                boundary_candidates.append(ps)
                    except Exception:
                        boundary_candidates = []
                    if boundary_candidates:
                        best = max(boundary_candidates)
                        if best > start_char_idx + int(
                            0.6 * (end_char_idx - start_char_idx)
                        ):
                            chunk_text = text[start_char_idx:best]
                            end_char_idx = best

                # Create chunk
                chunk_id = self._generate_chunk_id(document_id, chunk_index)
                chunk = TextChunk(
                    content=chunk_text,
                    metadata={
                        "chunk_index": chunk_index,
                        "token_count": (
                            len(chunk_words)
                            if self._fallback_encoding
                            else len(chunk_tokens)
                        ),
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "encoding": self.encoding_name,
                        "fallback_encoding": self._fallback_encoding,
                        "effective_chunk_size": eff_chunk_size
                        if self._fallback_encoding
                        else chunk_size,
                        "effective_overlap": eff_overlap
                        if self._fallback_encoding
                        else chunk_overlap,
                        "document_id": document_id,
                        "start_token": start_token_idx,
                        "end_token": start_token_idx
                        + (
                            len(chunk_words)
                            if self._fallback_encoding
                            else len(chunk_tokens)
                        ),
                        "start_index": start_char_idx,
                        "end_index": end_char_idx,
                    },
                    start_index=start_char_idx,
                    end_index=end_char_idx,
                    chunk_id=chunk_id,
                )

                chunks.append(chunk)

                # Move to next chunk with overlap
                if (
                    eff_overlap if self._fallback_encoding else chunk_overlap
                ) > 0 and end_token_idx < total_tokens:
                    start_token_idx = end_token_idx - (
                        eff_overlap if self._fallback_encoding else chunk_overlap
                    )
                else:
                    start_token_idx = end_token_idx

                chunk_index += 1

                # Safety check to prevent infinite loops
                if chunk_index > 10000:
                    logger.error(
                        "Too many chunks generated, stopping to prevent infinite loop"
                    )
                    break

            # Update total_chunks in metadata
            total_chunks = len(chunks)
            for chunk in chunks:
                chunk.metadata["total_chunks"] = total_chunks

            logger.info(
                f"Successfully chunked text into {total_chunks} chunks",
                total_tokens=total_tokens,
                total_chunks=total_chunks,
                avg_tokens_per_chunk=total_tokens // total_chunks
                if total_chunks > 0
                else 0,
            )

            # Annotate page/slide where possible
            try:
                from ragbot.rag.chunkers.base import BaseChunker as _B

                _B._annotate_page_slide(
                    self,
                    chunks,
                    text,
                    metadata_in.get("headings"),
                    metadata_in.get("page_ranges"),
                )
            except Exception:
                pass

            return chunks

        except Exception as e:
            logger.error(f"Error during token chunking: {e}")
            raise DocumentProcessingError(
                f"Failed to chunk text: {str(e)}", details=str(e)
            ) from e

    def _adjust_chunk_boundary(
        self, chunk_text: str, full_text: str, start_token_idx: int, end_token_idx: int
    ) -> str:
        """
        Adjust chunk boundary to preserve sentence boundaries.

        Args:
            chunk_text: Current chunk text
            full_text: Full original text
            start_token_idx: Starting token index
            end_token_idx: Ending token index

        Returns:
            str: Adjusted chunk text
        """
        try:
            # Find the last sentence ending in the chunk
            last_sentence_end = -1
            for i in range(len(chunk_text) - 1, -1, -1):
                if chunk_text[i] in self.sentence_endings:
                    # Check if this is followed by whitespace or end of text
                    if i == len(chunk_text) - 1 or chunk_text[i + 1].isspace():
                        last_sentence_end = i + 1
                        break

            # If we found a sentence boundary and it's not too close to the start
            if last_sentence_end > len(chunk_text) * 0.7:  # At least 70% of the chunk
                return chunk_text[:last_sentence_end].rstrip()

            # Otherwise, return the original chunk
            return chunk_text

        except Exception as e:
            logger.debug(f"Error adjusting chunk boundary: {e}")
            return chunk_text

    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """
        Generate a unique chunk ID.

        Args:
            document_id: Document identifier
            chunk_index: Index of the chunk

        Returns:
            str: Unique chunk ID
        """
        chunk_string = (
            f"{document_id}_{chunk_index}_{self.chunk_size}_{self.chunk_overlap}"
        )
        return hashlib.md5(chunk_string.encode()).hexdigest()[:12]

    def estimate_chunks(self, text: str) -> int:
        """
        Estimate the number of chunks that will be created.

        Args:
            text: Text to estimate chunks for

        Returns:
            int: Estimated number of chunks
        """
        if not text:
            return 1
        if self._fallback_encoding or self.encoding is None:
            total_tokens = len(text.split())
        else:
            try:
                total_tokens = len(self.encoding.encode(text))
            except Exception:
                total_tokens = len(text.split())

        if total_tokens <= self.chunk_size:
            return 1

        effective_chunk_size = max(1, self.chunk_size - self.chunk_overlap)
        estimated_chunks = max(
            1, (total_tokens - self.chunk_overlap) // effective_chunk_size
        )
        return estimated_chunks

    def get_chunk_overlap_info(self) -> Dict[str, Any]:
        """Get information about chunk overlap settings."""
        return {
            "has_overlap": self.chunk_overlap > 0,
            "overlap_size": self.chunk_overlap,
            "overlap_strategy": "token_based",
        }

    # remove duplicate count_tokens (kept unified version above)
