"""
Content filter middleware to guard incoming messages/callbacks.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from ragbot.security.content_filter import ContentFilter, FilterResult


class ContentFilterMiddleware(BaseMiddleware):
    """Middleware فیلتر محتوا"""

    def __init__(self, content_filter: ContentFilter) -> None:
        """Initialize content filter middleware."""

        self.content_filter = content_filter
        self.filtered_count = 0
        self.blocked_users: set[int] = set()

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Any],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        """Process message through content filter."""

        # Extract text/user id
        if isinstance(event, Message):
            text = (event.text or event.caption or "").strip()
            user_id = event.from_user.id if event.from_user else 0
        elif isinstance(event, CallbackQuery):
            text = (event.data or "").strip()
            user_id = event.from_user.id if event.from_user else 0
        else:
            return await handler(event, data)

        # Skip empty messages
        if not text:
            return await handler(event, data)

        result: FilterResult = await self.content_filter.filter_content(
            text, str(user_id)
        )
        if not result.is_safe:
            self.filtered_count += 1

            # Notify user (bilingual message already handled in locale elsewhere)
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ پیام شما حاوی محتوای نامناسب است و فیلتر شده است.\n"
                    f"دلیل: {', '.join(result.reasons)}"
                )

            # Optional simple auto-block on repeated violations
            if self.filtered_count > 3:
                self.blocked_users.add(user_id)
                if isinstance(event, Message):
                    await event.answer(
                        "🚫 شما به دلیل ارسال محتوای نامناسب مسدود شده‌اید."
                    )
            return

        return await handler(event, data)
