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

from .plugin_manager import PluginManager
from .plugin_registry import PluginRegistry
from .plugin_loader import PluginLoader
from .base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginStatus,
    PluginType,
    HookType,
)
from .plugin_validator import PluginValidator
from .plugin_marketplace import PluginMarketplace

__all__ = [
    "PluginManager",
    "PluginRegistry",
    "PluginLoader",
    "BasePlugin",
    "PluginContext",
    "PluginResult",
    "PluginStatus",
    "PluginType",
    "HookType",
    "PluginValidator",
    "PluginMarketplace",
]
