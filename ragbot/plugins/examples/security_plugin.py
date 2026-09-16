"""
Advanced Security Plugin

This plugin provides comprehensive security features for RAG Bot including:
- Content filtering and moderation
- Anomaly detection
- Threat assessment
- Security monitoring
"""

import asyncio
import re
from typing import Dict, Any, Optional, List

from ragbot.plugins.base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginType,
    PluginStatus,
)
from ragbot.outputs.logger import logger


class AdvancedSecurityPlugin(BasePlugin):
    """
    Advanced security plugin for RAG Bot

    Provides comprehensive security monitoring, content filtering,
    and threat detection capabilities.
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)

        # Default security configuration
        self.default_config = {
            "enable_content_filtering": True,
            "enable_threat_detection": True,
            "enable_anomaly_detection": True,
            "sensitivity_level": "medium",  # low, medium, high
            "block_suspicious_queries": True,
            "log_security_events": True,
            "max_query_length": 1000,
            "allowed_languages": ["fa", "en"],
            "banned_keywords": [],
            "suspicious_patterns": [
                r"password\s*[:=]",  # Password patterns
                r"api\s*key\s*[:=]",  # API key patterns
                r"token\s*[:=]",  # Token patterns
                r".{200,}",  # Very long strings
            ],
        }

        # Merge configuration
        self.config.update(self.default_config)

        # Security state tracking
        self.security_event_log: List[Dict[str, Any]] = []
        self.blocked_queries: List[str] = []
        self.suspicious_users: Dict[int, Dict[str, Any]] = {}

        # Threat detection thresholds
        self.threat_levels = {
            "low": {"score_threshold": 0.3, "action": "log"},
            "medium": {"score_threshold": 0.6, "action": "warn"},
            "high": {"score_threshold": 0.8, "action": "block"},
        }

    @property
    def plugin_name(self) -> str:
        return "Advanced Security Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return (
            "Comprehensive security plugin for threat detection and content filtering"
        )

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.SECURITY_PLUGIN

    @property
    def plugin_author(self) -> str:
        return "RAG Bot Security Team"

    async def initialize(self, context: PluginContext) -> bool:
        """
        Initialize the security plugin

        Args:
            context: Plugin initialization context

        Returns:
            True if initialization successful
        """
        try:
            self.set_status(PluginStatus.ACTIVE)

            # Register security hooks
            self.register_hook("pre_query", self.analyze_query_security)
            self.register_hook("pre_document_ingest", self.filter_document_content)
            self.register_hook("on_user_interaction", self.monitor_user_behavior)

            logger.info("Advanced Security Plugin initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Security plugin initialization failed: {e}")
            return False

    async def execute(self, context: PluginContext) -> PluginResult:
        """
        Execute security analysis

        Args:
            context: Security analysis context

        Returns:
            Security analysis results
        """
        try:
            command = (
                context.data.get("command", "analyze") if context.data else "analyze"
            )

            if command == "analyze":
                return await self._perform_security_analysis(context)
            elif command == "report":
                return await self._generate_security_report()
            elif command == "block_user":
                return await self._block_user(context.data.get("user_id"))
            elif command == "unblock_user":
                return await self._unblock_user(context.data.get("user_id"))
            else:
                return PluginResult(
                    success=False, error_message=f"Unknown security command: {command}"
                )

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Security execution error: {e}"
            )

    async def cleanup(self) -> bool:
        """
        Cleanup security plugin resources

        Returns:
            True if cleanup successful
        """
        try:
            # Log security plugin shutdown
            if self.get_config("log_security_events", True):
                await self._log_security_event(
                    "plugin_shutdown", {"plugin_id": self.plugin_id}, threat_level="low"
                )

            self.set_status(PluginStatus.INACTIVE)
            return True

        except Exception as e:
            logger.error(f"Security plugin cleanup failed: {e}")
            return False

    async def analyze_query_security(self, context: PluginContext) -> PluginResult:
        """
        Analyze query for security threats

        Args:
            context: Query context

        Returns:
            Security analysis result
        """
        try:
            if not self.get_config("enable_content_filtering", True):
                return PluginResult(success=True)

            query_text = context.data.get("query", "") if context.data else ""
            user_id = context.user_id

            # Perform comprehensive security analysis
            analysis_result = await self._analyze_query_content(query_text, user_id)

            # Check if query should be blocked
            if analysis_result["should_block"]:
                self.blocked_queries.append(query_text)
                await self._log_security_event(
                    "blocked_query",
                    {
                        "query": query_text[:100] + "..."
                        if len(query_text) > 100
                        else query_text,
                        "reason": analysis_result["reason"],
                        "threat_score": analysis_result["threat_score"],
                    },
                    threat_level="high",
                )

                return PluginResult(
                    success=False,
                    error_message=f"Query blocked by security filter: {analysis_result['reason']}",
                )

            # Log suspicious but allowed queries
            elif analysis_result["is_suspicious"]:
                await self._log_security_event(
                    "suspicious_query",
                    {
                        "query": query_text,
                        "threat_score": analysis_result["threat_score"],
                    },
                    threat_level="medium",
                )

            return PluginResult(success=True, data=analysis_result)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Query security analysis error: {e}"
            )

    async def filter_document_content(self, context: PluginContext) -> PluginResult:
        """
        Filter document content for security

        Args:
            context: Document ingestion context

        Returns:
            Content filtering result
        """
        try:
            if not self.get_config("enable_content_filtering", True):
                return PluginResult(success=True)

            document_content = context.data.get("content", "") if context.data else ""

            # Analyze document content
            analysis = await self._analyze_document_content(document_content)

            if analysis["should_block"]:
                await self._log_security_event(
                    "blocked_document",
                    {
                        "document_type": context.data.get("type", "unknown")
                        if context.data
                        else "unknown",
                        "reason": analysis["reason"],
                        "threat_score": analysis["threat_score"],
                    },
                    threat_level="high",
                )

                return PluginResult(
                    success=False,
                    error_message=f"Document blocked by security filter: {analysis['reason']}",
                )

            return PluginResult(success=True, data=analysis)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Document filtering error: {e}"
            )

    async def monitor_user_behavior(self, context: PluginContext) -> PluginResult:
        """
        Monitor user behavior for anomalies

        Args:
            context: User interaction context

        Returns:
            Monitoring result
        """
        try:
            if not self.get_config("enable_anomaly_detection", True):
                return PluginResult(success=True)

            user_id = context.user_id
            action = context.data.get("action", "") if context.data else ""

            if not user_id:
                return PluginResult(success=True)

            # Update user behavior profile
            await self._update_user_profile(user_id, action)

            # Detect anomalies
            if user_id not in self.suspicious_users:
                self.suspicious_users[user_id] = {"score": 0, "violations": []}

            anomaly_score = await self._calculate_anomaly_score(user_id)

            if anomaly_score > self.threat_levels["high"]["score_threshold"]:
                await self._log_security_event(
                    "suspicious_user",
                    {
                        "user_id": user_id,
                        "anomaly_score": anomaly_score,
                        "action": action,
                    },
                    threat_level="high",
                )

                # Auto-block if configured
                if self.get_config("block_suspicious_queries", True):
                    self.suspicious_users[user_id]["blocked"] = True

            return PluginResult(success=True, data={"anomaly_score": anomaly_score})

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Behavior monitoring error: {e}"
            )

    async def _analyze_query_content(self, query: str, user_id: int) -> Dict[str, Any]:
        """
        Analyze query content for security threats

        Args:
            query: Query text to analyze
            user_id: User making the query

        Returns:
            Security analysis results
        """
        threat_score = 0.0
        issues = []

        # Check query length
        if len(query) > self.get_config("max_query_length", 1000):
            threat_score += 0.3
            issues.append("Query too long")

        # Check for banned keywords
        banned_keywords = self.get_config("banned_keywords", [])
        for keyword in banned_keywords:
            if keyword.lower() in query.lower():
                threat_score += 0.5
                issues.append(f"Contains banned keyword: {keyword}")

        # Check for suspicious patterns
        suspicious_patterns = self.get_config("suspicious_patterns", [])
        for pattern in suspicious_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                threat_score += 0.4
                issues.append(f"Matches suspicious pattern: {pattern}")

        # Check user history for suspicious behavior
        if user_id in self.suspicious_users:
            user_score = self.suspicious_users[user_id].get("score", 0)
            threat_score += user_score * 0.2
            if user_score > 0.5:
                issues.append("User has suspicious history")

        sensitivity = self.get_config("sensitivity_level", "medium")
        threshold = self.threat_levels[sensitivity]["score_threshold"]

        return {
            "threat_score": threat_score,
            "is_suspicious": threat_score > 0.3,
            "should_block": threat_score > threshold,
            "reason": "; ".join(issues) if issues else "No security issues",
            "analysis_details": {
                "issues": issues,
                "threshold": threshold,
                "sensitivity": sensitivity,
            },
        }

    async def _analyze_document_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze document content for security issues

        Args:
            content: Document content to analyze

        Returns:
            Analysis results
        """
        threat_score = 0.0
        issues = []

        # Check content length
        if len(content) > 10000:  # Very large documents might be suspicious
            threat_score += 0.2
            issues.append("Document very large")

        # Check for suspicious patterns in content
        suspicious_patterns = self.get_config("suspicious_patterns", [])
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                threat_score += 0.3 * len(matches)
                issues.append(f"Contains {len(matches)} suspicious patterns")

        return {
            "threat_score": threat_score,
            "should_block": threat_score > 0.6,
            "reason": "; ".join(issues) if issues else "Content appears safe",
        }

    async def _update_user_profile(self, user_id: int, action: str) -> None:
        """Update user behavior profile"""
        if user_id not in self.suspicious_users:
            self.suspicious_users[user_id] = {
                "score": 0,
                "violations": [],
                "query_count": 0,
                "last_activity": None,
            }

        profile = self.suspicious_users[user_id]
        profile["query_count"] = profile.get("query_count", 0) + 1

        # Track rapid-fire queries (potential spam)
        if profile["last_activity"]:
            import time

            time_diff = time.time() - profile["last_activity"]
            if time_diff < 1.0 and action == "query":  # Less than 1 second
                profile["score"] += 0.1
                profile["violations"].append("Rapid-fire queries")

        profile["last_activity"] = time.time()

    async def _calculate_anomaly_score(self, user_id: int) -> float:
        """Calculate anomaly score for user"""
        if user_id not in self.suspicious_users:
            return 0.0

        profile = self.suspicious_users[user_id]
        score = profile["score"]

        # Normalize based on query count
        query_count = profile.get("query_count", 1)
        normalized_score = score / max(query_count, 1)

        return min(normalized_score, 1.0)

    async def _log_security_event(
        self, event_type: str, data: Dict[str, Any], threat_level: str
    ) -> None:
        """Log security event"""
        if not self.get_config("log_security_events", True):
            return

        event = {
            "timestamp": asyncio.get_event_loop().time(),
            "event_type": event_type,
            "threat_level": threat_level,
            "data": data,
        }

        self.security_event_log.append(event)

        # Log to main logger
        logger.warning(f"Security event: {event_type} (threat: {threat_level})")

    async def _perform_security_analysis(self, context: PluginContext) -> PluginResult:
        """Perform comprehensive security analysis"""
        try:
            analysis_data = {
                "total_blocked_queries": len(self.blocked_queries),
                "security_events_count": len(self.security_event_log),
                "suspicious_users_count": len(
                    [
                        u
                        for u in self.suspicious_users.values()
                        if u.get("score", 0) > 0.5
                    ]
                ),
                "current_threats": self._analyze_current_threats(),
                "security_score": self._calculate_overall_security_score(),
            }

            return PluginResult(success=True, data=analysis_data)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Security analysis error: {e}"
            )

    async def _generate_security_report(self) -> PluginResult:
        """Generate comprehensive security report"""
        try:
            report = {
                "timestamp": asyncio.get_event_loop().time(),
                "summary": await self._perform_security_analysis(None),
                "recent_events": self.security_event_log[-10:],  # Last 10 events
                "top_blocked_patterns": self._get_top_blocked_patterns(),
                "security_recommendations": self._get_security_recommendations(),
            }

            return PluginResult(success=True, data=report)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Security report error: {e}"
            )

    def _analyze_current_threats(self) -> List[Dict[str, Any]]:
        """Analyze current security threats"""
        threats = []

        if len(self.blocked_queries) > 10:
            threats.append(
                {
                    "type": "high_blocked_queries",
                    "severity": "medium",
                    "message": f"High number of blocked queries: {len(self.blocked_queries)}",
                }
            )

        suspicious_users = [
            user_id
            for user_id, profile in self.suspicious_users.items()
            if profile.get("score", 0) > 0.7
        ]

        if suspicious_users:
            threats.append(
                {
                    "type": "suspicious_users",
                    "severity": "high",
                    "message": f"{len(suspicious_users)} suspicious users detected",
                }
            )

        return threats

    def _calculate_overall_security_score(self) -> float:
        """Calculate overall security score (0-1, higher is safer)"""
        total_queries = sum(
            u.get("query_count", 0) for u in self.suspicious_users.values()
        )
        if total_queries == 0:
            return 1.0

        blocked_ratio = len(self.blocked_queries) / max(total_queries, 1)
        suspicious_ratio = len(
            [u for u in self.suspicious_users.values() if u.get("score", 0) > 0.5]
        ) / max(len(self.suspicious_users), 1)

        # Security score decreases with threats
        security_score = 1.0 - (blocked_ratio * 0.3) - (suspicious_ratio * 0.4)
        return max(0.0, security_score)

    def _get_top_blocked_patterns(self) -> List[Dict[str, Any]]:
        """Get most common blocked patterns"""
        pattern_counts = {}
        for query in self.blocked_queries:
            for pattern in self.get_config("suspicious_patterns", []):
                if re.search(pattern, query, re.IGNORECASE):
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        return [
            {"pattern": pattern, "count": count}
            for pattern, count in sorted(
                pattern_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

    def _get_security_recommendations(self) -> List[str]:
        """Get security recommendations based on current state"""
        recommendations = []

        if len(self.blocked_queries) > 5:
            recommendations.append("Consider enabling stricter content filtering")

        if (
            len([u for u in self.suspicious_users.values() if u.get("score", 0) > 0.7])
            > 0
        ):
            recommendations.append("Review suspicious user activity")

        if self.get_config("sensitivity_level") == "low":
            recommendations.append("Consider increasing sensitivity level to 'medium'")

        return recommendations

    async def _block_user(self, user_id: int) -> PluginResult:
        """Block a user"""
        try:
            if not user_id:
                return PluginResult(success=False, error_message="User ID required")

            if user_id not in self.suspicious_users:
                self.suspicious_users[user_id] = {"score": 0, "violations": []}

            self.suspicious_users[user_id]["blocked"] = True

            await self._log_security_event(
                "user_blocked", {"user_id": user_id}, threat_level="high"
            )

            return PluginResult(
                success=True, data={"user_id": user_id, "action": "blocked"}
            )

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Failed to block user: {e}"
            )

    async def _unblock_user(self, user_id: int) -> PluginResult:
        """Unblock a user"""
        try:
            if not user_id:
                return PluginResult(success=False, error_message="User ID required")

            if user_id in self.suspicious_users:
                self.suspicious_users[user_id]["blocked"] = False

            await self._log_security_event(
                "user_unblocked", {"user_id": user_id}, threat_level="low"
            )

            return PluginResult(
                success=True, data={"user_id": user_id, "action": "unblocked"}
            )

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Failed to unblock user: {e}"
            )
