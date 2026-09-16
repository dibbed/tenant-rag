"""
Enhanced metrics system with comprehensive monitoring capabilities.

This module extends the base metrics system with advanced features like
custom metrics, alerting integration, and detailed performance tracking.
"""

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from ragbot.outputs.alerting import alert_manager
from ragbot.outputs.analytics import analytics_collector
from ragbot.outputs.health import health_checker
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager


@dataclass
class CustomMetric:
    """Custom metric definition."""
    name: str
    description: str
    metric_type: str
    labels: Dict[str, str]
    value_extractor: Optional[Callable] = None


class EnhancedMetricsManager:
    """
    Enhanced metrics manager with advanced monitoring capabilities.
    
    Extends the base metrics system with custom metrics, alerting integration,
    performance profiling, and comprehensive system monitoring.
    """
    
    def __init__(self) -> None:
        """Initialize enhanced metrics manager."""
        self.base_metrics = metrics_manager
        self.custom_metrics: Dict[str, CustomMetric] = {}
        self.performance_profiles: Dict[str, List[float]] = {}
        self.metric_thresholds: Dict[str, Dict[str, float]] = {}
        
        # Integration with other systems
        self.analytics = analytics_collector
        self.health_checker = health_checker
        self.alert_manager = alert_manager
        
        self._setup_custom_metrics()
        self._setup_metric_thresholds()
        
        logger.info("Enhanced metrics manager initialized")
    
    def _setup_custom_metrics(self) -> None:
        """Setup custom metrics for detailed monitoring."""
        custom_metrics = [
            CustomMetric(
                name="user_engagement_score",
                description="User engagement score based on activity",
                metric_type="gauge",
                labels={"user_type": "active"}
            ),
            CustomMetric(
                name="document_quality_score",
                description="Document processing quality score",
                metric_type="gauge",
                labels={"document_type": "pdf"}
            ),
            CustomMetric(
                name="query_satisfaction_score",
                description="Query satisfaction based on user feedback",
                metric_type="gauge",
                labels={"language": "en"}
            ),
            CustomMetric(
                name="system_efficiency_score",
                description="Overall system efficiency score",
                metric_type="gauge",
                labels={"component": "overall"}
            ),
            CustomMetric(
                name="resource_utilization_score",
                description="Resource utilization efficiency",
                metric_type="gauge",
                labels={"resource": "memory"}
            ),
        ]
        
        for metric in custom_metrics:
            self.custom_metrics[metric.name] = metric
    
    def _setup_metric_thresholds(self) -> None:
        """Setup metric thresholds for alerting."""
        self.metric_thresholds = {
            "response_time": {"warning": 2.0, "critical": 5.0},
            "error_rate": {"warning": 5.0, "critical": 10.0},
            "memory_usage": {"warning": 80.0, "critical": 90.0},
            "cpu_usage": {"warning": 70.0, "critical": 85.0},
            "disk_usage": {"warning": 80.0, "critical": 90.0},
            "cache_hit_rate": {"warning": 70.0, "critical": 50.0},
            "active_users": {"warning": 100, "critical": 200},
            "queue_size": {"warning": 50, "critical": 100},
        }
    
    async def record_comprehensive_metrics(
        self,
        operation: str,
        duration: float,
        status: str = "success",
        user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record comprehensive metrics for an operation."""
        metadata = metadata or {}
        
        # Record in base metrics system
        self.base_metrics.record_query_processing(
            language=metadata.get("language", "unknown"),
            status=status,
            total_duration=duration
        )
        
        # Record in analytics system
        self.analytics.record_request_metrics(
            duration=duration,
            status=status,
            endpoint=operation,
            user_id=user_id
        )
        
        # Update performance profiles
        if operation not in self.performance_profiles:
            self.performance_profiles[operation] = []
        
        self.performance_profiles[operation].append(duration)
        
        # Keep only last 1000 measurements per operation
        if len(self.performance_profiles[operation]) > 1000:
            self.performance_profiles[operation] = self.performance_profiles[operation][-1000:]
        
        # Check thresholds and trigger alerts if needed
        await self._check_metric_thresholds(operation, duration, metadata)
        
        logger.log_performance(
            operation,
            duration,
            status=status,
            user_id=user_id,
            **metadata
        )
    
    async def _check_metric_thresholds(
        self,
        operation: str,
        value: float,
        metadata: Dict[str, Any]
    ) -> None:
        """Check if metric values exceed thresholds."""
        threshold_key = operation.lower().replace(" ", "_")
        
        if threshold_key in self.metric_thresholds:
            thresholds = self.metric_thresholds[threshold_key]
            
            if value > thresholds.get("critical", float('inf')):
                logger.log_structured(
                    "critical",
                    "metric_threshold_exceeded",
                    operation=operation,
                    value=value,
                    threshold=thresholds["critical"],
                    level="critical",
                    **metadata
                )
            elif value > thresholds.get("warning", float('inf')):
                logger.log_structured(
                    "warning",
                    "metric_threshold_exceeded",
                    operation=operation,
                    value=value,
                    threshold=thresholds["warning"],
                    level="warning",
                    **metadata
                )
    
    def calculate_custom_metrics(self) -> Dict[str, float]:
        """Calculate custom metrics based on collected data."""
        custom_values = {}
        
        # User engagement score
        user_analytics = self.analytics.get_user_analytics(hours=24)
        if "avg_activities_per_user" in user_analytics:
            engagement_score = min(user_analytics["avg_activities_per_user"] * 10, 100)
            custom_values["user_engagement_score"] = engagement_score
        
        # System efficiency score
        health_summary = self.health_checker.get_health_summary()
        if health_summary["status"] == "healthy":
            efficiency_score = 100
        elif health_summary["status"] == "degraded":
            efficiency_score = 70
        else:
            efficiency_score = 30
        
        custom_values["system_efficiency_score"] = efficiency_score
        
        # Resource utilization score
        system_metrics = self.analytics.get_system_health_metrics()
        if "memory_usage" in system_metrics:
            memory_usage = system_metrics["memory_usage"]["value"]
            # Optimal usage is around 60-70%, score decreases as it goes higher or lower
            if 60 <= memory_usage <= 70:
                utilization_score = 100
            elif 50 <= memory_usage < 60 or 70 < memory_usage <= 80:
                utilization_score = 80
            elif 40 <= memory_usage < 50 or 80 < memory_usage <= 90:
                utilization_score = 60
            else:
                utilization_score = 30
            
            custom_values["resource_utilization_score"] = utilization_score
        
        return custom_values
    
    @asynccontextmanager
    async def measure_operation(self, operation_name: str, **metadata):
        """Context manager for measuring operation performance."""
        start_time = time.time()
        status = "success"
        
        try:
            yield
        except Exception as e:
            status = "error"
            logger.error(f"Operation {operation_name} failed: {e}")
            raise
        finally:
            duration = time.time() - start_time
            await self.record_comprehensive_metrics(
                operation=operation_name,
                duration=duration,
                status=status,
                metadata=metadata
            )
    
    def get_performance_profile(self, operation: str) -> Dict[str, Any]:
        """Get performance profile for an operation."""
        if operation not in self.performance_profiles:
            return {"error": f"No performance data for operation: {operation}"}
        
        measurements = self.performance_profiles[operation]
        
        if not measurements:
            return {"error": "No measurements available"}
        
        return {
            "operation": operation,
            "total_measurements": len(measurements),
            "avg_duration": sum(measurements) / len(measurements),
            "min_duration": min(measurements),
            "max_duration": max(measurements),
            "p50_duration": sorted(measurements)[len(measurements) // 2],
            "p95_duration": sorted(measurements)[int(len(measurements) * 0.95)],
            "p99_duration": sorted(measurements)[int(len(measurements) * 0.99)],
            "recent_avg": sum(measurements[-100:]) / min(100, len(measurements)),
            "trend": self._calculate_performance_trend(measurements)
        }
    
    def _calculate_performance_trend(self, measurements: List[float]) -> str:
        """Calculate performance trend from measurements."""
        if len(measurements) < 10:
            return "insufficient_data"
        
        # Compare recent measurements with earlier ones
        recent_avg = sum(measurements[-10:]) / 10
        earlier_avg = sum(measurements[:10]) / 10
        
        if recent_avg > earlier_avg * 1.2:
            return "degrading"
        elif recent_avg < earlier_avg * 0.8:
            return "improving"
        else:
            return "stable"
    
    def get_comprehensive_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive metrics dashboard."""
        # Get data from all systems
        performance_summary = self.analytics.get_performance_summary(hours=24)
        user_analytics = self.analytics.get_user_analytics(hours=24)
        health_summary = self.health_checker.get_health_summary()
        custom_metrics = self.calculate_custom_metrics()
        
        # Get top operations by performance
        top_operations = []
        for operation, measurements in self.performance_profiles.items():
            if measurements:
                profile = self.get_performance_profile(operation)
                top_operations.append({
                    "operation": operation,
                    "avg_duration": profile["avg_duration"],
                    "total_calls": profile["total_measurements"],
                    "trend": profile["trend"]
                })
        
        top_operations.sort(key=lambda x: x["avg_duration"], reverse=True)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overview": {
                "system_status": health_summary["status"],
                "total_requests_24h": performance_summary["metrics"].get("total_requests", 0),
                "avg_response_time": performance_summary["metrics"].get("avg_response_time", 0),
                "error_rate": performance_summary["metrics"].get("error_rate", 0),
                "active_users": performance_summary["metrics"].get("active_users", 0),
            },
            "performance": {
                "summary": performance_summary,
                "top_slow_operations": top_operations[:5],
                "performance_trends": {
                    op: self._calculate_performance_trend(measurements)
                    for op, measurements in self.performance_profiles.items()
                    if len(measurements) >= 10
                }
            },
            "users": user_analytics,
            "health": health_summary,
            "custom_metrics": custom_metrics,
            "alerts": {
                "active_alerts": len(self.alert_manager.get_active_alerts()),
                "alerts_24h": len(self.alert_manager.get_alert_history(hours=24))
            }
        }
    
    async def generate_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Collect data from all systems
        dashboard = self.get_comprehensive_dashboard()
        
        # Add report-specific analysis
        report = {
            "report_period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_hours": hours
            },
            "executive_summary": self._generate_executive_summary(dashboard),
            "detailed_metrics": dashboard,
            "recommendations": self._generate_performance_recommendations(dashboard),
            "action_items": self._generate_action_items(dashboard)
        }
        
        return report
    
    def _generate_executive_summary(self, dashboard: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary from dashboard data."""
        overview = dashboard["overview"]
        
        # Calculate health score
        health_score = 100
        if overview["system_status"] == "degraded":
            health_score = 70
        elif overview["system_status"] == "unhealthy":
            health_score = 30
        
        # Calculate performance score
        avg_response_time = overview.get("avg_response_time", 0)
        if avg_response_time < 1.0:
            performance_score = 100
        elif avg_response_time < 2.0:
            performance_score = 80
        elif avg_response_time < 5.0:
            performance_score = 60
        else:
            performance_score = 30
        
        # Calculate reliability score
        error_rate = overview.get("error_rate", 0)
        if error_rate < 1.0:
            reliability_score = 100
        elif error_rate < 5.0:
            reliability_score = 80
        elif error_rate < 10.0:
            reliability_score = 60
        else:
            reliability_score = 30
        
        overall_score = (health_score + performance_score + reliability_score) / 3
        
        return {
            "overall_score": round(overall_score, 1),
            "health_score": health_score,
            "performance_score": performance_score,
            "reliability_score": reliability_score,
            "key_metrics": {
                "total_requests": overview.get("total_requests_24h", 0),
                "avg_response_time": round(avg_response_time, 3),
                "error_rate": round(error_rate, 2),
                "active_users": overview.get("active_users", 0)
            },
            "status": "excellent" if overall_score >= 90 else "good" if overall_score >= 70 else "needs_attention"
        }
    
    def _generate_performance_recommendations(self, dashboard: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        overview = dashboard["overview"]
        performance = dashboard["performance"]
        
        # Response time recommendations
        avg_response_time = overview.get("avg_response_time", 0)
        if avg_response_time > 2.0:
            recommendations.append(f"Average response time is {avg_response_time:.2f}s. Consider optimizing slow operations.")
        
        # Error rate recommendations
        error_rate = overview.get("error_rate", 0)
        if error_rate > 5.0:
            recommendations.append(f"Error rate is {error_rate:.1f}%. Investigate and fix recurring errors.")
        
        # Slow operations recommendations
        slow_ops = performance.get("top_slow_operations", [])
        if slow_ops and slow_ops[0]["avg_duration"] > 3.0:
            recommendations.append(f"Operation '{slow_ops[0]['operation']}' is slow ({slow_ops[0]['avg_duration']:.2f}s avg). Consider optimization.")
        
        # Health recommendations
        if dashboard["health"]["status"] != "healthy":
            recommendations.append("System health is not optimal. Check component health and resolve issues.")
        
        if not recommendations:
            recommendations.append("System performance looks good. Continue monitoring.")
        
        return recommendations
    
    def _generate_action_items(self, dashboard: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable items based on metrics."""
        action_items = []
        
        # High priority items
        if dashboard["overview"]["error_rate"] > 10:
            action_items.append({
                "priority": "high",
                "title": "Critical Error Rate",
                "description": f"Error rate is {dashboard['overview']['error_rate']:.1f}%, exceeding critical threshold",
                "action": "Investigate error patterns and implement fixes immediately"
            })
        
        if dashboard["health"]["status"] == "unhealthy":
            action_items.append({
                "priority": "high",
                "title": "System Health Critical",
                "description": "System health is critical",
                "action": "Check component health and resolve critical issues"
            })
        
        # Medium priority items
        if dashboard["overview"]["avg_response_time"] > 3.0:
            action_items.append({
                "priority": "medium",
                "title": "Slow Response Times",
                "description": f"Average response time is {dashboard['overview']['avg_response_time']:.2f}s",
                "action": "Profile and optimize slow operations"
            })
        
        # Low priority items
        if dashboard["alerts"]["active_alerts"] > 0:
            action_items.append({
                "priority": "low",
                "title": "Active Alerts",
                "description": f"{dashboard['alerts']['active_alerts']} active alerts",
                "action": "Review and resolve active alerts"
            })
        
        return action_items


# Global enhanced metrics manager instance
enhanced_metrics = EnhancedMetricsManager()
