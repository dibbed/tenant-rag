"""
Signal handling utilities for graceful shutdown
"""

import asyncio
import signal
import sys
from collections.abc import Callable
from types import FrameType, TracebackType
from typing import Any

from ragbot.outputs.logger import logger

ShutdownCallback = Callable[[], Any]


class SignalHandler:
    """Enhanced signal handler for graceful shutdown"""

    def __init__(self) -> None:
        self.shutdown_requested = False
        self.force_shutdown = False
        self._original_handlers: dict[signal.Signals, Any] = {}
        self._shutdown_callbacks: list[ShutdownCallback] = []
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def add_shutdown_callback(self, callback: ShutdownCallback) -> None:
        """Add a callback to be called during shutdown"""
        self._shutdown_callbacks.append(callback)

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals"""
        if self.shutdown_requested:
            if not self.force_shutdown:
                logger.warning("Second signal received, forcing immediate shutdown...")
                self.force_shutdown = True
                # Force exit after a short delay and keep the task alive.
                force_task = asyncio.create_task(self._force_exit())
                self._background_tasks.add(force_task)
                force_task.add_done_callback(self._background_tasks.discard)
            return

        self.shutdown_requested = True
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")

        # Call all shutdown callbacks
        for callback in self._shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Schedule the coroutine and keep it alive until completion.
                    callback_task = asyncio.create_task(callback())
                    self._background_tasks.add(callback_task)
                    callback_task.add_done_callback(self._background_tasks.discard)
                else:
                    callback()
            except Exception as e:  # noqa: PERF203 - intentional per-iteration fault isolation
                logger.warning(f"Error in shutdown callback: {e}")

    async def _force_exit(self) -> None:
        """Force exit after a short delay"""
        await asyncio.sleep(2)  # Give 2 seconds for cleanup
        logger.error("Force shutdown timeout reached, exiting immediately...")
        sys.exit(1)

    def setup_handlers(self) -> None:
        """Set up signal handlers"""
        self._original_handlers[signal.SIGINT] = signal.signal(
            signal.SIGINT, self._signal_handler
        )
        self._original_handlers[signal.SIGTERM] = signal.signal(
            signal.SIGTERM, self._signal_handler
        )

    def restore_handlers(self) -> None:
        """Restore original signal handlers"""
        signal.signal(signal.SIGINT, self._original_handlers[signal.SIGINT])
        signal.signal(signal.SIGTERM, self._original_handlers[signal.SIGTERM])

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested"""
        return self.shutdown_requested

    def is_force_shutdown(self) -> bool:
        """Check if force shutdown was requested"""
        return self.force_shutdown


class GracefulShutdown:
    """Context manager for graceful shutdown handling"""

    def __init__(self) -> None:
        self.signal_handler = SignalHandler()

    def __enter__(self) -> "GracefulShutdown":
        """Set up signal handlers"""
        self.signal_handler.setup_handlers()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Restore original signal handlers"""
        self.signal_handler.restore_handlers()

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested"""
        return self.signal_handler.is_shutdown_requested()

    def is_force_shutdown(self) -> bool:
        """Check if force shutdown was requested"""
        return self.signal_handler.is_force_shutdown()

    def add_shutdown_callback(self, callback: ShutdownCallback) -> None:
        """Add a callback to be called during shutdown"""
        self.signal_handler.add_shutdown_callback(callback)
