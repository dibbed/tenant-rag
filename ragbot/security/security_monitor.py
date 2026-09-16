"""
Security monitoring counters/hooks (lightweight, Prometheus-friendly).
"""

from __future__ import annotations

from typing import Dict


class SecurityMonitor:
    """ناظر امنیتی برای شمارش رویدادها"""

    def __init__(self) -> None:
        self.counters: Dict[str, int] = {
            "filtered_messages": 0,
            "blocked_users": 0,
            "rate_limit_hits": 0,
            "security_events": 0,
        }

    async def inc(self, key: str) -> None:
        self.counters[key] = self.counters.get(key, 0) + 1

    async def get_snapshot(self) -> Dict[str, int]:
        return dict(self.counters)
