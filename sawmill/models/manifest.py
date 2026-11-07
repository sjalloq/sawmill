"""Manifest models for the manifest and rules design.

A manifest names a project and its targets. Each target is a plugin plus a
set of log globs (relative to the project root) and rule files (relative to
``.sawmill/rules/``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class Target(BaseModel):
    """A manifest target: one plugin applied to a set of logs.

    ``index`` and ``line`` are provenance fields filled in by the loader.
    """

    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    plugin: StrictStr
    logs: list[StrictStr] = Field(min_length=1)
    rules: list[StrictStr] = []
    fail_on: StrictStr | None = None
    unused_rules: Literal["warn", "ignore"] = "warn"
    plugin_options: dict[str, Any] = {}
    index: int = 0
    line: int | None = None

    @field_validator("name", "plugin")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("logs")
    @classmethod
    def _logs_valid(cls, v: list[str]) -> list[str]:
        for pattern in v:
            if not pattern:
                raise ValueError("logs entries must be non-empty strings")
            if Path(pattern).is_absolute():
                raise ValueError(f"logs glob {pattern!r} must be relative to the project root")
        return v

    def resolve_logs(self, root: Path) -> list[Path]:
        """Expand the log globs under ``root``.

        Returns files only, sorted within each glob and deduplicated across
        globs in order of first appearance.
        """
        seen: set[Path] = set()
        result: list[Path] = []
        for pattern in self.logs:
            for match in sorted(root.glob(pattern)):
                if match.is_file() and match not in seen:
                    seen.add(match)
                    result.append(match)
        return result

    def rule_paths(self, rules_dir: Path) -> list[Path]:
        """Return this target's own rule files resolved under ``rules_dir``."""
        return [rules_dir / name for name in self.rules]


class Manifest(BaseModel):
    """A parsed manifest: project-wide settings plus targets."""

    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    rules: list[StrictStr] = []
    report: StrictStr | None = None
    fail_on: StrictStr | None = None
    targets: list[Target] = []
    path: Path | None = None

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("must be a non-empty string")
        return v

    @property
    def root(self) -> Path:
        """Project root: the directory containing ``.sawmill/``."""
        if self.path is None:
            raise ValueError("manifest has no path")
        return self.path.parent.parent

    @property
    def rules_dir(self) -> Path:
        """Directory holding rule files: ``.sawmill/rules``."""
        if self.path is None:
            raise ValueError("manifest has no path")
        return self.path.parent / "rules"

    def rule_paths(self) -> list[Path]:
        """Return the plugin-wide rule files, in listed order."""
        return [self.rules_dir / name for name in self.rules]

    def rule_paths_for(self, target: Target) -> list[Path]:
        """Return plugin-wide rule files followed by the target's own."""
        return self.rule_paths() + target.rule_paths(self.rules_dir)

    def effective_fail_on(self, target: Target) -> str | None:
        """Return the target's ``fail_on``, else the manifest's, else None."""
        return target.fail_on if target.fail_on is not None else self.fail_on

    def get_target(self, name: str) -> Target | None:
        """Return the target called ``name``, or None."""
        return next((t for t in self.targets if t.name == name), None)

    def report_path(self) -> Path | None:
        """Return the report path resolved against the project root."""
        return self.root / self.report if self.report is not None else None
