"""
Hierarchical text chunker.

This chunker analyzes document structure (titles, sections, paragraphs, sentences)
and produces leveled chunks with rich metadata while staying compatible with
BaseChunker/TextChunk APIs used across the project.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ragbot.configs.settings import settings
from ragbot.rag.chunkers.base import BaseChunker, TextChunk


@dataclass
class _HierChunkMeta:
    level: int
    parent_id: Optional[str]
    type: str  # title | section | paragraph | sentence


class HierarchicalChunker(BaseChunker):
    """
    Chunk text by hierarchical structure (Markdown-like headings, paragraphs, sentences).

    Metadata fields added to each chunk:
      - chunk_type: "hierarchical"
      - level: 1 (title) | 2 (section) | 3 (paragraph) | 4 (sentence)
      - structure_type: title|section|paragraph|sentence
      - parent_id: optional parent chunk id
    """

    def __init__(
        self,
        *,
        min_chunk_chars: Optional[int] = None,
        max_chunk_chars: Optional[int] = None,
        include_sentences_for_long_paragraphs: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        adv = getattr(settings, "advanced_chunking", None)
        default_min = getattr(adv, "hierarchical_min_chunk_size", 100) if adv else 100
        default_max = getattr(adv, "hierarchical_max_chunk_size", 2000) if adv else 2000
        self.min_chunk_chars = max(
            0, int(min_chunk_chars if min_chunk_chars is not None else default_min)
        )
        self.max_chunk_chars = max(
            1, int(max_chunk_chars if max_chunk_chars is not None else default_max)
        )
        self.include_sentences = include_sentences_for_long_paragraphs
        # Optional token-aware limits
        try:
            from ragbot.rag.chunkers.token_chunker import TokenChunker

            self._token_counter = TokenChunker()
        except Exception:
            self._token_counter = None

    def chunk(self, text: str, **kwargs: Any) -> List[TextChunk]:  # type: ignore[override]
        if not isinstance(text, str) or not text.strip():
            return []

        # Analyze structure (prefer metadata.headings when provided)
        metadata_in: Dict[str, Any] = kwargs.get("metadata", {}) or {}
        ext_headings = metadata_in.get("headings") or []
        title: Optional[tuple[str, int, int]] = None
        sections: List[tuple[str, int, int]] = []
        if isinstance(ext_headings, list) and ext_headings:
            used_positions: List[tuple[int, int]] = []
            for h in ext_headings:
                try:
                    lvl = int(h.get("level"))
                    txt = (h.get("text") or "").strip()
                    if not txt:
                        continue
                    start_search = used_positions[-1][1] if used_positions else 0
                    pos = text.find(txt, start_search)
                    if pos < 0:
                        pos = text.find(txt)
                        if pos < 0:
                            continue
                    span = (pos, pos + len(txt))
                    used_positions.append(span)
                    line_start = text.rfind("\n", 0, pos) + 1
                    line_end = text.find("\n", span[1])
                    if line_end == -1:
                        line_end = len(text)
                    if lvl == 1 and title is None:
                        title = (txt, line_start, line_end)
                    elif lvl >= 2:
                        sections.append((txt, line_start, line_end))
                except Exception:
                    continue
            if sections:
                sections = sorted(sections, key=lambda t: t[1])
        else:
            title = self._extract_title(text)
            sections = self._extract_sections(text)
        paragraphs = self._extract_paragraphs(text)

        chunks: List[TextChunk] = []

        # Level 1: title
        parent_map: Dict[Any, str] = {}
        last_parent_id: Optional[str] = None
        if title:
            t_txt = title[0] if isinstance(title, (tuple, list)) else str(title)
            t_start = title[1] if isinstance(title, (tuple, list)) and len(title) > 1 else None
            t_end = title[2] if isinstance(title, (tuple, list)) and len(title) > 2 else None
            t_chunk = self._make_chunk(
                text,
                t_txt,
                start=t_start,
                end=t_end,
                meta=_HierChunkMeta(level=1, parent_id=None, type="title"),
                index=len(chunks),
            )
            chunks.append(t_chunk)
            last_parent_id = t_chunk.chunk_id

        # Level 2: sections
        for sec in sections:
            s_txt = sec[0] if isinstance(sec, (tuple, list)) else str(sec)
            s_start = sec[1] if isinstance(sec, (tuple, list)) and len(sec) > 1 else None
            s_end = sec[2] if isinstance(sec, (tuple, list)) and len(sec) > 2 else None
            chunk = self._make_chunk(
                text,
                s_txt,
                start=s_start,
                end=s_end,
                meta=_HierChunkMeta(level=2, parent_id=last_parent_id, type="section"),
                index=len(chunks),
            )
            chunks.append(chunk)
            parent_map[s_txt] = chunk.chunk_id or f"chunk_{len(chunks) - 1}"
            parent_map[sec] = chunk.chunk_id or f"chunk_{len(chunks) - 1}"
            last_parent_id = chunk.chunk_id or last_parent_id

        # Level 3: paragraphs (avoid merging table-like blocks)
        buffer_para: Optional[str] = None
        for para_content, para_start, para_end in paragraphs:
            p = para_content.strip()
            if not p:
                continue
            parent_id = last_parent_id
            is_table_block = p.startswith("[Table]") or ("\t" in p)
            if len(p) < self.min_chunk_chars and not is_table_block:
                if buffer_para:
                    buffer_para = buffer_para + "\n\n" + p
                else:
                    buffer_para = p
                continue
            if buffer_para:
                merged = buffer_para + "\n\n" + p
                if len(merged) <= self.max_chunk_chars:
                    p = merged
                    buffer_para = None
            chunk = self._make_chunk(
                text,
                p,
                meta=_HierChunkMeta(
                    level=3,
                    parent_id=parent_id,
                    type="table" if is_table_block else "paragraph",
                ),
                index=len(chunks),
                start=para_start,
                end=para_end,
            )
            chunks.append(chunk)
        if buffer_para:
            chunk = self._make_chunk(
                text,
                buffer_para,
                meta=_HierChunkMeta(
                    level=3, parent_id=last_parent_id, type="paragraph"
                ),
                index=len(chunks),
            )
            chunks.append(chunk)

        # Level 4: sentences for long paragraphs
        if self.include_sentences:
            new_chunks: List[TextChunk] = []
            for c in chunks:
                if (
                    c.metadata.get("level") == 3
                    and len(c.content) > self.max_chunk_chars
                ):
                    # position-aware sentence iteration within paragraph span
                    for s_text, s_start, s_end in self._iter_sentences(
                        text[c.start_index : c.end_index], c.start_index
                    ):
                        s = s_text.strip()
                        if len(s) < 20:
                            continue
                        new_chunks.append(
                            TextChunk(
                                content=s,
                                metadata={
                                    "chunk_type": "hierarchical",
                                    "level": 4,
                                    "structure_type": "sentence",
                                    "parent_id": c.chunk_id,
                                },
                                start_index=s_start,
                                end_index=s_end,
                                chunk_id=f"hchunk_{len(new_chunks)}",
                            )
                        )
                else:
                    new_chunks.append(c)
            chunks = new_chunks

        # Dynamic overlap near boundaries (last short sentence appended to next)
        chunks = self._add_dynamic_overlap(chunks)
        # Re-enforce size limits after overlap merge
        enforced: List[TextChunk] = []
        for c in chunks:
            if self._is_within_limit(c.content):
                enforced.append(c)
            else:
                for piece in self._split_by_paragraph_or_mid_sentence(c.content):
                    enforced.append(
                        self._make_chunk(
                            text,
                            piece,
                            meta=_HierChunkMeta(
                                level=c.metadata.get("level", 3),
                                parent_id=c.metadata.get("parent_id"),
                                type=c.metadata.get("structure_type", "paragraph"),
                            ),
                            index=len(enforced),
                        )
                    )
        chunks = enforced

        # Enforce size constraints by splitting oversized chunks (token-aware when possible)
        final_chunks: List[TextChunk] = []
        for c in chunks:
            if self._is_within_limit(c.content):
                final_chunks.append(c)
                continue
            for piece in self._split_by_paragraph_or_mid_sentence(c.content):
                final_chunks.append(
                    self._make_chunk(
                        text,
                        piece,
                        meta=_HierChunkMeta(
                            level=c.metadata.get("level", 3),
                            parent_id=c.metadata.get("parent_id"),
                            type=c.metadata.get("structure_type", "paragraph"),
                        ),
                        index=len(final_chunks),
                    )
                )

        # Annotate page/slide using headings when available
        try:
            from ragbot.rag.chunkers.base import BaseChunker as _B

            meta_in = kwargs.get("metadata", {}) or {}
            _B._annotate_page_slide(
                self,
                final_chunks,
                text,
                meta_in.get("headings"),
                meta_in.get("page_ranges"),
            )  # type: ignore[arg-type]
        except Exception:
            pass

        return final_chunks

    # ---------- helpers ----------
    def _extract_title(self, text: str) -> Optional[tuple[str, int, int]]:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if not m:
            return None
        title_text = m.group(1).strip()
        # span for the entire line containing title
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        if line_end == -1:
            line_end = len(text)
        return (title_text, line_start, line_end)

    def _extract_sections(self, text: str) -> List[tuple[str, int, int]]:
        spans: List[tuple[str, int, int]] = []
        for m in re.finditer(r"^##+\s+(.+)$", text, re.MULTILINE):
            sec_text = m.group(1).strip()
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            if line_end == -1:
                line_end = len(text)
            spans.append((sec_text, line_start, line_end))
        return spans

    def _extract_paragraphs(self, text: str) -> List[tuple[str, int, int]]:
        spans: List[tuple[str, int, int]] = []
        start = 0
        while start < len(text):
            end = text.find("\n\n", start)
            if end == -1:
                end = len(text)
            para = text[start:end]
            if para.strip():
                spans.append((para, start, end))
            start = end + 2
        return spans

    def _split_sentences(self, txt: str) -> List[str]:
        # Support Persian punctuation: . ! ? ؟ ؛ ،
        sentences = re.split(r"[\.\!\?\u061F\u061B\u060C]+\s+", txt)
        return [s for s in sentences if s and s.strip()]

    def _iter_sentences(
        self, txt_slice: str, base_offset: int
    ) -> List[tuple[str, int, int]]:
        out: List[tuple[str, int, int]] = []
        pos = 0
        for s in self._split_sentences(txt_slice):
            s = s.strip()
            if not s:
                continue
            # find this occurrence from current pos to avoid matching earlier duplicates
            rel = txt_slice.find(s, pos)
            if rel < 0:
                # fallback: use current pos
                rel = pos
            start = base_offset + rel
            end = start + len(s)
            out.append((s, start, end))
            pos = rel + len(s)
        return out

    def _split_by_paragraph_or_mid_sentence(self, txt: str) -> List[str]:
        paragraphs = self._extract_paragraphs(txt)
        if len(paragraphs) > 1:
            return paragraphs
        sents = self._split_sentences(txt)
        if len(sents) > 1:
            mid = max(1, len(sents) // 2)
            first = " ".join(sents[:mid]).strip()
            second = " ".join(sents[mid:]).strip()
            return [first, second]
        return [txt]

    def _is_within_limit(self, content: str) -> bool:
        if self._token_counter is None:
            return len(content) <= self.max_chunk_chars
        # Approximate: map char limits to token limits ~ 4 chars/token
        token_limit = max(1, self.max_chunk_chars // 4)
        return self._token_counter.count_tokens(content) <= token_limit

    def _add_dynamic_overlap(self, chunks: List[TextChunk]) -> List[TextChunk]:
        if not chunks:
            return chunks
        out: List[TextChunk] = []
        prev_last_sentence: Optional[str] = None
        for c in chunks:
            text = c.content
            sentences = self._split_sentences(text)
            # prepend previous last sentence if short
            if prev_last_sentence and len(prev_last_sentence) <= 120:
                merged = prev_last_sentence + " " + text
                c = TextChunk(
                    content=merged,
                    metadata={**c.metadata, "overlap_prefix": True},
                    start_index=c.start_index,
                    end_index=c.start_index + len(merged),
                    chunk_id=c.chunk_id,
                )
            # update prev_last_sentence
            prev_last_sentence = sentences[-1].strip() if sentences else None
            out.append(c)
        return out

    def _make_chunk(
        self,
        original_text: str,
        content: Any,
        *,
        meta: _HierChunkMeta,
        index: int,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> TextChunk:
        if isinstance(content, (tuple, list)):
            if len(content) >= 3 and isinstance(content[1], int) and isinstance(content[2], int):
                if start is None:
                    start = content[1]
                if end is None:
                    end = content[2]
                content = str(content[0])
            elif len(content) > 0:
                content = str(content[0])
            else:
                content = ""
        if start is None or end is None:
            start = original_text.find(content)
            if start < 0:
                start = 0
            end = start + len(content)
        metadata: Dict[str, Any] = {
            "chunk_type": "hierarchical",
            "level": meta.level,
            "structure_type": meta.type,
        }
        if meta.parent_id is not None:
            metadata["parent_id"] = meta.parent_id
        return TextChunk(
            content=content,
            metadata=metadata,
            start_index=start,
            end_index=end,
            chunk_id=f"hchunk_{index}",
        )
