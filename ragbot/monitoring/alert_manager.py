"""
Alert management utilities.

Persian developer notes:
- مدیریت قوانین هشدار و ارسال به کانال‌های اطلاع‌رسانی.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class AlertRule:
    """Alert rule definition."""

    name: str
    condition: str
    threshold: float
    severity: str
    enabled: bool = True


@dataclass
class NotificationChannel:
    """Notification channel config."""

    type: str  # email, slack, discord, webhook
    config: Dict[str, Any]
    enabled: bool = True


class AlertManager:
    """Manage alert rules and dispatch notifications."""

    def __init__(self) -> None:
        self.alert_rules: Dict[str, AlertRule] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}
        self.alert_history: list[Dict[str, Any]] = []

        self.default_rules: Dict[str, AlertRule] = {
            "high_cpu": AlertRule(
                "High CPU Usage", "cpu_usage > threshold", 80.0, "warning"
            ),
            "high_memory": AlertRule(
                "High Memory Usage", "memory_usage > threshold", 85.0, "critical"
            ),
            "high_disk": AlertRule(
                "High Disk Usage", "disk_usage > threshold", 90.0, "warning"
            ),
            "slow_response": AlertRule(
                "Slow Response Time", "response_time > threshold", 5.0, "warning"
            ),
            "high_error_rate": AlertRule(
                "High Error Rate", "error_rate > threshold", 10.0, "critical"
            ),
        }
        for rule_id, rule in self.default_rules.items():
            self.alert_rules[rule_id] = rule

    async def add_alert_rule(self, rule_id: str, rule: AlertRule) -> None:
        self.alert_rules[rule_id] = rule

    async def remove_alert_rule(self, rule_id: str) -> None:
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]

    async def add_notification_channel(
        self, channel_id: str, channel: NotificationChannel
    ) -> None:
        self.notification_channels[channel_id] = channel

    async def evaluate_metrics(self, metrics: Dict[str, Any]) -> None:
        triggered: list[tuple[str, AlertRule]] = []
        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            if await self._evaluate_condition(rule.condition, rule.threshold, metrics):
                triggered.append((rule_id, rule))
        for rule_id, rule in triggered:
            await self._send_alert(rule_id, rule, metrics)

    async def _evaluate_condition(
        self, condition: str, threshold: float, metrics: Dict[str, Any]
    ) -> bool:
        try:
            expr = condition
            for k, v in metrics.items():
                expr = expr.replace(k, str(v))
            expr = expr.replace("threshold", str(threshold))
            return bool(eval(expr))
        except Exception:
            return False

    async def _send_alert(
        self, rule_id: str, rule: AlertRule, metrics: Dict[str, Any]
    ) -> None:
        data = {
            "rule_id": rule_id,
            "rule_name": rule.name,
            "severity": rule.severity,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "message": f"{rule.name}: {rule.condition.replace('threshold', str(rule.threshold))}",
        }
        self.alert_history.append(data)
        for _, channel in self.notification_channels.items():
            if channel.enabled:
                await self._send_to_channel(channel, data)

    async def _send_to_channel(
        self, channel: NotificationChannel, alert_data: Dict[str, Any]
    ) -> None:
        try:
            if channel.type == "email":
                await self._send_email(channel.config, alert_data)
            elif channel.type == "slack":
                await self._send_slack(channel.config, alert_data)
            elif channel.type == "discord":
                await self._send_discord(channel.config, alert_data)
            elif channel.type == "webhook":
                await self._send_webhook(channel.config, alert_data)
        except Exception as exc:
            print(f"❌ Error sending alert to {channel.type}: {exc}")

    async def _send_email(
        self, config: Dict[str, Any], alert_data: Dict[str, Any]
    ) -> None:
        return None

    async def _send_slack(
        self, config: Dict[str, Any], alert_data: Dict[str, Any]
    ) -> None:
        return None

    async def _send_discord(
        self, config: Dict[str, Any], alert_data: Dict[str, Any]
    ) -> None:
        return None

    async def _send_webhook(
        self, config: Dict[str, Any], alert_data: Dict[str, Any]
    ) -> None:
        return None
