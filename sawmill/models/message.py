"""Message and FileRef data models for sawmill.

These models represent the core data structures for log messages.
Plugins create Message instances; the base app is just an orchestrator.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FileRef(BaseModel):
    """Reference to a source file location extracted from a log message."""

    model_config = ConfigDict(frozen=True)

    path: str
    line: Optional[int] = None


class Message(BaseModel):
    """A logical log message (single or multi-line).

    Plugins handle grouping of multi-line messages and create Message instances.
    The base app operates on these as complete logical units.

    Attributes:
        start_line: First line number in the source log file (1-indexed).
        end_line: Last line number in the source log file (1-indexed).
        raw_text: Complete original text including all lines.
        content: Extracted/cleaned message content.
        severity: Severity level (e.g., "error", "warning", "info", "critical_warning").
        message_id: Tool-specific message ID (e.g., "Vivado 12-3523").
        category: Optional category for grouping (e.g., "timing", "drc").
        file_ref: Optional reference to source file mentioned in message.
        metadata: Plugin-specific metadata for custom grouping/filtering.
            Plugins can populate this with tool-specific fields like
            "hierarchy", "phase", "clock_domain", etc.
    """

    model_config = ConfigDict(frozen=False)

    start_line: int
    end_line: int
    raw_text: str
    content: str
    severity: Optional[str] = None
    message_id: Optional[str] = None
    category: Optional[str] = None
    file_ref: Optional[FileRef] = None
    metadata: dict[str, str] = {}

    def matches_filter(self, pattern: str, case_sensitive: bool = True) -> bool:
        """Check if this message matches the given regex pattern.

        Matches are performed against the raw_text (full original message).

        Args:
            pattern: Regular expression pattern to match.
            case_sensitive: Whether to perform case-sensitive matching.

        Returns:
            True if the pattern matches, False otherwise.
        """
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return bool(re.search(pattern, self.raw_text, flags))
        except re.error:
            return False

    def get_field_value(self, field_id: str) -> str | None:
        """Get the value of a field by its ID.

        This method supports both builtin fields and metadata fields,
        allowing plugins to define custom grouping dimensions.

        Args:
            field_id: The field identifier. Can be:
                - "severity", "message_id", "category" (builtin)
                - "file" (uses file_ref.path)
                - Any key in the metadata dict

        Returns:
            The field value as a string, or None if not set.
        """
        # Builtin fields
        if field_id == "severity":
            return self.severity
        elif field_id == "message_id" or field_id == "id":
            return self.message_id
        elif field_id == "category":
            return self.category
        elif field_id == "file":
            return self.file_ref.path if self.file_ref else None
        # Metadata fields
        elif field_id in self.metadata:
            return self.metadata[field_id]
        else:
            return None
