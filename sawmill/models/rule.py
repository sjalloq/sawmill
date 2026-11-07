"""Rule models for the manifest and rules design.

A rule file targets one plugin and holds a list of rules. Each rule names
match keys (``id``, ``regex``, ``file``, ``logs``, ``severity``), optional
limits (``max_count``, ``per``) and a required ``comment``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

_MATCH_KEYS = ("id", "regex", "file", "logs", "severity")


__all__ = ["Rule", "RuleFile"]


class Rule(BaseModel):
    """A single rule from a rule file.

    Identity is ``(source, index)``. ``source``, ``index`` and ``line`` are
    provenance fields filled in by the loader.
    """

    model_config = ConfigDict(extra="forbid")

    id: StrictStr | None = None
    regex: StrictStr | None = None
    file: StrictStr | None = None
    logs: list[StrictStr] | None = None
    severity: StrictStr | None = None
    max_count: StrictInt | None = Field(default=None, ge=1)
    per: Literal["log", "target"] = "log"
    comment: StrictStr
    author: StrictStr | None = None
    date: StrictStr | None = None
    name: StrictStr | None = None
    source: Path | None = None
    index: int = 0
    line: int | None = None

    @field_validator("comment")
    @classmethod
    def _comment_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("comment must not be empty")
        return v

    @field_validator("regex")
    @classmethod
    def _regex_compiles(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"invalid regex {v!r}: {e}") from e
        return v

    @field_validator("logs")
    @classmethod
    def _logs_not_empty(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and any(not s for s in v):
            raise ValueError("logs entries must be non-empty strings")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> Rule:
        if self.id is None and self.regex is None and self.file is None:
            raise ValueError("rule needs at least one of id, regex or file")
        if "per" in self.model_fields_set and self.max_count is None:
            raise ValueError("per requires max_count")
        return self

    @property
    def display(self) -> str:
        """Short display form: ``<basename>#<n>`` or ``<basename>:<name>``."""
        base = self.source.name if self.source is not None else ""
        if self.name:
            return f"{base}:{self.name}" if base else self.name
        return f"{base}#{self.index + 1}"

    def match_keys(self) -> dict[str, str | list[str]]:
        """Return the match keys present on this rule, for listing."""
        result: dict[str, str | list[str]] = {}
        for key in _MATCH_KEYS:
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result


class RuleFile(BaseModel):
    """A parsed rule file: target plugin plus its rules."""

    plugin: str
    rules: list[Rule] = []
    path: Path | None = None
