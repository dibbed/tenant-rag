"""Unit tests for RAGBot plugin architecture, lifecycle, and hook execution."""

import pytest
from typing import Dict, Any, Optional

from ragbot.plugins.base_plugin import (
    BasePlugin,
    PluginContext,
    PluginMetadata,
    PluginResult,
    PluginStatus,
    PluginType,
    HookType,
)
from ragbot.plugins.plugin_manager import PluginManager
from ragbot.plugins.plugin_registry import PluginRegistry


class MockRAGPlugin(BasePlugin):
    """A mock plugin implementing RAG query and ingest hooks."""

    def __init__(self, plugin_id: str = "mock_rag_plugin", config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)
        self.pre_query_called = 0
        self.post_query_called = 0

    @property
    def plugin_name(self) -> str:
        return "Mock RAG Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return "Test plugin for RAG query and ingest hooks"

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.QUERY_ENHANCEMENT

    async def initialize(self, context: PluginContext) -> bool:
        self.register_hook(HookType.PRE_QUERY, self.on_pre_query)
        self.register_hook(HookType.POST_QUERY, self.on_post_query)
        return True

    async def on_pre_query(self, context: PluginContext) -> PluginResult:
        self.pre_query_called += 1
        query = context.data.get("query", "") if context.data else ""
        return PluginResult(
            success=True,
            data={"annotated_query": f"enhanced_{query}"},
        )

    async def on_post_query(self, context: PluginContext) -> PluginResult:
        self.post_query_called += 1
        return PluginResult(
            success=True,
            data={"status": "completed"},
        )

    async def execute(self, context: PluginContext) -> PluginResult:
        return PluginResult(success=True, data="executed")

    async def cleanup(self) -> bool:
        return True


class FailingHookPlugin(BasePlugin):
    """A mock plugin whose hook raises an exception to test failure isolation."""

    def __init__(self, plugin_id: str = "failing_plugin", config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)

    @property
    def plugin_name(self) -> str:
        return "Failing Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return "Plugin designed to test observable failure isolation"

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.SECURITY_PLUGIN

    async def initialize(self, context: PluginContext) -> bool:
        self.register_hook(HookType.PRE_QUERY, self.on_exploding_hook)
        return True

    async def on_exploding_hook(self, context: PluginContext) -> PluginResult:
        raise RuntimeError("Deliberate hook failure for testing failure isolation")

    async def execute(self, context: PluginContext) -> PluginResult:
        return PluginResult(success=False, error_message="Execution failed")

    async def cleanup(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_plugin_metadata_and_initialization():
    """Verify plugin metadata and hook registration."""
    plugin = MockRAGPlugin()
    assert plugin.plugin_name == "Mock RAG Plugin"
    assert plugin.plugin_version == "1.0.0"
    assert plugin.plugin_type == PluginType.QUERY_ENHANCEMENT
    assert plugin.status == PluginStatus.INSTALLED

    init_ok = await plugin.initialize(PluginContext(plugin_id=plugin.plugin_id))
    assert init_ok is True
    assert HookType.PRE_QUERY in plugin.hooks
    assert HookType.POST_QUERY in plugin.hooks
    assert len(plugin.hooks[HookType.PRE_QUERY]) == 1


@pytest.mark.asyncio
async def test_plugin_lifecycle_in_manager(tmp_path):
    """Test plugin registration, startup, execution, and cleanup through PluginManager."""
    manager = PluginManager(plugin_directory=str(tmp_path))

    plugin = MockRAGPlugin()
    # Register plugin directly
    await manager.registry.register_plugin(plugin)
    assert plugin.plugin_id in manager.registry.plugins

    # Start plugin
    start_ok = await manager.start_plugin(plugin.plugin_id)
    assert start_ok is True
    assert plugin.status == PluginStatus.ACTIVE
    assert plugin.plugin_id in manager.active_plugins

    # Verify hooks registered in manager
    assert plugin in manager.hook_registry[HookType.PRE_QUERY]
    assert plugin in manager.hook_registry[HookType.POST_QUERY]

    # Execute hook via manager
    context = PluginContext(plugin_id="", data={"query": "test query"})
    results = await manager.execute_hooks(HookType.PRE_QUERY, context)
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].data["annotated_query"] == "enhanced_test query"
    assert plugin.pre_query_called == 1

    # Stop plugin
    stop_ok = await manager.stop_plugin(plugin.plugin_id)
    assert stop_ok is True
    assert plugin.status == PluginStatus.INACTIVE
    assert plugin.plugin_id not in manager.active_plugins
    assert plugin not in manager.hook_registry[HookType.PRE_QUERY]


@pytest.mark.asyncio
async def test_hook_failure_isolation(tmp_path):
    """Verify that a failing plugin hook does not crash the host and is isolated."""
    manager = PluginManager(plugin_directory=str(tmp_path))

    good_plugin = MockRAGPlugin("good_plugin")
    failing_plugin = FailingHookPlugin("failing_plugin")

    await manager.registry.register_plugin(good_plugin)
    await manager.registry.register_plugin(failing_plugin)

    await manager.start_plugin("good_plugin")
    await manager.start_plugin("failing_plugin")

    # Execute PRE_QUERY hook where both plugins are registered
    context = PluginContext(plugin_id="", data={"query": "safe test"})
    results = await manager.execute_hooks(HookType.PRE_QUERY, context)

    # Should have 2 results: one success, one failure
    assert len(results) == 2
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    assert len(successes) == 1
    assert successes[0].data["annotated_query"] == "enhanced_safe test"

    assert len(failures) == 1
    assert "Deliberate hook failure" in failures[0].error_message or "Hook execution error" in failures[0].error_message
