"""Phase 3.5 regression tests: servers bind to the loopback interface unless configured.

Bandit B104 (docs/security/PHASE3_5_SECURITY_HARDENING.md).

Before: the API server bound all interfaces (0.0.0.0) when neither HOST nor
--host was given, and start_health_server always bound all interfaces.
Expected: the loopback interface by default. The container image and
docker-compose.yml select all interfaces explicitly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import ragbot.main as package_main

ROOT = Path(__file__).resolve().parents[2]


def test_the_api_server_binds_to_loopback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    with patch.object(sys, "argv", ["ragbot"]), patch("uvicorn.run") as run:
        package_main.main()
    assert run.call_args.kwargs["host"] == "127.0.0.1"


def test_the_host_setting_still_selects_another_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "0.0.0.0")
    with patch.object(sys, "argv", ["ragbot"]), patch("uvicorn.run") as run:
        package_main.main()
    assert run.call_args.kwargs["host"] == "0.0.0.0"


def test_the_container_selects_all_interfaces_explicitly() -> None:
    assert '"--host", "0.0.0.0"' in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HOST=0.0.0.0" in (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_the_health_server_binds_to_loopback_by_default() -> None:
    from ragbot.outputs import health_endpoints

    with patch("uvicorn.run") as run, patch.object(health_endpoints, "create_health_app", return_value=object()):
        health_endpoints.start_health_server(port=8181)
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 8181
