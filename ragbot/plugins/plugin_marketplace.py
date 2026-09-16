"""
Plugin Marketplace

This module provides marketplace functionality for plugins,
including discovery, installation, and management of plugins
from remote sources.
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Optional
from pathlib import Path
import requests
from dataclasses import dataclass

from ragbot.outputs.logger import logger
from .base_plugin import PluginType
from .plugin_validator import PluginValidator


@dataclass
class MarketplacePlugin:
    """Representation of a plugin available in the marketplace"""

    id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    downloads: int
    rating: float
    tags: List[str]
    dependencies: List[str]
    download_url: str
    github_url: Optional[str] = None
    website: Optional[str] = None
    license: str = "MIT"
    verified: bool = False


class PluginMarketplace:
    """
    Plugin marketplace for discovering and installing plugins

    Provides functionality for:
    - Plugin discovery and search
    - Remote plugin installation
    - Plugin verification and trust
    - Plugin ratings and reviews
    - Installation management
    """

    def __init__(
        self,
        marketplace_url: str = "https://api.ragbot-marketplace.com",
        local_cache_dir: str = "plugins/marketplace",
    ):
        """
        Initialize plugin marketplace

        Args:
            marketplace_url: URL of the marketplace API
            local_cache_dir: Local directory for caching marketplace data
        """
        self.marketplace_url = marketplace_url
        self.cache_dir = Path(local_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.validator = PluginValidator()
        self.downloaded_plugins: Dict[str, str] = {}  # plugin_id -> local_path

    async def search_plugins(
        self,
        query: str = "",
        plugin_type: Optional[PluginType] = None,
        limit: int = 20,
        sort_by: str = "downloads",
    ) -> List[MarketplacePlugin]:
        """
        Search for plugins in the marketplace

        Args:
            query: Search query string
            plugin_type: Optional plugin type filter
            limit: Maximum number of results
            sort_by: Sort criteria ('downloads', 'rating', 'recent')

        Returns:
            List of marketplace plugins matching criteria
        """
        try:
            # Build search parameters
            params = {
                "q": query,
                "type": plugin_type.value if plugin_type else None,
                "limit": limit,
                "sort": sort_by,
            }

            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            # Make API request
            response = requests.get(
                f"{self.marketplace_url}/search", params=params, timeout=10
            )
            response.raise_for_status()

            # Parse response
            data = response.json()
            plugins = []

            for plugin_data in data.get("plugins", []):
                try:
                    marketplace_plugin = MarketplacePlugin(
                        id=plugin_data["id"],
                        name=plugin_data["name"],
                        version=plugin_data["version"],
                        description=plugin_data["description"],
                        author=plugin_data["author"],
                        plugin_type=PluginType(plugin_data["type"]),
                        downloads=plugin_data.get("download_sum", 0),
                        rating=plugin_data.get("rating", 0.0),
                        tags=plugin_data.get("tags", []),
                        dependencies=plugin_data.get("dependencies", []),
                        download_url=plugin_data["download_url"],
                        github_url=plugin_data.get("github_url"),
                        website=plugin_data.get("website"),
                        license=plugin_data.get("license", "MIT"),
                        verified=plugin_data.get("verified", False),
                    )
                    plugins.append(marketplace_plugin)

                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid plugin data: {e}")

            # Cache results
            await self._cache_search_results(query, plugins)

            return plugins

        except requests.RequestException as e:
            logger.error(f"Marketplace search failed: {e}")
            # Fallback to cached results if available
            return await self._get_cached_search_results(query)

    async def get_plugin_details(self, plugin_id: str) -> Optional[MarketplacePlugin]:
        """
        Get detailed information about a plugin

        Args:
            plugin_id: Plugin identifier

        Returns:
            MarketplacePlugin instance or None if not found
        """
        try:
            # Make API request
            response = requests.get(
                f"{self.marketplace_url}/plugin/{plugin_id}", timeout=10
            )
            response.raise_for_status()

            # Parse response
            plugin_data = response.json()

            marketplace_plugin = MarketplacePlugin(
                id=plugin_data["id"],
                name=plugin_data["name"],
                version=plugin_data["version"],
                description=plugin_data["description"],
                author=plugin_data["author"],
                plugin_type=PluginType(plugin_data["type"]),
                downloads=plugin_data.get("download_sum", 0),
                rating=plugin_data.get("rating", 0.0),
                tags=plugin_data.get("tags", []),
                dependencies=plugin_data.get("dependencies", []),
                download_url=plugin_data["download_url"],
                github_url=plugin_data.get("github_url"),
                website=plugin_data.get("website"),
                license=plugin_data.get("license", "MIT"),
                verified=plugin_data.get("verified", False),
            )

            return marketplace_plugin

        except requests.RequestException as e:
            logger.error(f"Failed to get plugin details for {plugin_id}: {e}")
            return None

    async def install_plugin(
        self, plugin: MarketplacePlugin, install_dir: str = "plugins"
    ) -> Optional[str]:
        """
        Install a plugin from the marketplace

        Args:
            plugin: Marketplace plugin to install
            install_dir: Directory to install plugin to

        Returns:
            Local path to installed plugin or None if failed
        """
        try:
            install_path = Path(install_dir)
            install_path.mkdir(parents=True, exist_ok=True)

            # Download plugin file
            plugin_file = await self._download_plugin(plugin)

            if not plugin_file:
                logger.error(f"Failed to download plugin {plugin.id}")
                return None

            # Validate downloaded plugin
            validation_results = await self.validator.validate_plugin_file(
                str(plugin_file)
            )

            if not validation_results["valid"]:
                logger.error(
                    f"Plugin validation failed: {validation_results['errors']}"
                )
                plugin_file.unlink(missing_ok=True)  # Clean up
                return None

            # Move to install directory
            final_path = install_path / f"{plugin.id}.py"
            plugin_file.rename(final_path)

            # Store download information
            self.downloaded_plugins[plugin.id] = str(final_path)

            logger.info(f"Plugin {plugin.id} installed successfully to {final_path}")
            return str(final_path)

        except Exception as e:
            logger.error(f"Failed to install plugin {plugin.id}: {e}")
            return None

    async def uninstall_plugin(
        self, plugin_id: str, install_dir: str = "plugins"
    ) -> bool:
        """
        Uninstall a plugin

        Args:
            plugin_id: Plugin identifier
            install_dir: Directory where plugin is installed

        Returns:
            True if successful, False otherwise
        """
        try:
            install_path = Path(install_dir)
            plugin_file = install_path / f"{plugin_id}.py"

            if plugin_file.exists():
                plugin_file.unlink()
                logger.info(f"Plugin {plugin_id} uninstalled successfully")

            # Remove from downloads tracking
            if plugin_id in self.downloaded_plugins:
                del self.downloaded_plugins[plugin_id]

            return True

        except Exception as e:
            logger.error(f"Failed to uninstall plugin {plugin_id}: {e}")
            return False

    async def list_installed_plugins(
        self, install_dir: str = "plugins"
    ) -> Dict[str, str]:
        """
        List plugins installed from marketplace

        Args:
            install_dir: Directory to scan for installed plugins

        Returns:
            Dictionary mapping plugin IDs to file paths
        """
        try:
            install_path = Path(install_dir)

            if not install_path.exists():
                return {}

            installed = {}

            for plugin_file in install_path.glob("*.py"):
                # Try to determine plugin ID from file
                plugin_id = plugin_file.stem
                installed[plugin_id] = str(plugin_file)

            return installed

        except Exception as e:
            logger.error(f"Failed to list installed plugins: {e}")
            return {}

    async def verify_plugin_integrity(
        self, plugin_id: str, install_dir: str = "plugins"
    ) -> bool:
        """
        Verify integrity of installed plugin

        Args:
            plugin_id: Plugin identifier
            install_dir: Directory where plugin is installed

        Returns:
            True if integrity check passes, False otherwise
        """
        try:
            install_path = Path(install_dir)
            plugin_file = install_path / f"{plugin_id}.py"

            if not plugin_file.exists():
                logger.warning(f"Plugin file not found: {plugin_file}")
                return False

            # Basic file validation
            validation_results = await self.validator.validate_plugin_file(
                str(plugin_file)
            )

            if not validation_results["valid"]:
                logger.error(
                    f"Plugin integrity check failed: {validation_results['errors']}"
                )
                return False

            logger.info(f"Plugin {plugin_id} integrity check passed")
            return True

        except Exception as e:
            logger.error(f"Integrity check failed for plugin {plugin_id}: {e}")
            return False

    async def _download_plugin(self, plugin: MarketplacePlugin) -> Optional[Path]:
        """
        Download plugin from marketplace

        Args:
            plugin: Plugin to download

        Returns:
            Path to downloaded file or None if failed
        """
        try:
            # Download plugin file
            response = requests.get(plugin.download_url, timeout=30)
            response.raise_for_status()

            # Generate temporary filename
            temp_dir = self.cache_dir / "downloads"
            temp_dir.mkdir(exist_ok=True)

            temp_file = temp_dir / f"{plugin.id}.py"

            # Save downloaded content
            with open(temp_file, "wb") as f:
                f.write(response.content)

            logger.info(f"Plugin {plugin.id} downloaded to {temp_file}")
            return temp_file

        except requests.RequestException as e:
            logger.error(f"Failed to download plugin {plugin.id}: {e}")
            return None

    async def _cache_search_results(
        self, query: str, results: List[MarketplacePlugin]
    ) -> None:
        """Cache search results locally"""
        try:
            cache_file = (
                self.cache_dir
                / f"search_{hashlib.md5(query.encode()).hexdigest()}.json"
            )

            cache_data = {
                "query": query,
                "results": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "version": p.version,
                        "description": p.description,
                        "author": p.author,
                        "type": p.plugin_type.value,
                        "downloads": p.downloads,
                        "rating": p.rating,
                    }
                    for p in results
                ],
                "timestamp": asyncio.get_event_loop().time(),
            }

            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to cache search results: {e}")

    async def _get_cached_search_results(self, query: str) -> List[MarketplacePlugin]:
        """Get cached search results"""
        try:
            cache_file = (
                self.cache_dir
                / f"search_{hashlib.md5(query.encode()).hexdigest():.json}"
            )

            if not cache_file.exists():
                return []

            with open(cache_file, "r") as f:
                cache_data = json.load(f)

            # Check cache age (1 hour expiry)
            cache_age = asyncio.get_event_loop().time() - cache_data["timestamp"]
            if cache_age > 3600:
                return []

            # Convert cached data back to MarketplacePlugin objects
            cached_plugins = []
            for plugin_data in cache_data["results"]:
                marketplace_plugin = MarketplacePlugin(
                    id=plugin_data["id"],
                    name=plugin_data["name"],
                    version=plugin_data["version"],
                    description=plugin_data["description"],
                    author=plugin_data["author"],
                    plugin_type=PluginType(plugin_data["type"]),
                    downloads=plugin_data["downloads"],
                    rating=plugin_data["rating"],
                    tags=[],
                    dependencies=[],
                    download_url=f"{self.marketplace_url}/download/{plugin_data['id']}",
                )
                cached_plugins.append(marketplace_plugin)

            return cached_plugins

        except Exception as e:
            logger.warning(f"Failed to get cached search results: {e}")
            return []
