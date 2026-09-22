"""
Logging Analytics Plugin

This plugin provides comprehensive logging and analytics for RAG Bot operations
including user interaction tracking, performance metrics, and custom reporting.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from ragbot.plugins.base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginType,
    PluginStatus,
)
from ragbot.outputs.logger import logger


class LoggingAnalyticsPlugin(BasePlugin):
    """
    Plugin for comprehensive logging and analytics

    Tracks user interactions, query patterns, and system performance
    to provide insights and monitoring capabilities.
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)

        # Default configuration
        self.default_config = {
            "track_queries": True,
            "track_responses": True,
            "track_performance": True,
            "log_user_behavior": True,
            "retention_days": 30,
            "alert_thresholds": {"slow_query_ms": 5000, "error_rate_percent": 10.0},
        }

        # Merge configuration
        self.config.update(self.default_config)

        # Analytics data storage
        self.query_logs: List[Dict[str, Any]] = []
        self.user_interactions: List[Dict[str, Any]] = []
        self.performance_metrics: List[Dict[str, Any]] = []

        # Statistics tracking
        self.stats = {
            "total_queries": 0,
            "avg_response_time": 0.0,
            "error_count": 0,
            "unique_users": set(),
        }

    @property
    def plugin_name(self) -> str:
        return "Logging Analytics Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return (
            "Comprehensive logging and analytics plugin for tracking RAG Bot operations"
        )

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.ANALYTICS_PLUGIN

    @property
    def plugin_author(self) -> str:
        return "RAG Bot Analytics Team"

    async def initialize(self, context: PluginContext) -> None:
        """
        Initialize the analytics plugin

        Args:
            context: Plugin initialization context

        Returns:
            True if initialization successful
        """
        try:
            self.set_status(PluginStatus.ACTIVE)

            # Register comprehensive hooks
            self.register_hook("on_user_interaction", self.track_user_interaction)
            self.register_hook("pre_query", self.log_query_start)
            self.register_hook("post_query", self.log_query_result)
            self.register_hook("pre_response", self.log_response_generation)
            self.register_hook("post_response", self.log_response_complete)
            self.register_hook("on_error", self.log_error_event)

            return True

        except Exception as e:
            logger.error(f"Analytics plugin initialization failed: {e}")
            return False

    async def execute(self, context: PluginContext) -> PluginResult:
        """
        Execute analytics analysis

        Args:
            context: Analytics execution context

        Returns:
            Analysis results
        """
        try:
            command = context.data.get("command", "stats") if context.data else "stats"

            if command == "stats":
                return await self._generate_stats()
            elif command == "report":
                return await self._generate_report()
            elif command == "cleanup":
                return await self._cleanup_old_data()
            else:
                return PluginResult(
                    success=False, error_message=f"Unknown analytics command: {command}"
                )

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Analytics execution error: {e}"
            )

    async def cleanup(self) -> bool:
        """
        Cleanup plugin resources

        Returns:
            True if cleanup successful
        """
        try:
            # Backup analytics data before cleanup
            await self._save_analytics_data()

            self.set_status(PluginStatus.INACTIVE)
            return True

        except Exception as e:
            logger.error(f"Analytics plugin cleanup failed: {e}")
            return False

    async def track_user_interaction(self, context: PluginContext) -> PluginResult:
        """
        Track user interactions

        Args:
            context: Interaction context

        Returns:
            Tracking result
        """
        try:
            if not self.get_config("log_user_behavior", True):
                return PluginResult(success=True)

            timestamp = datetime.now()
            user_id = context.user_id

            # Record user interaction
            interaction = {
                "user_id": user_id,
                "action": context.data.get("action", "unknown"),
                "timestamp": timestamp,
                "metadata": context.metadata or {},
            }

            self.user_interactions.append(interaction)
            self.stats["unique_users"].add(user_id)

            return PluginResult(success=True, data=interaction)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"User interaction tracking error: {e}"
            )

    async def log_query_start(self, context: PluginContext) -> PluginResult:
        """
        Log query start event

        Args:
            context: Query context

        Returns:
            Logging result
        """
        try:
            if not self.get_config("track_queries", True):
                return PluginResult(success=True)

            timestamp = time.time()

            # Store query start info for performance tracking
            context.metadata = context.metadata or {}
            context.metadata["query_start_time"] = timestamp

            return PluginResult(success=True, data={"start_time": timestamp})

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Query start logging error: {e}"
            )

    async def log_query_result(self, context: PluginContext) -> PluginResult:
        """
        Log query completion

        Args:
            context: Query context

        Returns:
            Logging result
        """
        try:
            if not self.get_config("track_queries", True):
                return PluginResult(success=True)

            timestamp = datetime.now()

            # Calculate response time
            query_start = (
                context.metadata.get("query_start_time") if context.metadata else None
            )
            response_time = time.time() - query_start if query_start else None

            # Create query log entry
            query_log = {
                "timestamp": timestamp,
                "query": context.data.get("query", "") if context.data else "",
                "response_time": response_time,
                "confidence": context.data.get("confidence", 0.0)
                if context.data
                else 0.0,
                "source_count": context.data.get("source_count", 0)
                if context.data
                else 0,
            }

            self.query_logs.append(query_log)
            self.stats["total_queries"] += 1

            # Update performance metrics
            if response_time and self.get_config("track_performance", True):
                self._update_performance_metrics(response_time, query_log)

            return PluginResult(success=True, data=query_log)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Query result logging error: {e}"
            )

    async def log_response_generation(self, context: PluginContext) -> PluginResult:
        """
        Log response generation start

        Args:
            context: Response context

        Returns:
            Logging result
        """
        try:
            timestamp = time.time()

            context.metadata = context.metadata or {}
            context.metadata["response_start_time"] = timestamp

            return PluginResult(success=True, data={"response_start": timestamp})

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Response generation logging error: {e}"
            )

    async def log_response_complete(self, context: PluginContext) -> PluginResult:
        """
        Log response completion

        Args:
            context: Response context

        Returns:
            Logging result
        """
        try:
            timestamp = time.time()

            response_start = (
                context.metadata.get("response_start_time")
                if context.metadata
                else None
            )
            generation_time = timestamp - response_start if response_start else None

            # Log response metrics
            response_data = {
                "completion_time": timestamp,
                "generation_time": generation_time,
                "response_length": len(context.data.get("answer", ""))
                if context.data
                else 0,
            }

            return PluginResult(success=True, data=response_data)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Response completion logging error: {e}"
            )

    async def log_error_event(self, context: PluginContext) -> PluginResult:
        """
        Log error events

        Args:
            context: Error context

        Returns:
            Logging result
        """
        try:
            timestamp = datetime.now()

            error_log = {
                "timestamp": timestamp,
                "error_type": context.data.get("error_type", "unknown")
                if context.data
                else "unknown",
                "error_message": context.data.get("error_message", "")
                if context.data
                else "",
                "context": context.metadata or {},
            }

            self.stats["error_count"] += 1

            return PluginResult(success=True, data=error_log)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Error logging error: {e}"
            )

    async def _generate_stats(self) -> PluginResult:
        """Generate analytics statistics"""
        try:
            stats_summary = {
                "total_queries": self.stats["total_queries"],
                "unique_users": len(self.stats["unique_users"]),
                "error_count": self.stats["error_count"],
                "error_rate": self.stats["error_count"]
                / max(self.stats["total_queries"], 1)
                * 100,
                "avg_response_time": self._calculate_avg_response_time(),
                "data_retention": {
                    "query_logs": len(self.query_logs),
                    "user_interactions": len(self.user_interactions),
                },
            }

            return PluginResult(success=True, data=stats_summary)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Stats generation error: {e}"
            )

    async def _generate_report(self) -> PluginResult:
        """Generate comprehensive analytics report"""
        try:
            report = {
                "timestamp": datetime.now(),
                "summary": await self._generate_stats(),
                "top_queries": self._get_top_queries(),
                "user_activity": self._get_user_activity_summary(),
                "performance_trends": self._get_performance_trends(),
            }

            return PluginResult(success=True, data=report)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Report generation error: {e}"
            )

    async def _cleanup_old_data(self) -> PluginResult:
        """Clean up old analytics data based on retention policy"""
        try:
            retention_days = self.get_config("retention_days", 30)
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            # Clean query logs
            original_count = len(self.query_logs)
            self.query_logs = [
                log for log in self.query_logs if log["timestamp"] > cutoff_date
            ]
            cleaned_queries = original_count - len(self.query_logs)

            # Clean user interactions
            original_interactions = len(self.user_interactions)
            self.user_interactions = [
                interaction
                for interaction in self.user_interactions
                if interaction["timestamp"] > cutoff_date
            ]
            cleaned_interactions = original_interactions - len(self.user_interactions)

            cleanup_result = {
                "cleaned_query_logs": cleaned_queries,
                "cleaned_interactions": cleaned_interactions,
                "retention_days": retention_days,
            }

            return PluginResult(success=True, data=cleanup_result)

        except Exception as e:
            return PluginResult(success=False, error_message=f"Data cleanup error: {e}")

    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time"""
        if not self.query_logs:
            return 0.0

        total_time = sum(
            log.get("response_time", 0.0)
            for log in self.query_logs
            if "response_time" in log
        )
        return total_time / len(self.query_logs)

    def _get_top_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequent queries"""
        if not self.query_logs:
            return []

        query_counts = {}
        for log in self.query_logs:
            query = log.get("query", "")
            if query:
                query_counts[query] = query_counts.get(query, 0) + 1

        sorted_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"query": query, "count": count} for query, count in sorted_queries[:limit]
        ]

    def _get_user_activity_summary(self) -> Dict[str, Any]:
        """Get user activity summary"""
        if not self.user_interactions:
            return {"total_interactions": 0, "unique_users": 0}

        interactions_by_user = {}
        for interaction in self.user_interactions:
            user_id = interaction.get("user_id")
            if user_id:
                interactions_by_user[user_id] = interactions_by_user.get(user_id, 0) + 1

        return {
            "total_interactions": len(self.user_interactions),
            "unique_users": len(interactions_by_user),
            "top_active_users": sorted(
                [(user_id, count) for user_id, count in interactions_by_user.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

    def _get_performance_trends(self) -> Dict[str, Any]:
        """Get performance trends"""
        if not self.query_logs:
            return {"trend_data": []}

        # Group by hour for trend analysis
        hourly_data = {}
        for log in self.query_logs:
            hour = log["timestamp"].hour
            if hour not in hourly_data:
                hourly_data[hour] = []
            hourly_data[hour].append(log.get("response_time", 0.0))

        trends = []
        for hour in sorted(hourly_data.keys()):
            times = hourly_data[hour]
            trends.append(
                {
                    "hour": hour,
                    "avg_response_time": sum(times) / len(times),
                    "query_count": len(times),
                }
            )

        return {"trend_data": trends}

    async def _save_analytics_data(self) -> bool:
        """Save analytics data to persistent storage"""
        try:
            # This would save to a file or database in a real implementation
            logger.info(
                f"Saved analytics data: {len(self.query_logs)} queries, "
                f"{len(self.user_interactions)} interactions"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save analytics data: {e}")
            return False

    def _update_performance_metrics(
        self, response_time: float, query_log: Dict[str, Any]
    ) -> None:
        """Update performance metrics based on query"""
        self.performance_metrics.append(
            {
                "timestamp": datetime.now(),
                "response_time": response_time,
                "confidence": query_log.get("confidence", 0.0),
                "source_count": query_log.get("source_count", 0),
            }
        )
