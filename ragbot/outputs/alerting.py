"""
Alerting system for critical component failures.

This module provides alerting capabilities for health check failures,
supporting multiple notification channels and escalation policies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from ragbot.configs.settings import settings
from ragbot.outputs.health import ComponentHealth, HealthStatus, SystemHealth
from ragbot.outputs.logger import logger


class AlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert notification channels."""

    LOG = "log"
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class Alert:
    """Alert data structure."""

    id: str
    component: str
    severity: AlertSeverity
    status: HealthStatus
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "component": self.component,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass
class AlertRule:
    """Alert rule configuration."""

    component: str
    severity: AlertSeverity
    channels: List[AlertChannel]
    conditions: Dict[str, Any]
    cooldown_minutes: int = 5
    max_alerts_per_hour: int = 10


class AlertManager:
    """
    Alert manager for health check failures.

    Manages alert generation, notification, and escalation based on
    component health status and configured rules.
    """

    def __init__(self) -> None:
        """Initialize alert manager."""
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_counts: Dict[str, int] = {}
        self.last_alert_times: Dict[str, datetime] = {}

        # Default alert rules
        self.alert_rules = self._setup_default_alert_rules()

        logger.info("Alert manager initialized", rules_count=len(self.alert_rules))

    def _setup_default_alert_rules(self) -> List[AlertRule]:
        """Setup default alert rules for components."""
        return [
            # Critical components
            AlertRule(
                component="telegram_api",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.TELEGRAM],
                conditions={"status": [HealthStatus.UNHEALTHY]},
                cooldown_minutes=5,
                max_alerts_per_hour=6,
            ),
            AlertRule(
                component="llm_service",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.TELEGRAM],
                conditions={"status": [HealthStatus.UNHEALTHY]},
                cooldown_minutes=5,
                max_alerts_per_hour=6,
            ),
            AlertRule(
                component="vector_store",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG, AlertChannel.TELEGRAM],
                conditions={"status": [HealthStatus.UNHEALTHY]},
                cooldown_minutes=10,
                max_alerts_per_hour=4,
            ),
            AlertRule(
                component="embedding_service",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG],
                conditions={"status": [HealthStatus.UNHEALTHY]},
                cooldown_minutes=10,
                max_alerts_per_hour=4,
            ),
            AlertRule(
                component="cache_service",
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.LOG],
                conditions={"status": [HealthStatus.UNHEALTHY]},
                cooldown_minutes=15,
                max_alerts_per_hour=3,
            ),
            AlertRule(
                component="file_system",
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG, AlertChannel.TELEGRAM],
                conditions={"status": [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]},
                cooldown_minutes=30,
                max_alerts_per_hour=2,
            ),
            AlertRule(
                component="memory_usage",
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.LOG],
                conditions={"status": [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]},
                cooldown_minutes=15,
                max_alerts_per_hour=3,
            ),
        ]

    async def process_health_status(self, system_health: SystemHealth) -> List[Alert]:
        """
        Process system health status and generate alerts.

        Args:
            system_health: Current system health status

        Returns:
            List[Alert]: Generated alerts
        """
        generated_alerts = []

        for component_name, component_health in system_health.components.items():
            alerts = await self._check_component_alerts(component_health)
            generated_alerts.extend(alerts)

        # Check for resolved alerts
        await self._check_resolved_alerts(system_health.components)

        return generated_alerts

    async def _check_component_alerts(
        self, component_health: ComponentHealth
    ) -> List[Alert]:
        """Check if component health triggers any alerts."""
        generated_alerts = []

        # Find matching alert rules
        matching_rules = [
            rule for rule in self.alert_rules if rule.component == component_health.name
        ]

        for rule in matching_rules:
            if self._should_trigger_alert(component_health, rule):
                alert = await self._create_alert(component_health, rule)
                if alert:
                    generated_alerts.append(alert)

        return generated_alerts

    def _should_trigger_alert(
        self, component_health: ComponentHealth, rule: AlertRule
    ) -> bool:
        """Check if alert should be triggered based on rule conditions."""
        # Check status condition
        if "status" in rule.conditions:
            if component_health.status not in rule.conditions["status"]:
                return False

        # Check error count condition
        if "min_error_count" in rule.conditions:
            if component_health.error_count < rule.conditions["min_error_count"]:
                return False

        # Check response time condition
        if "max_response_time" in rule.conditions and component_health.response_time:
            if component_health.response_time < rule.conditions["max_response_time"]:
                return False

        # Check cooldown period
        alert_key = f"{rule.component}_{rule.severity.value}"
        if alert_key in self.last_alert_times:
            time_since_last = datetime.now() - self.last_alert_times[alert_key]
            if time_since_last < timedelta(minutes=rule.cooldown_minutes):
                return False

        # Check rate limiting
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        hour_key = f"{alert_key}_{current_hour.isoformat()}"
        if self.alert_counts.get(hour_key, 0) >= rule.max_alerts_per_hour:
            return False

        # Check if alert is already active
        if alert_key in self.active_alerts:
            return False

        return True

    async def _create_alert(
        self, component_health: ComponentHealth, rule: AlertRule
    ) -> Optional[Alert]:
        """Create and process a new alert."""
        alert_id = (
            f"{rule.component}_{rule.severity.value}_{int(datetime.now().timestamp())}"
        )

        alert = Alert(
            id=alert_id,
            component=component_health.name,
            severity=rule.severity,
            status=component_health.status,
            message=self._generate_alert_message(component_health, rule),
            timestamp=datetime.now(),
            metadata={
                "error_count": component_health.error_count,
                "response_time": component_health.response_time,
                "error_message": component_health.error_message,
                "component_metadata": component_health.metadata,
            },
        )

        # Store alert
        alert_key = f"{rule.component}_{rule.severity.value}"
        self.active_alerts[alert_key] = alert
        self.alert_history.append(alert)

        # Update counters
        self.last_alert_times[alert_key] = datetime.now()
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        hour_key = f"{alert_key}_{current_hour.isoformat()}"
        self.alert_counts[hour_key] = self.alert_counts.get(hour_key, 0) + 1

        # Send notifications
        await self._send_alert_notifications(alert, rule.channels)

        logger.log_structured(
            "warning",
            "alert_generated",
            alert_id=alert.id,
            component=alert.component,
            severity=alert.severity.value,
            status=alert.status.value,
        )

        return alert

    def _generate_alert_message(
        self, component_health: ComponentHealth, rule: AlertRule
    ) -> str:
        """Generate alert message based on component health and rule."""
        base_message = (
            f"Component '{component_health.name}' is {component_health.status.value}"
        )

        details = []
        if component_health.error_message:
            details.append(f"Error: {component_health.error_message}")

        if component_health.error_count > 0:
            details.append(f"Error count: {component_health.error_count}")

        if component_health.response_time:
            details.append(f"Response time: {component_health.response_time:.2f}s")

        if details:
            return f"{base_message}. {'. '.join(details)}"

        return base_message

    async def _send_alert_notifications(
        self, alert: Alert, channels: List[AlertChannel]
    ) -> None:
        """Send alert notifications through specified channels."""
        for channel in channels:
            try:
                if channel == AlertChannel.LOG:
                    await self._send_log_notification(alert)
                elif channel == AlertChannel.TELEGRAM:
                    await self._send_telegram_notification(alert)
                elif channel == AlertChannel.EMAIL:
                    await self._send_email_notification(alert)
                elif channel == AlertChannel.WEBHOOK:
                    await self._send_webhook_notification(alert)
            except Exception as e:
                logger.error(
                    f"Failed to send alert via {channel.value}: {e}", alert_id=alert.id
                )

    async def _send_log_notification(self, alert: Alert) -> None:
        """Send alert notification to logs."""
        logger.log_structured(
            "error"
            if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]
            else "warning",
            "component_alert",
            alert_id=alert.id,
            component=alert.component,
            severity=alert.severity.value,
            message=alert.message,
            **alert.metadata,
        )

    async def _send_telegram_notification(self, alert: Alert) -> None:
        """Send alert notification via Telegram."""
        try:
            from telegram import Bot

            bot = Bot(token=settings.bot_token)

            # Send to admin users (first user in allow list)
            admin_users = settings.allow_users_list[:1]  # Only first user gets alerts

            if not admin_users:
                logger.warning("No admin users configured for Telegram alerts")
                return

            message = self._format_telegram_alert(alert)

            for user_id in admin_users:
                try:
                    await bot.send_message(
                        chat_id=user_id, text=message, parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send Telegram alert to user {user_id}: {e}"
                    )

        except ImportError:
            logger.error("Telegram library not available for alerts")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def _format_telegram_alert(self, alert: Alert) -> str:
        """Format alert message for Telegram."""
        severity_emoji = {
            AlertSeverity.LOW: "🟡",
            AlertSeverity.MEDIUM: "🟠",
            AlertSeverity.HIGH: "🔴",
            AlertSeverity.CRITICAL: "🚨",
        }

        emoji = severity_emoji.get(alert.severity, "⚠️")

        message = f"{emoji} *RAGBot Alert*\n\n"
        message += f"*Component:* {alert.component}\n"
        message += f"*Severity:* {alert.severity.value.upper()}\n"
        message += f"*Status:* {alert.status.value}\n"
        message += f"*Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"*Message:* {alert.message}\n"

        if alert.metadata.get("error_count", 0) > 0:
            message += f"*Error Count:* {alert.metadata['error_count']}\n"

        if alert.metadata.get("response_time"):
            message += f"*Response Time:* {alert.metadata['response_time']:.2f}s\n"

        return message

    async def _send_email_notification(self, alert: Alert) -> None:
        """Send alert notification via email."""
        # Placeholder for email notification
        # In a real implementation, you would integrate with an email service
        logger.info(f"Email alert notification (not implemented): {alert.id}")

    async def _send_webhook_notification(self, alert: Alert) -> None:
        """Send alert notification via webhook."""
        # Placeholder for webhook notification
        # In a real implementation, you would send HTTP POST to configured webhook URL
        logger.info(f"Webhook alert notification (not implemented): {alert.id}")

    async def _check_resolved_alerts(
        self, components: Dict[str, ComponentHealth]
    ) -> None:
        """Check if any active alerts should be resolved."""
        resolved_alerts = []

        for alert_key, alert in list(self.active_alerts.items()):
            component_name = alert.component

            if component_name in components:
                current_health = components[component_name]

                # Check if component is now healthy
                if current_health.status == HealthStatus.HEALTHY:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    resolved_alerts.append(alert)

                    # Remove from active alerts
                    del self.active_alerts[alert_key]

                    logger.log_structured(
                        "info",
                        "alert_resolved",
                        alert_id=alert.id,
                        component=alert.component,
                        duration_minutes=(
                            alert.resolved_at - alert.timestamp
                        ).total_seconds()
                        / 60,
                    )

        # Send resolution notifications
        for alert in resolved_alerts:
            await self._send_resolution_notifications(alert)

    async def _send_resolution_notifications(self, alert: Alert) -> None:
        """Send alert resolution notifications."""
        try:
            from telegram import Bot

            bot = Bot(token=settings.bot_token)
            admin_users = settings.allow_users_list[:1]

            if admin_users:
                message = "✅ *Alert Resolved*\n\n"
                message += f"*Component:* {alert.component}\n"
                message += f"*Severity:* {alert.severity.value.upper()}\n"
                message += (
                    f"*Resolved:* {alert.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )

                duration = alert.resolved_at - alert.timestamp
                message += f"*Duration:* {duration.total_seconds() / 60:.1f} minutes"

                for user_id in admin_users:
                    try:
                        await bot.send_message(
                            chat_id=user_id, text=message, parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send resolution notification to user {user_id}: {e}"
                        )

        except Exception as e:
            logger.error(f"Failed to send resolution notification: {e}")

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get list of active alerts."""
        return [alert.to_dict() for alert in self.active_alerts.values()]

    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_alerts = [
            alert for alert in self.alert_history if alert.timestamp >= cutoff_time
        ]

        return [alert.to_dict() for alert in recent_alerts]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        recent_alerts = [a for a in self.alert_history if a.timestamp >= last_24h]
        weekly_alerts = [a for a in self.alert_history if a.timestamp >= last_7d]

        return {
            "active_alerts": len(self.active_alerts),
            "alerts_last_24h": len(recent_alerts),
            "alerts_last_7d": len(weekly_alerts),
            "total_alerts": len(self.alert_history),
            "alerts_by_severity_24h": {
                severity.value: len(
                    [a for a in recent_alerts if a.severity == severity]
                )
                for severity in AlertSeverity
            },
            "alerts_by_component_24h": {
                comp: len([a for a in recent_alerts if a.component == comp])
                for comp in set(a.component for a in recent_alerts)
            },
        }


# Global alert manager instance
alert_manager = AlertManager()
