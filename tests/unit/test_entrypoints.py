"""
Unit and regression tests for application entrypoints and startup lifecycles.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main as root_main
import ragbot.main as pkg_main
from ragbot.api.app import create_app, lifespan


class TestApplicationEntrypoints:
    """Test suite verifying startup entrypoints, parameter parsing, and lifecycles."""

    def test_root_main_delegates_to_package_main(self) -> None:
        """Root main.py must import and delegate directly to ragbot.main.main."""
        assert hasattr(root_main, "main")
        assert callable(root_main.main)
        assert root_main.main is pkg_main.main

    @patch("uvicorn.run")
    def test_package_main_default_arguments(self, mock_uvicorn_run: MagicMock) -> None:
        """Test pkg_main.main with default arguments."""
        with patch.object(sys, "argv", ["ragbot"]):
            pkg_main.main()

        mock_uvicorn_run.assert_called_once_with(
            "ragbot.api.app:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            workers=1,
            proxy_headers=False,
        )

    @patch("uvicorn.run")
    def test_package_main_custom_cli_arguments(self, mock_uvicorn_run: MagicMock) -> None:
        """Test pkg_main.main with explicit CLI flags."""
        with patch.object(
            sys,
            "argv",
            ["ragbot", "--host", "127.0.0.1", "--port", "9090", "--workers", "4"],
        ):
            pkg_main.main()

        mock_uvicorn_run.assert_called_once_with(
            "ragbot.api.app:app",
            host="127.0.0.1",
            port=9090,
            reload=False,
            workers=4,
            proxy_headers=False,
        )

    @patch("uvicorn.run")
    def test_package_main_reload_flag(self, mock_uvicorn_run: MagicMock) -> None:
        """Test that --reload forces workers to 1 even if workers is specified."""
        with patch.object(
            sys, "argv", ["ragbot", "--reload", "--workers", "4"]
        ):
            pkg_main.main()

        mock_uvicorn_run.assert_called_once_with(
            "ragbot.api.app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            workers=1,
            proxy_headers=False,
        )

    @patch("uvicorn.run", side_effect=KeyboardInterrupt)
    def test_package_main_keyboard_interrupt_handled(
        self, mock_uvicorn_run: MagicMock
    ) -> None:
        """KeyboardInterrupt should be caught and exit cleanly without bubbling."""
        with patch.object(sys, "argv", ["ragbot"]):
            # Should not raise
            pkg_main.main()

    @patch("uvicorn.run", side_effect=RuntimeError("Bind address already in use"))
    def test_package_main_fatal_exception_exits(
        self, mock_uvicorn_run: MagicMock
    ) -> None:
        """Fatal startup exception should log error and call sys.exit(1)."""
        with patch.object(sys, "argv", ["ragbot"]):
            with pytest.raises(SystemExit) as exc_info:
                pkg_main.main()
            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_app_lifespan_lifecycle(self) -> None:
        """Test that FastAPI app lifespan initializes and shuts down cleanly."""
        mock_service = MagicMock()
        mock_service._initialized = False
        mock_service.initialize = MagicMock()
        mock_service.shutdown = MagicMock()
        mock_service.get_rag_service.return_value = MagicMock()

        async def async_init():
            mock_service._initialized = True

        async def async_shutdown():
            pass

        mock_service.initialize.side_effect = async_init
        mock_service.shutdown.side_effect = async_shutdown

        app = FastAPI(lifespan=lifespan)
        app.state.integration_service = mock_service

        async with lifespan(app):
            assert app.state.integration_service is mock_service
            assert mock_service.initialize.called

        assert mock_service.shutdown.called

    def test_app_creation_and_health_probe(self) -> None:
        """Verify created app responds to /health probe."""
        from ragbot.api.dependencies import get_integration_service_dep

        from unittest.mock import AsyncMock

        mock_svc = MagicMock()
        mock_svc.health_check = AsyncMock(
            return_value={
                "status": "healthy",
                "timestamp": 1234567890.0,
                "components": {"store": {"status": "healthy"}},
                "issues": [],
            }
        )

        app = create_app()
        app.dependency_overrides[get_integration_service_dep] = lambda: mock_svc

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["timestamp"] == 1234567890.0

