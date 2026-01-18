"""Plugin management for sawmill.

This module provides the PluginManager class that handles plugin discovery
via Python entry points and registration with pluggy.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pluggy

from sawmill.plugin import SawmillHookSpec, SawmillPlugin

if TYPE_CHECKING:
    pass

# Entry point group name for sawmill plugins
ENTRY_POINT_GROUP = "sawmill.plugins"


class PluginError(Exception):
    """Base exception for plugin-related errors."""


class PluginConflictError(PluginError):
    """Raised when multiple plugins both claim high confidence for a file."""


class NoPluginFoundError(PluginError):
    """Raised when no plugin can handle a file."""


class PluginManager:
    """Manages plugin discovery and registration.

    This class handles:
    - Discovering plugins via Python entry points
    - Registering plugins with pluggy
    - Listing available plugins
    - Calling plugin hooks

    Example:
        manager = PluginManager()
        manager.discover()  # Find and register entry point plugins
        manager.register(MyPlugin())  # Manually register a plugin

        # List available plugins
        for name in manager.list_plugins():
            print(name)

        # Call hooks
        results = manager.pm.hook.can_handle(path=Path("test.log"))
    """

    def __init__(self) -> None:
        """Initialize the plugin manager."""
        self.pm = pluggy.PluginManager("sawmill")
        self.pm.add_hookspecs(SawmillHookSpec)
        self._plugins: dict[str, SawmillPlugin] = {}

    def register(self, plugin: SawmillPlugin) -> None:
        """Register a plugin instance.

        Args:
            plugin: The plugin instance to register.
        """
        name = plugin.name
        self._plugins[name] = plugin
        self.pm.register(plugin, name=name)

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name.

        Args:
            name: The name of the plugin to unregister.
        """
        if name in self._plugins:
            plugin = self._plugins.pop(name)
            self.pm.unregister(plugin)

    def discover(self) -> list[str]:
        """Discover and register plugins from entry points.

        Scans the 'sawmill.plugins' entry point group and registers
        any plugins found.

        Returns:
            List of discovered plugin names.
        """
        discovered = []

        if sys.version_info >= (3, 10):
            from importlib.metadata import entry_points

            eps = entry_points(group=ENTRY_POINT_GROUP)
        else:
            from importlib.metadata import entry_points

            all_eps = entry_points()
            eps = all_eps.get(ENTRY_POINT_GROUP, [])

        for ep in eps:
            try:
                plugin_class = ep.load()
                plugin_instance = plugin_class()
                self.register(plugin_instance)
                discovered.append(plugin_instance.name)
            except Exception:
                # Skip plugins that fail to load
                pass

        return discovered

    def list_plugins(self) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names.
        """
        return list(self._plugins.keys())

    def get_plugin(self, name: str) -> SawmillPlugin | None:
        """Get a plugin by name.

        Args:
            name: The name of the plugin.

        Returns:
            The plugin instance, or None if not found.
        """
        return self._plugins.get(name)

    def get_plugin_info(self, name: str) -> dict[str, str] | None:
        """Get information about a plugin.

        Args:
            name: The name of the plugin.

        Returns:
            Dictionary with plugin info (name, version, description),
            or None if not found.
        """
        plugin = self._plugins.get(name)
        if plugin is None:
            return None

        return {
            "name": plugin.name,
            "version": getattr(plugin, "version", "0.0.0"),
            "description": getattr(plugin, "description", ""),
        }
