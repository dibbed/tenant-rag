"""
Enhanced authentication and rate limiting middleware for the RAG Telegram bot.

This module provides comprehensive user authentication, authorization, and rate limiting
to protect the bot from abuse and unauthorized access.
"""

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, DefaultDict, Deque, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


class RateLimiter:
    """Rate limiter implementation using sliding window."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: DefaultDict[int, Deque[float]] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limits."""
        now = time.time()
        user_requests = self.requests[user_id]

        # Remove old requests outside the window
        while user_requests and user_requests[0] <= now - self.window_seconds:
            user_requests.popleft()

        # Check if under limit
        if len(user_requests) < self.max_requests:
            user_requests.append(now)
            return True

        return False

    def get_reset_time(self, user_id: int) -> float:
        """Get time until rate limit resets for user."""
        user_requests = self.requests[user_id]
        if not user_requests:
            return 0.0

        oldest_request = user_requests[0]
        return max(0.0, oldest_request + self.window_seconds - time.time())


class AuthMiddleware(BaseMiddleware):
    """
    Enhanced middleware for authentication, authorization, and rate limiting.

    Features:
    - User allowlist enforcement
    - Rate limiting per user
    - Security validation
    - Comprehensive audit logging
    """

    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_requests=settings.security.rate_limit_requests,
            window_seconds=settings.security.rate_limit_window,
        )
        self.blocked_users: Dict[int, float] = {}  # user_id -> block_until_timestamp

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        """Main middleware handler."""

        # Only process Message events
        if not isinstance(event, Message):
            return await handler(event, data)

        # Skip if no user information
        if not event.from_user:
            logger.warning("Received message without user information")
            return

        user_id = event.from_user.id
        username = event.from_user.username or "unknown"

        # Check if user is temporarily blocked
        if await self._is_user_blocked(user_id):
            logger.log_user_action(
                user_id=user_id, action="blocked_user_attempt", username=username
            )
            return

        # Check user allowlist (if enabled)
        if settings.security.enable_user_allowlist:
            if not await self._is_user_allowed(user_id, username):
                return

        # Check rate limits
        if not await self._check_rate_limit(user_id, username, event):
            return

        # Validate message content
        if not await self._validate_message_content(event, user_id):
            return

        # Log successful authentication
        logger.log_user_action(
            user_id=user_id,
            action="authenticated_request",
            username=username,
            command=self._extract_command(event.text) if event.text else None,
        )

        # Proceed to handler
        try:
            return await handler(event, data)
        except Exception as e:
            logger.log_error_event(
                error=e, context="handler_execution", user_id=user_id, username=username
            )
            raise

    async def _is_user_blocked(self, user_id: int) -> bool:
        """Check if user is temporarily blocked."""
        if user_id in self.blocked_users:
            if time.time() < self.blocked_users[user_id]:
                return True
            else:
                # Block expired, remove it
                del self.blocked_users[user_id]
        return False

    async def _is_user_allowed(self, user_id: int, username: str) -> bool:
        """Check if user is in the allowlist."""
        allowed_users = settings.allow_users_list

        if not allowed_users:
            # If no allowlist is configured, allow all users
            return True

        if user_id not in allowed_users:
            logger.log_user_action(
                user_id=user_id, action="unauthorized_access_attempt", username=username
            )

            # Optionally send a polite rejection message
            # (commented out to avoid spam, but can be enabled)
            # await event.reply(
            #     "متأسفانه شما مجاز به استفاده از این ربات نیستید."
            #     if settings.default_lang == "fa" else
            #     "Sorry, you are not authorized to use this bot."
            # )

            return False

        return True

    async def _check_rate_limit(
        self, user_id: int, username: str, event: Message
    ) -> bool:
        """Check and enforce rate limits."""
        if not self.rate_limiter.is_allowed(user_id):
            reset_time = self.rate_limiter.get_reset_time(user_id)

            logger.log_user_action(
                user_id=user_id,
                action="rate_limit_exceeded",
                username=username,
                reset_time=reset_time,
            )

            # Send rate limit message
            if settings.default_lang == "fa":
                rate_limit_msg = (
                    f"⚠️ شما بیش از حد مجاز درخواست ارسال کرده‌اید.\n"
                    f"لطفاً {reset_time:.0f} ثانیه صبر کنید."
                )
            else:
                rate_limit_msg = (
                    f"⚠️ You have exceeded the rate limit.\n"
                    f"Please wait {reset_time:.0f} seconds."
                )

            try:
                await event.reply(rate_limit_msg)
            except Exception as e:
                logger.error(f"Failed to send rate limit message: {e}")

            # Temporarily block user if they continue to exceed limits
            if reset_time > settings.security.rate_limit_window * 0.8:
                self.blocked_users[user_id] = time.time() + 300  # Block for 5 minutes
                logger.log_user_action(
                    user_id=user_id,
                    action="user_temporarily_blocked",
                    username=username,
                    block_duration=300,
                )

            return False

        return True

    async def _validate_message_content(self, event: Message, user_id: int) -> bool:
        """Validate message content for security."""

        # Check for file uploads
        if event.document:
            # Validate file size
            if (
                event.document.file_size
                and event.document.file_size
                > settings.security.max_file_size_mb * 1024 * 1024
            ):
                logger.log_user_action(
                    user_id=user_id,
                    action="file_size_violation",
                    file_size=event.document.file_size,
                )

                error_msg = (
                    f"❌ فایل بیش از حد بزرگ است. حداکثر: {settings.security.max_file_size_mb}MB"
                    if settings.default_lang == "fa"
                    else f"❌ File too large. Maximum: {settings.security.max_file_size_mb}MB"
                )

                try:
                    await event.reply(error_msg)
                except Exception as e:
                    logger.error(f"Failed to send file size error: {e}")

                return False

            # Validate file type (by extension OR known MIME types)
            file_name = getattr(event.document, "file_name", "") or ""
            file_ext = ""
            try:
                from pathlib import Path

                file_ext = Path(file_name).suffix.lower().lstrip(".")
            except Exception:
                file_ext = ""

            mime_type = event.document.mime_type or ""

            # Known MIME types we explicitly allow in addition to extension checks
            known_allowed_mimes = {
                "application/pdf": "pdf",
                "text/plain": "txt",
                "text/html": "html",
                "text/markdown": "md",
                "text/x-markdown": "md",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            }

            ext_allowed = bool(file_ext) and file_ext in (
                settings.security.allowed_file_types or []
            )
            mime_allowed = mime_type in known_allowed_mimes and (
                known_allowed_mimes[mime_type]
                in (settings.security.allowed_file_types or [])
            )

            if not (ext_allowed or mime_allowed):
                logger.log_user_action(
                    user_id=user_id,
                    action="file_type_violation",
                    mime_type=mime_type,
                    file_ext=file_ext,
                )

                # Build dynamic, user-friendly list from allowed types
                display_map = {
                    "pdf": "PDF",
                    "docx": "DOCX",
                    "txt": "TXT",
                    "html": "HTML",
                    "htm": "HTML",
                    "md": "MD",
                    "pptx": "PPTX",
                    "xlsx": "XLSX",
                    "png": "PNG",
                    "jpg": "JPG",
                    "jpeg": "JPEG",
                    "tiff": "TIFF",
                    "bmp": "BMP",
                }
                try:
                    allowed_list = [
                        display_map.get(ft, ft.upper())
                        for ft in (settings.security.allowed_file_types or [])
                    ]
                except Exception:
                    allowed_list = ["PDF", "DOCX", "TXT", "HTML", "MD"]

                allowed_str = (
                    "، ".join(allowed_list)
                    if settings.default_lang == "fa"
                    else ", ".join(allowed_list)
                )
                error_msg = (
                    f"❌ نوع فایل مجاز نیست. فقط {allowed_str} پذیرفته می‌شود."
                    if settings.default_lang == "fa"
                    else f"❌ File type not allowed. Only {allowed_str} are accepted."
                )

                try:
                    await event.reply(error_msg)
                except Exception as e:
                    logger.error(f"Failed to send file type error: {e}")

                return False

        # Check text content length
        if event.text and len(event.text) > 10000:  # 10KB limit for text messages
            logger.log_user_action(
                user_id=user_id,
                action="text_length_violation",
                text_length=len(event.text),
            )

            error_msg = (
                "❌ متن بیش از حد طولانی است."
                if settings.default_lang == "fa"
                else "❌ Text is too long."
            )

            try:
                await event.reply(error_msg)
            except Exception as e:
                logger.error(f"Failed to send text length error: {e}")

            return False

        return True

    def _extract_command(self, text: str) -> str:
        """Extract command from message text."""
        if not text or not text.startswith("/"):
            return "message"

        parts = text.split()
        if parts:
            return parts[0][1:]  # Remove the '/' prefix

        return "unknown"
