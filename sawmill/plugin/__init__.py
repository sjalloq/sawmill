"""Plugin system for sawmill.

This module provides the plugin infrastructure using pluggy.
Plugins implement hooks defined in hookspec.py to provide log parsing capabilities.

Usage:
    from sawmill.plugin import SawmillPlugin, hookimpl

    class MyPlugin(SawmillPlugin):
        name = "my-plugin"

        @hookimpl
        def can_handle(self, path):
            return 0.9 if "mylog" in str(path) else 0.0

        @hookimpl
        def load_and_parse(self, path):
            # Parse the log file
            return [...]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pluggy

from sawmill.plugin.hookspec import SawmillHookSpec

if TYPE_CHECKING:
    from sawmill.models.filter_def import FilterDefinition
    from sawmill.models.message import FileRef, Message

# Create the hookimpl marker for plugins to use
hookimpl = pluggy.HookimplMarker("sawmill")

# Export SawmillHookSpec for use by the PluginManager
__all__ = ["SawmillPlugin", "hookimpl", "SawmillHookSpec"]


class SawmillPlugin:
    """Base class for sawmill plugins.

    Plugins should inherit from this class and override the hooks they implement.
    The base class provides default implementations that opt-out (return empty/None).

    Subclasses must define:
        name: Unique identifier for the plugin (str)

    Optional attributes:
        version: Plugin version string (str)
        description: Human-readable description (str)

    Example:
        class VivadoPlugin(SawmillPlugin):
            name = "vivado"
            version = "1.0.0"
            description = "Parser for Xilinx Vivado logs"

            @hookimpl
            def can_handle(self, path):
                # Check if this is a Vivado log
                ...
    """

    name: str = "base"
    version: str = "0.0.0"
    description: str = ""

    @hookimpl
    def can_handle(self, path: Path) -> float:
        """Default implementation: cannot handle any files.

        Subclasses should override this to return a confidence score
        for files they can parse.

        Args:
            path: Path to the log file to check.

        Returns:
            0.0 (cannot handle) by default.
        """
        return 0.0

    @hookimpl
    def load_and_parse(self, path: Path) -> list["Message"]:
        """Default implementation: returns empty list.

        Subclasses should override this to parse the log file.

        Args:
            path: Path to the log file to parse.

        Returns:
            Empty list by default.
        """
        return []

    @hookimpl
    def get_filters(self) -> list["FilterDefinition"]:
        """Default implementation: returns empty list.

        Subclasses should override this to provide pre-defined filters.

        Returns:
            Empty list by default.
        """
        return []

    @hookimpl
    def extract_file_reference(self, content: str) -> "FileRef | None":
        """Default implementation: returns None.

        Subclasses should override this to extract file references.

        Args:
            content: The message content to search.

        Returns:
            None by default.
        """
        return None
