"""
Performance and usage analytics for RAGBot.

This module provides comprehensive analytics collection, aggregation,
and reporting for system performance and user behavior analysis.
"""

import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from ragbot.outputs.logger import logger


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "labels": self.labels
        }


@dataclass
class MetricSeries:
    """Time series of metric points."""
    name: str
    metric_type: MetricType
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    description: str = ""
    
    def add_point(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Add a new metric point."""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            labels=labels or {}
        )
        self.points.append(point)
    
    def get_recent_points(self, minutes: int = 60) -> List[MetricPoint]:
        """Get metric points from the last N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [p for p in self.points if p.timestamp >= cutoff_time]
    
    def get_aggregated_value(self, minutes: int = 60, aggregation: str = "avg") -> Optional[float]:
        """Get aggregated value for the specified time period."""
        recent_points = self.get_recent_points(minutes)
        
        if not recent_points:
            return None
        
        values = [p.value for p in recent_points]
        
        if aggregation == "avg":
            return sum(values) / len(values)
        elif aggregation == "sum":
            return sum(values)
        elif aggregation == "min":
            return min(values)
        elif aggregation == "max":
            return max(values)
        elif aggregation == "count":
            return len(values)
        else:
            return None


class AnalyticsCollector:
    """
    Advanced analytics collector for performance and usage metrics.
    
    Collects detailed metrics about system performance, user behavior,
    and operational statistics for analysis and optimization.
    """
    
    def __init__(self) -> None:
        """Initialize analytics collector."""
        self.metrics: Dict[str, MetricSeries] = {}
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.performance_baselines: Dict[str, float] = {}
        
        # Initialize core metrics
        self._initialize_core_metrics()
        
        logger.info("Analytics collector initialized")
    
    def _initialize_core_metrics(self) -> None:
        """Initialize core metric series."""
        core_metrics = [
            # Performance metrics
            ("request_duration", MetricType.HISTOGRAM, "Request processing duration in seconds"),
            ("request_count", MetricType.COUNTER, "Total number of requests processed"),
            ("error_rate", MetricType.GAUGE, "Error rate percentage"),
            ("throughput", MetricType.GAUGE, "Requests per second"),
            
            # User metrics
            ("active_users", MetricType.GAUGE, "Number of active users"),
            ("user_sessions", MetricType.COUNTER, "Total user sessions"),
            ("user_retention", MetricType.GAUGE, "User retention rate"),
            
            # Document metrics
            ("documents_processed", MetricType.COUNTER, "Documents processed"),
            ("document_processing_time", MetricType.HISTOGRAM, "Document processing time"),
            ("document_size", MetricType.HISTOGRAM, "Document size in bytes"),
            ("chunks_created", MetricType.COUNTER, "Text chunks created"),
            
            # Query metrics
            ("queries_processed", MetricType.COUNTER, "Queries processed"),
            ("query_response_time", MetricType.HISTOGRAM, "Query response time"),
            ("query_accuracy", MetricType.GAUGE, "Query accuracy score"),
            ("retrieval_precision", MetricType.GAUGE, "Retrieval precision"),
            
            # System metrics
            ("memory_usage", MetricType.GAUGE, "Memory usage percentage"),
            ("cpu_usage", MetricType.GAUGE, "CPU usage percentage"),
            ("disk_usage", MetricType.GAUGE, "Disk usage percentage"),
            ("cache_hit_rate", MetricType.GAUGE, "Cache hit rate percentage"),
            
            # Business metrics
            ("user_satisfaction", MetricType.GAUGE, "User satisfaction score"),
            ("feature_usage", MetricType.COUNTER, "Feature usage count"),
            ("conversion_rate", MetricType.GAUGE, "Conversion rate percentage"),
        ]
        
        for name, metric_type, description in core_metrics:
            self.metrics[name] = MetricSeries(
                name=name,
                metric_type=metric_type,
                description=description
            )
    
    def record_request_metrics(
        self,
        duration: float,
        status: str = "success",
        endpoint: str = "unknown",
        user_id: Optional[int] = None
    ) -> None:
        """Record request processing metrics."""
        # Record duration
        self.metrics["request_duration"].add_point(
            duration,
            {"status": status, "endpoint": endpoint}
        )
        
        # Increment request count
        self.metrics["request_count"].add_point(
            1,
            {"status": status, "endpoint": endpoint}
        )
        
        # Update throughput (requests per second)
        self._update_throughput()
        
        # Update error rate
        self._update_error_rate()
        
        # Track user session if provided
        if user_id:
            self._update_user_session(user_id, "request", {"endpoint": endpoint, "status": status})
        
        logger.log_performance(
            "request_processed",
            duration,
            status=status,
            endpoint=endpoint,
            user_id=user_id
        )
    
    def record_document_processing(
        self,
        processing_time: float,
        document_size: int,
        chunks_created: int,
        document_type: str,
        status: str = "success"
    ) -> None:
        """Record document processing metrics."""
        labels = {"document_type": document_type, "status": status}
        
        self.metrics["document_processing_time"].add_point(processing_time, labels)
        self.metrics["document_size"].add_point(document_size, labels)
        self.metrics["chunks_created"].add_point(chunks_created, labels)
        self.metrics["documents_processed"].add_point(1, labels)
        
        logger.log_structured(
            "info",
            "document_processing_metrics",
            processing_time=processing_time,
            document_size=document_size,
            chunks_created=chunks_created,
            document_type=document_type,
            status=status
        )
    
    def record_query_metrics(
        self,
        response_time: float,
        retrieval_time: float,
        llm_time: float,
        chunks_retrieved: int,
        query_length: int,
        response_length: int,
        language: str = "unknown",
        user_id: Optional[int] = None
    ) -> None:
        """Record query processing metrics."""
        labels = {"language": language}
        
        self.metrics["query_response_time"].add_point(response_time, labels)
        self.metrics["queries_processed"].add_point(1, labels)
        
        # Calculate and record retrieval precision
        precision = min(chunks_retrieved / max(1, query_length * 0.1), 1.0)
        self.metrics["retrieval_precision"].add_point(precision, labels)
        
        # Track user session
        if user_id:
            self._update_user_session(user_id, "query", {
                "language": language,
                "response_time": response_time,
                "chunks_retrieved": chunks_retrieved
            })
        
        logger.log_performance(
            "query_processed",
            response_time,
            retrieval_time=retrieval_time,
            llm_time=llm_time,
            chunks_retrieved=chunks_retrieved,
            language=language,
            user_id=user_id
        )
    
    def record_system_metrics(
        self,
        memory_usage: float,
        cpu_usage: float,
        disk_usage: float,
        cache_hit_rate: float
    ) -> None:
        """Record system performance metrics."""
        self.metrics["memory_usage"].add_point(memory_usage)
        self.metrics["cpu_usage"].add_point(cpu_usage)
        self.metrics["disk_usage"].add_point(disk_usage)
        self.metrics["cache_hit_rate"].add_point(cache_hit_rate)
        
        logger.log_structured(
            "debug",
            "system_metrics",
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            disk_usage=disk_usage,
            cache_hit_rate=cache_hit_rate
        )
    
    def record_user_activity(
        self,
        user_id: int,
        activity_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record user activity for behavior analysis."""
        self._update_user_session(user_id, activity_type, metadata or {})
        
        # Update active users count
        self._update_active_users()
        
        logger.log_user_action(user_id, activity_type, **(metadata or {}))
    
    def _update_user_session(
        self,
        user_id: int,
        activity_type: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Update user session data."""
        now = datetime.now()
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "start_time": now,
                "last_activity": now,
                "activity_count": 0,
                "activities": []
            }
            
            # Increment session counter
            self.metrics["user_sessions"].add_point(1, {"user_id": str(user_id)})
        
        session = self.user_sessions[user_id]
        session["last_activity"] = now
        session["activity_count"] += 1
        session["activities"].append({
            "type": activity_type,
            "timestamp": now,
            "metadata": metadata
        })
        
        # Keep only last 100 activities per user
        if len(session["activities"]) > 100:
            session["activities"] = session["activities"][-100:]
    
    def _update_throughput(self) -> None:
        """Update throughput metric (requests per second)."""
        recent_requests = self.metrics["request_count"].get_recent_points(1)  # Last minute
        if recent_requests:
            throughput = len(recent_requests) / 60.0  # Requests per second
            self.metrics["throughput"].add_point(throughput)
    
    def _update_error_rate(self) -> None:
        """Update error rate metric."""
        recent_requests = self.metrics["request_count"].get_recent_points(5)  # Last 5 minutes
        
        if recent_requests:
            error_requests = [p for p in recent_requests if p.labels.get("status") == "error"]
            error_rate = (len(error_requests) / len(recent_requests)) * 100
            self.metrics["error_rate"].add_point(error_rate)
    
    def _update_active_users(self) -> None:
        """Update active users count."""
        now = datetime.now()
        cutoff_time = now - timedelta(hours=1)  # Active in last hour
        
        active_users = [
            user_id for user_id, session in self.user_sessions.items()
            if session["last_activity"] >= cutoff_time
        ]
        
        self.metrics["active_users"].add_point(len(active_users))
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the specified time period."""
        summary = {
            "time_period_hours": hours,
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        # Key performance indicators
        kpis = [
            ("avg_response_time", "query_response_time", "avg"),
            ("total_requests", "request_count", "sum"),
            ("error_rate", "error_rate", "avg"),
            ("throughput", "throughput", "avg"),
            ("active_users", "active_users", "max"),
            ("documents_processed", "documents_processed", "sum"),
            ("cache_hit_rate", "cache_hit_rate", "avg"),
            ("memory_usage", "memory_usage", "avg"),
        ]
        
        for kpi_name, metric_name, aggregation in kpis:
            if metric_name in self.metrics:
                value = self.metrics[metric_name].get_aggregated_value(
                    minutes=hours * 60,
                    aggregation=aggregation
                )
                summary["metrics"][kpi_name] = value
        
        return summary
    
    def get_user_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get user behavior analytics."""
        now = datetime.now()
        cutoff_time = now - timedelta(hours=hours)
        
        # Filter recent sessions
        recent_sessions = {
            user_id: session for user_id, session in self.user_sessions.items()
            if session["last_activity"] >= cutoff_time
        }
        
        if not recent_sessions:
            return {"message": "No user activity in the specified time period"}
        
        # Calculate analytics
        total_users = len(recent_sessions)
        total_activities = sum(session["activity_count"] for session in recent_sessions.values())
        avg_activities_per_user = total_activities / total_users if total_users > 0 else 0
        
        # Activity type distribution
        activity_types = defaultdict(int)
        for session in recent_sessions.values():
            for activity in session["activities"]:
                if activity["timestamp"] >= cutoff_time:
                    activity_types[activity["type"]] += 1
        
        # Session duration analysis
        session_durations = []
        for session in recent_sessions.values():
            duration = (session["last_activity"] - session["start_time"]).total_seconds() / 60
            session_durations.append(duration)
        
        avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
        
        return {
            "time_period_hours": hours,
            "total_users": total_users,
            "total_activities": total_activities,
            "avg_activities_per_user": round(avg_activities_per_user, 2),
            "avg_session_duration_minutes": round(avg_session_duration, 2),
            "activity_distribution": dict(activity_types),
            "top_activities": sorted(activity_types.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def get_system_health_metrics(self) -> Dict[str, Any]:
        """Get current system health metrics."""
        health_metrics = {}
        
        # Get latest values for key health indicators
        health_indicators = [
            "memory_usage",
            "cpu_usage", 
            "disk_usage",
            "cache_hit_rate",
            "error_rate",
            "throughput",
            "active_users"
        ]
        
        for indicator in health_indicators:
            if indicator in self.metrics and self.metrics[indicator].points:
                latest_point = self.metrics[indicator].points[-1]
                health_metrics[indicator] = {
                    "value": latest_point.value,
                    "timestamp": latest_point.timestamp.isoformat(),
                    "status": self._get_metric_status(indicator, latest_point.value)
                }
        
        return health_metrics
    
    def _get_metric_status(self, metric_name: str, value: float) -> str:
        """Get status (healthy/warning/critical) for a metric value."""
        thresholds = {
            "memory_usage": {"warning": 80, "critical": 90},
            "cpu_usage": {"warning": 70, "critical": 85},
            "disk_usage": {"warning": 80, "critical": 90},
            "error_rate": {"warning": 5, "critical": 10},
            "cache_hit_rate": {"warning": 70, "critical": 50},  # Lower is worse for cache hit rate
        }
        
        if metric_name not in thresholds:
            return "healthy"
        
        threshold = thresholds[metric_name]
        
        if metric_name == "cache_hit_rate":
            # For cache hit rate, lower values are worse
            if value < threshold["critical"]:
                return "critical"
            elif value < threshold["warning"]:
                return "warning"
            else:
                return "healthy"
        else:
            # For other metrics, higher values are worse
            if value > threshold["critical"]:
                return "critical"
            elif value > threshold["warning"]:
                return "warning"
            else:
                return "healthy"
    
    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format."""
        if format == "json":
            return self._export_json()
        elif format == "prometheus":
            return self._export_prometheus()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self) -> str:
        """Export metrics as JSON."""
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for name, series in self.metrics.items():
            export_data["metrics"][name] = {
                "type": series.metric_type.value,
                "description": series.description,
                "points": [point.to_dict() for point in list(series.points)[-100:]]  # Last 100 points
            }
        
        return json.dumps(export_data, indent=2)
    
    def _export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for name, series in self.metrics.items():
            if not series.points:
                continue
            
            # Add help and type comments
            lines.append(f"# HELP ragbot_{name} {series.description}")
            lines.append(f"# TYPE ragbot_{name} {series.metric_type.value}")
            
            # Add metric points
            for point in list(series.points)[-10:]:  # Last 10 points
                labels_str = ""
                if point.labels:
                    label_pairs = [f'{k}="{v}"' for k, v in point.labels.items()]
                    labels_str = "{" + ",".join(label_pairs) + "}"
                
                timestamp_ms = int(point.timestamp.timestamp() * 1000)
                lines.append(f"ragbot_{name}{labels_str} {point.value} {timestamp_ms}")
            
            lines.append("")  # Empty line between metrics
        
        return "\n".join(lines)


# Global analytics collector instance
analytics_collector = AnalyticsCollector()
