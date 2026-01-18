"""Hook specifications for sawmill plugins.

This module defines the pluggy hook specification that plugins must implement.
Plugins use the @hookimpl decorator to register their implementations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pluggy

if TYPE_CHECKING:
    from sawmill.models.filter_def import FilterDefinition
    from sawmill.models.message import FileRef, Message

hookspec = pluggy.HookspecMarker("sawmill")


class SawmillHookSpec:
    """Hook specification defining the plugin interface.

    Plugins implement these hooks to provide log parsing capabilities.
    The base application calls these hooks through the pluggy PluginManager.
    """

    @hookspec
    def can_handle(self, path: Path) -> float:
        """Determine if this plugin can handle the given log file.

        Plugins should examine the file (name, initial content, etc.) and return
        a confidence score indicating how well they can parse it.

        Args:
            path: Path to the log file to check.

        Returns:
            Confidence score from 0.0 to 1.0:
            - 0.0: Cannot handle this file
            - 0.5: Might be able to handle (ambiguous)
            - 1.0: Definitely can handle this file

            The plugin with the highest confidence score will be selected.
            If no plugin has confidence > 0.5, an error is raised.
        """

    @hookspec
    def load_and_parse(self, path: Path) -> list["Message"]:
        """Load and parse the log file into messages.

        This is the primary parsing hook. Plugins should:
        1. Open and read the file (handling encoding issues)
        2. Parse each line/section into logical messages
        3. Group multi-line messages into single Message objects
        4. Extract severity, message IDs, and other metadata

        Args:
            path: Path to the log file to parse.

        Returns:
            List of Message objects, each representing a complete logical
            message (single or multi-line). Messages should have start_line
            and end_line set correctly for multi-line messages.
        """

    @hookspec
    def get_filters(self) -> list["FilterDefinition"]:
        """Get filter definitions provided by this plugin.

        Plugins can provide pre-defined filters for common use cases,
        such as filtering by severity level or message category.

        Returns:
            List of FilterDefinition objects that users can enable/disable.
        """

    @hookspec
    def extract_file_reference(self, content: str) -> "FileRef | None":
        """Extract a file reference from message content.

        Many log messages reference source files with line numbers.
        This hook extracts that information for navigation.

        Args:
            content: The message content to search for file references.

        Returns:
            FileRef if a reference is found, None otherwise.
        """
