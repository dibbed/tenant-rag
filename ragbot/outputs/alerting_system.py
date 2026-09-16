"""
Alerting system integration glue.

Persian developer notes:
- این ماژول لایه اتصال برای مدیریت هشدارها و کانال‌های اطلاع‌رسانی است.
"""

from __future__ import annotations

from typing import Any, Dict

from ragbot.monitoring.alert_manager import AlertManager, NotificationChannel


class AlertingSystem:
    """Thin wrapper around AlertManager to register channels from settings."""

    def __init__(self, manager: AlertManager) -> None:
        self.manager = manager

    async def configure_from_settings(
        self, settings_dict: Dict[str, Dict[str, Any]]
    ) -> None:
        for channel_type, cfg in settings_dict.items():
            enabled = bool(cfg.get("enabled", False))
            channel = NotificationChannel(
                type=channel_type, config=cfg, enabled=enabled
            )
            await self.manager.add_notification_channel(channel_type, channel)
