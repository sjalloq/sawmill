"""Search bar filter parser for the sawmill TUI.

Parses prefix syntax in the search bar:
    sev:error          → filter by severity
    severity:warning   → same (long form)
    id:Synth 8-*       → filter by message ID (fnmatch)
    plain text         → regex on raw_text

Multiple prefixes compose with AND logic.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field


@dataclass
class ParsedFilter:
    """Structured filter parsed from search bar text.

    Attributes:
        severities: Severity IDs to show (from sev:/severity: prefix).
        message_id: Message ID pattern (from id: prefix, supports fnmatch).
        pattern: Remaining text treated as regex on raw_text.
    """

    severities: list[str] = field(default_factory=list)
    message_id: str | None = None
    pattern: str | None = None


def parse_filter(text: str) -> ParsedFilter:
    """Parse search bar text into a structured filter.

    Supports prefixes:
        sev:<id> or severity:<id>  → severity filter
        id:<pattern>               → message ID filter (fnmatch wildcards)
        <text>                     → regex on everything

    Args:
        text: Raw search bar input.

    Returns:
        ParsedFilter with parsed components.
    """
    if not text or not text.strip():
        return ParsedFilter()

    result = ParsedFilter()
    remaining: list[str] = []

    # Use shlex to handle quoted strings, but fall back to simple split
    # if quotes are unbalanced
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    for token in tokens:
        lower = token.lower()

        # sev: or severity: prefix
        if lower.startswith("sev:") or lower.startswith("severity:"):
            _, _, value = token.partition(":")
            if value:
                result.severities.append(value.lower())

        # id: prefix
        elif lower.startswith("id:"):
            _, _, value = token.partition(":")
            if value:
                result.message_id = value

        else:
            remaining.append(token)

    if remaining:
        result.pattern = " ".join(remaining)

    return result
