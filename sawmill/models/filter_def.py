"""FilterDefinition data model for sawmill.

This model represents filter patterns that can be applied to log messages.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class FilterDefinition(BaseModel):
    """A filter pattern with metadata.

    Plugins can provide filter definitions, and users can also create them.
    Filters are applied by the FilterEngine to select matching messages.

    Attributes:
        id: Unique identifier for the filter.
        name: Human-readable name for display.
        pattern: Regular expression pattern to match.
        enabled: Whether the filter is currently active.
        source: Origin of the filter (e.g., "plugin:vivado", "config", "user").
        description: Optional description of what this filter matches.
    """

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    pattern: str
    enabled: bool = True
    source: Optional[str] = None
    description: Optional[str] = None

    @field_validator("pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        """Validate that the pattern is a valid regular expression."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e
        return v
