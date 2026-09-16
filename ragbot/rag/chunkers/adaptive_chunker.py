"""
Adaptive text chunker that selects between Semantic, Hierarchical, and Token-based strategies.

The selection is based on lightweight analysis of the input text and configuration
thresholds. Output is a list of TextChunk compatible with pipeline expectations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.chunkers.base import BaseChunker, TextChunk


class AdaptiveChunker(BaseChunker):
    """Selects best chunker based on structure, length, and heuristics."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Child chunkers are created lazily to avoid heavy imports when unused
        self._semantic = None
        self._hier = None
        self._token = None

        # Thresholds (pull from settings if present, otherwise defaults)
        adv = getattr(settings, "advanced_chunking", None)
        self.text_length_threshold = getattr(
            adv, "adaptive_text_length_threshold", 5000
        )
        self.structure_complexity_threshold = getattr(
            adv, "adaptive_structure_complexity_threshold", 0.3
        )
        self.semantic_coherence_threshold = getattr(
            adv, "adaptive_semantic_coherence_threshold", 0.7
        )

    def chunk(self, text: str, **kwargs: Any) -> List[TextChunk]:  # type: ignore[override]
        if not isinstance(text, str) or not text.strip():
            return []

        # Pass-through structural metadata from loaders to downstream chunkers
        metadata_in: Dict[str, Any] = kwargs.get("metadata", {}) or {}
        headings = metadata_in.get("headings") or []
        language = metadata_in.get("language") or metadata_in.get("likely_language")
        _tables_max_cols = metadata_in.get("tables_max_cols")

        # 1) Explicit override: if user set a concrete strategy, honor it directly
        explicit = getattr(
            getattr(settings, "advanced_chunking", object()), "chunking_strategy", None
        )
        if explicit in {"full", "hybrid", "semantic", "hierarchical", "token"}:
            strategy = explicit
            analysis = {"reason": "explicit_strategy"}
        else:
            # 2) Adaptive selection based on lightweight analysis
            analysis = self._analyze_text(text)
            strategy = self._select_strategy(analysis)

        try:
            logger.info(
                f"AdaptiveChunker strategy selected: {strategy} (analysis={analysis})"
            )
        except Exception:
            pass

        if strategy == "hierarchical":
            chunks = self._get_hier().chunk(
                text, metadata={"headings": headings, "language": language}
            )
            # Optional final optimization
            try:
                adv = getattr(settings, "advanced_chunking", object())
                if getattr(adv, "enable_chunk_optimization", True):
                    from ragbot.rag.chunkers.chunk_optimizer import ChunkOptimizer

                    opt = ChunkOptimizer(
                        target_size=getattr(adv, "chunk_target_size", 500),
                        size_tolerance=getattr(adv, "chunk_size_tolerance", 0.2),
                    )
                    chunks = opt.optimize(chunks)
            except Exception:
                pass
            for ch in chunks:
                ch.metadata.setdefault("analysis", analysis)
                ch.metadata.setdefault("selected_strategy", strategy)
            return chunks
        if strategy == "semantic":
            chunks = self._get_semantic().chunk(
                text, metadata={"headings": headings, "language": language}
            )
            # Optional final optimization
            try:
                adv = getattr(settings, "advanced_chunking", object())
                if getattr(adv, "enable_chunk_optimization", True):
                    from ragbot.rag.chunkers.chunk_optimizer import ChunkOptimizer

                    opt = ChunkOptimizer(
                        target_size=getattr(adv, "chunk_target_size", 500),
                        size_tolerance=getattr(adv, "chunk_size_tolerance", 0.2),
                    )
                    chunks = opt.optimize(chunks)  # type: ignore[misc]
            except Exception:
                pass
            for ch in chunks:
                ch.metadata.setdefault("analysis", analysis)
                ch.metadata.setdefault("selected_strategy", strategy)
            return chunks

        # Full: apply hierarchical first, then semantic refinement (token-aware) on eligible chunks
        if strategy == "full":
            base_chunks = self._get_hier().chunk(
                text, metadata={"headings": headings, "language": language}
            )
            if not base_chunks:
                try:
                    logger.warning(
                        "Full: hierarchical produced 0 chunks, falling back to token"
                    )
                except Exception:
                    pass
                return self._get_token().chunk(text, **kwargs)
            refined: List[TextChunk] = []
            # Determine token-based refinement threshold (fallback to chunk_target_size or 500)
            full_refine_threshold = getattr(
                getattr(settings, "advanced_chunking", object()),
                "chunk_target_size",
                500,
            )
            try:
                from ragbot.rag.chunkers.token_chunker import TokenChunker

                tok = TokenChunker()
            except Exception:
                tok = None

            for c in base_chunks:
                # Decide if this chunk needs semantic refinement
                try:
                    token_len = tok.count_tokens(c.content) if tok else len(c.content)
                except Exception:
                    token_len = len(c.content)

                if token_len <= max(1, int(full_refine_threshold)):
                    # Keep hierarchical chunk as-is
                    c.metadata.setdefault("analysis", analysis)
                    c.metadata.setdefault("selected_strategy", strategy)
                    refined.append(c)
                    continue

                # Run semantic refinement on chunk content
                subs = self._get_semantic().chunk(
                    c.content, metadata={"headings": headings, "language": language}
                )
                if subs:
                    for s in subs:
                        # Adjust positions to absolute by offsetting with parent start
                        try:
                            s.start_index = (s.start_index or 0) + (c.start_index or 0)
                            s.end_index = (s.end_index or 0) + (c.start_index or 0)
                        except Exception:
                            pass
                        s.metadata = {
                            **c.metadata,
                            **s.metadata,
                            "chunk_type": "full",
                            "parent_id": c.chunk_id,
                            "selected_strategy": strategy,
                            "analysis": analysis,
                        }
                    refined.extend(subs)
                else:
                    # Fallback to original chunk
                    c.metadata.setdefault("analysis", analysis)
                    c.metadata.setdefault("selected_strategy", strategy)
                    refined.append(c)
            if not refined:
                try:
                    logger.warning(
                        "Full: semantic refinement produced 0 chunks, using base chunks"
                    )
                except Exception:
                    pass
                refined = base_chunks
            try:
                logger.info(
                    f"Full chunking pipeline applied: base_count={len(base_chunks)}, refined_count={len(refined)}"
                )
            except Exception:
                pass
            for ch in refined:
                ch.metadata.setdefault("analysis", analysis)
                ch.metadata.setdefault("selected_strategy", strategy)
            # Merge very short adjacent chunks to reduce noise
            try:
                adv = getattr(settings, "advanced_chunking", object())
                min_chars = getattr(adv, "semantic_min_chunk_size", 100)
                merged: List[TextChunk] = []
                for ch in refined:
                    if merged:
                        prev = merged[-1]
                        if len(ch.content.strip()) < max(1, int(min_chars * 0.5)):
                            # merge into previous
                            sep = (
                                " "
                                if (prev.content and not prev.content.endswith("\n"))
                                else ""
                            )
                            prev_end_before = prev.end_index or 0
                            prev.content = f"{prev.content}{sep}{ch.content}".strip()
                            try:
                                prev.end_index = max(
                                    prev_end_before, (ch.end_index or prev_end_before)
                                )
                            except Exception:
                                pass
                            prev.metadata["merged_next"] = True
                            continue
                    merged.append(ch)
                refined = merged
            except Exception:
                pass

            # Optional final optimization
            try:
                adv = getattr(settings, "advanced_chunking", object())
                if getattr(adv, "enable_chunk_optimization", True):
                    from ragbot.rag.chunkers.chunk_optimizer import ChunkOptimizer

                    opt = ChunkOptimizer(
                        target_size=getattr(adv, "chunk_target_size", 500),
                        size_tolerance=getattr(adv, "chunk_size_tolerance", 0.2),
                    )
                    refined = opt.optimize(refined)  # type: ignore[misc]
            except Exception:
                pass
            for ch in refined:
                ch.metadata.setdefault("analysis", analysis)
                ch.metadata.setdefault("selected_strategy", strategy)
            return refined

        # Hybrid: start hierarchical, refine very long chunks semantically
        if strategy == "hybrid":
            chunks = self._get_hier().chunk(
                text, metadata={"headings": headings, "language": language}
            )
            refined: List[TextChunk] = []
            for c in chunks:
                # Token-aware threshold from settings when available
                try:
                    from ragbot.rag.chunkers.token_chunker import TokenChunker

                    tok = TokenChunker()
                    token_len = tok.count_tokens(c.content)
                except Exception:
                    token_len = len(c.content)
                hybrid_threshold = getattr(
                    getattr(settings, "advanced_chunking", object()),
                    "chunk_target_size",
                    500,
                )
                if token_len > hybrid_threshold:
                    subs = self._get_semantic().chunk(
                        c.content,
                        metadata={"headings": headings, "language": language},
                    )
                    # Propagate parent metadata
                    for s in subs:
                        s.metadata = {
                            **c.metadata,
                            **s.metadata,
                            "chunk_type": "hybrid",
                            "parent_id": c.chunk_id,
                        }
                    refined.extend(subs)
                else:
                    refined.append(c)
            # Optional final optimization
            try:
                adv = getattr(settings, "advanced_chunking", object())
                if getattr(adv, "enable_chunk_optimization", True):
                    from ragbot.rag.chunkers.chunk_optimizer import ChunkOptimizer

                    opt = ChunkOptimizer(
                        target_size=getattr(adv, "chunk_target_size", 500),
                        size_tolerance=getattr(adv, "chunk_size_tolerance", 0.2),
                    )
                    refined = opt.optimize(refined)  # type: ignore[misc]
            except Exception:
                pass
            for ch in refined:
                ch.metadata.setdefault("analysis", analysis)
                ch.metadata.setdefault("selected_strategy", strategy)
            return refined

        # Default: token-based
        chunks = self._get_token().chunk(
            text, metadata={"headings": headings, "language": language}
        )
        # Optional final optimization
        try:
            adv = getattr(settings, "advanced_chunking", object())
            if getattr(adv, "enable_chunk_optimization", True):
                from ragbot.rag.chunkers.chunk_optimizer import ChunkOptimizer

                opt = ChunkOptimizer(
                    target_size=getattr(adv, "chunk_target_size", 500),
                    size_tolerance=getattr(adv, "chunk_size_tolerance", 0.2),
                )
                chunks = opt.optimize(chunks)  # type: ignore[misc]
        except Exception:
            pass
        for ch in chunks:
            ch.metadata.setdefault("analysis", analysis)
            ch.metadata.setdefault("selected_strategy", strategy)
        # Best-effort annotation already handled in token chunker; return
        return chunks

    # ---------- internals ----------
    def _get_semantic(self):
        if self._semantic is None:
            from ragbot.rag.chunkers.semantic_chunker import SemanticChunker

            self._semantic = SemanticChunker()
        return self._semantic

    def _get_hier(self):
        if self._hier is None:
            from ragbot.rag.chunkers.hierarchical_chunker import HierarchicalChunker

            self._hier = HierarchicalChunker()
        return self._hier

    def _get_token(self):
        if self._token is None:
            from ragbot.rag.chunkers.token_chunker import TokenChunker

            self._token = TokenChunker(
                chunk_size=settings.rag.chunk_size,
                chunk_overlap=settings.rag.chunk_overlap,
            )
        return self._token

    def _analyze_text(self, text: str) -> Dict[str, Any]:
        length = len(text)
        word_count = len(text.split())
        sentence_count = max(
            1,
            len(
                re.split(
                    r"[\.!?\u061F\u061B\u060C\u3002\uff01\uff1f]+",
                    text,
                )
            ),
        )
        paragraph_count = len([p for p in text.split("\n\n") if p.strip()])
        structure_score = self._calculate_structure_score(text)
        semantic_score = self._approximate_semantic_score(text)
        return {
            "length": length,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "structure_score": structure_score,
            "semantic_score": semantic_score,
        }

    def _select_strategy(self, a: Dict[str, Any]) -> str:
        if a["structure_score"] > self.structure_complexity_threshold:
            return "hierarchical"
        if a["semantic_score"] > self.semantic_coherence_threshold:
            return "semantic"
        if a["length"] > self.text_length_threshold:
            return "hybrid"
        return getattr(
            getattr(settings, "advanced_chunking", object()),
            "chunking_strategy",
            "semantic",
        )

    def _calculate_structure_score(self, text: str) -> float:
        headers = len(re.findall(r"^#+\s+", text, re.MULTILINE))
        lists = len(re.findall(r"^\s*[-*+]\s+", text, re.MULTILINE))
        tables = text.count("|")
        struct = headers + lists + tables
        return min(struct / max(1, len(text) / 1000.0), 1.0)

    def _approximate_semantic_score(self, text: str) -> float:
        # Lightweight heuristic; real semantics handled by SemanticChunker
        keywords = ["است", "بود", "می‌شود", "خواهد", "کرد", "شد"]
        k = sum(text.count(w) for w in keywords)
        wc = max(1, len(text.split()))
        return min(k / (wc / 10.0), 1.0)
