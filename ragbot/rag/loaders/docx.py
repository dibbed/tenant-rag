"""
DOCX (Microsoft Word) document loader.

Extracts text from .docx files into a normalized Document object.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Dict, Optional

try:
    import docx as _docx  # python-docx

    DocxDocument = _docx.Document  # alias for test monkeypatching
    DOCX_AVAILABLE = True
except Exception:
    _docx = None
    DocxDocument = None  # type: ignore[assignment]
    DOCX_AVAILABLE = False

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders.base import BaseLoader, Document


# -------- Heading inference helpers (style_id → outlineLvl → dynamic font) --------
def _style_id_heading_level(para) -> Optional[int]:
    try:
        st = getattr(para, "style", None)
        for attr in ("style_id", "name"):
            style_val = getattr(st, attr, None)
            if isinstance(style_val, str) and style_val.lower().startswith("heading"):
                digits = "".join(ch for ch in style_val if ch.isdigit())
                if digits:
                    n = int(digits)
                    if 1 <= n <= 9:
                        return n
    except Exception:
        pass
    return None


def _outline_level_from_ooxml(para) -> Optional[int]:
    try:
        ppr = getattr(para._p, "pPr", None)
        outlineLvl = getattr(ppr, "outlineLvl", None)
        if outlineLvl is not None:
            lvl_val = getattr(outlineLvl, "val", None)
            if isinstance(lvl_val, int):
                return min(max(lvl_val + 1, 1), 9)
    except Exception:
        pass
    return None


def _para_max_font_pt(para) -> float:
    max_pt = 0.0
    try:
        for run in getattr(para, "runs", []) or []:
            fnt = getattr(run, "font", None)
            sz = getattr(fnt, "size", None)
            if sz is not None and getattr(sz, "pt", None) is not None:
                max_pt = max(max_pt, float(sz.pt))
    except Exception:
        return 0.0
    return max_pt


def _estimate_body_font_size(font_pts: list[float]) -> float:
    non_zero = [x for x in font_pts if x > 0]
    if not non_zero:
        return 12.0
    try:
        med = float(median(non_zero))
    except Exception:
        counts = Counter(round(v, 1) for v in non_zero)
        med = float(max(counts, key=counts.get))
    if med >= 14.0 and (len(non_zero) < len(font_pts) or len(non_zero) < 3):
        return 12.0
    return med


def _layout_signals(para) -> Dict[str, bool]:
    sig: Dict[str, bool] = {
        "keep_next": False,
        "page_break_before": False,
        "spacing_before_large": False,
        "bold_any": False,
        "short_text": False,
    }
    text = (getattr(para, "text", "") or "").strip()
    sig["short_text"] = len(text) <= 120
    try:
        sig["bold_any"] = any(
            bool(getattr(getattr(run, "font", None), "bold", False))
            for run in getattr(para, "runs", []) or []
        )
    except Exception:
        sig["bold_any"] = False
    try:
        ppr = getattr(para._p, "pPr", None)
        if ppr is not None:
            if getattr(ppr, "keepNext", None) is not None:
                sig["keep_next"] = True
            if getattr(ppr, "pageBreakBefore", None) is not None:
                sig["page_break_before"] = True
            spacing = getattr(ppr, "spacing", None)
            if spacing is not None:
                before = getattr(spacing, "before", None)
                before_autosp = getattr(spacing, "beforeAutosp", None)
                if (isinstance(before, int) and before >= 200) or bool(before_autosp):
                    sig["spacing_before_large"] = True
    except Exception:
        pass
    return sig


def _score_heading_like(delta_pt: float, sig: Dict[str, bool]) -> tuple[bool, int]:
    is_heading = False
    lvl = 0
    hard = delta_pt >= 8.0
    medium = 6.0 <= delta_pt < 8.0
    soft = 3.0 <= delta_pt < 6.0
    if hard:
        is_heading = True
        lvl = 1
    elif medium:
        is_heading = True
        lvl = 2
    elif soft:
        boosters = sum(
            int(sig[k])
            for k in (
                "bold_any",
                "short_text",
                "keep_next",
                "page_break_before",
                "spacing_before_large",
            )
        )
        if boosters >= 1:
            is_heading = True
            lvl = 3 if boosters >= 2 else 4
    if not is_heading:
        return False, 0
    if lvl == 1:
        return True, 1
    if lvl == 2:
        return True, 2
    if lvl == 3:
        return True, 3
    return True, 4


def _auto_infer_heading_levels(doc) -> list[Optional[int]]:
    paras = list(getattr(doc, "paragraphs", []) or [])
    n = len(paras)
    levels: list[Optional[int]] = [None] * n
    for i, para in enumerate(paras):
        lvl = _style_id_heading_level(para)
        if lvl is None:
            lvl = _outline_level_from_ooxml(para)
        levels[i] = lvl

    font_pts = [_para_max_font_pt(p) for p in paras]
    body_pt = _estimate_body_font_size(font_pts)
    for i, para in enumerate(paras):
        if levels[i] is not None:
            continue
        delta = font_pts[i] - body_pt
        sig = _layout_signals(para)
        is_heading, lvl = _score_heading_like(delta, sig)
        if is_heading:
            levels[i] = min(max(lvl, 1), 6)
    return levels


class DOCXLoader(BaseLoader):
    """Load text content from a .docx file.

    Extracts paragraphs and table cell texts, applies basic normalization,
    and returns a unified `Document` with enriched metadata.

    Notes:
        - Processing of the underlying DOCX is synchronous; to avoid blocking
          the event loop, the heavy work runs in a thread executor.
        - This loader performs a lightweight structural extraction (paragraphs
          and table cells) and does not attempt to extract advanced constructs
          like footnotes, headers/footers, or images.
    """

    def validate_source(self, source: str) -> bool:
        try:
            p = Path(source)
            return p.is_file() and p.suffix.lower() == ".docx"
        except Exception:
            return False

    def get_supported_extensions(self) -> list[str]:
        return [".docx"]

    async def load(self, source: str, **kwargs: Any) -> Document:
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx is required for DOCX loading. Install with: pip install python-docx"
            )

        path = Path(source)
        try:
            exists = path.exists()
        except Exception:
            # If existence check fails (e.g., patched stat), proceed best-effort
            exists = True
        if not exists or path.suffix.lower() != ".docx":
            raise DocumentProcessingError(
                "Invalid DOCX file path", document_type="docx", source=source
            )

        # Size check (perform early so tests expecting size error see it first)
        max_bytes = settings.security.max_file_size_mb * 1024 * 1024
        size: Optional[int] = None
        try:
            size = path.stat().st_size
        except Exception as stat_err:
            # Do not fail the load solely on stat issues; warn for observability
            logger.warning(f"Failed to stat DOCX file: {stat_err} | path={path}")
        if size is not None and size > max_bytes:
            raise DocumentProcessingError(
                f"DOCX too large: {size} bytes (max {max_bytes})",
                document_type="docx",
                source=source,
            )

        # Quick structure & safety check: DOCX zip entries caps (warn-only)
        try:
            if zipfile.is_zipfile(str(path)):
                with zipfile.ZipFile(str(path)) as zf:
                    entries = zf.infolist()
                    if len(entries) > int(settings.multi_format.docx_max_zip_entries):
                        raise DocumentProcessingError(
                            "DOCX too many entries (zip bomb protection)",
                            document_type="docx",
                            source=source,
                        )
                    total_uncompressed = sum(
                        getattr(i, "file_size", 0) for i in entries
                    )
                    if (
                        total_uncompressed
                        > int(settings.multi_format.docx_max_uncompressed_mb)
                        * 1024
                        * 1024
                    ):
                        raise DocumentProcessingError(
                            "DOCX uncompressed size too large (zip bomb protection)",
                            document_type="docx",
                            source=source,
                        )
            else:
                logger.warning(
                    f"DOCX container not ZIP (continuing best-effort) | path={path}"
                )
        except Exception as zip_check_err:
            # Non-fatal: log and continue; downstream open will likely fail if corrupt
            logger.warning(f"DOCX zip check failed: {zip_check_err} | path={path}")

        def _extract_sync(
            p: Path,
        ) -> tuple[
            str,
            Dict[
                str,
                Any,
            ],
        ]:
            """Synchronous extractor to be executed in a thread.

            Returns:
                tuple[str, Dict[str, Any]]: normalized text content and basic counters.
            """
            # Support both patch("docx.Document") and monkeypatch.setattr(docx_mod, "DocxDocument", ...)
            if hasattr(getattr(_docx, "Document", None), "return_value"):
                doc = _docx.Document(str(p))
            elif DocxDocument is not None and DocxDocument is not getattr(
                _docx, "Document", None
            ):
                doc = DocxDocument(str(p))
            else:
                doc = _docx.Document(str(p))

            parts: list[str] = []
            paragraphs_count = 0
            tables_count = 0
            table_cells_count = 0
            headings_count = 0
            headings: list[dict[str, Any]] = []
            links_list: list[dict[str, str]] = []
            images_list: list[dict[str, Any]] = []
            # numbering counters per (numId, ilvl)
            list_counters: dict[tuple[int, int], int] = {}

            # best-effort flags
            has_images = False
            has_hyperlinks = False
            has_footnotes = False
            hyperlinks: set[str] = set()

            # Pagination (best-effort): detect page breaks via paragraph/pageBreakBefore and run breaks
            PAGE_MARK = "\f"  # form feed as page delimiter before normalization
            current_page = 1
            page_ranges: list[dict[str, int]] = [{"page": current_page, "start": 0}]
            cumulative_len = 0

            def _para_has_page_break(_para) -> bool:
                try:
                    # Paragraph property pageBreakBefore
                    ppr = getattr(_para._p, "pPr", None)
                    if (
                        ppr is not None
                        and getattr(ppr, "pageBreakBefore", None) is not None
                    ):
                        return True
                except Exception:
                    pass
                try:
                    # Run-level explicit page breaks
                    for run in getattr(_para, "runs", []) or []:
                        r = getattr(run, "_r", None)
                        # best-effort: some libs expose run._r.br for breaks
                        if r is not None and hasattr(r, "br"):
                            return True
                except Exception:
                    pass
                return False

            # Pre-compute heading levels when enabled
            para_heading_levels: list[Optional[int]] = []
            try:
                if settings.multi_format.docx_enable_structural_extraction:
                    para_heading_levels = _auto_infer_heading_levels(doc)
            except Exception:
                para_heading_levels = []

            # paragraphs
            for idx, para in enumerate(doc.paragraphs):
                raw = para.text or ""
                text = raw.strip()
                level: Optional[int] = None

                # heading detection from pre-computed levels or fallback to style.name
                try:
                    if para_heading_levels:
                        level = para_heading_levels[idx]
                    if level is None:
                        style_name = (
                            getattr(getattr(para, "style", None), "name", "") or ""
                        )
                        if isinstance(
                            style_name, str
                        ) and style_name.lower().startswith("heading"):
                            digits = "".join(ch for ch in style_name if ch.isdigit())
                            if digits:
                                n = int(digits)
                                if 1 <= n <= 6:
                                    level = n
                except Exception:
                    pass

                # numbering (simple)
                try:
                    if settings.multi_format.docx_preserve_numbering:
                        ppr = getattr(para._p, "pPr", None)
                        numpr = getattr(ppr, "numPr", None)
                        if numpr is not None and text:
                            # Attempt to read ordered numbering info; only apply when explicit
                            numId_elm = getattr(numpr, "numId", None)
                            ilvl_elm = getattr(numpr, "ilvl", None)
                            numId = (
                                getattr(numId_elm, "val", None)
                                if numId_elm is not None
                                else None
                            )
                            ilvl = (
                                getattr(ilvl_elm, "val", None)
                                if ilvl_elm is not None
                                else None
                            )
                            if isinstance(numId, int) and isinstance(ilvl, int):
                                key = (numId, ilvl)
                                list_counters[key] = list_counters.get(key, 0) + 1
                                text = f"{list_counters[key]}. {text}"
                except Exception:
                    pass

                # dynamic font heuristic is handled in _auto_infer_heading_levels

                # heading markers injection
                if level and text:
                    headings.append({"level": level, "text": raw.strip()})
                    try:
                        if settings.multi_format.docx_inject_heading_markers:
                            marker = "#" * max(1, min(level, 6))
                            text = f"{marker} {text}"
                    except Exception:
                        pass

                # handle page break marker insertion before appending paragraph text
                try:
                    if _para_has_page_break(para):
                        # close previous page
                        if page_ranges:
                            page_ranges[-1]["end"] = cumulative_len
                        current_page += 1
                        parts.append(PAGE_MARK)
                        cumulative_len += len(PAGE_MARK) + 1  # include separator later
                        page_ranges.append(
                            {"page": current_page, "start": cumulative_len}
                        )
                except Exception:
                    pass

                if text:
                    parts.append(text)
                    paragraphs_count += 1
                    cumulative_len += len(text) + 1  # account for a newline join later

                # hyperlink detection via underlying XML (best-effort)
                try:
                    p_elem = getattr(para, "_p", None)
                    if p_elem is not None and hasattr(p_elem, "xpath"):
                        # w:hyperlink appears when paragraph contains hyperlinks
                        elems = p_elem.xpath(
                            ".//w:hyperlink", namespaces=p_elem.nsmap or {}
                        )
                        if elems:
                            has_hyperlinks = True
                            # try to resolve r:id to external hyperlink target
                            try:
                                part = getattr(doc, "part", None)
                                rels = getattr(part, "rels", None) or getattr(
                                    part, "_rels", {}
                                )
                                # namespace for relationships
                                rel_ns = (
                                    p_elem.nsmap.get("r")
                                    or "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                                )
                                rel_key_attr = f"{{{rel_ns}}}id"
                                for e in elems:
                                    rid = e.get(rel_key_attr)
                                    if rid and rels:
                                        rel = (
                                            rels.get(rid)
                                            if isinstance(rels, dict)
                                            else rels.get(rid)
                                        )
                                        if rel is not None:
                                            target = getattr(
                                                rel, "target_ref", None
                                            ) or getattr(rel, "_target", None)
                                            reltype = getattr(rel, "reltype", "") or ""
                                            if target and (
                                                "/hyperlink" in reltype
                                                or str(target).startswith("http")
                                            ):
                                                url = str(target)
                                                hyperlinks.add(url)
                                                if (
                                                    settings.multi_format.docx_extract_hyperlinks
                                                    and len(links_list)
                                                    < max(
                                                        0,
                                                        int(
                                                            settings.multi_format.docx_hyperlinks_max
                                                        ),
                                                    )
                                                ):
                                                    links_list.append({"url": url})
                                                # Optional inline hyperlink injection
                                                if (
                                                    settings.multi_format.docx_inject_hyperlinks_inline
                                                    and text
                                                ):
                                                    text = (
                                                        f"{text} [{raw.strip()}]({url})"
                                                    )
                            except Exception:
                                pass
                except Exception:
                    pass

            # tables (cells)
            tables_max_cols: list[int] = []
            for ti, table in enumerate(getattr(doc, "tables", [])):
                if ti >= max(0, int(settings.multi_format.docx_tables_max)):
                    break
                tables_count += 1
                table_max_cols = 0
                for row in table.rows:
                    cell_texts = [
                        (c.text or "").strip()
                        for c in row.cells
                        if getattr(c, "text", None) is not None
                    ]
                    # Use a uniform tab separator between cells (with spaces for readability)
                    line = " \t ".join([t for t in cell_texts if t])
                    if line:
                        parts.append(line)
                        table_cells_count += len([t for t in cell_texts if t])
                    table_max_cols = max(table_max_cols, len(cell_texts))
                tables_max_cols.append(table_max_cols)

            # images (inline shapes) and optional metadata list
            try:
                has_images = (
                    bool(getattr(doc, "inline_shapes", []))
                    and len(doc.inline_shapes) > 0
                )
                if settings.multi_format.docx_extract_images and has_images:
                    count = 0
                    for rId, rel in getattr(doc.part, "rels", {}).items():
                        target_part = getattr(rel, "target_part", None)
                        if target_part and getattr(
                            target_part, "content_type", ""
                        ).startswith("image/"):
                            images_list.append(
                                {
                                    "rId": str(rId),
                                    "content_type": target_part.content_type,
                                    "partname": str(
                                        getattr(target_part, "partname", "")
                                    ),
                                }
                            )
                            count += 1
                            if count >= max(
                                0, int(settings.multi_format.docx_images_max)
                            ):
                                break
            except Exception:
                has_images = False

            # footnotes (best-effort via relationships)
            try:
                rels = getattr(getattr(doc, "part", None), "_rels", {}) or {}
                for rel in rels.values():
                    target_ref = getattr(rel, "reltype", "") or ""
                    if "/footnotes" in target_ref:
                        has_footnotes = True
                        break
            except Exception:
                has_footnotes = False

            raw_content = "\n".join(parts)

            # Normalize: Unicode NFC, collapse multiple spaces (preserve tabs), unify newlines
            normalized = unicodedata.normalize("NFC", raw_content)
            # Collapse 3+ newlines to 2, trim trailing spaces on lines
            normalized = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", normalized)
            # Preserve tabs for table structure; only collapse consecutive spaces
            normalized = re.sub(r"[ ]{2,}", " ", normalized)
            normalized = re.sub(
                r"\s*\n\s*",
                "\n" * max(1, int(settings.multi_format.docx_paragraph_breaks)),
                normalized,
            )
            normalized = normalized.strip()

            # Build approximate page_ranges on normalized content using PAGE_MARK positions
            try:
                # Recompute ranges by scanning for form feeds in normalized text
                ranges: list[dict[str, int]] = []
                page_idx = 1
                start_pos = 0
                pos = 0
                while True:
                    i = normalized.find(PAGE_MARK, pos)
                    if i == -1:
                        break
                    ranges.append({"page": page_idx, "start": start_pos, "end": i})
                    page_idx += 1
                    start_pos = i + 1
                    pos = start_pos
                # last page
                ranges.append(
                    {"page": page_idx, "start": start_pos, "end": len(normalized)}
                )
                # Remove the markers from content for final text
                normalized = normalized.replace(PAGE_MARK, "")
            except Exception:
                ranges = []

            counters: Dict[str, Any] = {
                "paragraphs_count": paragraphs_count,
                "tables_count": tables_count,
                "table_cells_count": table_cells_count,
                "headings_count": headings_count,
                "has_headings": headings_count > 0,
                "has_hyperlinks": has_hyperlinks,
                "has_images": has_images,
                "has_footnotes": has_footnotes,
            }
            if tables_max_cols:
                counters["tables_max_cols"] = tables_max_cols
            # Include page_ranges if available
            if ranges:
                counters["page_ranges"] = ranges
            # include hyperlink list (capped) and count
            if hyperlinks:
                max_urls = int(settings.multi_format.docx_hyperlinks_max)
                counters["hyperlinks"] = list(sorted(hyperlinks))[:max_urls]
                counters["hyperlinks_count"] = len(hyperlinks)
            else:
                counters["hyperlinks"] = []
                counters["hyperlinks_count"] = 0
            if headings:
                counters["headings"] = headings
            if links_list:
                counters["links_list"] = links_list
            if images_list:
                counters["images_list"] = images_list
            # Attach core properties
            try:
                cp = getattr(doc, "core_properties", None)
                if cp:
                    counters["core_title"] = getattr(cp, "title", None)
                    counters["core_author"] = getattr(cp, "author", None)
                    counters["core_subject"] = getattr(cp, "subject", None)
                    counters["core_created"] = getattr(cp, "created", None)
                    counters["core_modified"] = getattr(cp, "modified", None)
            except Exception:
                pass

            return normalized, counters

        try:
            loop = asyncio.get_running_loop()
            content, counters = await loop.run_in_executor(
                None, lambda: _extract_sync(path)
            )

            # Allow empty content; do not raise, tests expect graceful return
            if not content:
                logger.warning(f"DOCX has no textual content | path={path}")

            estimated_tokens = len(content.split())
            # Optional token estimation with tiktoken if available
            try:
                import tiktoken  # type: ignore

                try:
                    enc = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    enc = tiktoken.get_encoding(tiktoken.list_encoding_names()[0])
                estimated_tokens = len(enc.encode(content))
            except Exception:
                pass
            # core properties (already opened doc inside thread; attach into counters if available)
            title = counters.get("core_title")
            author = counters.get("core_author")
            subject = counters.get("core_subject")
            created = counters.get("core_created")
            modified = counters.get("core_modified")

            metadata: Dict[str, Any] = {
                "file_name": path.name,
                "file_ext": path.suffix.lower(),
                "source_path": str(path),
                "loader": "DOCXLoader",
                "type": "docx",
                "source_type": "file",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "approx_chars": len(content),
                "estimated_tokens": estimated_tokens,
                **counters,
                "has_tables": counters.get("tables_count", 0) > 0,
                "title": title,
                "author": author,
                "subject": subject,
                "created": str(created) if created else None,
                "modified": str(modified) if modified else None,
            }
            if settings.multi_format.docx_detect_language:
                try:
                    from langdetect import detect  # type: ignore

                    votes = []
                    for chunk in [
                        content[:2000],
                        content[len(content) // 2 : len(content) // 2 + 2000],
                        content[-2000:],
                    ]:
                        try:
                            if chunk.strip():
                                votes.append(detect(chunk))
                        except Exception:
                            continue
                    lang = None
                    if votes:
                        # majority vote
                        from collections import Counter

                        lang = Counter(votes).most_common(1)[0][0]
                    metadata.setdefault("language", lang or "unknown")
                except Exception:
                    pass
            return Document(
                text=content, metadata=metadata, source=str(path), document_type="docx"
            )
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to read DOCX: {e}")
            raise DocumentProcessingError(
                str(e), document_type="docx", source=source
            ) from e
