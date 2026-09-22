"""
Plugin Loader

This module provides dynamic plugin loading capabilities, including
hot-swapping, dependency resolution, and runtime plugin management.
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
import inspect
import traceback

from ragbot.outputs.logger import logger
from .base_plugin import BasePlugin
from .plugin_registry import PluginRegistry


class PluginLoadError(Exception):
    """Exception raised when plugin loading fails"""

    pass


class PluginLoader:
    """
    Dynamic plugin loader with hot-swapping capabilities

    Provides functionality to load, unload, and reload plugins
    at runtime without requiring system restart.
    """

    def __init__(
        self,
        plugin_directory: str = "plugins",
        registry: Optional[PluginRegistry] = None,
    ):
        """
        Initialize plugin loader

        Args:
            plugin_directory: Directory containing plugin modules
            registry: Plugin registry instance
        """
        self.plugin_directory = Path(plugin_directory)
        self.registry = registry or PluginRegistry()
        self.loaded_modules: Dict[str, Any] = {}
        self.plugin_classes: Dict[str, Type[BasePlugin]] = {}

        # Ensure plugin directory exists
        self.plugin_directory.mkdir(parents=True, exist_ok=True)

    async def load_plugin(
        self, plugin_path: str, config: Optional[Dict[str, Any]] = None
    ) -> Optional[BasePlugin]:
        """
        Load a plugin from file or directory

        Args:
            plugin_path: Path to plugin module or directory
            config: Configuration for the plugin

        Returns:
            Loaded plugin instance or None if failed
        """
        try:
            plugin_path = Path(plugin_path)

            if not plugin_path.exists():
                raise PluginLoadError(f"Plugin path does not exist: {plugin_path}")

            # Determine plugin ID from path
            plugin_id = plugin_path.stem

            # Load the plugin module
            module = await self._load_module(plugin_path, plugin_id)

            # Find plugin class in module
            plugin_class = self._find_plugin_class(module)

            if not plugin_class:
                raise PluginLoadError(f"No valid plugin class found in {plugin_path}")

            # Create plugin instance
            plugin_instance = plugin_class(plugin_id, config)

            # Validate plugin
            await self._validate_plugin_instance(plugin_instance)

            # Register plugin
            registered_id = await self.registry.register_plugin(plugin_instance)

            if registered_id:
                logger.info(f"Plugin {plugin_id} loaded successfully")
                return plugin_instance
            else:
                logger.error(f"Failed to register plugin {plugin_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}")
            logger.debug(traceback.format_exc())
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
            # Unregister from registry
            success = await self.registry.unregister_plugin(plugin_id)

            if not success:
                logger.warning(f"Plugin {plugin_id} not found in registry")
                return False

            # Remove from loaded modules
            if plugin_id in self.loaded_modules:
                # Clean up module from sys.modules
                module_name = plugin_id
                if module_name in sys.modules:
                    del sys.modules[module_name]

                del self.loaded_modules[plugin_id]

            # Remove plugin class reference
            if plugin_id in self.plugin_classes:
                del self.plugin_classes[plugin_id]

            logger.info(f"Plugin {plugin_id} unloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False

    async def reload_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """
        Reload a plugin without interrupting service

        Args:
            plugin_id: Plugin identifier

        Returns:
            Reloaded plugin instance or None if failed
        """
        try:
            # Get plugin configuration before unloading
            plugin = await self.registry.get_plugin(plugin_id)
            if not plugin:
                logger.error(f"Plugin {plugin_id} not found for reload")
                return None

            config = plugin.config.copy()

            # Unload current plugin
            await self.unload_plugin(plugin_id)

            # Reload module
            module = await self._load_module(plugin_id, plugin_id, reload=True)

            # Find new plugin class
            new_plugin_class = self._find_plugin_class(module)
            if not new_plugin_class:
                raise PluginLoadError(f"No valid plugin class found in reloaded module")

            # Create new instance
            new_plugin_instance = new_plugin_class(plugin_id, config)

            # Register new instance
            registered_id = await self.registry.register_plugin(new_plugin_instance)

            if registered_id:
                logger.info(f"Plugin {plugin_id} reloaded successfully")
                return new_plugin_instance
            else:
                logger.error(f"Failed to register reloaded plugin {plugin_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_id}: {e}")
            return None

    async def load_plugins_from_directory(
        self, directory: Optional[str] = None
    ) -> List[BasePlugin]:
        """
        Load all plugins from a directory

        Args:
            directory: Directory to scan (defaults to plugin_directory)

        Returns:
            List of successfully loaded plugins
        """
        directory = directory or self.plugin_directory
        directory_path = Path(directory)

        if not directory_path.exists():
            logger.warning(f"Plugin directory does not exist: {directory_path}")
            return []

        loaded_plugins = []

        # Scan for Python files and directories
        plugin_candidates = []

        for item in directory_path.iterdir():
            if (
                item.is_file()
                and item.suffix == ".py"
                and not item.name.startswith("_")
            ):
                plugin_candidates.append(item)
            elif item.is_dir() and not item.name.startswith("_"):
                # Look for __init__.py
                init_file = item / "__init__.py"
                if init_file.exists():
                    plugin_candidates.append(item)

        # Load each plugin
        for candidate in plugin_candidates:
            try:
                plugin = await self.load_plugin(str(candidate))
                if plugin:
                    loaded_plugins.append(plugin)
            except Exception as e:
                logger.warning(f"Skipping {candidate}: {e}")

        logger.info(f"Loaded {len(loaded_plugins)} plugins from {directory_path}")
        return loaded_plugins

    async def list_available_plugins(self) -> List[Dict[str, Any]]:
        """
        List all available plugins that can be loaded

        Returns:
            List of plugin information dictionaries
        """
        available_plugins = []

        if not self.plugin_directory.exists():
            return available_plugins

        # Scan directory for plugins
        for item in self.plugin_directory.iterdir():
            if item.is_file() and item.suffix == ".py":
                plugin_info = self._get_plugin_info(str(item))
                if plugin_info:
                    available_plugins.append(plugin_info)

        return available_plugins

    async def _load_module(
        self, path: Path, module_name: str, reload: bool = False
    ) -> Any:
        """
        Load a Python module from path

        Args:
            path: Path to module file
            module_name: Name for the loaded module
            reload: Whether to reload if already loaded

        Returns:
            Loaded module
        """
        try:
            full_module_name = f"plugins.{module_name}"

            # Check if module is already loaded
            if not reload and full_module_name in sys.modules:
                return sys.modules[full_module_name]

            # Load module from file path
            spec = importlib.util.spec_from_file_location(full_module_name, path)

            if not spec:
                raise PluginLoadError(f"Could not create spec for {path}")

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules before executing
            sys.modules[full_module_name] = module

            # Execute module
            spec.loader.exec_module(module)

            # Store loaded module
            self.loaded_modules[module_name] = module

            logger.debug(f"Module {full_module_name} loaded from {path}")
            return module

        except Exception as e:
            raise PluginLoadError(f"Failed to load module from {path}: {e}")

    def _find_plugin_class(self, module: Any) -> Optional[Type[BasePlugin]]:
        """
        Find BasePlugin subclass in module

        Args:
            module: Loaded module to search

        Returns:
            Plugin class or None if not found
        """
        try:
            for _, obj in inspect.getmembers(module, inspect.isclass):
                # Skip imports and non-plugin classes
                if obj.__module__ != module.__name__:
                    continue

                # Check if it's a BasePlugin subclass
                if (
                    issubclass(obj, BasePlugin)
                    and obj is not BasePlugin
                    and hasattr(obj, "__abstractmethods__")
                    and len(obj.__abstractmethods__) == 0
                ):
                    return obj

        except Exception as e:
            logger.error(f"Error finding plugin class: {e}")

        return None

    async def _validate_plugin_instance(self, plugin: BasePlugin) -> None:
        """
        Validate plugin instance

        Args:
            plugin: Plugin instance to validate

        Raises:
            PluginLoadError: If validation fails
        """
        # Check required attributes
        required_attrs = [
            "plugin_name",
            "plugin_version",
            "plugin_description",
            "plugin_type",
        ]

        for attr in required_attrs:
            if not hasattr(plugin, attr):
                raise PluginLoadError(f"Plugin missing required attribute: {attr}")

        # Check metadata generation
        try:
            metadata = plugin.get_metadata()
            if not metadata or not metadata.name:
                raise PluginLoadError("Plugin metadata is invalid")
        except Exception as e:
            raise PluginLoadError(f"Plugin metadata validation failed: {e}")

        # Check configuration validation
        try:
            config_errors = plugin.validate_config()
            if config_errors:
                logger.warning(
                    f"Plugin {plugin.plugin_id} config issues: {config_errors}"
                )
        except Exception as e:
            raise PluginLoadError(f"Plugin config validation failed: {e}")

    def _get_plugin_info(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin information without fully loading it

        Args:
            path: Path to plugin file

        Returns:
            Plugin information dictionary or None if not a valid plugin
        """
        try:
            import ast

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            plugin_info = {"path": path, "file": Path(path).name}

            # Look for plugin class information in AST
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if class looks like a plugin
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "BasePlugin":
                            plugin_info["class_name"] = node.name
                            plugin_info["file"] = Path(path).name
                            return plugin_info

        except Exception as e:
            logger.debug(f"Error analyzing plugin info for {path}: {e}")

        return None
