"""
Alert management utilities.

Persian developer notes:
- مدیریت قوانین هشدار و ارسال به کانال‌های اطلاع‌رسانی.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from datetime import datetime
from typing import Any


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
    config: dict[str, Any]
    enabled: bool = True


class AlertManager:
    """Manage alert rules and dispatch notifications."""

    def __init__(self) -> None:
        self.alert_rules: dict[str, AlertRule] = {}
        self.notification_channels: dict[str, NotificationChannel] = {}
        self.alert_history: list[dict[str, Any]] = []

        self.default_rules: dict[str, AlertRule] = {
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

    async def evaluate_metrics(self, metrics: dict[str, Any]) -> None:
        triggered: list[tuple[str, AlertRule]] = []
        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
            if await self._evaluate_condition(rule.condition, rule.threshold, metrics):
                triggered.append((rule_id, rule))
        for rule_id, rule in triggered:
            await self._send_alert(rule_id, rule, metrics)

    async def _evaluate_condition(
        self, condition: str, threshold: float, metrics: dict[str, Any]
    ) -> bool:
        """Evaluate a constrained alert expression without executing Python code.

        Supported expressions may reference numeric/boolean metric names and
        the threshold value and may use comparisons, boolean operators, and
        basic arithmetic. Executable Python constructs are rejected.
        """
        compare_ops = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
        }
        binary_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
        }

        def resolve(node: ast.AST) -> Any:
            if isinstance(node, ast.Expression):
                return resolve(node.body)
            if isinstance(node, ast.Constant) and isinstance(
                node.value, int | float | bool
            ):
                return node.value
            if isinstance(node, ast.Name):
                if node.id == "threshold":
                    return threshold
                if node.id not in metrics:
                    raise ValueError(f"Unknown alert metric: {node.id}")
                value = metrics[node.id]
                if not isinstance(value, int | float | bool):
                    raise ValueError(f"Alert metric {node.id!r} is not numeric")
                return value
            if isinstance(node, ast.UnaryOp):
                value = resolve(node.operand)
                if isinstance(node.op, ast.Not):
                    return not bool(value)
                if isinstance(node.op, ast.USub):
                    return -value
                if isinstance(node.op, ast.UAdd):
                    return +value
                raise ValueError("Unsupported unary operator")
            if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
                return binary_ops[type(node.op)](resolve(node.left), resolve(node.right))
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    return all(bool(resolve(value)) for value in node.values)
                if isinstance(node.op, ast.Or):
                    return any(bool(resolve(value)) for value in node.values)
                raise ValueError("Unsupported boolean operator")
            if isinstance(node, ast.Compare):
                left = resolve(node.left)
                for op_node, comparator in zip(node.ops, node.comparators, strict=False):
                    operation = compare_ops.get(type(op_node))
                    if operation is None:
                        raise ValueError("Unsupported comparison operator")
                    right = resolve(comparator)
                    if not operation(left, right):
                        return False
                    left = right
                return True
            raise ValueError(
                f"Unsupported alert expression node: {type(node).__name__}"
            )

        try:
            tree = ast.parse(condition, mode="eval")
            return bool(resolve(tree))
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError):
            return False

    async def _send_alert(
        self, rule_id: str, rule: AlertRule, metrics: dict[str, Any]
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
        for channel in self.notification_channels.values():
            if channel.enabled:
                await self._send_to_channel(channel, data)

    async def _send_to_channel(
        self, channel: NotificationChannel, alert_data: dict[str, Any]
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
        self, config: dict[str, Any], alert_data: dict[str, Any]
    ) -> None:
        return None

    async def _send_slack(
        self, config: dict[str, Any], alert_data: dict[str, Any]
    ) -> None:
        return None

    async def _send_discord(
        self, config: dict[str, Any], alert_data: dict[str, Any]
    ) -> None:
        return None

    async def _send_webhook(
        self, config: dict[str, Any], alert_data: dict[str, Any]
    ) -> None:
        return None
