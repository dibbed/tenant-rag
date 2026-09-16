"""
Structured logging setup for the RAG Telegram bot.

This module provides comprehensive logging configuration with file rotation,
structured formats, and multiple output targets for production use.
"""

import json
import sys
from typing import Any, Dict, Optional

from loguru import logger as loguru_logger

from ragbot.configs.settings import settings


class StructuredLogger:
    """
    Structured logger wrapper providing consistent logging interface.

    This class wraps loguru to provide structured logging capabilities
    with JSON formatting, file rotation, and multiple output targets.
    """

    def __init__(self) -> None:
        """Initialize the structured logger."""
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup logger configuration with file and console outputs."""
        # Remove default handler
        loguru_logger.remove()

        # Console handler with colored output
        loguru_logger.add(
            sys.stderr,
            level=settings.monitoring.log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{extra[caller_module]}</cyan>:<cyan>{extra[caller_function]}</cyan>:<cyan>{extra[caller_line]}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
            backtrace=True,
            diagnose=True,
            filter=self._add_caller_info,
        )

        # File handler with structured format (if log file is configured)
        if settings.log_file:
            # Ensure log directory exists
            settings.log_file.parent.mkdir(parents=True, exist_ok=True)

            loguru_logger.add(
                str(settings.log_file),
                level="INFO",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {extra[caller_module]}:{extra[caller_function]}:{extra[caller_line]} | {message}",
                rotation="1 day",
                retention="7 days",
                compression="gz",
                encoding="utf-8",
                serialize=False,  # Keep human-readable format
                filter=self._add_caller_info,
            )

            # Separate JSON log file for structured logging
            json_log_file = settings.log_file.with_suffix(".json")
            loguru_logger.add(
                str(json_log_file),
                level="INFO",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {extra[caller_module]}:{extra[caller_function]}:{extra[caller_line]} | {message} | {extra}",
                rotation="1 day",
                retention="7 days",
                compression="gz",
                encoding="utf-8",
                serialize=True,  # Use loguru's built-in JSON serialization
                filter=self._add_caller_info,
            )

    def _add_caller_info(self, record):
        """Add caller information to log record."""
        import inspect
        import os

        # Get the caller frame (skip logger methods)
        frame = inspect.currentframe()
        try:
            # Go up the stack to find the actual caller
            for _ in range(5):  # Skip logger internal calls
                frame = frame.f_back
                if frame is None:
                    break

            if frame:
                caller_file = frame.f_code.co_filename
                caller_function = frame.f_code.co_name
                caller_line = frame.f_lineno

                # Convert absolute path to module path
                if caller_file.startswith(os.getcwd()):
                    # Convert file path to module path
                    relative_path = (
                        caller_file[len(os.getcwd()) :].replace("\\", "/").lstrip("/")
                    )
                    # Remove .py extension and convert to module path
                    module_path = relative_path.replace("/", ".").replace(".py", "")
                    # Remove __init__ if it's the last part
                    if module_path.endswith(".__init__"):
                        module_path = module_path[:-9]
                else:
                    module_path = "unknown"

                record["extra"]["caller_module"] = module_path
                record["extra"]["caller_function"] = caller_function
                record["extra"]["caller_line"] = caller_line
            else:
                record["extra"]["caller_module"] = "unknown"
                record["extra"]["caller_function"] = "unknown"
                record["extra"]["caller_line"] = 0
        finally:
            del frame

        return True

    def _json_formatter(self, record: Dict[str, Any]) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "module": record["extra"].get("caller_module", "unknown"),
            "function": record["extra"].get("caller_function", "unknown"),
            "line": record["extra"].get("caller_line", 0),
            "message": record["message"],
        }

        # Add extra fields if present
        if "extra" in record:
            log_entry.update(record["extra"])

        return json.dumps(log_entry, ensure_ascii=False)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with optional structured data."""
        loguru_logger.bind(**kwargs).debug(message)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with optional structured data."""
        loguru_logger.bind(**kwargs).info(message)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with optional structured data."""
        loguru_logger.bind(**kwargs).warning(message)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with optional structured data."""
        loguru_logger.bind(**kwargs).error(message)

    def success(self, message: str, **kwargs: Any) -> None:
        """Log success message with optional structured data."""
        loguru_logger.bind(**kwargs).info(f"✅ {message}")

    def error_with_traceback(
        self, message: str, exc_info: bool = True, **kwargs: Any
    ) -> None:
        """Log error message with full traceback."""
        loguru_logger.bind(**kwargs).opt(exception=exc_info).error(message)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with optional structured data."""
        loguru_logger.bind(**kwargs).critical(message)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback and optional structured data."""
        loguru_logger.bind(**kwargs).exception(message)

    def log_structured(
        self, level: str, event: str, user_id: Optional[int] = None, **kwargs: Any
    ) -> None:
        """
        Log structured event with additional context.

        Args:
            level: Log level (debug, info, warning, error, critical)
            event: Event name/type
            user_id: Optional user ID for user-related events
            **kwargs: Additional structured data
        """
        structured_data = {"event": event, **kwargs}

        if user_id is not None:
            structured_data["user_id"] = user_id

        log_method = getattr(loguru_logger.bind(**structured_data), level.lower())
        log_method(f"Event: {event}")

    def log_user_action(self, user_id: int, action: str, **kwargs: Any) -> None:
        """
        Log user action with structured data.

        Args:
            user_id: User ID
            action: Action performed
            **kwargs: Additional context data
        """
        self.log_structured(
            "info", "user_action", user_id=user_id, action=action, **kwargs
        )

    def log_system_event(self, event: str, **kwargs: Any) -> None:
        """
        Log system event with structured data.

        Args:
            event: System event name
            **kwargs: Additional context data
        """
        self.log_structured("info", "system_event", event_type=event, **kwargs)

    def log_error_event(
        self,
        error: Exception,
        context: str,
        user_id: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log error event with exception details.

        Args:
            error: Exception that occurred
            context: Context where error occurred
            user_id: Optional user ID if user-related
            **kwargs: Additional context data
        """
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            **kwargs,
        }

        if user_id is not None:
            error_data["user_id"] = user_id

        loguru_logger.bind(**error_data).error(f"Error in {context}: {error}")

    def log_performance(self, operation: str, duration: float, **kwargs: Any) -> None:
        """
        Log performance metrics.

        Args:
            operation: Operation name
            duration: Duration in seconds
            **kwargs: Additional metrics
        """
        self.log_structured(
            "info",
            "performance",
            operation=operation,
            duration_seconds=duration,
            **kwargs,
        )


# Global logger instance
logger = StructuredLogger()

# Expose loguru logger for direct access if needed
loguru_logger = loguru_logger
