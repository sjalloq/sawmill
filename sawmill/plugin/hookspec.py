"""Hook specifications for sawmill plugins.

This module defines the pluggy hook specification that plugins must implement.
Plugins use the @hookimpl decorator to register their implementations.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pluggy

if TYPE_CHECKING:
    from sawmill.models.filter_def import FilterDefinition
    from sawmill.models.message import FileRef, Message

SAWMILL_PLUGIN_API = "2"

hookspec = pluggy.HookspecMarker("sawmill")


class SawmillHookSpec:
    """Hook specification defining the plugin interface.

    Plugins implement these hooks to provide log parsing capabilities.
    The base application calls these hooks through the pluggy PluginManager.
    """

    @hookspec
    def can_handle(self, path: Path) -> float:  # type: ignore[empty-body]
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
        ...

    @hookspec
    def load_and_parse(self, path: Path) -> Iterator[Message]:  # type: ignore[empty-body]
        """Load and parse the log file into messages.

        This is the primary parsing hook. Plugins MUST be generators (or
        otherwise return an iterator) so the base app can stream large
        logs without holding every line in memory at once.

        Implementations should:

        1. Open the file and stream line-by-line (``for line in f``, not
           ``f.readlines()``) so memory is O(in-flight message), not O(file).
        2. Parse each line/section into logical messages.
        3. Group multi-line messages into single Message objects.
        4. Extract severity, message IDs, and other metadata.
        5. ``yield`` each completed Message as soon as it is built.

        Args:
            path: Path to the log file to parse.

        Yields:
            Message objects, each representing a complete logical message
            (single or multi-line). Messages should have start_line and
            end_line set correctly for multi-line messages.
        """
        ...

    @hookspec
    def get_filters(self) -> list[FilterDefinition]:  # type: ignore[empty-body]
        """Get filter definitions provided by this plugin.

        Plugins can provide pre-defined filters for common use cases,
        such as filtering by severity level or message category.

        Returns:
            List of FilterDefinition objects that users can enable/disable.
        """
        ...

    @hookspec
    def extract_file_reference(self, content: str) -> FileRef | None:  # type: ignore[empty-body]
        """Extract a file reference from message content.

        Many log messages reference source files with line numbers.
        This hook extracts that information for navigation.

        Args:
            content: The message content to search for file references.

        Returns:
            FileRef if a reference is found, None otherwise.
        """
        ...

    @hookspec
    def get_severity_levels(self) -> list[dict]:  # type: ignore[empty-body]
        """REQUIRED: Get severity levels supported by this plugin.

        Plugins MUST implement this hook to define their severity levels.
        The base app uses these levels for:

        - Filtering messages by severity in the TUI
        - Sorting and grouping messages
        - Styling output (colours in the terminal)
        - Determining pass/fail in ``sawmill check`` (``fail_on``)

        Level numbering contract: plugins MUST use consecutive integers
        starting at 0. Level 0 is the lowest severity (informational/note).
        Higher numbers indicate more severe levels.

        Returns:
            List of severity definitions with these fields::

                [
                    {
                        "id": "fatal",       # Internal identifier (lowercase)
                        "name": "Fatal",     # Display name
                        "style": "red bold", # Rich style for display
                        "level": 3,          # Numeric level (0 = lowest)
                    },
                    {"id": "error", "name": "Error", "style": "red", "level": 2},
                    {"id": "warning", "name": "Warning", "style": "yellow", "level": 1},
                    {"id": "note", "name": "Note", "style": "cyan", "level": 0},
                ]

            The numeric ``level`` field is used for threshold comparisons:
            ``sawmill check`` defaults to failing on the second-lowest level
            and above, and ``fail_on`` sets the threshold to that severity's
            level.

        Raises:
            NotImplementedError: If not implemented by the plugin.
        """
        ...

    @hookspec
    def get_grouping_fields(self) -> list[dict]:  # type: ignore[empty-body]
        """Get fields available for grouping and sorting.

        Plugins can declare what dimensions are available for grouping
        messages. This includes both standard fields (severity, id, file)
        and custom metadata fields populated by the plugin.

        Standard field types:

        - ``"builtin"``: Uses Message attributes (severity, message_id, category)
        - ``"metadata"``: Uses ``Message.metadata[field_id]``
        - ``"file_ref"``: Uses ``Message.file_ref.path``

        If not implemented, the base app provides default groupings:
        severity, id, file, category.

        Returns:
            List of field definitions::

                [
                    {
                        "id": "severity",     # Field identifier
                        "name": "Severity",   # Display name
                        "type": "builtin",    # "builtin", "metadata", or "file_ref"
                        "description": "Group by message severity level",
                    },
                    {
                        "id": "hierarchy",
                        "name": "Design Hierarchy",
                        "type": "metadata",   # Uses Message.metadata["hierarchy"]
                        "description": "Group by RTL hierarchy path",
                    },
                ]
        """
        ...

    @hookspec
    def configure(self, options: dict) -> None:
        """Configure the plugin for one target before any log is parsed.

        Optional hook. The base app calls it once per manifest target, before
        loading any log, with the target's ``plugin_options`` table from the
        manifest (an empty dict when the target gives none, so a plugin can
        reset state between targets).

        Plugins should validate the options and raise ``ValueError`` with a
        clear message for unknown keys or bad values.

        Args:
            options: The target's ``plugin_options`` table.
        """
