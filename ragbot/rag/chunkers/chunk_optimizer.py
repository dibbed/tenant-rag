"""
Chunk optimizer utilities for enforcing target sizes and analyzing quality.

Operates on TextChunk objects to preserve pipeline compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ragbot.rag.chunkers.base import TextChunk


class ChunkOptimizer:
    """Optimize chunk sizes and provide simple quality analysis."""

    def __init__(self, *, target_size: int = 500, size_tolerance: float = 0.2) -> None:
        self.target_size = int(target_size)
        self.size_tolerance = float(size_tolerance)
        self.min_size = max(1, int(self.target_size * (1 - self.size_tolerance)))
        self.max_size = max(
            self.min_size + 1, int(self.target_size * (1 + self.size_tolerance))
        )

    def optimize(self, chunks: List[TextChunk]) -> List[TextChunk]:
        optimized: List[TextChunk] = []
        for c in chunks:
            n = len(c.content)
            if n < self.min_size:
                optimized = self._merge_with_previous(optimized, c)
            elif n > self.max_size:
                optimized.extend(self._split_large(c))
            else:
                optimized.append(c)
        # Update total_chunks and indices consistently
        total = len(optimized)
        for idx, ch in enumerate(optimized):
            ch.metadata = {**ch.metadata, "chunk_index": idx, "total_chunks": total}
        return optimized

    def _merge_with_previous(
        self, acc: List[TextChunk], small: TextChunk
    ) -> List[TextChunk]:
        if not acc:
            return [small]
        last = acc[-1]
        # Avoid merging across protected structural boundaries (tables/code/heading)
        last_type = str(last.metadata.get("structure_type", "")).lower()
        small_type = str(small.metadata.get("structure_type", "")).lower()
        if any(
            t in {"table", "code", "heading", "title", "section"}
            for t in (last_type, small_type)
        ):
            acc.append(small)
            return acc
        # Decide separator to preserve formatting
        sep = ""
        if last.content and small.content:
            if not last.content.endswith((" ", "\n")) and not small.content.startswith(
                (" ", "\n")
            ):
                sep = " "
        combined = last.content + sep + small.content
        # Position-aware end index: prefer max to avoid assuming strict contiguity
        new_start = last.start_index
        new_end = max(last.end_index, small.end_index)
        merged_meta = {
            **last.metadata,
            "chunk_type": "merged",
            "chunk_size": len(combined),
            "source_chunk_ids": self._merge_source_ids(
                last.metadata.get("source_chunk_ids"), last.chunk_id, small.chunk_id
            ),
            "merge_count": int(last.metadata.get("merge_count", 0)) + 1,
        }
        merged = TextChunk(
            content=combined,
            metadata=merged_meta,
            start_index=new_start,
            end_index=new_end,
            chunk_id=last.chunk_id,
        )
        acc[-1] = merged
        # If merged chunk is still too large, split it immediately
        if len(merged.content) > self.max_size:
            parts = self._split_large(merged)
            acc.pop()
            acc.extend(parts)
        return acc

    def _split_large(self, c: TextChunk) -> List[TextChunk]:
        text = c.content
        base = c.start_index
        out: List[TextChunk] = []
        # 1) Try paragraph-aware splitting (double newlines)
        paras = self._iter_paragraphs(text)
        if len(paras) > 1:
            # Keep short paragraphs by merging with neighbors instead of dropping
            temp: List[str] = []
            for p in paras:
                temp.append(p)
            # Rebuild with size constraints and position-aware indices
            cursor = 0
            for p in temp:
                p_txt = p
                if not p_txt.strip():
                    continue
                # Do not split inside fenced code blocks or explicit table markers
                if p_txt.strip().startswith("[Table]") or p_txt.strip().startswith(
                    "```"
                ):
                    out.append(
                        TextChunk(
                            content=p_txt,
                            metadata={**c.metadata, "chunk_type": "split_protected"},
                            start_index=base + cursor,
                            end_index=base + cursor + len(p_txt),
                            chunk_id=f"{c.chunk_id or 'chunk'}_{len(out)}",
                        )
                    )
                    cursor += len(p_txt)
                    continue
                start_off = text.find(p_txt, cursor)
                if start_off < 0:
                    start_off = cursor
                end_off = start_off + len(p_txt)
                cursor = end_off
                if len(p_txt) > self.max_size:
                    # Recursively split long paragraph by sentences
                    out.extend(
                        self._split_large(
                            TextChunk(
                                content=p_txt,
                                metadata={**c.metadata, "chunk_type": "split"},
                                start_index=base + start_off,
                                end_index=base + end_off,
                                chunk_id=f"{c.chunk_id or 'chunk'}_p",
                            )
                        )
                    )
                else:
                    out.append(
                        TextChunk(
                            content=p_txt,
                            metadata={
                                **c.metadata,
                                "chunk_type": "split",
                                "split_from_id": c.chunk_id,
                            },
                            start_index=base + start_off,
                            end_index=base + end_off,
                            chunk_id=f"{c.chunk_id or 'chunk'}_{len(out)}",
                        )
                    )
            if out:
                return out
        # 2) Sentence-based fallback (multilingual punctuation)
        sents = self._iter_sentences(text)
        if len(sents) > 1:
            mid = max(1, len(sents) // 2)
            first = "".join(sentence for sentence, _start, _end in sents[:mid]).strip()
            second = "".join(sentence for sentence, _start, _end in sents[mid:]).strip()
            # Find offsets robustly relative to current text
            pos = 0
            f_at = text.find(first, pos) if first else -1
            if f_at < 0:
                f_at = 0
            pos = f_at + len(first)
            s_at = text.find(second, pos) if second else -1
            if s_at < 0:
                s_at = pos
            p1 = TextChunk(
                content=first,
                metadata={
                    **c.metadata,
                    "chunk_type": "split",
                    "split_from_id": c.chunk_id,
                },
                start_index=base + f_at,
                end_index=base + f_at + len(first),
                chunk_id=f"{c.chunk_id or 'chunk'}_1",
            )
            p2 = TextChunk(
                content=second,
                metadata={
                    **c.metadata,
                    "chunk_type": "split",
                    "split_from_id": c.chunk_id,
                },
                start_index=base + s_at,
                end_index=base + s_at + len(second),
                chunk_id=f"{c.chunk_id or 'chunk'}_2",
            )
            return [p1, p2]
        # 3) Fallback: return original chunk when no safe split found
        return [c]

    async def analyze_quality(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        if not chunks:
            return {"total": 0, "quality_score": 0.0}
        # Prefer token-based measures when available
        sizes = [
            int(ch.metadata.get("token_count", 0))
            or len(ch.content.split())
            or len(ch.content)
            for ch in chunks
        ]
        avg = sum(sizes) / len(sizes)
        small = sum(1 for s in sizes if s < max(1, int(self.target_size * 0.5)))
        optimal = sum(
            1
            for s in sizes
            if int(self.target_size * 0.5) <= s <= int(self.target_size * 1.5)
        )
        large = sum(1 for s in sizes if s > int(self.target_size * 1.5))
        # Multilingual sentence markers for simple fluency heuristic
        puncts = {".", "!", "?", " "}
        puncts.update({"\u061f", "\u061b", "\u060c", "。", "！", "？"})
        punct_score = sum(
            1 for c in chunks if any(p in c.content for p in puncts)
        ) / len(chunks)
        # Simple scoring: balance size distribution and basic fluency proxy
        score = (optimal / len(sizes)) * 0.7 + punct_score * 0.3
        return {
            "total": len(chunks),
            "average_size": round(avg, 2),
            "distribution": {"small": small, "optimal": optimal, "large": large},
            "quality_score": round(score, 3),
        }

    def _iter_paragraphs(self, txt: str) -> List[str]:
        # Split by double newlines; keep raw paragraphs
        parts = [p.strip("\n") for p in txt.split("\n\n")]
        return [p for p in parts if p is not None]

    def _iter_sentences(self, txt: str) -> List[tuple[str, int, int]]:
        # Multilingual regex: English .!? | Persian ؟ ؛ ، | CJK 。 ！ ？
        import re

        pattern = re.compile(r"(?<=[\.!?\u061F\u061B\u060C\u3002\uff01\uff1f])\s+")
        sentences = []
        pos = 0
        for part in re.split(pattern, txt.strip()):
            p = part.strip()
            if not p:
                continue
            at = txt.find(p, pos)
            if at < 0:
                at = pos
            start = at
            end = start + len(p)
            sentences.append((p, start, end))
            pos = end
        return sentences

    def _merge_source_ids(
        self, existing: Any, id1: str | None, id2: str | None
    ) -> List[str]:
        ids: List[str] = []
        if isinstance(existing, list):
            ids.extend([str(x) for x in existing])
        for x in (id1, id2):
            if x is not None:
                ids.append(str(x))
        # Deduplicate while preserving order
        seen = set()
        unique: List[str] = []
        for x in ids:
            if x in seen:
                continue
            seen.add(x)
            unique.append(x)
        return unique
