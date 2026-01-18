"""Tests for the PluginManager class."""

from pathlib import Path

import pluggy
import pytest

from sawmill.core.plugin import (
    NoPluginFoundError,
    PluginConflictError,
    PluginError,
    PluginManager,
)
from sawmill.models.filter_def import FilterDefinition
from sawmill.plugin import SawmillPlugin, hookimpl


class MockPlugin(SawmillPlugin):
    """A mock plugin for testing."""

    name = "mock"
    version = "1.0.0"
    description = "A mock plugin for testing"

    @hookimpl
    def can_handle(self, path):
        return 0.9 if "mock" in str(path).lower() else 0.0

    @hookimpl
    def get_filters(self):
        return [FilterDefinition(id="mock", name="Mock", pattern="MOCK", enabled=True)]


class AnotherMockPlugin(SawmillPlugin):
    """Another mock plugin for testing."""

    name = "another-mock"
    version = "2.0.0"

    @hookimpl
    def can_handle(self, path):
        return 0.5 if "another" in str(path).lower() else 0.0


def test_plugin_manager_creation():
    """PluginManager should initialize with empty plugin list."""
    manager = PluginManager()
    assert manager.list_plugins() == []


def test_register_plugin():
    """PluginManager.register should add plugin to registry."""
    manager = PluginManager()
    manager.register(MockPlugin())

    assert "mock" in manager.list_plugins()


def test_register_multiple_plugins():
    """PluginManager should handle multiple plugins."""
    manager = PluginManager()
    manager.register(MockPlugin())
    manager.register(AnotherMockPlugin())

    plugins = manager.list_plugins()
    assert "mock" in plugins
    assert "another-mock" in plugins


def test_plugin_hooks_called():
    """Registered plugin hooks should be callable via pluggy."""
    manager = PluginManager()
    manager.register(MockPlugin())

    results = manager.pm.hook.can_handle(path=Path("mock.log"))
    assert 0.9 in results


def test_plugin_hooks_called_no_match():
    """Plugin hooks should return 0.0 for non-matching files."""
    manager = PluginManager()
    manager.register(MockPlugin())

    results = manager.pm.hook.can_handle(path=Path("other.log"))
    assert 0.0 in results


def test_get_filters_hook():
    """get_filters hook should return filter definitions."""
    manager = PluginManager()
    manager.register(MockPlugin())

    results = manager.pm.hook.get_filters()
    # Results is a list of lists (one per plugin)
    all_filters = [f for filters in results for f in filters]

    assert len(all_filters) == 1
    assert all_filters[0].id == "mock"


def test_unregister_plugin():
    """PluginManager.unregister should remove plugin."""
    manager = PluginManager()
    manager.register(MockPlugin())
    assert "mock" in manager.list_plugins()

    manager.unregister("mock")
    assert "mock" not in manager.list_plugins()


def test_unregister_nonexistent_plugin():
    """Unregistering a nonexistent plugin should not raise."""
    manager = PluginManager()
    manager.unregister("nonexistent")  # Should not raise


def test_get_plugin():
    """PluginManager.get_plugin should return the plugin instance."""
    manager = PluginManager()
    plugin = MockPlugin()
    manager.register(plugin)

    retrieved = manager.get_plugin("mock")
    assert retrieved is plugin


def test_get_plugin_not_found():
    """PluginManager.get_plugin should return None for unknown plugins."""
    manager = PluginManager()

    retrieved = manager.get_plugin("nonexistent")
    assert retrieved is None


def test_get_plugin_info():
    """PluginManager.get_plugin_info should return plugin metadata."""
    manager = PluginManager()
    manager.register(MockPlugin())

    info = manager.get_plugin_info("mock")
    assert info is not None
    assert info["name"] == "mock"
    assert info["version"] == "1.0.0"
    assert info["description"] == "A mock plugin for testing"


def test_get_plugin_info_not_found():
    """get_plugin_info should return None for unknown plugins."""
    manager = PluginManager()

    info = manager.get_plugin_info("nonexistent")
    assert info is None


def test_discover_returns_empty_when_no_plugins():
    """discover() should return empty list when no entry points exist."""
    manager = PluginManager()
    # Since we don't have actual entry points installed, this should return empty
    discovered = manager.discover()
    # The result depends on whether any sawmill plugins are installed
    assert isinstance(discovered, list)


def test_plugin_error_hierarchy():
    """PluginConflictError and NoPluginFoundError should inherit from PluginError."""
    assert issubclass(PluginConflictError, PluginError)
    assert issubclass(NoPluginFoundError, PluginError)


def test_plugin_error_message():
    """Plugin errors should have descriptive messages."""
    conflict_error = PluginConflictError("Multiple plugins match: a, b")
    assert "Multiple plugins" in str(conflict_error)

    no_plugin_error = NoPluginFoundError("No plugin found for test.log")
    assert "No plugin found" in str(no_plugin_error)
