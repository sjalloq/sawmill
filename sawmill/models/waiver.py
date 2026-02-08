"""Waiver data models for sawmill.

Waivers are for CI acceptance (pass/fail decisions with audit trail).
They are distinct from suppressions which are for display filtering.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Waiver(BaseModel):
    """A waiver entry for CI acceptance.

    Waivers indicate that a specific error or warning has been reviewed
    and accepted, so it should not cause CI failure.

    Every waiver matches on message_id (required). An optional content_pattern
    narrows the match to specific instances of that message ID.

    Attributes:
        message_id: The message ID to match (exact match, required).
        content_match: How to interpret content_pattern ("raw" or "regex").
            None when content_pattern is absent.
        content_pattern: Optional pattern to match against message content.
            If absent/empty, waiver matches all instances of the message_id.
        reason: Explanation of why this is waived.
        author: Who created this waiver.
        date: When this waiver was created (ISO format string).
        expires: Optional expiration date (ISO format string).
        ticket: Optional reference to issue tracker.
    """

    model_config = ConfigDict(frozen=False)

    message_id: str
    content_match: Literal["raw", "regex"] | None = None
    content_pattern: str | None = None
    reason: str
    author: str
    date: str
    expires: str | None = None
    ticket: str | None = None


class WaiverFile(BaseModel):
    """A collection of waivers loaded from a file.

    Attributes:
        tool: The tool this waiver file is for (e.g., "vivado").
        waivers: List of waiver entries.
        path: Optional path to the source file (for error reporting).
    """

    model_config = ConfigDict(frozen=False)

    tool: str | None = None
    waivers: list[Waiver] = []
    path: str | None = None
