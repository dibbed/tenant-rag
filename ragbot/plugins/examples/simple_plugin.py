"""
Simple Example Plugin

This plugin demonstrates basic plugin functionality including:
- Document preprocessing
- Query enhancement
- Custom response formatting
"""

from typing import Dict, Any, Optional

from ragbot.plugins.base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginType,
    PluginStatus,
    HookType,
)
from ragbot.outputs.logger import logger


class SimplePlugin(BasePlugin):
    """
    Simple plugin example for RAG Bot

    Demonstrates basic plugin functionality with query enhancement.
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)

        # Default configuration
        self.default_config = {
            "enhancement_factor": 1.2,
            "custom_prefix": "🔍 Enhanced: ",
            "enable_formatting": True,
        }

        # Merge with provided config
        self.config.update(self.default_config)

    @property
    def plugin_name(self) -> str:
        return "Simple Enhancement Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return "Simple plugin that enhances query results with formatting and custom processing"

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.QUERY_ENHANCEMENT

    @property
    def plugin_author(self) -> str:
        return "RAG Bot Team"

    async def initialize(self, context: PluginContext) -> bool:
        """
        Initialize the plugin

        Args:
            context: Plugin initialization context

        Returns:
            True if initialization successful
        """
        try:
            self.set_status(PluginStatus.ACTIVE)

            # Register hooks for query processing
            self.register_hook(HookType.POST_QUERY, self.enhance_query_result)
            self.register_hook(HookType.PRE_RESPONSE, self.format_response)

            return True

        except Exception as e:
            logger.error(f"Simple plugin initialization failed: {e}")
            return False

    async def execute(self, context: PluginContext) -> PluginResult:
        """
        Execute custom plugin functionality

        Args:
            context: Execution context

        Returns:
            Plugin result
        """
        try:
            data = context.data or {}
            query_text = data.get("query", "")

            if not query_text:
                return PluginResult(success=False, error_message="No query provided")

            # Simple query enhancement
            enhanced_query = await self._enhance_query(query_text)

            return PluginResult(
                success=True,
                data={
                    "original_query": query_text,
                    "enhanced_query": enhanced_query,
                    "enhancement_applied": True,
                },
            )

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Plugin execution error: {e}"
            )

    async def cleanup(self) -> bool:
        """
        Cleanup plugin resources

        Returns:
            True if cleanup successful
        """
        try:
            self.set_status(PluginStatus.INACTIVE)
            return True

        except Exception as e:
            logger.error(f"Simple plugin cleanup failed: {e}")
            return False

    async def enhance_query_result(self, context: PluginContext) -> PluginResult:
        """
        Hook to enhance query results

        Args:
            context: Hook context

        Returns:
            Enhancement result
        """
        try:
            if not self.get_config("enable_formatting", True):
                return PluginResult(success=True)

            # Get query context data
            data = context.data or {}

            # Simple enhancement logic
            if "confidence_score" in data:
                original_score = data["confidence_score"]
                enhanced_score = min(
                    1.0, original_score * self.get_config("enhancement_factor", 1.2)
                )
                data["confidence_score"] = enhanced_score

            return PluginResult(success=True, data=data)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Query enhancement error: {e}"
            )

    async def format_response(self, context: PluginContext) -> PluginResult:
        """
        Hook to format responses

        Args:
            context: Hook context

        Returns:
            Formatting result
        """
        try:
            data = context.data or {}
            response_text = data.get("answer", "")

            if response_text and self.get_config("enable_formatting", True):
                prefix = self.get_config("custom_prefix", "🔍 Enhanced: ")
                formatted_response = prefix + response_text
                data["answer"] = formatted_response

            return PluginResult(success=True, data=data)

        except Exception as e:
            return PluginResult(
                success=False, error_message=f"Response formatting error: {e}"
            )

    async def _enhance_query(self, query: str) -> str:
        """
        Enhance query text with custom processing

        Args:
            query: Original query text

        Returns:
            Enhanced query text
        """
        # Simple enhancement - add clarifying phrases
        enhancements = [
            "مختصری و دقیق پاسخ دهید",
            "از منابع معتبر استفاده کنید",
            "موضوع را کاملاً توضیح دهید",
        ]

        # Add one enhancement per query (cycling through)
        if "؟" in query or "?" in query:
            return query + f" ({enhancements[0]})"
        elif len(query.split()) > 5:
            return query + f" ({enhancements[1]})"
        else:
            return query + f" ({enhancements[2]})"
