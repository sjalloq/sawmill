"""FilterEngine for applying regex filters to log messages.

This module provides the core filtering logic that operates on plugin output.
The FilterEngine applies regex filters to messages.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Literal

from sawmill.models.filter_def import FilterDefinition
from sawmill.models.message import Message


class FilterEngine:
    """Engine for applying regex filters to log messages.

    The FilterEngine operates on lists of Message objects provided by plugins.
    It supports single filter matching and multi-filter combinations (AND/OR modes).
    """

    def apply_filter(
        self,
        pattern: str,
        messages: list[Message],
        case_sensitive: bool = True,
    ) -> list[Message]:
        """Apply a single regex filter to messages.

        Args:
            pattern: Regular expression pattern to match against message raw_text.
            messages: List of messages to filter.
            case_sensitive: Whether to perform case-sensitive matching.

        Returns:
            List of messages that match the pattern.
            Returns empty list if pattern is invalid regex.
        """
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
        except re.error:
            # Invalid regex returns empty results
            return []

        return [msg for msg in messages if compiled.search(msg.raw_text)]

    def apply_filters(
        self,
        filters: list[FilterDefinition],
        messages: list[Message],
        mode: Literal["AND", "OR"] = "AND",
        active_ids: set[str] | None = None,
    ) -> list[Message]:
        """Apply multiple filters to messages with AND or OR logic.

        Args:
            filters: List of filter definitions to apply.
            messages: List of messages to filter.
            mode: "AND" requires all active filters to match,
                  "OR" requires any active filter to match.
            active_ids: Set of filter IDs to apply. If None, all filters
                are applied.

        Returns:
            List of messages that match according to the mode.
            If no active filters, returns all messages.
        """
        # Get only active filters
        if active_ids is not None:
            active_filters = [f for f in filters if f.id in active_ids]
        else:
            active_filters = list(filters)

        # If no active filters, return all messages
        if not active_filters:
            return list(messages)

        # Compile all filter patterns
        compiled_filters: list[re.Pattern[str]] = []
        for filt in active_filters:
            try:
                compiled_filters.append(re.compile(filt.pattern))
            except re.error:
                # Skip invalid patterns
                continue

        # If all patterns were invalid, return empty list
        if not compiled_filters:
            return []

        result: list[Message] = []
        for msg in messages:
            if mode == "AND":
                # All filters must match
                if all(cf.search(msg.raw_text) for cf in compiled_filters):
                    result.append(msg)
            else:  # OR mode
                # Any filter must match
                if any(cf.search(msg.raw_text) for cf in compiled_filters):
                    result.append(msg)

        return result


def filter_by_severity_toggles(
    messages: list[Message],
    toggles: dict[str, bool],
) -> list[Message]:
    """Filter messages by severity toggle state.

    Messages with None severity are always included.
    Severity IDs not present in toggles default to True (visible).

    Args:
        messages: List of messages to filter.
        toggles: Dict mapping severity ID to enabled state.

    Returns:
        List of messages whose severity is enabled.
    """
    if not toggles:
        return list(messages)

    return [m for m in messages if m.severity is None or toggles.get(m.severity.lower(), True)]


def match_message_id(message_id: str | None, pattern: str) -> bool:
    """Check if a message ID matches a pattern (supports wildcards).

    Uses fnmatch for glob-style pattern matching:

    - ``*`` matches any sequence of characters
    - ``?`` matches any single character

    Args:
        message_id: The message ID to check (may be None).
        pattern: The pattern to match against (e.g. ``"Synth 8-*"``).

    Returns:
        True if the message ID matches the pattern.
    """
    if message_id is None:
        return False

    return fnmatch.fnmatch(message_id, pattern)
