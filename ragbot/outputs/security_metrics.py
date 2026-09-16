"""
Prometheus-like counters for security events. Kept lightweight to avoid hard deps.
"""

from __future__ import annotations

from typing import Dict


class SecurityMetrics:
    """متریک‌های امنیتی"""

    def __init__(self) -> None:
        self.filtered_messages_total = 0
        self.blocked_users_total = 0
        self.rate_limit_hits_total = 0
        self.security_events_total = 0

    async def record_filtered_message(self) -> None:
        self.filtered_messages_total += 1

    async def record_blocked_user(self) -> None:
        self.blocked_users_total += 1

    async def record_rate_limit_hit(self) -> None:
        self.rate_limit_hits_total += 1

    async def record_security_event(self) -> None:
        self.security_events_total += 1

    async def snapshot(self) -> Dict[str, int]:
        return {
            "filtered_messages_total": self.filtered_messages_total,
            "blocked_users_total": self.blocked_users_total,
            "rate_limit_hits_total": self.rate_limit_hits_total,
            "security_events_total": self.security_events_total,
        }
