"""FilterEngine for applying regex filters to log messages.

This module provides the core filtering logic that operates on plugin output.
The FilterEngine applies filters, suppressions, and provides statistics.
"""

from __future__ import annotations

import re
from typing import Literal

from sawmill.models.filter_def import FilterDefinition
from sawmill.models.message import Message


class FilterEngine:
    """Engine for applying regex filters to log messages.

    The FilterEngine operates on lists of Message objects provided by plugins.
    It supports single filter matching, multi-filter combinations (AND/OR modes),
    and suppression patterns for hiding unwanted messages.
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

        return [
            msg for msg in messages
            if compiled.search(msg.raw_text)
        ]

    def apply_filters(
        self,
        filters: list[FilterDefinition],
        messages: list[Message],
        mode: Literal["AND", "OR"] = "AND",
    ) -> list[Message]:
        """Apply multiple filters to messages with AND or OR logic.

        Args:
            filters: List of filter definitions to apply.
            messages: List of messages to filter.
            mode: "AND" requires all enabled filters to match,
                  "OR" requires any enabled filter to match.

        Returns:
            List of messages that match according to the mode.
            If no enabled filters, returns all messages.
        """
        # Get only enabled filters
        enabled_filters = [f for f in filters if f.enabled]

        # If no enabled filters, return all messages
        if not enabled_filters:
            return list(messages)

        # Compile all filter patterns
        compiled_filters: list[re.Pattern[str]] = []
        for filt in enabled_filters:
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

    def apply_suppressions(
        self,
        patterns: list[str],
        messages: list[Message],
    ) -> list[Message]:
        """Apply suppression patterns to remove matching messages.

        Suppressions are patterns that indicate messages to hide (exclude).
        This is for display filtering, not CI acceptance (use waivers for that).

        Args:
            patterns: List of regex patterns for messages to suppress.
            messages: List of messages to filter.

        Returns:
            List of messages that do NOT match any suppression pattern.
        """
        if not patterns:
            return list(messages)

        # Compile all suppression patterns
        compiled_patterns: list[re.Pattern[str]] = []
        for pattern in patterns:
            try:
                compiled_patterns.append(re.compile(pattern))
            except re.error:
                # Skip invalid patterns
                continue

        # If no valid patterns, return all messages
        if not compiled_patterns:
            return list(messages)

        return [
            msg for msg in messages
            if not any(cp.search(msg.raw_text) for cp in compiled_patterns)
        ]
