"""Phase 3 regression tests: oversized uploads are refused before they are read.

Audit finding C11 (docs/BASELINE_AUDIT.md), requirement REQ-MTS-EDGE-004.

Vulnerability: the upload route called ``await file.read()``, so the whole
file was held in memory before its size was checked, and the request body
itself had no limit.

Expected behavior: a declared Content-Length above the Upload Size Limit is
refused before any body is read; a body that passes the limit while it is
received is cut off and refused; the caller is told the limit; nothing of a
refused upload is kept; uploads within the limit work as before and are
copied to disk in bounded chunks.
"""

from __future__ import annotations

import gc
import json
import tempfile
import tracemalloc
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ragbot.services.rag_service import IngestResult

UPLOAD_PATH = "/api/v1/documents/upload"
TEXT_PATH = "/api/v1/documents/text"
MIB = 1024 * 1024
CHUNK = 64 * 1024
EDGE_ALLOWANCE = 64 * 1024


def _declared(headers, total):
    return [*headers, ("content-length", str(total))]


async def test_upload_under_the_limit_succeeds(
    edge_app, asgi_call, multipart, tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    app, rag = edge_app(upload_mb=1)
    seen = {}

    async def capture(source, *_args, **kwargs):
        seen["size_on_disk"] = Path(source).stat().st_size
        seen["metadata"] = kwargs.get("metadata") or {}
        return IngestResult(
            success=True,
            document_id="doc_1",
            chunks_created=1,
            processing_time=0.01,
            metadata={},
        )

    rag.ingest_document.side_effect = capture
    headers, chunks, total = multipart(200_000)
    result = await asgi_call(
        app, path=UPLOAD_PATH, chunks=chunks, headers=_declared(headers, total)
    )
    assert result.status == 200, result.body
    assert seen["size_on_disk"] == 200_000
    assert seen["metadata"]["file_size"] == 200_000
    assert list(tmp_path.iterdir()) == []


async def test_upload_of_exactly_the_limit_succeeds(edge_app, asgi_call, multipart):
    app, rag = edge_app(upload_mb=1)
    headers, chunks, total = multipart(MIB)
    result = await asgi_call(
        app, path=UPLOAD_PATH, chunks=chunks, headers=_declared(headers, total)
    )
    assert result.status == 200, result.body
    rag.ingest_document.assert_awaited_once()


async def test_upload_one_byte_above_the_limit_is_rejected(
    edge_app, asgi_call, multipart, tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    app, rag = edge_app(upload_mb=1)
    headers, chunks, total = multipart(MIB + 1)
    result = await asgi_call(
        app, path=UPLOAD_PATH, chunks=chunks, headers=_declared(headers, total)
    )
    assert result.status == 413
    assert "1MB" in result.json()["detail"]
    rag.ingest_document.assert_not_called()
    assert list(tmp_path.iterdir()) == []


async def test_declared_oversized_upload_is_rejected_before_reading(
    edge_app, asgi_call, multipart
):
    app, rag = edge_app(upload_mb=1)
    headers, chunks, total = multipart(5 * MIB)
    result = await asgi_call(
        app, path=UPLOAD_PATH, chunks=chunks, headers=_declared(headers, total)
    )
    assert result.status == 413
    assert result.receive_calls == 0
    body = result.json()
    assert body["max_size_mb"] == 1
    assert body["max_size_bytes"] == MIB
    assert "1MB" in body["detail"]
    rag.ingest_document.assert_not_called()


async def test_huge_declared_length_is_rejected_at_once(edge_app, asgi_call):
    app, rag = edge_app(upload_mb=1)
    result = await asgi_call(
        app,
        path=UPLOAD_PATH,
        chunks=[b"x"],
        headers=[
            ("content-type", "multipart/form-data; boundary=x"),
            ("content-length", str(10 * 1024 * MIB)),
        ],
    )
    assert result.status == 413
    assert result.receive_calls == 0
    rag.ingest_document.assert_not_called()


async def test_oversized_streamed_upload_is_cut_off(edge_app, asgi_call, multipart):
    app, rag = edge_app(upload_mb=1)
    headers, chunks, _ = multipart(20 * MIB)
    result = await asgi_call(app, path=UPLOAD_PATH, chunks=chunks, headers=headers)
    assert result.status == 413
    assert result.bytes_sent <= MIB + EDGE_ALLOWANCE + 2 * CHUNK
    assert result.headers.get("connection") == "close"
    assert "1MB" in result.json()["detail"]
    rag.ingest_document.assert_not_called()


async def test_upload_with_a_false_content_length_is_cut_off(
    edge_app, asgi_call, multipart
):
    app, rag = edge_app(upload_mb=1)
    headers, chunks, _ = multipart(5 * MIB)
    result = await asgi_call(
        app,
        path=UPLOAD_PATH,
        chunks=chunks,
        headers=[*headers, ("content-length", "1000")],
    )
    assert result.status == 413
    assert result.bytes_sent <= MIB + EDGE_ALLOWANCE + 2 * CHUNK
    rag.ingest_document.assert_not_called()


@pytest.mark.parametrize("values", [["abc"], ["-1"], ["1e9"], ["10", "20"]])
async def test_invalid_content_length_is_rejected(edge_app, asgi_call, values):
    app, rag = edge_app(upload_mb=1)
    headers = [("content-type", "application/json")]
    headers.extend(("content-length", value) for value in values)
    result = await asgi_call(app, path=TEXT_PATH, chunks=[b"{}"], headers=headers)
    assert result.status == 400
    assert result.receive_calls == 0
    rag.ingest_document.assert_not_called()


async def test_declared_oversized_text_payload_is_rejected_before_reading(
    edge_app, asgi_call
):
    app, rag = edge_app(upload_mb=1)
    result = await asgi_call(
        app,
        path=TEXT_PATH,
        chunks=[b"{}"],
        headers=[
            ("content-type", "application/json"),
            ("content-length", str(2 * MIB)),
        ],
    )
    assert result.status == 413
    assert result.receive_calls == 0
    rag.ingest_document.assert_not_called()


def test_text_limit_counts_utf8_bytes(edge_app):
    app, rag = edge_app(upload_mb=1)
    text = "\u0633" * 530_000  # 530,000 characters, 1,060,000 bytes in UTF-8
    payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    with TestClient(app) as client:
        response = client.post(
            TEXT_PATH, content=payload, headers={"content-type": "application/json"}
        )
    assert response.status_code == 413
    assert "1MB" in response.json()["detail"]
    rag.ingest_document.assert_not_called()


async def test_large_upload_within_the_limit_is_not_held_in_memory(
    edge_app, asgi_call, multipart
):
    app, _ = edge_app(upload_mb=50)
    headers, chunks, total = multipart(32 * MIB)
    tracemalloc.start()
    try:
        result = await asgi_call(
            app, path=UPLOAD_PATH, chunks=chunks, headers=_declared(headers, total)
        )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.status == 200, result.body
    assert peak < 8 * MIB, f"peak traced memory {peak} bytes"


async def test_oversized_upload_is_rejected_with_bounded_memory(
    edge_app, asgi_call, multipart
):
    app, rag = edge_app(upload_mb=2)
    headers, chunks, _ = multipart(40 * MIB)
    tracemalloc.start()
    try:
        result = await asgi_call(app, path=UPLOAD_PATH, chunks=chunks, headers=headers)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.status == 413
    assert result.bytes_sent < 3 * MIB
    assert peak < 6 * MIB, f"peak traced memory {peak} bytes"
    rag.ingest_document.assert_not_called()


async def test_rejected_uploads_leave_no_files(
    edge_app, asgi_call, multipart, tmp_path, monkeypatch
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    app, rag = edge_app(upload_mb=1)
    headers, chunks, _ = multipart(5 * MIB)
    streamed = await asgi_call(app, path=UPLOAD_PATH, chunks=chunks, headers=headers)
    headers, chunks, total = multipart(5 * MIB)
    declared = await asgi_call(
        app, path=UPLOAD_PATH, chunks=chunks, headers=_declared(headers, total)
    )
    gc.collect()
    assert streamed.status == 413
    assert declared.status == 413
    assert list(tmp_path.iterdir()) == []
    rag.ingest_document.assert_not_called()


def test_normal_upload_through_the_http_client_still_works(edge_app):
    app, rag = edge_app(upload_mb=1)
    content = b"hello edge protection"
    with TestClient(app) as client:
        response = client.post(
            UPLOAD_PATH, files={"file": ("notes.txt", content, "text/plain")}
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    metadata = rag.ingest_document.call_args.kwargs["metadata"]
    assert metadata["file_size"] == len(content)
