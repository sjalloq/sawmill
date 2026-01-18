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
