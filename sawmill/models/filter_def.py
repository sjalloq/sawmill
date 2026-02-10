"""FilterDefinition data model for sawmill.

This model represents filter patterns that can be applied to log messages.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


class FilterDefinition(BaseModel):
    """A filter pattern with metadata.

    Plugins can provide filter definitions, and users can also create them.
    Filters are applied by the FilterEngine to select matching messages.

    Attributes:
        id: Unique identifier for the filter.
        name: Human-readable name for display.
        pattern: Regular expression pattern to match.
        source: Origin of the filter (e.g., "plugin:vivado", "config", "user").
        description: Optional description of what this filter matches.
    """

    id: str
    name: str
    pattern: str
    source: str | None = None
    description: str | None = None

    @field_validator("pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        """Validate that the pattern is a valid regular expression."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e
        return v
