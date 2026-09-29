"""
Plugin Architecture for RAG Bot

This module provides a comprehensive plugin system that allows:
- Dynamic plugin loading and unloading
- Plugin lifecycle management
- Plugin metadata and versioning
- Hot-swapping capabilities
- Plugin marketplace support
- Third-party integration framework
"""

from .base_plugin import (
    BasePlugin,
    HookType,
    PluginContext,
    PluginResult,
    PluginStatus,
    PluginType,
)
from .plugin_loader import PluginLoader
from .plugin_manager import PluginManager
from .plugin_marketplace import PluginMarketplace
from .plugin_registry import PluginRegistry
from .plugin_validator import PluginValidator

__all__ = [
    "BasePlugin",
    "HookType",
    "PluginContext",
    "PluginLoader",
    "PluginManager",
    "PluginMarketplace",
    "PluginRegistry",
    "PluginResult",
    "PluginStatus",
    "PluginType",
    "PluginValidator",
]
