import types
from typing import Any, Dict, List

import pytest

from ragbot.rag.loaders.pdf import PDFLoader


class _MockPage:
    def __init__(self, layout_blocks: List[Dict[str, Any]], text: str = "body"):
        self._layout = {"blocks": layout_blocks}
        self._text = text

    def get_text(self, mode: str):
        if mode == "dict":
            return self._layout
        return self._text


class _MockDoc:
    def __init__(self, pages: List[_MockPage]):
        self._pages = pages
        self.page_count = len(pages)
        self.needs_pass = False

    def __getitem__(self, idx: int):
        return self._pages[idx]

    def close(self):
        return None


def _mk_span(text: str, size: float) -> Dict[str, Any]:
    return {"text": text, "size": size, "bbox": [0, 0, 10, 10]}


@pytest.mark.asyncio
async def test_pdf_headings_six_levels(monkeypatch) -> None:
    # Create a layout with multiple font sizes for 6 heading levels
    spans = [
        _mk_span("Heading1", 32.0),
        _mk_span("Heading2", 24.0),
        _mk_span("Heading3", 18.0),
        _mk_span("Heading4", 16.0),
        _mk_span("Heading5", 14.0),
        _mk_span("Heading6", 12.5),
    ]
    layout_blocks = [{"lines": [{"spans": spans}]}]
    doc = _MockDoc([_MockPage(layout_blocks, text="page body")])

    # Patch fitz.open to return our mock doc
    import ragbot.rag.loaders.pdf as pdf_mod

    monkeypatch.setattr(pdf_mod, "PYMUPDF_AVAILABLE", True)
    monkeypatch.setattr(pdf_mod, "fitz", types.SimpleNamespace(open=lambda src: doc))

    loader = PDFLoader(
        enable_structural_extraction=True,
        inject_heading_markers=True,
        detect_language=False,
        max_pages=10,
    )

    # Bypass filesystem checks and validation
    from pathlib import Path

    monkeypatch.setattr(Path, "exists", lambda self: True)

    class _Stat:
        st_size = 1

    monkeypatch.setattr(Path, "stat", lambda self: _Stat())
    monkeypatch.setattr(PDFLoader, "validate_source", lambda self, s: True)

    # Use a fake path; our open is mocked
    document = await loader.load("/tmp/fake.pdf")

    headings = document.metadata.get("headings") or []
    assert len(headings) >= 6
    levels = sorted({h.get("level") for h in headings})
    assert 1 in levels and 6 in levels
    # markers injected into text
    assert "# Heading1" in document.text
