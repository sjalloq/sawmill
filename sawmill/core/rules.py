"""Rule file loading and validation.

Rule files are TOML with a ``[rules]`` header table and ``[[rule]]`` entries.
Every error is reported as :class:`RuleValidationError` with the file path,
line number and rule index where they are known.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import tomli
import tomlkit
from pydantic import ValidationError

from sawmill.models.rule import Rule, RuleFile

_RULE_HEADER_RE = re.compile(r"^[ \t]*\[\[rule\]\]", re.MULTILINE)
_RULES_HEADER_RE = re.compile(r"^[ \t]*\[rules\]", re.MULTILINE)
_APPEND_ORDER = (
    "id",
    "regex",
    "file",
    "logs",
    "severity",
    "max_count",
    "per",
    "comment",
    "author",
    "date",
    "name",
)
_HEADER_KEYS = {"plugin"}
_RULE_KEYS = {
    "id",
    "regex",
    "file",
    "logs",
    "severity",
    "max_count",
    "per",
    "comment",
    "author",
    "date",
    "name",
}


class RuleValidationError(Exception):
    """Exception raised for rule file validation errors.

    Attributes:
        message: Error description
        line: Line number where error occurred (if available)
        path: Path to the rule file (if available)
        rule_index: 0-based index of the rule with the error (if available)
    """

    def __init__(
        self,
        message: str,
        line: int | None = None,
        path: Path | None = None,
        rule_index: int | None = None,
    ):
        self.message = message
        self.line = line
        self.path = path
        self.rule_index = rule_index

        parts = []
        if path:
            parts.append(f"Error in {path}")
        if rule_index is not None:
            parts.append(f"rule {rule_index + 1}")
        if line is not None:
            parts.append(f"at line {line}")
        full_message = f"{' '.join(parts)}: {message}" if parts else message
        super().__init__(full_message)


class RuleLoader:
    """Loads and validates rule files."""

    def load(self, path: Path) -> RuleFile:
        """Load rules from a TOML file.

        Args:
            path: Path to the rule file

        Returns:
            RuleFile with parsed rules

        Raises:
            FileNotFoundError: If the file does not exist
            RuleValidationError: If the file is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")
        return self.load_from_string(path.read_text(encoding="utf-8"), path)

    def load_from_string(self, content: str, path: Path | None = None) -> RuleFile:
        """Load rules from a TOML string.

        Args:
            content: TOML content
            path: Optional path for provenance and error reporting

        Returns:
            RuleFile with parsed rules

        Raises:
            RuleValidationError: If the content is invalid
        """
        try:
            data = tomli.loads(content)
        except tomli.TOMLDecodeError as e:
            line = self._extract_line_number(str(e))
            raise RuleValidationError(f"Invalid TOML: {e}", line=line, path=path) from e
        return self._parse(data, content, path)

    def _parse(self, data: dict[str, Any], content: str, path: Path | None) -> RuleFile:
        """Validate parsed TOML data and build a RuleFile."""
        header_match = _RULES_HEADER_RE.search(content)
        header_line = self._line_of(content, header_match.start()) if header_match else None
        rule_lines = [self._line_of(content, m.start()) for m in _RULE_HEADER_RE.finditer(content)]

        unknown_top = sorted(set(data) - {"rules", "rule"})
        if unknown_top:
            raise RuleValidationError(
                f"Unknown top-level key(s): {', '.join(unknown_top)}", path=path
            )

        header = data.get("rules")
        if not isinstance(header, dict):
            raise RuleValidationError("Missing [rules] table", line=header_line, path=path)
        unknown = sorted(set(header) - _HEADER_KEYS)
        if unknown:
            raise RuleValidationError(
                f"Unknown key(s) in [rules]: {', '.join(unknown)}", line=header_line, path=path
            )
        plugin = header.get("plugin")
        if not isinstance(plugin, str) or not plugin:
            raise RuleValidationError(
                "[rules] requires a non-empty string 'plugin'", line=header_line, path=path
            )

        entries = data.get("rule", [])
        if not isinstance(entries, list) or not all(isinstance(r, dict) for r in entries):
            raise RuleValidationError("'rule' must be an array of [[rule]] tables", path=path)

        rules = []
        for index, entry in enumerate(entries):
            line = rule_lines[index] if index < len(rule_lines) else None
            rules.append(self._parse_rule(entry, index, line, path))
        return RuleFile(plugin=plugin, rules=rules, path=path)

    def _parse_rule(
        self, entry: dict[str, Any], index: int, line: int | None, path: Path | None
    ) -> Rule:
        """Validate one [[rule]] table and build a Rule."""
        unknown = sorted(set(entry) - _RULE_KEYS)
        if unknown:
            raise RuleValidationError(
                f"Unknown key(s): {', '.join(unknown)}", line=line, path=path, rule_index=index
            )
        try:
            return Rule(**entry, source=path, index=index, line=line)
        except ValidationError as e:
            raise RuleValidationError(
                self._format_validation_error(e), line=line, path=path, rule_index=index
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


def append_rule(path: Path, rule: Rule, plugin: str) -> None:
    """Append one ``[[rule]]`` block to a rule file, preserving its content.

    The file is created with a ``[rules]`` header when missing. Existing
    content and comments are kept, the write is atomic, and the result is
    reloaded to validate it.

    Args:
        path: Rule file to append to.
        rule: The rule to append; provenance fields are not written.
        plugin: Plugin the file must belong to.

    Raises:
        RuleValidationError: If the file belongs to another plugin, is not
            valid TOML, or is invalid after the append.
    """
    if path.exists():
        try:
            doc = tomlkit.parse(path.read_text(encoding="utf-8"))
        except tomlkit.exceptions.TOMLKitError as e:
            raise RuleValidationError(f"Invalid TOML: {e}", path=path) from e
        header = doc.get("rules")
        owner = header.get("plugin") if isinstance(header, dict) else None
        if owner != plugin:
            raise RuleValidationError(
                f"file belongs to plugin '{owner}', not '{plugin}'", path=path
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = tomlkit.document()
        header_table = tomlkit.table()
        header_table.add("plugin", plugin)
        doc.add("rules", header_table)

    entry = tomlkit.table()
    for key in _APPEND_ORDER:
        if key == "per":
            if rule.max_count is not None:
                entry.add("per", rule.per)
            continue
        value = getattr(rule, key)
        if value is None:
            continue
        if key == "logs":
            arr = tomlkit.array()
            arr.extend(value)
            entry.add(key, arr)
        else:
            entry.add(key, value)

    existing = doc.get("rule")
    if existing is None:
        aot = tomlkit.aot()
        aot.append(entry)
        doc.append("rule", aot)
    else:
        existing.append(entry)

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(tomlkit.dumps(doc))
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    RuleLoader().load(path)


def ensure_rule_file(path: Path, plugin: str) -> None:
    """Create ``path`` with a ``[rules]`` header for ``plugin`` if it is missing.

    An existing file is left untouched.

    Args:
        path: Rule file to create.
        plugin: Plugin the new file belongs to.
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'[rules]\nplugin = "{plugin}"\n', encoding="utf-8")
