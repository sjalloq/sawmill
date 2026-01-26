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
    The base class provides default implementations for optional hooks and raises
    NotImplementedError for required hooks.

    Subclasses must define:
        name: Unique identifier for the plugin (str)

    Required hooks (must override):
        get_severity_levels(): Define the tool's severity levels

    Optional hooks (have defaults):
        can_handle(): Detection (default: 0.0)
        load_and_parse(): Parsing (default: empty list)
        get_filters(): Pre-defined filters (default: empty list)
        get_grouping_fields(): Grouping options (default: standard fields)
        extract_file_reference(): File ref extraction (default: None)

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

            @hookimpl
            def get_severity_levels(self):
                # REQUIRED: Define severity levels (0 = lowest, N-1 = highest)
                return [
                    {"id": "error", "name": "Error", "level": 2, "style": "red bold"},
                    {"id": "warning", "name": "Warning", "level": 1, "style": "yellow"},
                    {"id": "info", "name": "Info", "level": 0, "style": "cyan"},
                ]
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

    @hookimpl
    def get_severity_levels(self) -> list[dict]:
        """REQUIRED: Return the severity levels for this tool.

        Plugins MUST override this method to define their severity levels.
        The base app uses these levels for filtering, sorting, and display.

        Level numbering contract:
            Levels MUST be consecutive integers starting at 0.
            Level 0 is the lowest severity (informational/note).
            Higher numbers indicate more severe levels.

        Returns:
            List of severity level dictionaries, each containing:
            - id: Internal identifier (lowercase, e.g., "error", "warning")
            - name: Human-readable display name (e.g., "Error", "Warning")
            - level: Numeric level for comparison (0 = lowest, higher = more severe)
            - style: Rich style string for terminal display (e.g., "red bold")

        Raises:
            NotImplementedError: If not overridden by subclass.

        Example:
            return [
                {"id": "error", "name": "Error", "level": 2, "style": "red bold"},
                {"id": "warning", "name": "Warning", "level": 1, "style": "yellow"},
                {"id": "info", "name": "Info", "level": 0, "style": "cyan"},
            ]
        """
        raise NotImplementedError(
            f"Plugin '{self.name}' must implement get_severity_levels(). "
            "This hook is required to define the tool's severity levels."
        )

    @hookimpl
    def get_grouping_fields(self) -> list[dict]:
        """Return available grouping fields for this tool.

        Plugins can override this to provide custom grouping options.
        The default implementation provides standard fields: severity, id, file, category.

        Returns:
            List of grouping field dictionaries, each containing:
            - id: Field identifier (used in --group-by)
            - name: Human-readable display name
            - field_type: "builtin", "metadata", or "file_ref"
            - description: Help text for the field

        Example:
            return [
                {"id": "severity", "name": "Severity", "field_type": "builtin",
                 "description": "Group by message severity level"},
                {"id": "hierarchy", "name": "Design Hierarchy", "field_type": "metadata",
                 "description": "Group by RTL hierarchy path"},
            ]
        """
        # Default grouping fields available for all plugins
        return [
            {
                "id": "severity",
                "name": "Severity",
                "field_type": "builtin",
                "description": "Group by message severity level",
            },
            {
                "id": "id",
                "name": "Message ID",
                "field_type": "builtin",
                "description": "Group by tool-specific message ID",
            },
            {
                "id": "file",
                "name": "Source File",
                "field_type": "file_ref",
                "description": "Group by source file path",
            },
            {
                "id": "category",
                "name": "Category",
                "field_type": "builtin",
                "description": "Group by message category",
            },
        ]
