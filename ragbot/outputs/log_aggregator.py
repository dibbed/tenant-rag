"""
Log aggregation and analysis system for RAGBot.

This module provides log collection, parsing, aggregation, and analysis
capabilities for operational insights and troubleshooting.
"""

import asyncio
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: datetime
    level: LogLevel
    message: str
    logger_name: str
    function: str
    line: int
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "logger": self.logger_name,
            "function": self.function,
            "line": self.line,
            "extra": self.extra_data
        }


@dataclass
class LogPattern:
    """Log pattern for analysis."""
    name: str
    pattern: Pattern[str]
    description: str
    severity: LogLevel
    action_required: bool = False


class LogAggregator:
    """
    Log aggregation and analysis system.
    
    Collects, parses, and analyzes log entries to provide operational
    insights, error tracking, and performance monitoring.
    """
    
    def __init__(self) -> None:
        """Initialize log aggregator."""
        self.log_entries: List[LogEntry] = []
        self.error_patterns: List[LogPattern] = []
        self.performance_patterns: List[LogPattern] = []
        self.security_patterns: List[LogPattern] = []
        
        # Statistics
        self.log_stats = defaultdict(int)
        self.error_counts = Counter()
        self.performance_metrics = defaultdict(list)
        
        self._setup_patterns()
        
        logger.info("Log aggregator initialized")
    
    def _setup_patterns(self) -> None:
        """Setup log analysis patterns."""
        # Error patterns
        self.error_patterns = [
            LogPattern(
                name="api_timeout",
                pattern=re.compile(r"timeout|timed out", re.IGNORECASE),
                description="API timeout errors",
                severity=LogLevel.ERROR,
                action_required=True
            ),
            LogPattern(
                name="connection_error",
                pattern=re.compile(r"connection.*(?:refused|failed|lost)", re.IGNORECASE),
                description="Connection errors",
                severity=LogLevel.ERROR,
                action_required=True
            ),
            LogPattern(
                name="authentication_failure",
                pattern=re.compile(r"auth.*(?:failed|denied|invalid)", re.IGNORECASE),
                description="Authentication failures",
                severity=LogLevel.ERROR,
                action_required=True
            ),
            LogPattern(
                name="rate_limit_exceeded",
                pattern=re.compile(r"rate.?limit.*exceeded", re.IGNORECASE),
                description="Rate limit exceeded",
                severity=LogLevel.WARNING,
                action_required=False
            ),
            LogPattern(
                name="memory_error",
                pattern=re.compile(r"memory.*(?:error|exhausted|out of)", re.IGNORECASE),
                description="Memory-related errors",
                severity=LogLevel.CRITICAL,
                action_required=True
            ),
        ]
        
        # Performance patterns
        self.performance_patterns = [
            LogPattern(
                name="slow_query",
                pattern=re.compile(r"query.*(?:slow|timeout|(\d+\.?\d*)\s*(?:seconds?|ms))", re.IGNORECASE),
                description="Slow query performance",
                severity=LogLevel.WARNING,
                action_required=False
            ),
            LogPattern(
                name="high_memory_usage",
                pattern=re.compile(r"memory.*(?:usage|percent).*(\d+)", re.IGNORECASE),
                description="High memory usage",
                severity=LogLevel.WARNING,
                action_required=False
            ),
            LogPattern(
                name="cache_miss",
                pattern=re.compile(r"cache.*miss", re.IGNORECASE),
                description="Cache miss events",
                severity=LogLevel.INFO,
                action_required=False
            ),
        ]
        
        # Security patterns
        self.security_patterns = [
            LogPattern(
                name="unauthorized_access",
                pattern=re.compile(r"unauthorized|forbidden|access.*denied", re.IGNORECASE),
                description="Unauthorized access attempts",
                severity=LogLevel.WARNING,
                action_required=True
            ),
            LogPattern(
                name="suspicious_activity",
                pattern=re.compile(r"suspicious|malicious|attack", re.IGNORECASE),
                description="Suspicious activity detected",
                severity=LogLevel.ERROR,
                action_required=True
            ),
        ]
    
    async def collect_logs_from_file(self, log_file: Path, max_lines: int = 1000) -> int:
        """
        Collect logs from file.
        
        Args:
            log_file: Path to log file
            max_lines: Maximum number of lines to read
            
        Returns:
            Number of log entries collected
        """
        if not log_file.exists():
            logger.warning(f"Log file not found: {log_file}")
            return 0
        
        collected_count = 0
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # Read from the end of file (most recent logs)
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
                
                for line in recent_lines:
                    entry = self._parse_log_line(line.strip())
                    if entry:
                        self.log_entries.append(entry)
                        collected_count += 1
                        self._update_statistics(entry)
        
        except Exception as e:
            logger.error(f"Failed to collect logs from {log_file}: {e}")
        
        logger.info(f"Collected {collected_count} log entries from {log_file}")
        return collected_count
    
    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line into LogEntry."""
        if not line:
            return None
        
        # Try to parse structured log format
        # Format: YYYY-MM-DD HH:MM:SS | LEVEL | logger:function:line | message
        log_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|\s*([^:]+):([^:]+):(\d+)\s*\|\s*(.*)'
        )
        
        match = log_pattern.match(line)
        if match:
            timestamp_str, level_str, logger_name, function, line_num, message = match.groups()
            
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                level = LogLevel(level_str.upper())
                
                # Try to extract extra data from message
                extra_data = {}
                if ' | ' in message:
                    parts = message.split(' | ')
                    message = parts[0]
                    if len(parts) > 1:
                        # Try to parse as JSON
                        try:
                            extra_data = json.loads(parts[1])
                        except json.JSONDecodeError:
                            extra_data = {"raw_extra": parts[1]}
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    message=message,
                    logger_name=logger_name,
                    function=function,
                    line=int(line_num),
                    extra_data=extra_data
                )
            except (ValueError, KeyError) as e:
                logger.debug(f"Failed to parse log line: {e}")
        
        # Fallback: create basic entry
        return LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message=line,
            logger_name="unknown",
            function="unknown",
            line=0
        )
    
    def _update_statistics(self, entry: LogEntry) -> None:
        """Update log statistics."""
        self.log_stats[f"level_{entry.level.value.lower()}"] += 1
        self.log_stats["total_entries"] += 1
        
        # Track errors by type
        if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            self.error_counts[entry.message[:100]] += 1  # First 100 chars as error key
    
    def analyze_logs(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze collected logs for insights.
        
        Args:
            hours: Time period to analyze (in hours)
            
        Returns:
            Analysis results
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_entries = [e for e in self.log_entries if e.timestamp >= cutoff_time]
        
        if not recent_entries:
            return {"message": "No log entries found for the specified time period"}
        
        analysis = {
            "time_period_hours": hours,
            "total_entries": len(recent_entries),
            "timestamp": datetime.now().isoformat(),
            "level_distribution": self._analyze_log_levels(recent_entries),
            "error_analysis": self._analyze_errors(recent_entries),
            "performance_analysis": self._analyze_performance(recent_entries),
            "security_analysis": self._analyze_security(recent_entries),
            "trends": self._analyze_trends(recent_entries),
            "top_errors": self._get_top_errors(recent_entries),
            "recommendations": self._generate_recommendations(recent_entries)
        }
        
        return analysis
    
    def _analyze_log_levels(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """Analyze log level distribution."""
        level_counts = Counter(entry.level.value for entry in entries)
        total = len(entries)
        
        return {
            "counts": dict(level_counts),
            "percentages": {
                level: round((count / total) * 100, 2)
                for level, count in level_counts.items()
            },
            "error_rate": round(
                (level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)) / total * 100, 2
            ) if total > 0 else 0
        }
    
    def _analyze_errors(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """Analyze error patterns."""
        error_entries = [e for e in entries if e.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        
        pattern_matches = defaultdict(int)
        for entry in error_entries:
            for pattern in self.error_patterns:
                if pattern.pattern.search(entry.message):
                    pattern_matches[pattern.name] += 1
        
        return {
            "total_errors": len(error_entries),
            "pattern_matches": dict(pattern_matches),
            "error_rate_per_hour": len(error_entries) / max(1, len(set(e.timestamp.hour for e in entries))),
            "critical_errors": len([e for e in error_entries if e.level == LogLevel.CRITICAL])
        }
    
    def _analyze_performance(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """Analyze performance-related logs."""
        performance_entries = []
        
        for entry in entries:
            for pattern in self.performance_patterns:
                if pattern.pattern.search(entry.message):
                    performance_entries.append((entry, pattern.name))
        
        # Extract timing information
        timing_data = []
        for entry, _ in performance_entries:
            # Try to extract numeric values (timing, percentages, etc.)
            numbers = re.findall(r'\d+\.?\d*', entry.message)
            if numbers:
                timing_data.extend([float(n) for n in numbers])
        
        return {
            "performance_events": len(performance_entries),
            "avg_timing": sum(timing_data) / len(timing_data) if timing_data else 0,
            "max_timing": max(timing_data) if timing_data else 0,
            "min_timing": min(timing_data) if timing_data else 0
        }
    
    def _analyze_security(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """Analyze security-related logs."""
        security_entries = []
        
        for entry in entries:
            for pattern in self.security_patterns:
                if pattern.pattern.search(entry.message):
                    security_entries.append((entry, pattern.name))
        
        # Group by pattern
        security_events = defaultdict(int)
        for _, pattern_name in security_entries:
            security_events[pattern_name] += 1
        
        return {
            "total_security_events": len(security_entries),
            "event_types": dict(security_events),
            "requires_attention": len([
                e for e, p in security_entries 
                if any(pat.action_required for pat in self.security_patterns if pat.name == p)
            ])
        }
    
    def _analyze_trends(self, entries: List[LogEntry]) -> Dict[str, Any]:
        """Analyze log trends over time."""
        # Group entries by hour
        hourly_counts = defaultdict(int)
        hourly_errors = defaultdict(int)
        
        for entry in entries:
            hour_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] += 1
            
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                hourly_errors[hour_key] += 1
        
        # Calculate trends
        hours = sorted(hourly_counts.keys())
        if len(hours) >= 2:
            recent_avg = sum(hourly_counts[h] for h in hours[-3:]) / min(3, len(hours))
            earlier_avg = sum(hourly_counts[h] for h in hours[:3]) / min(3, len(hours))
            trend = "increasing" if recent_avg > earlier_avg * 1.1 else "decreasing" if recent_avg < earlier_avg * 0.9 else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "trend": trend,
            "hourly_activity": {h.isoformat(): count for h, count in hourly_counts.items()},
            "peak_hour": max(hourly_counts.items(), key=lambda x: x[1])[0].isoformat() if hourly_counts else None,
            "error_trend": {h.isoformat(): count for h, count in hourly_errors.items()}
        }
    
    def _get_top_errors(self, entries: List[LogEntry], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top error messages."""
        error_entries = [e for e in entries if e.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        error_messages = Counter(e.message[:200] for e in error_entries)  # First 200 chars
        
        return [
            {
                "message": message,
                "count": count,
                "percentage": round((count / len(error_entries)) * 100, 2) if error_entries else 0
            }
            for message, count in error_messages.most_common(limit)
        ]
    
    def _generate_recommendations(self, entries: List[LogEntry]) -> List[str]:
        """Generate recommendations based on log analysis."""
        recommendations = []
        
        error_entries = [e for e in entries if e.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        
        # Error rate recommendations
        error_rate = len(error_entries) / len(entries) * 100 if entries else 0
        if error_rate > 10:
            recommendations.append("High error rate detected (>10%). Investigate error patterns and implement fixes.")
        elif error_rate > 5:
            recommendations.append("Moderate error rate detected (>5%). Monitor error trends closely.")
        
        # Performance recommendations
        performance_issues = sum(1 for e in entries for p in self.performance_patterns if p.pattern.search(e.message))
        if performance_issues > len(entries) * 0.1:
            recommendations.append("Performance issues detected. Consider optimizing slow operations.")
        
        # Security recommendations
        security_issues = sum(1 for e in entries for p in self.security_patterns if p.pattern.search(e.message))
        if security_issues > 0:
            recommendations.append("Security events detected. Review access patterns and authentication logs.")
        
        # Memory recommendations
        memory_warnings = sum(1 for e in entries if "memory" in e.message.lower() and e.level == LogLevel.WARNING)
        if memory_warnings > 5:
            recommendations.append("Multiple memory warnings detected. Monitor memory usage and consider optimization.")
        
        if not recommendations:
            recommendations.append("Log analysis looks healthy. Continue monitoring.")
        
        return recommendations
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time log statistics."""
        recent_entries = [
            e for e in self.log_entries 
            if e.timestamp >= datetime.now() - timedelta(minutes=5)
        ]
        
        return {
            "last_5_minutes": {
                "total_entries": len(recent_entries),
                "errors": len([e for e in recent_entries if e.level in [LogLevel.ERROR, LogLevel.CRITICAL]]),
                "warnings": len([e for e in recent_entries if e.level == LogLevel.WARNING]),
                "latest_entry": recent_entries[-1].to_dict() if recent_entries else None
            },
            "overall_stats": dict(self.log_stats),
            "top_errors_today": [
                {"error": error, "count": count}
                for error, count in self.error_counts.most_common(5)
            ]
        }
    
    async def start_real_time_monitoring(self) -> None:
        """Start real-time log monitoring."""
        logger.info("Starting real-time log monitoring")
        
        while True:
            try:
                # Collect recent logs
                if settings.log_file and settings.log_file.exists():
                    await self.collect_logs_from_file(settings.log_file, max_lines=100)
                
                # Clean old entries (keep last 10000)
                if len(self.log_entries) > 10000:
                    self.log_entries = self.log_entries[-10000:]
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in real-time log monitoring: {e}")
                await asyncio.sleep(60)  # Wait longer on error


# Global log aggregator instance
log_aggregator = LogAggregator()
