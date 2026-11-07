"""Manifest loading and validation.

Manifests are TOML with a ``[manifest]`` table and ``[[target]]`` entries.
Every error is reported as :class:`ManifestError` with the file path, line
number and target index where they are known.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import tomli
from pydantic import ValidationError

from sawmill.models.manifest import IDENT_RE, Manifest, Target, find_unterminated

_MANIFEST_HEADER_RE = re.compile(r"^[ \t]*\[manifest\]", re.MULTILINE)
_TARGET_HEADER_RE = re.compile(r"^[ \t]*\[\[target\]\]", re.MULTILINE)
_MANIFEST_KEYS = {"name", "rules", "report", "fail_on"}
_TARGET_KEYS = {"name", "plugin", "logs", "rules", "fail_on", "unused_rules", "plugin_options"}


class ManifestError(Exception):
    """Exception raised for manifest validation errors.

    Attributes:
        message: Error description
        line: Line number where error occurred (if available)
        path: Path to the manifest (if available)
        target_index: 0-based index of the target with the error (if available)
    """

    def __init__(
        self,
        message: str,
        line: int | None = None,
        path: Path | None = None,
        target_index: int | None = None,
    ):
        self.message = message
        self.line = line
        self.path = path
        self.target_index = target_index

        parts = []
        if path:
            parts.append(f"Error in {path}")
        if target_index is not None:
            parts.append(f"target {target_index + 1}")
        if line is not None:
            parts.append(f"at line {line}")
        full_message = f"{' '.join(parts)}: {message}" if parts else message
        super().__init__(full_message)


class ManifestLoader:
    """Loads and validates manifest files."""

    def load(self, path: Path) -> Manifest:
        """Load a manifest from a TOML file.

        Args:
            path: Path to the manifest

        Returns:
            Manifest with ``path`` set to the resolved file path

        Raises:
            FileNotFoundError: If the file does not exist
            ManifestError: If the file is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {path}")
        return self.load_from_string(path.read_text(encoding="utf-8"), path.resolve())

    def load_from_string(self, content: str, path: Path | None = None) -> Manifest:
        """Load a manifest from a TOML string.

        Args:
            content: TOML content
            path: Optional manifest path for provenance and error reporting

        Returns:
            Parsed Manifest

        Raises:
            ManifestError: If the content is invalid
        """
        try:
            data = tomli.loads(content)
        except tomli.TOMLDecodeError as e:
            line = self._extract_line_number(str(e))
            raise ManifestError(f"Invalid TOML: {e}", line=line, path=path) from e
        return self._parse(data, content, path)

    def _parse(self, data: dict[str, Any], content: str, path: Path | None) -> Manifest:
        """Validate parsed TOML data and build a Manifest."""
        header_match = _MANIFEST_HEADER_RE.search(content)
        header_line = self._line_of(content, header_match.start()) if header_match else None
        target_lines = [
            self._line_of(content, m.start()) for m in _TARGET_HEADER_RE.finditer(content)
        ]

        unknown_top = sorted(set(data) - {"manifest", "target", "vars"})
        if unknown_top:
            raise ManifestError(f"Unknown top-level key(s): {', '.join(unknown_top)}", path=path)

        header = data.get("manifest")
        if not isinstance(header, dict):
            raise ManifestError("Missing [manifest] table", line=header_line, path=path)
        unknown = sorted(set(header) - _MANIFEST_KEYS)
        if unknown:
            raise ManifestError(
                f"Unknown key(s) in [manifest]: {', '.join(unknown)}", line=header_line, path=path
            )
        if "name" not in header:
            raise ManifestError(
                "[manifest] requires a non-empty string 'name'", line=header_line, path=path
            )

        if isinstance(header.get("report"), str) and find_unterminated(header["report"]):
            raise ManifestError(
                "[manifest] report has an unterminated '${'", line=header_line, path=path
            )

        vars_table = data.get("vars", {})
        if not isinstance(vars_table, dict):
            raise ManifestError("[vars] must be a table", path=path)
        for key, value in vars_table.items():
            if not IDENT_RE.fullmatch(key):
                raise ManifestError(f"[vars] key {key!r} is not a valid identifier", path=path)
            if not isinstance(value, str):
                raise ManifestError(f"[vars] value for {key!r} must be a string", path=path)

        entries = data.get("target", [])
        if not isinstance(entries, list) or not all(isinstance(t, dict) for t in entries):
            raise ManifestError("'target' must be an array of [[target]] tables", path=path)

        targets: list[Target] = []
        names: set[str] = set()
        for index, entry in enumerate(entries):
            line = target_lines[index] if index < len(target_lines) else None
            target = self._parse_target(entry, index, line, path)
            if target.name in names:
                raise ManifestError(
                    f"Duplicate target name {target.name!r}",
                    line=line,
                    path=path,
                    target_index=index,
                )
            names.add(target.name)
            targets.append(target)

        try:
            return Manifest(**header, vars=vars_table, targets=targets, path=path)
        except ValidationError as e:
            raise ManifestError(
                "[manifest] " + self._format_validation_error(e), line=header_line, path=path
            ) from e

    def _parse_target(
        self, entry: dict[str, Any], index: int, line: int | None, path: Path | None
    ) -> Target:
        """Validate one [[target]] table and build a Target."""
        unknown = sorted(set(entry) - _TARGET_KEYS)
        if unknown:
            raise ManifestError(
                f"Unknown key(s): {', '.join(unknown)}", line=line, path=path, target_index=index
            )
        logs = entry.get("logs")
        if isinstance(logs, list):
            for pattern in logs:
                if isinstance(pattern, str) and find_unterminated(pattern):
                    raise ManifestError(
                        f"logs entry {pattern!r} has an unterminated '${{'",
                        line=line,
                        path=path,
                        target_index=index,
                    )
        try:
            return Target(**entry, index=index, line=line)
        except ValidationError as e:
            raise ManifestError(
                self._format_validation_error(e), line=line, path=path, target_index=index
            ) from e

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        """Turn a pydantic error into a short message naming the fields."""
        parts = []
        for err in error.errors():
            loc = ".".join(str(p) for p in err["loc"] if not isinstance(p, int))
            msg = err["msg"].removeprefix("Value error, ")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return "; ".join(parts)

    @staticmethod
    def _line_of(content: str, offset: int) -> int:
        """Return the 1-based line number of a character offset."""
        return content.count("\n", 0, offset) + 1

    def _extract_line_number(self, error_message: str) -> int | None:
        """Extract line number from a tomli error message."""
        match = re.search(r"(?:at )?line (\d+)", error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None
