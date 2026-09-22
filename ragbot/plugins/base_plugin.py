"""
Base Plugin Interface

This module defines the abstract base class that all plugins must implement,
providing a standardized interface for plugin development and integration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime


class PluginType(Enum):
    """Types of plugins supported by the system"""

    QUERY_ENHANCEMENT = "query_enhancement"
    SECURITY_PLUGIN = "security_plugin"
    DATA_PROCESSOR = "data_processor"
    EXPORT_PLUGIN = "export_plugin"
    INTEGRATION_PLUGIN = "integration_plugin"
    ANALYTICS_PLUGIN = "analytics_plugin"
    UI_ENHANCEMENT = "ui_enhancement"
    CUSTOM_SPORES = "custom_stores"


class PluginStatus(Enum):
    """Plugin status states"""

    INSTALLED = "installed"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"


class HookType(Enum):
    """Types of hooks that plugins can register"""

    PRE_DOCUMENT_INGEST = "pre_document_ingest"
    POST_DOCUMENT_INGEST = "post_document_ingest"
    PRE_QUERY = "pre_query"
    POST_QUERY = "post_query"
    PRE_RESPONSE = "pre_response"
    POST_RESPONSE = "post_response"
    ON_USER_INTERACTION = "on_user_interaction"
    ON_ERROR = "on_error"


@dataclass
class PluginMetadata:
    """Metadata information for a plugin"""

    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    required_version: str = "1.0.0"
    compatibility: List[str] = field(default_factory=list)
    license: str = "MIT"
    homepage: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PluginContext:
    """Context passed to plugin methods"""

    plugin_id: str
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PluginResult:
    """Result returned by plugin operations"""

    success: bool
    data: Optional[Any] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None


class BasePlugin(ABC):
    """
    Abstract base class for RAG Bot plugins

    All plugins must inherit from this class and implement
    the required abstract methods.
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize plugin

        Args:
            plugin_id: Unique identifier for the plugin
            config: Configuration dictionary for the plugin
        """
        self.plugin_id = plugin_id
        self.config = config or {}
        self.metadata: Optional[PluginMetadata] = None
        self.status = PluginStatus.INSTALLED
        self.hooks: Dict[HookType, List[Callable]] = {}
        self.dependencies: List[str] = []

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Plugin name"""
        pass

    @property
    @abstractmethod
    def plugin_version(self) -> str:
        """Plugin version"""
        pass

    @property
    @abstractmethod
    def plugin_description(self) -> str:
        """Plugin description"""
        pass

    @property
    @abstractmethod
    def plugin_type(self) -> PluginType:
        """Plugin type"""
        pass

    @abstractmethod
    async def initialize(self, context: PluginContext) -> bool:
        """
        Initialize the plugin

        Args:
            context: Plugin initialization context

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def execute(self, context: PluginContext) -> PluginResult:
        """
        Execute the plugin's main functionality

        Args:
            context: Execution context

        Returns:
            Plugin result with success status and data
        """
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """
        Cleanup plugin resources

        Returns:
            True if cleanup successful, False otherwise
        """
        pass

    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata

        Returns:
            Plugin metadata object
        """
        if not self.metadata:
            self.metadata = PluginMetadata(
                name=self.plugin_name,
                version=self.plugin_version,
                description=self.plugin_description,
                author=getattr(self, "plugin_author", "Unknown"),
                plugin_type=self.plugin_type,
                dependencies=self.dependencies,
            )
        return self.metadata

    def register_hook(self, hook_type: HookType, callback: Callable) -> None:
        """
        Register a hook callback

        Args:
            hook_type: Type of hook to register
            callback: Function to call when hook is triggered
        """
        if hook_type not in self.hooks:
            self.hooks[hook_type] = []
        self.hooks[hook_type].append(callback)

    def unregister_hook(self, hook_type: HookType, callback: Callable) -> None:
        """
        Unregister a hook callback

        Args:
            hook_type: Type of hook to unregister
            callback: Function to remove
        """
        if hook_type in self.hooks:
            try:
                self.hooks[hook_type].remove(callback)
            except ValueError:
                pass

    async def execute_hook(
        self, hook_type: HookType, context: PluginContext
    ) -> List[PluginResult]:
        """
        Execute all registered hooks for a given type

        Args:
            hook_type: Type of hook to execute
            context: Context for hook execution

        Returns:
            List of results from hook executions
        """
        results = []

        if hook_type in self.hooks:
            for callback in self.hooks[hook_type]:
                try:
                    if callable(callback):
                        result = await callback(context)
                        results.append(result)
                except Exception as e:
                    # Log error but continue with other hooks
                    error_result = PluginResult(
                        success=False, error_message=f"Hook execution failed: {str(e)}"
                    )
                    results.append(error_result)

        return results

    def validate_config(self) -> List[str]:
        """
        Validate plugin configuration

        Returns:
            List of validation error messages, empty if valid
        """
        errors = []

        # Basic validation
        required_configs = getattr(self, "required_config_keys", [])
        for key in required_configs:
            if key not in self.config:
                errors.append(f"Required configuration key missing: {key}")

        return errors

    def get_status(self) -> PluginStatus:
        """Get current plugin status"""
        return self.status

    def set_status(self, status: PluginStatus) -> None:
        """Set plugin status"""
        self.status = status

    def is_active(self) -> bool:
        """Check if plugin is active"""
        return self.status == PluginStatus.ACTIVE

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """
        Set configuration value

        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value

    def get_info(self) -> Dict[str, Any]:
        """
        Get plugin information dictionary

        Returns:
            Dictionary with plugin information
        """
        metadata = self.get_metadata()

        return {
            "plugin_id": self.plugin_id,
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "type": metadata.plugin_type.value,
            "status": self.status.value,
            "dependencies": metadata.dependencies,
            "hooks": list(self.hooks.keys()),
            "config_keys": list(self.config.keys()),
        }
