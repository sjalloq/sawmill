"""Waiver loading, parsing, and matching for sawmill.

This module provides:
- WaiverLoader: For reading TOML waiver files and validating waiver entries
- WaiverMatcher: For matching log messages against waivers

Waivers are for CI acceptance (pass/fail decisions with audit trail).
They are distinct from suppressions which are for display filtering.
"""

import hashlib
import re
from pathlib import Path
from typing import Optional

import tomli

from sawmill.models.message import Message
from sawmill.models.waiver import Waiver, WaiverFile


class WaiverValidationError(Exception):
    """Exception raised for waiver file validation errors.

    Attributes:
        message: Error description
        line: Line number where error occurred (if available)
        path: Path to the waiver file (if available)
        waiver_index: Index of the waiver entry with the error (if available)
    """

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        path: Optional[Path] = None,
        waiver_index: Optional[int] = None
    ):
        self.line = line
        self.path = path
        self.waiver_index = waiver_index

        # Build error message with context
        parts = []
        if path:
            parts.append(f"Error in {path}")
        if waiver_index is not None:
            parts.append(f"waiver entry {waiver_index + 1}")
        if line is not None:
            parts.append(f"at line {line}")
        if parts:
            full_message = f"{' '.join(parts)}: {message}"
        else:
            full_message = message

        super().__init__(full_message)


class WaiverLoader:
    """Loader for sawmill TOML waiver files.

    Waiver files use the following format:

        [metadata]
        tool = "vivado"  # Optional, for documentation

        [[waiver]]
        type = "id"              # Required: id, pattern, file, or hash
        pattern = "Vivado 12-3523"  # Required: pattern to match
        reason = "Intentional"   # Required: why this is waived
        author = "user@email"    # Required: who created this waiver
        date = "2026-01-18"      # Required: when this was created
        expires = "2026-06-01"   # Optional: expiration date
        ticket = "PROJ-123"      # Optional: issue tracker reference

    Example usage:
        loader = WaiverLoader()
        waivers = loader.load(Path("waivers.toml"))
    """

    # Valid waiver types
    VALID_TYPES = frozenset({"id", "pattern", "file", "hash"})

    # Required fields for a waiver entry
    REQUIRED_FIELDS = frozenset({"type", "pattern", "reason", "author", "date"})

    def load(self, path: Path) -> WaiverFile:
        """Load waivers from a TOML file.

        Args:
            path: Path to the TOML waiver file

        Returns:
            WaiverFile instance with parsed waivers

        Raises:
            WaiverValidationError: If the file contains invalid TOML or
                waiver entries with missing/invalid fields
            FileNotFoundError: If the file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Waiver file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            data = tomli.loads(content)
        except tomli.TOMLDecodeError as e:
            line = self._extract_line_number(str(e))
            raise WaiverValidationError(
                f"Invalid TOML: {e}",
                line=line,
                path=path
            ) from e

        return self._parse_waiver_file(data, path)

    def load_from_string(self, content: str, path: Optional[Path] = None) -> WaiverFile:
        """Load waivers from a TOML string.

        Args:
            content: TOML content as a string
            path: Optional path for error reporting

        Returns:
            WaiverFile instance with parsed waivers

        Raises:
            WaiverValidationError: If the content contains invalid TOML or
                waiver entries with missing/invalid fields
        """
        try:
            data = tomli.loads(content)
        except tomli.TOMLDecodeError as e:
            line = self._extract_line_number(str(e))
            raise WaiverValidationError(
                f"Invalid TOML: {e}",
                line=line,
                path=path
            ) from e

        return self._parse_waiver_file(data, path)

    def _parse_waiver_file(self, data: dict, path: Optional[Path]) -> WaiverFile:
        """Parse waiver file data into WaiverFile instance.

        Args:
            data: Dictionary parsed from TOML
            path: Path to the source file for error reporting

        Returns:
            WaiverFile instance

        Raises:
            WaiverValidationError: If validation fails
        """
        # Extract metadata
        metadata = data.get("metadata", {})
        tool = metadata.get("tool")

        # Parse waiver entries
        waiver_entries = data.get("waiver", [])

        # Handle single waiver case (TOML returns dict instead of list)
        if isinstance(waiver_entries, dict):
            waiver_entries = [waiver_entries]

        waivers: list[Waiver] = []
        for i, entry in enumerate(waiver_entries):
            waiver = self._parse_waiver_entry(entry, i, path)
            waivers.append(waiver)

        return WaiverFile(
            tool=tool,
            waivers=waivers,
            path=str(path) if path else None
        )

    def _parse_waiver_entry(
        self,
        entry: dict,
        index: int,
        path: Optional[Path]
    ) -> Waiver:
        """Parse and validate a single waiver entry.

        Args:
            entry: Dictionary from TOML waiver entry
            index: Index of this entry in the waiver array
            path: Path to source file for error reporting

        Returns:
            Validated Waiver instance

        Raises:
            WaiverValidationError: If validation fails
        """
        # Check for required fields
        missing_fields = self.REQUIRED_FIELDS - set(entry.keys())
        if missing_fields:
            raise WaiverValidationError(
                f"Missing required fields: {', '.join(sorted(missing_fields))}",
                path=path,
                waiver_index=index
            )

        # Validate type field
        waiver_type = entry.get("type")
        if waiver_type not in self.VALID_TYPES:
            raise WaiverValidationError(
                f"Invalid waiver type '{waiver_type}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_TYPES))}",
                path=path,
                waiver_index=index
            )

        # Validate pattern based on type
        pattern = entry.get("pattern")
        if not pattern or not isinstance(pattern, str):
            raise WaiverValidationError(
                "Pattern must be a non-empty string",
                path=path,
                waiver_index=index
            )

        # For pattern type, validate regex
        if waiver_type == "pattern":
            try:
                re.compile(pattern)
            except re.error as e:
                raise WaiverValidationError(
                    f"Invalid regex pattern: {e}",
                    path=path,
                    waiver_index=index
                ) from e

        # Validate reason
        reason = entry.get("reason")
        if not reason or not isinstance(reason, str):
            raise WaiverValidationError(
                "Reason must be a non-empty string",
                path=path,
                waiver_index=index
            )

        # Validate author
        author = entry.get("author")
        if not author or not isinstance(author, str):
            raise WaiverValidationError(
                "Author must be a non-empty string",
                path=path,
                waiver_index=index
            )

        # Validate date
        date = entry.get("date")
        if not date or not isinstance(date, str):
            raise WaiverValidationError(
                "Date must be a non-empty string",
                path=path,
                waiver_index=index
            )

        # Create and return Waiver instance
        return Waiver(
            type=waiver_type,
            pattern=pattern,
            reason=reason,
            author=author,
            date=date,
            expires=entry.get("expires"),
            ticket=entry.get("ticket")
        )

    def _extract_line_number(self, error_message: str) -> Optional[int]:
        """Extract line number from tomli error message.

        Args:
            error_message: The error message from tomli

        Returns:
            Line number if found, None otherwise
        """
        # tomli error messages often contain "at line N" or "line N"
        match = re.search(r"(?:at )?line (\d+)", error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None


class WaiverMatcher:
    """Matches log messages against waivers.

    The matcher checks messages against a list of waivers and returns the
    first matching waiver, or None if no waiver matches.

    Waivers are matched in priority order:
    1. hash - Exact match on SHA-256 hash of message.raw_text
    2. id - Exact match on message.message_id
    3. pattern - Regex match on message.raw_text
    4. file - Match on message.file_ref.path

    Example usage:
        matcher = WaiverMatcher(waivers)
        waiver = matcher.is_waived(message)
        if waiver:
            print(f"Message waived by: {waiver.reason}")
    """

    def __init__(self, waivers: list[Waiver]):
        """Initialize the matcher with a list of waivers.

        Args:
            waivers: List of Waiver objects to match against
        """
        self._waivers = waivers

        # Pre-organize waivers by type for efficient matching
        self._hash_waivers: list[Waiver] = []
        self._id_waivers: list[Waiver] = []
        self._pattern_waivers: list[Waiver] = []
        self._file_waivers: list[Waiver] = []

        for waiver in waivers:
            if waiver.type == "hash":
                self._hash_waivers.append(waiver)
            elif waiver.type == "id":
                self._id_waivers.append(waiver)
            elif waiver.type == "pattern":
                self._pattern_waivers.append(waiver)
            elif waiver.type == "file":
                self._file_waivers.append(waiver)

    @property
    def waivers(self) -> list[Waiver]:
        """Get the list of waivers."""
        return self._waivers

    def is_waived(self, message: Message) -> Optional[Waiver]:
        """Check if a message is waived.

        Waivers are checked in priority order:
        1. hash - Exact match on SHA-256 hash of message.raw_text
        2. id - Exact match on message.message_id
        3. pattern - Regex match on message.raw_text
        4. file - Match on message.file_ref.path

        The first matching waiver is returned. If no waivers match, None is returned.

        Args:
            message: The Message to check against waivers

        Returns:
            The matching Waiver if found, or None
        """
        # Priority 1: Hash match (highest priority)
        for waiver in self._hash_waivers:
            if self._match_hash(message, waiver):
                return waiver

        # Priority 2: ID match
        for waiver in self._id_waivers:
            if self._match_id(message, waiver):
                return waiver

        # Priority 3: Pattern match
        for waiver in self._pattern_waivers:
            if self._match_pattern(message, waiver):
                return waiver

        # Priority 4: File match (lowest priority)
        for waiver in self._file_waivers:
            if self._match_file(message, waiver):
                return waiver

        return None

    def _match_hash(self, message: Message, waiver: Waiver) -> bool:
        """Check if message matches a hash waiver.

        Args:
            message: The message to check
            waiver: The hash waiver to match against

        Returns:
            True if the SHA-256 hash of message.raw_text matches the waiver pattern
        """
        message_hash = hashlib.sha256(message.raw_text.encode("utf-8")).hexdigest()
        return message_hash == waiver.pattern

    def _match_id(self, message: Message, waiver: Waiver) -> bool:
        """Check if message matches an ID waiver.

        Args:
            message: The message to check
            waiver: The ID waiver to match against

        Returns:
            True if message.message_id exactly matches the waiver pattern
        """
        if message.message_id is None:
            return False
        return message.message_id == waiver.pattern

    def _match_pattern(self, message: Message, waiver: Waiver) -> bool:
        """Check if message matches a pattern (regex) waiver.

        Args:
            message: The message to check
            waiver: The pattern waiver to match against

        Returns:
            True if waiver.pattern regex matches message.raw_text
        """
        try:
            # Use DOTALL flag so '.' matches newlines in multi-line messages
            return bool(re.search(waiver.pattern, message.raw_text, re.DOTALL))
        except re.error:
            # Invalid regex pattern - should not happen if WaiverLoader validated
            return False

    def _match_file(self, message: Message, waiver: Waiver) -> bool:
        """Check if message matches a file waiver.

        The file waiver pattern is matched against the message's file_ref.path.
        The match can be:
        - Exact match
        - Pattern matches end of path (for relative paths)
        - Glob-style wildcards (* matches any characters)

        Args:
            message: The message to check
            waiver: The file waiver to match against

        Returns:
            True if the message's file path matches the waiver pattern
        """
        if message.file_ref is None:
            return False

        file_path = message.file_ref.path
        pattern = waiver.pattern

        # Exact match
        if file_path == pattern:
            return True

        # End match (relative path matching)
        if file_path.endswith(pattern):
            return True

        # Glob-style matching (convert * to regex .*)
        # Escape regex special characters except *
        regex_pattern = re.escape(pattern).replace(r"\*", ".*")
        try:
            return bool(re.fullmatch(regex_pattern, file_path))
        except re.error:
            return False


class WaiverGenerator:
    """Generates waiver TOML from log messages.

    This class creates valid waiver TOML files from a list of messages,
    suitable for CI acceptance workflows. Generated waivers include
    placeholder values for author and reason that users should review
    and update.

    Generated waivers use:
    - type="id" for messages that have a message_id
    - type="hash" for messages without a message_id (SHA-256 of raw_text)

    Example usage:
        generator = WaiverGenerator()
        toml_content = generator.generate(messages)
        print(toml_content)  # Redirect to waivers.toml
    """

    # Severity levels that typically require waivers in CI
    WAIVER_SEVERITIES = frozenset({"error", "critical_warning", "warning"})

    def __init__(
        self,
        author: str = "<author>",
        reason: str = "<reason - explain why this is acceptable>",
        include_info: bool = False,
    ):
        """Initialize the waiver generator.

        Args:
            author: Default author to use in generated waivers.
            reason: Default reason placeholder for generated waivers.
            include_info: If True, include INFO messages in output.
                         By default, only error/warning/critical_warning are included.
        """
        self._author = author
        self._reason = reason
        self._include_info = include_info

    def generate(self, messages: list[Message], tool: Optional[str] = None) -> str:
        """Generate waiver TOML content from messages.

        Only includes messages with severity in WAIVER_SEVERITIES
        (error, critical_warning, warning) unless include_info=True.

        Args:
            messages: List of parsed log messages.
            tool: Optional tool name to include in metadata.

        Returns:
            Valid TOML content as a string.
        """
        from datetime import date

        lines: list[str] = []

        # Add header comment
        lines.append("# Sawmill generated waiver file")
        lines.append("# Review each waiver and update the reason before use")
        lines.append("")

        # Add metadata section
        lines.append("[metadata]")
        if tool:
            lines.append(f'tool = "{self._escape_toml_string(tool)}"')
        lines.append(f'generated = "{date.today().isoformat()}"')
        lines.append("")

        # Filter messages by severity
        filtered = self._filter_messages(messages)

        # Generate waiver entries
        for msg in filtered:
            lines.extend(self._generate_waiver_entry(msg))
            lines.append("")

        return "\n".join(lines)

    def _filter_messages(self, messages: list[Message]) -> list[Message]:
        """Filter messages to those that need waivers.

        Args:
            messages: All parsed messages.

        Returns:
            Messages that need waivers based on severity.
        """
        result: list[Message] = []
        for msg in messages:
            if msg.severity is None:
                continue
            severity = msg.severity.lower()
            if severity in self.WAIVER_SEVERITIES:
                result.append(msg)
            elif self._include_info and severity == "info":
                result.append(msg)
        return result

    def _generate_waiver_entry(self, message: Message) -> list[str]:
        """Generate a single waiver entry for a message.

        Args:
            message: The message to generate a waiver for.

        Returns:
            List of TOML lines for this waiver entry.
        """
        from datetime import date

        lines: list[str] = []
        lines.append("[[waiver]]")

        # Determine waiver type and pattern
        if message.message_id:
            waiver_type = "id"
            pattern = message.message_id
        else:
            waiver_type = "hash"
            pattern = hashlib.sha256(message.raw_text.encode("utf-8")).hexdigest()

        lines.append(f'type = "{waiver_type}"')
        lines.append(f'pattern = "{self._escape_toml_string(pattern)}"')
        lines.append(f'reason = "{self._escape_toml_string(self._reason)}"')
        lines.append(f'author = "{self._escape_toml_string(self._author)}"')
        lines.append(f'date = "{date.today().isoformat()}"')

        # Add comment with message context
        lines.append(f"# Severity: {message.severity or 'unknown'}")
        if message.content:
            # Truncate long content for readability
            content = message.content[:80]
            if len(message.content) > 80:
                content += "..."
            lines.append(f"# Content: {self._escape_comment(content)}")
        lines.append(f"# Line: {message.start_line}")

        return lines

    def _escape_toml_string(self, value: str) -> str:
        """Escape a string for use in TOML.

        Args:
            value: The string to escape.

        Returns:
            Escaped string safe for TOML basic strings.
        """
        # Escape backslashes first, then quotes and other special chars
        result = value.replace("\\", "\\\\")
        result = result.replace('"', '\\"')
        result = result.replace("\n", "\\n")
        result = result.replace("\r", "\\r")
        result = result.replace("\t", "\\t")
        return result

    def _escape_comment(self, value: str) -> str:
        """Escape a string for use in a TOML comment.

        Args:
            value: The string to escape.

        Returns:
            String safe for TOML comments (no newlines).
        """
        # Replace newlines with spaces for comments
        return value.replace("\n", " ").replace("\r", "")
