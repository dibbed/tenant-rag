"""
Plugin Manager

This module provides high-level plugin management functionality,
including loading, lifecycle management, hook execution, and integration
with the main RAG Bot system.
"""

from typing import Dict, List, Optional, Any

from ragbot.outputs.logger import logger
from ragbot.configs.settings import settings
from .base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginStatus,
    HookType,
)
from .plugin_registry import PluginRegistry
from .plugin_loader import PluginLoader


class PluginManager:
    """
    High-level plugin manager for RAG Bot system

    Provides unified interface for plugin management, including:
    - Plugin loading and lifecycle management
    - Hook execution coordination
    - Integration with main application
    - Configuration management
    - Error handling and monitoring
    """

    def __init__(self, plugin_directory: Optional[str] = None):
        """
        Initialize plugin manager

        Args:
            plugin_directory: Directory containing plugins
        """
        self.plugin_directory = plugin_directory or str(settings.plugin_directory)
        self.registry = PluginRegistry()
        self.loader = PluginLoader(self.plugin_directory, self.registry)
        self.active_plugins: Dict[str, BasePlugin] = {}
        self.hook_registry: Dict[HookType, List[BasePlugin]] = {}

        # Initialize hook registry
        for hook_type in HookType:
            self.hook_registry[hook_type] = []

    async def initialize(self) -> bool:
        """
        Initialize the plugin manager

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing plugin manager...")

            # Load registry
            await self.registry._load_registry()

            # Auto-load plugins if enabled
            if getattr(settings, "auto_load_plugins", False):
                await self.load_plugins_from_directory()

            logger.info(
                f"Plugin manager initialized with {len(self.active_plugins)} plugins"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize plugin manager: {e}")
            return False

    async def load_plugin(
        self,
        plugin_path: str,
        config: Optional[Dict[str, Any]] = None,
        auto_start: bool = True,
    ) -> Optional[str]:
        """
        Load a plugin into the system

        Args:
            plugin_path: Path to plugin file or directory
            config: Configuration for the plugin
            auto_start: Whether to automatically start the plugin

        Returns:
            Plugin ID if successful, None if failed
        """
        try:
            # Load plugin through loader
            plugin = await self.loader.load_plugin(plugin_path, config)

            if not plugin:
                logger.error(f"Failed to load plugin from {plugin_path}")
                return None

            plugin_id = plugin.plugin_id

            # Initialize plugin if requested
            if auto_start:
                success = await self.start_plugin(plugin_id)
                if success:
                    logger.info(f"Plugin {plugin_id} loaded and started")
                else:
                    logger.warning(f"Plugin {plugin_id} loaded but failed to start")

            return plugin_id

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_path}: {e}")
            return None

    async def unload_plugin(self, plugin_id: str) -> bool:
        """
        Unload a plugin from the system

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Stop plugin if running
            if plugin_id in self.active_plugins:
                await self.stop_plugin(plugin_id)

            # Remove from hook registry
            self._remove_from_hook_registry(plugin_id)

            # Unload through loader
            success = await self.loader.unload_plugin(plugin_id)

            if success:
                logger.info(f"Plugin {plugin_id} unloaded successfully")

            return success

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return False

    async def reload_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """
        Reload a plugin without service interruption

        Args:
            plugin_id: Plugin identifier

        Returns:
            Reloaded plugin instance or None if failed
        """
        try:
            # Get current plugin config
            current_plugin = await self.registry.get_plugin(plugin_id)
            config = current_plugin.config if current_plugin else {}

            # Stop current plugin
            if plugin_id in self.active_plugins:
                await self.stop_plugin(plugin_id)

            # Reload through loader
            reloaded_plugin = await self.loader.reload_plugin(plugin_id)

            if reloaded_plugin:
                # Start reloaded plugin
                await self.start_plugin(plugin_id)
                logger.info(f"Plugin {plugin_id} reloaded successfully")

            return reloaded_plugin

        except Exception as e:
            logger.error(f"Error reloading plugin {plugin_id}: {e}")
            return None

    async def start_plugin(
        self, plugin_id: str, context: Optional[PluginContext] = None
    ) -> bool:
        """
        Start a plugin

        Args:
            plugin_id: Plugin identifier
            context: Optional startup context

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get plugin instance
            plugin = await self.registry.get_plugin(plugin_id)

            if not plugin:
                logger.error(f"Plugin {plugin_id} not found for starting")
                return False

            # Check if already active
            if plugin_id in self.active_plugins:
                logger.warning(f"Plugin {plugin_id} is already active")
                return True

            # Create startup context
            startup_context = context or PluginContext(
                plugin_id=plugin_id, config=plugin.config
            )

            # Initialize plugin
            success = await plugin.initialize(startup_context)

            if success:
                # Set as active
                plugin.set_status(PluginStatus.ACTIVE)
                self.active_plugins[plugin_id] = plugin

                # Register hooks
                self._register_hooks(plugin)

                logger.info(f"Plugin {plugin_id} started successfully")

            else:
                plugin.set_status(PluginStatus.ERROR)
                logger.error(f"Plugin {plugin_id} failed to initialize")

            return success

        except Exception as e:
            logger.error(f"Error starting plugin {plugin_id}: {e}")
            return False

    async def stop_plugin(self, plugin_id: str) -> bool:
        """
        Stop a plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if plugin is active
            if plugin_id not in self.active_plugins:
                logger.warning(f"Plugin {plugin_id} is not active")
                return True

            plugin = self.active_plugins[plugin_id]

            # Cleanup plugin
            success = await plugin.cleanup()

            if success:
                # Remove from active plugins
                del self.active_plugins[plugin_id]

                # Remove from hook registry
                self._remove_from_hook_registry(plugin_id)

                # Set status
                plugin.set_status(PluginStatus.INACTIVE)

                logger.info(f"Plugin {plugin_id} stopped successfully")

            else:
                plugin.set_status(PluginStatus.ERROR)
                logger.error(f"Plugin {plugin_id} failed to cleanup")

            return success

        except Exception as e:
            logger.error(f"Error stopping plugin {plugin_id}: {e}")
            return False

    async def execute_plugin(
        self, plugin_id: str, context: PluginContext
    ) -> Optional[PluginResult]:
        """
        Execute a plugin

        Args:
            plugin_id: Plugin identifier
            context: Execution context

        Returns:
            Plugin result or None if failed
        """
        try:
            plugin = await self.registry.get_plugin(plugin_id)

            if not plugin:
                logger.error(f"Plugin {plugin_id} not found")
                return None

            # Check if plugin is active
            if plugin_id not in self.active_plugins:
                logger.error(f"Plugin {plugin_id} is not active")
                return None

            # Execute plugin
            result = await plugin.execute(context)

            return result

        except Exception as e:
            logger.error(f"Error executing plugin {plugin_id}: {e}")
            return None

    async def execute_hooks(
        self, hook_type: HookType, context: PluginContext
    ) -> List[PluginResult]:
        """
        Execute all registered hooks of a given type

        Args:
            hook_type: Type of hook to execute
            context: Context for hook execution

        Returns:
            List of results from hook executions
        """
        results = []

        try:
            hook_plugins = self.hook_registry.get(hook_type, [])

            for plugin in hook_plugins:
                try:
                    # Execute all hooks for this plugin
                    plugin_results = await plugin.execute_hook(hook_type, context)
                    results.extend(plugin_results)

                except Exception as e:
                    logger.error(
                        f"Hook execution failed for plugin {plugin.plugin_id}: {e}"
                    )
                    error_result = PluginResult(
                        success=False, error_message=f"Hook execution error: {str(e)}"
                    )
                    results.append(error_result)

        except Exception as e:
            logger.error(f"Hook execution system error: {e}")

        return results

    async def load_plugins_from_directory(
        self, directory: Optional[str] = None
    ) -> List[str]:
        """
        Load all plugins from a directory

        Args:
            directory: Directory to scan (defaults to plugin_directory)

        Returns:
            List of successful plugin IDs
        """
        directory = directory or self.plugin_directory

        try:
            # Load plugins through loader
            loaded_plugins = await self.loader.load_plugins_from_directory(directory)

            # Start plugins automatically
            started_ids = []
            for plugin in loaded_plugins:
                plugin_id = plugin.plugin_id
                success = await self.start_plugin(plugin_id)
                if success:
                    started_ids.append(plugin_id)

            logger.info(
                f"Loaded and started {len(started_ids)} plugins from {directory}"
            )
            return started_ids

        except Exception as e:
            logger.error(f"Error loading plugins from directory {directory}: {e}")
            return []

    async def list_plugins(
        self, status_filter: Optional[PluginStatus] = None
    ) -> Dict[str, Any]:
        """
        List all plugins with optional status filter

        Args:
            status_filter: Optional status to filter by

        Returns:
            Dictionary with plugin information
        """
        try:
            return await self.registry.list_plugins(status_filter)

        except Exception as e:
            logger.error(f"Error listing plugins: {e}")
            return {}

    async def get_plugin_status(self, plugin_id: str) -> Optional[PluginStatus]:
        """
        Get status of a specific plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin status or None if not found
        """
        try:
            plugin = await self.registry.get_plugin(plugin_id)
            return plugin.get_status() if plugin else None

        except Exception as e:
            logger.error(f"Error getting plugin status for {plugin_id}: {e}")
            return None

    def get_active_plugins_status(self) -> Dict[str, str]:
        """
        Get status of all active plugins

        Returns:
            Dictionary with plugin IDs and their statuses
        """
        return {
            plugin_id: plugin.get_status().value
            for plugin_id, plugin in self.active_plugins.items()
        }

    def _register_hooks(self, plugin: BasePlugin) -> None:
        """
        Register plugin hooks

        Args:
            plugin: Plugin to register
        """
        for hook_type, hooks in plugin.hooks.items():
            if plugin not in self.hook_registry[hook_type]:
                self.hook_registry[hook_type].append(plugin)

    def _remove_from_hook_registry(self, plugin_id: str) -> None:
        """
        Remove plugin from hook registry

        Args:
            plugin_id: Plugin identifier
        """
        plugin = self.active_plugins.get(plugin_id)

        if plugin:
            for hook_type in self.hook_registry:
                if plugin in self.hook_registry[hook_type]:
                    self.hook_registry[hook_type].remove(plugin)

    async def shutdown(self) -> bool:
        """
        Shutdown plugin manager and stop all plugins

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Shutting down plugin manager...")

            # Stop all active plugins
            for plugin_id in list(self.active_plugins.keys()):
                await self.stop_plugin(plugin_id)

            # Save registry state
            await self.registry._save_registry()

            logger.info("Plugin manager shutdown complete")
            return True

        except Exception as e:
            logger.error(f"Error during plugin manager shutdown: {e}")
            return False
