"""
Plugin Registry

This module provides plugin registration and discovery functionality,
including versioning, compatibility checks, and dependency management.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import json
import time

from ragbot.outputs.logger import logger
from .base_plugin import (
    BasePlugin,
    PluginMetadata,
    PluginType,
    PluginStatus,
)


class PluginRegistry:
    """
    Plugin registry for managing plugin instances

    Provides registration, discovery, validation, and lifecycle management
    of plugins in the RAG Bot system.
    """

    def __init__(self, registry_file: Optional[str] = None):
        """
        Initialize plugin registry

        Args:
            registry_file: Path to registry persistence file
        """
        self.registry_file = registry_file or "plugins/registry.json"
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_metadata: Dict[str, PluginMetadata] = {}
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.plugin_types: Dict[PluginType, Set[str]] = defaultdict(set)
        self.status_queue: Dict[str, PluginStatus] = {}

    async def register_plugin(self, plugin: BasePlugin) -> str:
        """
        Register a plugin in the registry

        Args:
            plugin: Plugin instance to register

        Returns:
            Plugin ID if successful, empty string if failed
        """
        try:
            plugin_id = plugin.plugin_id

            # Check if plugin already exists
            if plugin_id in self.plugins:
                logger.warning(
                    f"Plugin {plugin_id} already registered, updating instead"
                )

            # Validate plugin
            validation_errors = await self._validate_plugin(plugin)
            if validation_errors:
                logger.error(
                    f"Plugin {plugin_id} validation failed: {validation_errors}"
                )
                return ""

            # Check dependencies
            missing_deps = await self._check_dependencies(plugin)
            if missing_deps:
                logger.warning(
                    f"Plugin {plugin_id} has missing dependencies: {missing_deps}"
                )

            # Register plugin
            self.plugins[plugin_id] = plugin
            self.plugin_metadata[plugin_id] = plugin.get_metadata()

            # Update type index
            plugin_type = plugin.plugin_type
            self.plugin_types[plugin_type].add(plugin_id)

            # Update dependency graph
            for dep in plugin.dependencies:
                self.dependency_graph[plugin_id].add(dep)

            # Set initial status
            plugin.set_status(PluginStatus.INSTALLED)

            logger.info(f"Plugin {plugin_id} registered successfully")

            # Persist registry
            await self._save_registry()

            return plugin_id

        except Exception as e:
            logger.error(f"Failed to register plugin {plugin_id}: {e}")
            return ""

    async def unregister_plugin(self, plugin_id: str) -> bool:
        """
        Unregister a plugin from the registry

        Args:
            plugin_id: ID of plugin to unregister

        Returns:
            True if successful, False otherwise
        """
        try:
            if plugin_id not in self.plugins:
                logger.warning(f"Plugin {plugin_id} not found in registry")
                return False

            # Check if plugins depend on this one
            dependents = self._get_dependent_plugins(plugin_id)
            if dependents:
                logger.warning(
                    f"Cannot unregister {plugin_id}: dependencies: {dependents}"
                )
                return False

            # Cleanup plugin
            plugin = self.plugins[plugin_id]
            await plugin.cleanup()

            # Remove from registry
            del self.plugins[plugin_id]
            del self.plugin_metadata[plugin_id]

            # Remove from type index
            plugin_type = plugin.plugin_type
            self.plugin_types[plugin_type].discard(plugin_id)

            # Remove from dependency graph
            if plugin_id in self.dependency_graph:
                del self.dependency_graph[plugin_id]

            # Remove from status队列
            if plugin_id in self.status_queue:
                del self.status_queue[plugin_id]

            logger.info(f"Plugin {plugin_id} unregistered successfully")

            # Persist registry
            await self._save_registry()

            return True

        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_id}: {e}")
            return False

    async def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """
        Get plugin instance by ID

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(plugin_id)

    async def get_plugins_by_type(self, plugin_type: PluginType) -> List[BasePlugin]:
        """
        Get all plugins of a specific type

        Args:
            plugin_type: Type of plugins to retrieve

        Returns:
            List of plugin instances
        """
        plugin_ids = self.plugin_types.get(plugin_type, set())
        return [self.plugins[pid] for pid in plugin_ids if pid in self.plugins]

    async def get_active_plugins(self) -> List[BasePlugin]:
        """
        Get all active plugins

        Returns:
            List of active plugin instances
        """
        return [
            plugin
            for plugin in self.plugins.values()
            if plugin.get_status() == PluginStatus.ACTIVE
        ]

    async def get_plugin_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """
        Get metadata for a plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin metadata or None if not found
        """
        return self.plugin_metadata.get(plugin_id)

    async def list_plugins(
        self, status_filter: Optional[PluginStatus] = None
    ) -> Dict[str, Any]:
        """
        List all registered plugins with optional status filter

        Args:
            status_filter: Optional status to filter by

        Returns:
            Dictionary with plugin information
        """
        plugins_info = {}

        for plugin_id, plugin in self.plugins.items():
            plugin_status = plugin.get_status()

            # Apply status filter if provided
            if status_filter and plugin_status != status_filter:
                continue

            plugins_info[plugin_id] = {
                "metadata": plugin.get_metadata().__dict__,
                "status": plugin_status.value,
                "hooks": list(plugin.hooks.keys()),
                "dependencies": plugin.dependencies,
                "config_keys": list(plugin.config.keys()),
            }

        return plugins_info

    async def validate_plugin_compatibility(self, plugin: BasePlugin) -> List[str]:
        """
        Validate plugin compatibility with current system

        Args:
            plugin: Plugin to validate

        Returns:
            List of compatibility issues
        """
        issues = []

        try:
            # Check version compatibility。
            required_version = plugin.get_metadata().required_version
            current_version = "2.0.0"  # Current system version

            # Simple version comparison (semver)
            if not self._is_version_compatible(current_version, required_version):
                issues.append(
                    f"Version incompatibility: requires {required_version}, have {current_version}"
                )

            # Check plugin type support
            plugin_type = plugin.plugin_type
            if not self._is_plugin_type_supported(plugin_type):
                issues.append(f"Plugin type not supported: {plugin_type.value}")

            # Validate dependencies exist
            missing_deps = await self._check_dependencies(plugin)
            if missing_deps:
                issues.extend([f"Missing dependency: {dep}" for dep in missing_deps])

        except Exception as e:
            issues.append(f"Validation error: {str(e)}")

        return issues

    async def reload_plugin(self, plugin_id: str) -> bool:
        """
        Reload a plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if reload successful, False otherwise
        """
        try:
            if plugin_id not in self.plugins:
                logger.error(f"Plugin {plugin_id} not found")
                return False

            plugin = self.plugins[plugin_id]

            # Cleanup current instance
            await plugin.cleanup()

            # Reload plugin (implementation depends on loader)
            # This would typically involve reimporting and reinstantiating
            logger.info(f"Plugin {plugin_id} reloaded")

            return True

        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_id}: {e}")
            return False

    async def _validate_plugin(self, plugin: BasePlugin) -> List[str]:
        """
        Validate plugin implementation

        Args:
            plugin: Plugin to validate

        Returns:
            List of validation errors
        """
        errors = []

        try:
            # Check required methods exist
            required_methods = ["initialize", "execute", "cleanup"]
            for method_name in required_methods:
                if not hasattr(plugin, method_name):
                    errors.append(f"Missing required method: {method_name}")

            # Validate configuration
            config_errors = plugin.validate_config()
            errors.extend(config_errors)

            # Check metadata
            try:
                metadata = plugin.get_metadata()
                if not metadata.name or not metadata.version:
                    errors.append("Plugin metadata incomplete")
            except Exception as e:
                errors.append(f"Metadata validation failed: {str(e)}")

        except Exception as e:
            errors.append(f"Plugin validation failed: {str(e)}")

        return errors

    async def _check_dependencies(self, plugin: BasePlugin) -> List[str]:
        """
        Check if plugin dependencies are satisfied

        Args:
            plugin: Plugin to check

        Returns:
            List of missing dependencies
        """
        missing = []

        for dep in plugin.dependencies:
            if dep not in self.plugins:
                missing.append(dep)

        return missing

    def _get_dependent_plugins(self, plugin_id: str) -> List[str]:
        """
        Get plugins that depend on the given plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            List of dependent plugin IDs
        """
        dependents = []

        for other_id, deps in self.dependency_graph.items():
            if plugin_id in deps:
                dependents.append(other_id)

        return dependents

    def _is_version_compatible(self, current: str, required: str) -> bool:
        """
        Check if current version is compatible with required version

        Args:
            current: Current system version
            required: Required plugin version

        Returns:
            True if compatible, False otherwise
        """
        # Simple implementation - can be enhanced with proper semver
        current_major = int(current.split(".")[0])
        required_major = int(required.split(".")[0])

        return current_major >= required_major

    def _is_plugin_type_supported(self, plugin_type: PluginType) -> bool:
        """
        Check if plugin type is supported

        Args:
            plugin_type: Plugin type to check

        Returns:
            True if supported, False otherwise
        """
        # All defined types are supported
        return True

    async def _save_registry(self) -> None:
        """Persist registry state to file"""
        try:
            registry_data = {
                "plugins": {},
                "metadata": {},
                "dependency_graph": dict(self.dependency_graph),
                "timestamp": time.time(),
            }

            # Serialize plugins (basic info only for persistence)
            for plugin_id, plugin in self.plugins.items():
                registry_data["plugins"][plugin_id] = {
                    "class_name": plugin.__class__.__name__,
                    "module_path": plugin.__class__.__module__,
                }

            # Serialize metadata
            for plugin_id, metadata in self.plugin_metadata.items():
                registry_data["metadata"][plugin_id] = metadata.__dict__

            # Write to file
            registry_path = Path(self.registry_file)
            registry_path.parent.mkdir(parents=True, exist_ok=True)

            with open(registry_path, "w") as f:
                json.dump(registry_data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    async def _load_registry(self) -> None:
        """Load registry state from file"""
        try:
            registry_path = Path(self.registry_file)

            if not registry_path.exists():
                logger.info("No registry file found, starting with empty registry")
                return

            with open(registry_path, "r") as f:
                registry_data = json.load(f)

            # Reconstruct metadata
            metadata_dict = registry_data.get("metadata", {})
            for plugin_id, meta_dict in metadata_dict.items():
                self.plugin_metadata[plugin_id] = PluginMetadata(**meta_dict)

            # Reconstruct dependency graph
            dep_graph = registry_data.get("dependency_graph", {})
            self.dependency_graph.update({k: set(v) for k, v in dep_graph.items()})

            logger.info(f"Registry loaded with {len(metadata_dict)} plugins")

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
