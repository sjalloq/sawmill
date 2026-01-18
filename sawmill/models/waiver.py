"""Waiver data models for sawmill.

Waivers are for CI acceptance (pass/fail decisions with audit trail).
They are distinct from suppressions which are for display filtering.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class Waiver(BaseModel):
    """A waiver entry for CI acceptance.

    Waivers indicate that a specific error or warning has been reviewed
    and accepted, so it should not cause CI failure.

    Attributes:
        type: The type of matching to use ("id", "pattern", "file", "hash").
        pattern: The pattern to match against (meaning depends on type).
        reason: Explanation of why this is waived.
        author: Who created this waiver.
        date: When this waiver was created (ISO format string).
        expires: Optional expiration date (ISO format string).
        ticket: Optional reference to issue tracker.
    """

    model_config = ConfigDict(frozen=False)

    type: Literal["id", "pattern", "file", "hash"]
    pattern: str
    reason: str
    author: str
    date: str
    expires: Optional[str] = None
    ticket: Optional[str] = None


class WaiverFile(BaseModel):
    """A collection of waivers loaded from a file.

    Attributes:
        tool: The tool this waiver file is for (e.g., "vivado").
        waivers: List of waiver entries.
        path: Optional path to the source file (for error reporting).
    """

    model_config = ConfigDict(frozen=False)

    tool: Optional[str] = None
    waivers: list[Waiver] = []
    path: Optional[str] = None
