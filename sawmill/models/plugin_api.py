"""Data models for plugin API definitions.

This module provides structured models for plugin-defined metadata
such as severity levels and grouping fields.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SeverityLevel(BaseModel):
    """Definition of a severity level.

    Plugins use this to declare their severity levels in order from
    most to least severe. This allows the base app to properly order
    and style messages regardless of the tool's naming conventions.

    Level numbering contract:
        Levels MUST be consecutive integers starting at 0.
        Level 0 is the lowest severity (informational/note).
        Higher numbers indicate more severe levels.

    Attributes:
        id: Internal identifier (lowercase, e.g., "error", "warning").
        name: Human-readable display name (e.g., "Error", "Warning").
        level: Numeric level for comparison (0 = lowest, higher = more severe).
        style: Rich style string for terminal display.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    level: int = 0
    style: str = ""


class GroupingField(BaseModel):
    """Definition of a field available for grouping messages.

    Plugins use this to declare what dimensions are available for
    grouping and sorting messages.

    Attributes:
        id: Field identifier (used in CLI as --group-by value).
        name: Human-readable display name.
        field_type: How to extract the value from a Message:
            - "builtin": Use Message.severity, Message.message_id, etc.
            - "metadata": Use Message.metadata[id]
            - "file_ref": Use Message.file_ref.path
        description: Optional description for help text.
        sort_order: Optional list of values for custom sort ordering.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    field_type: Literal["builtin", "metadata", "file_ref"] = "builtin"
    description: str = ""
    sort_order: Optional[list[str]] = None


# Default grouping fields used when plugin doesn't provide any
DEFAULT_GROUPING_FIELDS = [
    GroupingField(
        id="severity",
        name="Severity",
        field_type="builtin",
        description="Group by message severity level",
    ),
    GroupingField(
        id="id",
        name="Message ID",
        field_type="builtin",
        description="Group by tool-specific message ID",
    ),
    GroupingField(
        id="file",
        name="Source File",
        field_type="file_ref",
        description="Group by source file path",
    ),
    GroupingField(
        id="category",
        name="Category",
        field_type="builtin",
        description="Group by message category",
    ),
]


def severity_levels_from_dicts(dicts: list[dict]) -> list[SeverityLevel]:
    """Convert a list of dictionaries to SeverityLevel objects.

    Args:
        dicts: List of dictionaries with severity level data.

    Returns:
        List of SeverityLevel objects.
    """
    return [SeverityLevel(**d) for d in dicts]


def grouping_fields_from_dicts(dicts: list[dict]) -> list[GroupingField]:
    """Convert a list of dictionaries to GroupingField objects.

    Args:
        dicts: List of dictionaries with grouping field data.

    Returns:
        List of GroupingField objects.
    """
    return [GroupingField(**d) for d in dicts]
