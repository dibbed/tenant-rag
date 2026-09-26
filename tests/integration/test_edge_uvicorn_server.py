"""Integration test: the request size limit on a real uvicorn server (C11).

A client that sends ``Expect: 100-continue`` with an oversized
``Content-Length`` gets HTTP 413 at once and never has to send the body.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration

APP_SOURCE = textwrap.dedent(
    """
    from fastapi import FastAPI, File, UploadFile

    from ragbot.api.middleware.body_size_limit import BodySizeLimitMiddleware

    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_size_mb=1)


    @app.post("/upload")
    async def upload(file: UploadFile = File(...)) -> dict:
        size = 0
        while True:
            chunk = await file.read(65536)
            if not chunk:
                break
            size += len(chunk)
        return {"size": size}
    """
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def server_port(tmp_path: Path) -> Iterator[int]:
    (tmp_path / "edge_size_app.py").write_text(APP_SOURCE)
    port = _free_port()
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(tmp_path), str(repo_root), env.get("PYTHONPATH", ""))
        if part
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "edge_size_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-proxy-headers",
            "--log-level",
            "warning",
        ],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 90
        while True:
            if process.poll() is not None:
                output = (
                    process.stdout.read().decode(errors="replace")
                    if process.stdout
                    else ""
                )
                pytest.fail(f"uvicorn exited early:\n{output[-4000:]}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                if time.monotonic() > deadline:
                    pytest.fail("uvicorn did not start within 90 seconds")
                time.sleep(0.25)
        yield port
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _read_until_closed(sock: socket.socket) -> bytes:
    sock.settimeout(15)
    data = b""
    while True:
        try:
            chunk = sock.recv(65536)
        except TimeoutError:
            break
        if not chunk:
            break
        data += chunk
    return data


def test_oversized_upload_is_refused_before_the_body_is_sent(server_port):
    request = (
        "POST /upload HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{server_port}\r\n"
        "Content-Type: multipart/form-data; boundary=edge\r\n"
        "Content-Length: 5242880\r\n"
        "Expect: 100-continue\r\n"
        "\r\n"
    ).encode()
    with socket.create_connection(("127.0.0.1", server_port), timeout=10) as sock:
        sock.sendall(request)
        response = _read_until_closed(sock)
    status_line = response.split(b"\r\n", 1)[0]
    assert status_line.startswith(b"HTTP/1.1 413"), response[:300]
    assert b"100 Continue" not in response
    assert b"maximum allowed size of 1MB" in response
