"""
Semantic text chunker using sentence similarity.

This module provides functionality to split text into semantically coherent chunks
by analyzing sentence similarity and grouping related sentences together.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    SEMANTIC_DEPS_AVAILABLE = False

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.chunkers.base import BaseChunker, TextChunk
from ragbot.rag.chunkers.token_chunker import TokenChunker
from ragbot.rag.exceptions import DocumentProcessingError

if TYPE_CHECKING:  # only for type checkers
    from ragbot.rag.loaders.base import Document


class SemanticChunker(BaseChunker):
    """
    Semantic text chunker using sentence similarity.

    This chunker splits text into semantically coherent chunks by:
    1. Splitting text into sentences
    2. Computing sentence embeddings
    3. Grouping similar sentences together
    4. Ensuring chunks stay within token limits
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize semantic chunker.

        Args:
            **kwargs: Configuration options including:
                - max_chunk_size: Maximum tokens per chunk
                - min_chunk_size: Minimum tokens per chunk
                - similarity_threshold: Similarity threshold for grouping sentences
                - model_name: Sentence transformer model name
                - fallback_to_token: Whether to fallback to token chunking if semantic fails
        """
        super().__init__(**kwargs)

        self.max_chunk_size = kwargs.get(
            "max_chunk_size", kwargs.get("chunk_size", settings.rag.chunk_size)
        )
        self.min_chunk_size = kwargs.get("min_chunk_size", 100)
        # Minimum characters for a sentence to be considered (configurable)
        adv = getattr(settings, "advanced_chunking", None)
        self.min_sentence_chars = kwargs.get(
            "min_sentence_chars",
            getattr(adv, "semantic_min_sentence_chars", 8),
        )
        self.similarity_threshold = kwargs.get("similarity_threshold", 0.7)
        # Model resolution: explicit arg -> embedding.model (single source of truth)
        self.model_name = kwargs.get(
            "model_name",
            getattr(
                getattr(settings, "embedding", object()), "model", "all-MiniLM-L6-v2"
            ),
        )
        self.fallback_to_token = kwargs.get("fallback_to_token", True)

        # Initialize components
        self.model: Optional[SentenceTransformer] = None
        # Optional external embedder (unified provider: openai/hf/st)
        self._external_embedder = kwargs.get("embedder")
        self.token_chunker = TokenChunker(
            chunk_size=self.max_chunk_size,
            chunk_overlap=kwargs.get("chunk_overlap", settings.rag.chunk_overlap),
        )

        if self._external_embedder is None:
            # Only load local ST model if no external embedder provided
            if SEMANTIC_DEPS_AVAILABLE:
                try:
                    # Ensure local cache directory is respected (align with STEmbedder/HF embedder)
                    cache_dir = getattr(
                        getattr(settings, "embedding", object()),
                        "cache_folder",
                        "./cache/sentence_transformers",
                    )
                    self.model = SentenceTransformer(
                        self.model_name, cache_folder=cache_dir
                    )
                    logger.info(f"Loaded semantic model: {self.model_name}")
                except Exception as e:
                    logger.warning(f"Failed to load semantic model: {e}")
                    if not self.fallback_to_token:
                        raise DocumentProcessingError(
                            f"Failed to initialize semantic chunker: {e}",
                            details=str(e),
                        ) from e
            else:
                logger.warning(
                    "Semantic dependencies not available, will fallback to token chunking"
                )
                if not self.fallback_to_token:
                    raise ImportError(
                        "sentence-transformers and scikit-learn are required for semantic chunking. "
                        "Install with: pip install sentence-transformers scikit-learn"
                    )

        # Sentence splitting patterns
        self.sentence_patterns = [
            r"(?<=[.!?])\s+(?=[A-Z])",  # English sentences (capital next)
            r"(?<=[。！？])\s*",  # Chinese/Japanese sentences
            r"(?<=[\.!?])\s+(?=\S)",  # General pattern
            r"(?<=[\u061F\u061B\u060C])\s+",  # Persian: ؟ ؛ ،
        ]

        logger.debug(
            "SemanticChunker initialized",
            max_chunk_size=self.max_chunk_size,
            min_chunk_size=self.min_chunk_size,
            similarity_threshold=self.similarity_threshold,
            model_available=self.model is not None,
        )

    # Compatibility properties for tests
    @property
    def chunk_size(self) -> int:
        """Compatibility property for chunk_size."""
        return self.max_chunk_size

    async def chunk_text(self, text: str, **kwargs: Any) -> List[TextChunk]:
        """Async compatibility method for chunk_text."""
        return self.chunk(text, **kwargs)

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
                return [document]  # Return original if no content

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

    def _get_sentence_embeddings(self, sentences: List[str]) -> List[List[float]]:
        """Compatibility method for _get_sentence_embeddings."""
        return self._compute_sentence_embeddings([(s, 0, len(s)) for s in sentences])

    def _calculate_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Compatibility method for _calculate_similarity."""
        if not SEMANTIC_DEPS_AVAILABLE:
            return 0.5  # Default similarity
        return float(cosine_similarity([emb1], [emb2])[0][0])

    def chunk(self, text: str, **kwargs: Any) -> List[TextChunk]:
        """
        Split text into semantically coherent chunks.

        Args:
            text: Text to be chunked
            **kwargs: Additional options:
                - document_id: Document identifier for chunk IDs
                - force_semantic: Force semantic chunking even if model unavailable

        Returns:
            List[TextChunk]: List of semantically coherent text chunks

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

        # Consume structural metadata for boundary protection
        metadata_in: Dict[str, Any] = kwargs.get("metadata", {}) or {}
        headings = metadata_in.get("headings") or []
        # Optional hints (may be unused depending on structure availability)
        _tables_max_cols = metadata_in.get("tables_max_cols")
        _language = metadata_in.get("language") or metadata_in.get("likely_language")

        # Build protected spans: headings text occurrences and table-like lines
        protected_spans: List[Tuple[int, int]] = []
        try:
            if isinstance(headings, list):
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

        # Mark table/code blocks as protected (avoid splitting inside)
        for m in re.finditer(
            r"(^\s*\[Table\].*$)|(^\s*```[\s\S]*?```)|(^.*\t.*$)", text, re.MULTILINE
        ):
            protected_spans.append((m.start(), m.end()))

        # Normalize and merge protected spans to simplify checks
        if protected_spans:
            protected_spans.sort(key=lambda x: x[0])
            merged: List[Tuple[int, int]] = []
            for s, e in protected_spans:
                if not merged or s > merged[-1][1]:
                    merged.append((s, e))
                else:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            protected_spans = merged

        # Fallback to token chunking if semantic model not available
        if (
            self.model is None
            and self._external_embedder is None
            and self.fallback_to_token
        ):
            logger.info("Falling back to token chunking")
            return self.token_chunker.chunk(text, **kwargs)

        if self.model is None and self._external_embedder is None:
            raise DocumentProcessingError(
                "Semantic model not available and fallback disabled",
                details="Cannot perform semantic chunking without model",
            )

        try:
            logger.debug(f"Semantic chunking text: {len(text)} characters")

            document_id = kwargs.get("document_id", "unknown")

            # Split text into sentences
            sentences = self._split_into_sentences(text)
            # Penalize/adjust boundaries using structure: avoid starting/ending inside protected spans
            if sentences:
                adjusted: List[Tuple[str, int, int]] = []
                for s, a, b in sentences:
                    if self._intersects_protected(a, b, protected_spans):
                        # extend to cover full protected block
                        a2, b2 = self._expand_to_protected(a, b, protected_spans)
                        seg = text[a2:b2].strip()
                        if seg:
                            adjusted.append((seg, a2, b2))
                    else:
                        adjusted.append((s, a, b))
                sentences = adjusted

            if len(sentences) <= 1:
                # Single sentence or no sentences, return as single chunk
                return self._create_single_chunk(text, document_id)

            # Compute sentence embeddings
            embeddings = self._compute_sentence_embeddings(sentences)

            # Group sentences into semantic chunks
            sentence_groups = self._group_sentences_by_similarity(sentences, embeddings)
            # Strengthen boundaries: split groups at heading lines and protected gaps
            if headings or protected_spans:
                sentence_groups = self._respect_structural_boundaries(
                    sentence_groups, sentences, protected_spans
                )

            # Convert sentence groups to text chunks (use actual sentences with positions)
            chunks = self._create_chunks_from_groups(
                sentence_groups, text, document_id, sentences
            )

            # Ensure chunks meet size constraints
            chunks = self._enforce_size_constraints(chunks, document_id)

            logger.info(
                f"Successfully created {len(chunks)} semantic chunks from {len(sentences)} sentences",
                total_sentences=len(sentences),
                total_chunks=len(chunks),
            )

            # Annotate page/slide using headings/page_ranges when available
            try:
                from ragbot.rag.chunkers.base import BaseChunker as _B

                meta_in = kwargs.get("metadata", {}) or {}
                _B._annotate_page_slide(
                    self,
                    chunks,
                    text,
                    meta_in.get("headings"),
                    meta_in.get("page_ranges"),
                )
            except Exception:
                pass

            return chunks

        except Exception as e:
            logger.error(f"Error during semantic chunking: {e}")

            # Fallback to token chunking if enabled
            if self.fallback_to_token:
                logger.info("Falling back to token chunking due to error")
                return self.token_chunker.chunk(text, **kwargs)

            raise DocumentProcessingError(
                f"Failed to perform semantic chunking: {str(e)}", details=str(e)
            ) from e

    def _split_into_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Split text into sentences with position information.

        Args:
            text: Text to split

        Returns:
            List[Tuple[str, int, int]]: List of (sentence, start_pos, end_pos) tuples
        """
        sentences = []

        # Try different sentence splitting patterns
        for pattern in self.sentence_patterns:
            try:
                parts = re.split(pattern, text)
                if len(parts) > 1:
                    # Found sentence boundaries
                    current_pos = 0
                    for part in parts:
                        if part.strip():
                            start_pos = text.find(part, current_pos)
                            end_pos = start_pos + len(part)
                            sentences.append((part.strip(), start_pos, end_pos))
                            current_pos = end_pos
                    break
            except Exception as e:
                logger.debug(f"Error with pattern {pattern}: {e}")
                continue

        # Fallback: treat entire text as single sentence
        if not sentences:
            sentences = [(text.strip(), 0, len(text))]

        # Filter out very short sentences
        min_len = max(1, int(self.min_sentence_chars))
        sentences = [
            (s, start, end) for s, start, end in sentences if len(s.strip()) >= min_len
        ]

        return sentences

    def _compute_sentence_embeddings(
        self, sentences: List[Tuple[str, int, int]]
    ) -> "np.ndarray":
        """
        Compute embeddings for sentences.

        Args:
            sentences: List of sentence tuples

        Returns:
            np.ndarray: Sentence embeddings matrix
        """
        sentence_texts = [s[0] for s in sentences]
        try:
            if self._external_embedder is not None:
                vecs = self._external_embedder.embed_texts(sentence_texts)
                # Convert to numpy if available
                try:
                    import numpy as _np  # local import to avoid hard dependency

                    return _np.array(vecs)
                except Exception as e:
                    # As a minimal fallback, require ST deps
                    if not SEMANTIC_DEPS_AVAILABLE:
                        raise DocumentProcessingError(
                            "NumPy not available for external embeddings conversion"
                        ) from e
                    import numpy as _np  # type: ignore

                    return _np.array(vecs)
            # Local ST model path
            embeddings = self.model.encode(sentence_texts, convert_to_numpy=True)  # type: ignore[union-attr]
            return embeddings
        except Exception as e:
            logger.error(f"Error computing sentence embeddings: {e}")
            raise DocumentProcessingError(
                f"Failed to compute sentence embeddings: {str(e)}", details=str(e)
            ) from e

    def _intersects_protected(
        self, a: int, b: int, spans: List[Tuple[int, int]]
    ) -> bool:
        for s, e in spans:
            if a < e and b > s:
                return True
        return False

    def _expand_to_protected(
        self, a: int, b: int, spans: List[Tuple[int, int]]
    ) -> Tuple[int, int]:
        if not spans:
            return a, b
        new_a, new_b = a, b
        for s, e in spans:
            if a < e and b > s:
                new_a = min(new_a, s)
                new_b = max(new_b, e)
        return new_a, new_b

    def _respect_structural_boundaries(
        self,
        groups: List[List[int]],
        sentences: List[Tuple[str, int, int]],
        protected: List[Tuple[int, int]],
    ) -> List[List[int]]:
        if not groups:
            return groups
        if not protected:
            return groups
        out: List[List[int]] = []
        for grp in groups:
            if not grp:
                continue
            current: List[int] = []
            prev_end: Optional[int] = None
            for idx in grp:
                s, a, b = sentences[idx]
                # cut if a protected boundary between previous and current
                if prev_end is not None and any(
                    prev_end <= ps <= a or prev_end <= pe <= a for ps, pe in protected
                ):
                    if current:
                        out.append(current)
                        current = []
                current.append(idx)
                prev_end = b
            if current:
                out.append(current)
        return out

    def _group_sentences_by_similarity(
        self, sentences: List[Tuple[str, int, int]], embeddings: np.ndarray
    ) -> List[List[int]]:
        """
        Group sentences by semantic similarity.

        Args:
            sentences: List of sentence tuples
            embeddings: Sentence embeddings matrix

        Returns:
            List[List[int]]: List of sentence index groups
        """
        if len(sentences) <= 1:
            return [[0]] if sentences else []

        # Compute similarity matrix
        similarity_matrix = cosine_similarity(embeddings)

        # Group sentences using simple clustering
        groups = []
        used_sentences = set()

        for i, (_, _, _) in enumerate(sentences):
            if i in used_sentences:
                continue

            # Start new group with current sentence
            current_group = [i]
            used_sentences.add(i)

            # Find similar sentences
            for j in range(i + 1, len(sentences)):
                if j in used_sentences:
                    continue

                # Check if sentence j is similar to any sentence in current group
                max_similarity = max(similarity_matrix[i][j] for i in current_group)

                if max_similarity >= self.similarity_threshold:
                    current_group.append(j)
                    used_sentences.add(j)

            groups.append(current_group)

        return groups

    def _create_chunks_from_groups(
        self,
        sentence_groups: List[List[int]],
        original_text: str,
        document_id: str,
        sentences: List[Tuple[str, int, int]],
    ) -> List[TextChunk]:
        """
        Create text chunks from sentence groups.

        Args:
            sentence_groups: List of sentence index groups
            original_text: Original text
            document_id: Document identifier

        Returns:
            List[TextChunk]: List of text chunks
        """
        chunks = []

        for chunk_index, group in enumerate(sentence_groups):
            if not group:
                continue

            # Combine actual sentences in group preserving order and positions
            group_sentences: List[str] = []
            min_start = float("inf")
            max_end = 0

            for sentence_idx in sorted(group):
                try:
                    sentence_text, start_pos, end_pos = sentences[sentence_idx]
                except Exception:
                    # Fallback: skip invalid indices safely
                    continue
                if sentence_text and sentence_text.strip():
                    group_sentences.append(sentence_text.strip())
                    if start_pos < min_start:
                        min_start = start_pos
                    if end_pos > max_end:
                        max_end = end_pos

            chunk_text = " ".join(group_sentences).strip()
            if not chunk_text:
                continue

            # Create chunk
            chunk_id = self._generate_chunk_id(document_id, chunk_index)
            chunk = TextChunk(
                content=chunk_text,
                metadata={
                    "chunk_index": chunk_index,
                    "sentence_count": len(group),
                    "sentence_indices": group,
                    "chunking_method": "semantic",
                    "similarity_threshold": self.similarity_threshold,
                    "document_id": document_id,
                },
                start_index=int(min_start) if min_start != float("inf") else 0,
                end_index=int(max_end)
                if max_end > 0
                else min(
                    len(original_text),
                    (int(min_start) if min_start != float("inf") else 0)
                    + len(chunk_text),
                ),
                chunk_id=chunk_id,
            )

            chunks.append(chunk)

        return chunks

    def _enforce_size_constraints(
        self, chunks: List[TextChunk], document_id: str
    ) -> List[TextChunk]:
        """
        Ensure chunks meet size constraints by splitting or merging as needed.

        Args:
            chunks: List of chunks to process
            document_id: Document identifier

        Returns:
            List[TextChunk]: Size-constrained chunks
        """
        constrained_chunks = []

        prev_chunk: Optional[TextChunk] = None
        for chunk in chunks:
            token_count = self.token_chunker.count_tokens(chunk.content)
            # If very small chunk and there is a previous one, try merging for quality
            if prev_chunk is not None and token_count < max(
                1, int(self.min_chunk_size * 0.5)
            ):
                merged_text = prev_chunk.content.rstrip() + " " + chunk.content.lstrip()
                prev_chunk.content = merged_text
                # Update metadata and indices conservatively
                prev_chunk.metadata["merged_with_next"] = True
                prev_chunk.end_index = max(prev_chunk.end_index, chunk.end_index)
                # Recompute tokens for merged chunk
                prev_tokens = self.token_chunker.count_tokens(prev_chunk.content)
                prev_chunk.metadata["token_count"] = prev_tokens
                continue

            if token_count <= self.max_chunk_size:
                # Chunk is within size limits
                chunk.metadata["token_count"] = token_count
                constrained_chunks.append(chunk)
                prev_chunk = chunk
            else:
                # Chunk is too large, split using token chunker
                logger.debug(f"Splitting large semantic chunk: {token_count} tokens")

                sub_chunks = self.token_chunker.chunk(
                    chunk.content,
                    document_id=document_id,
                    chunk_size=self.max_chunk_size,
                )

                # Update metadata to indicate this was split from semantic chunk
                for i, sub_chunk in enumerate(sub_chunks):
                    sub_chunk.metadata.update(
                        {
                            "parent_chunk_id": chunk.chunk_id,
                            "semantic_split": True,
                            "sub_chunk_index": i,
                        }
                    )

                constrained_chunks.extend(sub_chunks)
                prev_chunk = sub_chunks[-1] if sub_chunks else None

        # Update chunk indices and total count
        for i, chunk in enumerate(constrained_chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = len(constrained_chunks)

        return constrained_chunks

    def _create_single_chunk(self, text: str, document_id: str) -> List[TextChunk]:
        """Create a single chunk from text."""
        chunk_id = self._generate_chunk_id(document_id, 0)
        token_count = self.token_chunker.count_tokens(text)

        chunk = TextChunk(
            content=text,
            metadata={
                "chunk_index": 0,
                "total_chunks": 1,
                "token_count": token_count,
                "chunking_method": "semantic_single",
                "document_id": document_id,
            },
            start_index=0,
            end_index=len(text),
            chunk_id=chunk_id,
        )

        return [chunk]

    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        chunk_string = (
            f"{document_id}_semantic_{chunk_index}_{self.similarity_threshold}"
        )
        return hashlib.md5(chunk_string.encode()).hexdigest()[:12]

    def estimate_chunks(self, text: str) -> int:
        """Estimate the number of chunks that will be created."""
        try:
            sentences = self._split_into_sentences(text)
            # Rough estimate: assume average grouping of 3-5 sentences per chunk
            estimated_groups = max(1, len(sentences) // 4)

            # Account for size constraints
            avg_tokens_per_sentence = self.token_chunker.count_tokens(text) // len(
                sentences
            )
            avg_tokens_per_group = avg_tokens_per_sentence * 4

            if avg_tokens_per_group > self.max_chunk_size:
                # Groups will be split further
                split_factor = avg_tokens_per_group // self.max_chunk_size + 1
                estimated_groups *= split_factor

            return estimated_groups
        except Exception:
            # Fallback to token chunker estimate
            return self.token_chunker.estimate_chunks(text)

    def get_chunk_overlap_info(self) -> Dict[str, Any]:
        """Get information about chunk overlap settings."""
        return {
            "has_overlap": False,  # Semantic chunking doesn't use traditional overlap
            "overlap_size": 0,
            "overlap_strategy": "semantic_similarity",
            "similarity_threshold": self.similarity_threshold,
        }
