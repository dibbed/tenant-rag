"""Phase 3 verification: malformed Content-Length values never cause a 500.

Found during the edge protection verification review
(docs/security/PHASE3_EDGE_SECURITY_REVIEW.md). ``str.isdigit()`` accepts
Unicode digits such as ``²`` that ``int()`` rejects, and ``int()`` refuses
strings with more than 4300 digits. Before the fix both values raised
ValueError in BodySizeLimitMiddleware, and the server answered HTTP 500.
Uvicorn rejects such headers itself; other ASGI servers may pass them on.
"""

from __future__ import annotations

import pytest

TEXT_PATH = "/api/v1/documents/text"


@pytest.mark.parametrize("value", ["\u00b2", "\u00b9\u00b2", "1\u00b3"])
async def test_non_ascii_digits_in_content_length_are_rejected(
    edge_app, asgi_call, value
):
    app, rag = edge_app(upload_mb=1)
    result = await asgi_call(
        app,
        path=TEXT_PATH,
        chunks=[b"{}"],
        headers=[("content-type", "application/json"), ("content-length", value)],
    )
    assert result.status == 400
    assert result.receive_calls == 0
    rag.ingest_document.assert_not_called()


async def test_content_length_with_thousands_of_digits_is_refused_as_too_large(
    edge_app, asgi_call
):
    app, rag = edge_app(upload_mb=1)
    result = await asgi_call(
        app,
        path=TEXT_PATH,
        chunks=[b"{}"],
        headers=[("content-type", "application/json"), ("content-length", "9" * 5000)],
    )
    assert result.status == 413
    assert result.receive_calls == 0
    rag.ingest_document.assert_not_called()
