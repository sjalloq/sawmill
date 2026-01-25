"""Aggregation and grouping utilities for messages.

This module provides classes for aggregating messages by severity, ID, file,
or category - useful for summary views and grouped output.

The Aggregator class can be configured with plugin-provided severity levels
and grouping fields for tool-specific customization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sawmill.models.message import Message
    from sawmill.models.plugin_api import GroupingField, SeverityLevel


# Default severity ordering for display (most severe first)
# Used when plugin doesn't provide custom levels
DEFAULT_SEVERITY_ORDER = ["critical", "critical_warning", "error", "warning", "info"]


def make_severity_sort_key(
    severity_levels: list[SeverityLevel] | None = None,
):
    """Create a severity sort key function.

    Args:
        severity_levels: Optional list of severity levels from plugin.
            If None, uses DEFAULT_SEVERITY_ORDER.

    Returns:
        A function that returns a sort key for a severity string.
    """
    if severity_levels:
        # Build order from plugin-provided levels (highest level = most severe = lowest sort key)
        level_map = {s.id.lower(): -s.level for s in severity_levels}
    else:
        # Use default order (index = sort key)
        level_map = {s: i for i, s in enumerate(DEFAULT_SEVERITY_ORDER)}

    def sort_key(severity: str | None) -> int:
        if severity is None:
            return 999
        sev_lower = severity.lower()
        return level_map.get(sev_lower, 998)  # Unknown severities sort before None

    return sort_key


@dataclass
class MessageStats:
    """Statistics for messages grouped by a key.

    Attributes:
        key: The grouping key (ID, file, category, or severity).
        severity: The severity level for this group (if grouping by ID/file/category).
        count: Number of messages in this group.
        messages: List of messages in this group.
        files_affected: Set of unique files affected by messages in this group.
    """

    key: str
    severity: str | None = None
    count: int = 0
    messages: list = field(default_factory=list)
    files_affected: set = field(default_factory=set)

    def add_message(self, message: Message) -> None:
        """Add a message to this group.

        Args:
            message: The message to add.
        """
        self.count += 1
        self.messages.append(message)
        if message.file_ref:
            self.files_affected.add(message.file_ref.path)


@dataclass
class SeverityStats:
    """Statistics for a severity level with breakdown by message ID.

    Attributes:
        severity: The severity level.
        total: Total count of messages at this severity.
        by_id: Breakdown of counts by message ID.
    """

    severity: str
    total: int = 0
    by_id: dict = field(default_factory=dict)


class Aggregator:
    """Aggregate messages for summary and grouped views.

    This class provides methods to group messages by various fields and
    compute statistics for display. It can be configured with plugin-provided
    severity levels and grouping fields for tool-specific customization.

    Attributes:
        severity_levels: List of severity level definitions from plugin.
        grouping_fields: List of grouping field definitions from plugin.
    """

    def __init__(
        self,
        severity_levels: list[SeverityLevel] | None = None,
        grouping_fields: list[GroupingField] | None = None,
    ):
        """Initialize the aggregator.

        Args:
            severity_levels: Optional list of severity levels from plugin.
            grouping_fields: Optional list of grouping fields from plugin.
        """
        self.severity_levels = severity_levels
        self.grouping_fields = grouping_fields
        self._severity_sort_key = make_severity_sort_key(severity_levels)

    def get_available_groupings(self) -> list[str]:
        """Get list of field IDs available for grouping.

        Returns:
            List of field IDs that can be used with group_by().
        """
        if self.grouping_fields:
            return [f.id for f in self.grouping_fields]
        return ["severity", "id", "file", "category"]

    def get_grouping_field(self, field_id: str) -> GroupingField | None:
        """Get a grouping field definition by ID.

        Args:
            field_id: The field identifier.

        Returns:
            GroupingField if found, None otherwise.
        """
        if self.grouping_fields:
            for f in self.grouping_fields:
                if f.id == field_id:
                    return f
        return None

    def get_severity_style(self, severity: str) -> str:
        """Get the display style for a severity level.

        Args:
            severity: The severity level.

        Returns:
            Rich style string, or empty string if not found.
        """
        if self.severity_levels:
            for s in self.severity_levels:
                if s.id.lower() == severity.lower():
                    return s.style
        # Default styles
        default_styles = {
            "critical": "red bold",
            "critical_warning": "red",
            "error": "red",
            "warning": "yellow",
            "info": "cyan",
        }
        return default_styles.get(severity.lower(), "")

    def get_severity_name(self, severity: str) -> str:
        """Get the display name for a severity level.

        Args:
            severity: The severity level.

        Returns:
            Display name, or title-cased severity if not found.
        """
        if self.severity_levels:
            for s in self.severity_levels:
                if s.id.lower() == severity.lower():
                    return s.name
        return severity.title().replace("_", " ")

    def get_summary(self, messages: list[Message]) -> dict[str, SeverityStats]:
        """Get summary statistics grouped by severity with ID breakdown.

        Args:
            messages: List of messages to summarize.

        Returns:
            Dictionary mapping severity to SeverityStats.
        """
        summary: dict[str, SeverityStats] = {}

        for msg in messages:
            sev = msg.severity.lower() if msg.severity else "other"

            if sev not in summary:
                summary[sev] = SeverityStats(severity=sev)

            summary[sev].total += 1

            # Track by message ID
            msg_id = msg.message_id or "(no id)"
            if msg_id not in summary[sev].by_id:
                summary[sev].by_id[msg_id] = 0
            summary[sev].by_id[msg_id] += 1

        return summary

    def group_by_field(
        self, messages: list[Message], field_id: str
    ) -> dict[str, MessageStats]:
        """Group messages by any field (builtin or metadata).

        This is the generic grouping method that uses Message.get_field_value()
        to support both builtin fields and plugin-defined metadata fields.

        Args:
            messages: List of messages to group.
            field_id: The field to group by.

        Returns:
            Dictionary mapping field value to MessageStats.
        """
        groups: dict[str, MessageStats] = {}

        for msg in messages:
            value = msg.get_field_value(field_id)
            key = value.lower() if value else f"(no {field_id})"

            if key not in groups:
                groups[key] = MessageStats(key=key, severity=msg.severity)

            groups[key].add_message(msg)

        return groups

    def group_by_severity(self, messages: list[Message]) -> dict[str, MessageStats]:
        """Group messages by severity level.

        Args:
            messages: List of messages to group.

        Returns:
            Dictionary mapping severity to MessageStats.
        """
        groups: dict[str, MessageStats] = {}

        for msg in messages:
            sev = msg.severity.lower() if msg.severity else "other"

            if sev not in groups:
                groups[sev] = MessageStats(key=sev, severity=sev)

            groups[sev].add_message(msg)

        return groups

    def group_by_id(self, messages: list[Message]) -> dict[str, MessageStats]:
        """Group messages by message ID.

        Args:
            messages: List of messages to group.

        Returns:
            Dictionary mapping message ID to MessageStats.
        """
        groups: dict[str, MessageStats] = {}

        for msg in messages:
            msg_id = msg.message_id or "(no id)"

            if msg_id not in groups:
                # Use the severity of the first message as the group's severity
                groups[msg_id] = MessageStats(key=msg_id, severity=msg.severity)

            groups[msg_id].add_message(msg)

        return groups

    def group_by_file(self, messages: list[Message]) -> dict[str, MessageStats]:
        """Group messages by source file.

        Messages without file references are grouped under "(no file)".

        Args:
            messages: List of messages to group.

        Returns:
            Dictionary mapping file path to MessageStats.
        """
        groups: dict[str, MessageStats] = {}

        for msg in messages:
            file_path = msg.file_ref.path if msg.file_ref else "(no file)"

            if file_path not in groups:
                groups[file_path] = MessageStats(key=file_path)

            groups[file_path].add_message(msg)

        return groups

    def group_by_category(self, messages: list[Message]) -> dict[str, MessageStats]:
        """Group messages by category.

        Messages without categories are grouped under "(no category)".

        Args:
            messages: List of messages to group.

        Returns:
            Dictionary mapping category to MessageStats.
        """
        groups: dict[str, MessageStats] = {}

        for msg in messages:
            category = msg.category.lower() if msg.category else "(no category)"

            if category not in groups:
                groups[category] = MessageStats(key=category)

            groups[category].add_message(msg)

        return groups

    def group_by(
        self, messages: list[Message], field: str
    ) -> dict[str, MessageStats]:
        """Group messages by the specified field.

        This method supports both builtin fields and plugin-defined metadata
        fields. For builtin fields, it uses optimized methods. For metadata
        fields, it uses the generic group_by_field() method.

        Args:
            messages: List of messages to group.
            field: The field to group by.

        Returns:
            Dictionary mapping field value to MessageStats.

        Raises:
            ValueError: If the field is not a builtin field and not in
                the plugin-provided grouping fields.
        """
        # Check if it's a builtin field with optimized method
        if field == "severity":
            return self.group_by_severity(messages)
        elif field == "id":
            return self.group_by_id(messages)
        elif field == "file":
            return self.group_by_file(messages)
        elif field == "category":
            return self.group_by_category(messages)

        # Check if it's a known metadata field from plugin
        if self.grouping_fields:
            field_def = self.get_grouping_field(field)
            if field_def:
                return self.group_by_field(messages, field)

        # Unknown field - raise error
        raise ValueError(f"Unknown grouping field: {field}")

    def sorted_groups(
        self, groups: dict[str, MessageStats], by_count: bool = True
    ) -> list[tuple[str, MessageStats]]:
        """Sort groups for display.

        Args:
            groups: Dictionary of groups to sort.
            by_count: If True, sort by count descending. If False, sort by key.

        Returns:
            List of (key, stats) tuples in sorted order.
        """
        if by_count:
            return sorted(groups.items(), key=lambda x: (-x[1].count, x[0]))
        else:
            return sorted(groups.items(), key=lambda x: x[0])

    def sorted_summary(
        self, summary: dict[str, SeverityStats]
    ) -> list[tuple[str, SeverityStats]]:
        """Sort summary by severity order.

        Uses plugin-provided severity levels if available, otherwise
        uses default ordering.

        Args:
            summary: Summary dictionary to sort.

        Returns:
            List of (severity, stats) tuples in severity order.
        """
        return sorted(
            summary.items(),
            key=lambda x: self._severity_sort_key(x[0]),
        )


# Backward compatibility: export these for existing code
SEVERITY_ORDER = DEFAULT_SEVERITY_ORDER


def _severity_sort_key(severity: str | None) -> int:
    """Get sort key for severity (lower = more severe).

    This is a backward-compatible function for code that doesn't use
    the Aggregator class. For new code, use make_severity_sort_key()
    or Aggregator with plugin-provided severity levels.
    """
    return make_severity_sort_key()(severity)
