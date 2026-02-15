"""Waiver loading, parsing, and matching for sawmill.

This module provides:
- WaiverLoader: For reading TOML waiver files and validating waiver entries
- WaiverMatcher: For matching log messages against waivers
- WaiverGenerator: For generating waiver TOML from log messages

Waivers are for CI acceptance (pass/fail decisions with audit trail).
They are distinct from suppressions which are for display filtering.
"""

import re
from pathlib import Path

import tomli

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.waiver import Waiver, WaiverFile
from sawmill.utils.toml import escape_toml_basic_string


def waiver_to_toml(waiver: Waiver) -> str:
    """Serialize a Waiver object to a [[waiver]] TOML block string.

    Handles optional fields (content_match/pattern, expires, ticket).

    Args:
        waiver: The Waiver object to serialize.

    Returns:
        A TOML string representing the waiver entry.
    """
    lines: list[str] = ["[[waiver]]"]
    lines.append(f'message_id = "{escape_toml_basic_string(waiver.message_id)}"')
    if waiver.content_match and waiver.content_pattern:
        lines.append(f'content_match = "{waiver.content_match}"')
        lines.append(f'content_pattern = "{escape_toml_basic_string(waiver.content_pattern)}"')
    lines.append(f'reason = "{escape_toml_basic_string(waiver.reason)}"')
    lines.append(f'author = "{escape_toml_basic_string(waiver.author)}"')
    lines.append(f'date = "{waiver.date}"')
    if waiver.expires:
        lines.append(f'expires = "{waiver.expires}"')
    if waiver.ticket:
        lines.append(f'ticket = "{escape_toml_basic_string(waiver.ticket)}"')
    return "\n".join(lines)


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
        line: int | None = None,
        path: Path | None = None,
        waiver_index: int | None = None,
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
        full_message = f"{' '.join(parts)}: {message}" if parts else message

        super().__init__(full_message)


class WaiverLoader:
    """Loader for sawmill TOML waiver files.

    Waiver files use the following format:

        [metadata]
        tool = "vivado"  # Optional, for documentation

        [[waiver]]
        message_id = "Vivado 12-3523"  # Required: message ID to match
        content_match = "raw"           # Optional: "raw" or "regex"
        content_pattern = "some text"   # Optional: narrows match
        reason = "Intentional"          # Required: why this is waived
        author = "user@email"           # Required: who created this waiver
        date = "2026-01-18"             # Required: when this was created
        expires = "2026-06-01"          # Optional: expiration date
        ticket = "PROJ-123"             # Optional: issue tracker reference

    Example usage:
        loader = WaiverLoader()
        waivers = loader.load(Path("waivers.toml"))
    """

    # Valid content_match values
    VALID_CONTENT_MATCH = frozenset({"raw", "regex"})

    # Required fields for a waiver entry
    REQUIRED_FIELDS = frozenset({"message_id", "reason", "author", "date"})

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
            raise WaiverValidationError(f"Invalid TOML: {e}", line=line, path=path) from e

        return self._parse_waiver_file(data, path)

    def load_from_string(self, content: str, path: Path | None = None) -> WaiverFile:
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
            raise WaiverValidationError(f"Invalid TOML: {e}", line=line, path=path) from e

        return self._parse_waiver_file(data, path)

    def _parse_waiver_file(self, data: dict, path: Path | None) -> WaiverFile:
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

        return WaiverFile(tool=tool, waivers=waivers, path=str(path) if path else None)

    def _parse_waiver_entry(self, entry: dict, index: int, path: Path | None) -> Waiver:
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
                waiver_index=index,
            )

        # Validate message_id
        message_id = entry.get("message_id")
        if not message_id or not isinstance(message_id, str):
            raise WaiverValidationError(
                "message_id must be a non-empty string", path=path, waiver_index=index
            )

        # Validate reason
        reason = entry.get("reason")
        if not reason or not isinstance(reason, str):
            raise WaiverValidationError(
                "Reason must be a non-empty string", path=path, waiver_index=index
            )

        # Validate author
        author = entry.get("author")
        if not author or not isinstance(author, str):
            raise WaiverValidationError(
                "Author must be a non-empty string", path=path, waiver_index=index
            )

        # Validate date
        date = entry.get("date")
        if not date or not isinstance(date, str):
            raise WaiverValidationError(
                "Date must be a non-empty string", path=path, waiver_index=index
            )

        # Validate content_match if present
        content_match = entry.get("content_match")
        if content_match is not None and content_match not in self.VALID_CONTENT_MATCH:
            raise WaiverValidationError(
                f"Invalid content_match '{content_match}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_CONTENT_MATCH))}",
                path=path,
                waiver_index=index,
            )

        # Validate content_match / content_pattern consistency
        content_pattern = entry.get("content_pattern")

        # content_match without content_pattern is meaningless — the waiver
        # would silently become a catch-all, which is almost certainly not intended
        if content_match is not None and not content_pattern:
            raise WaiverValidationError(
                f"content_match is '{content_match}' but content_pattern is not set. "
                "Either add a content_pattern or remove content_match.",
                path=path,
                waiver_index=index,
            )

        # content_pattern without content_match: make the implicit raw behavior explicit
        if content_pattern and content_match is None:
            content_match = "raw"

        # Validate content_pattern as regex if content_match == "regex"
        if content_match == "regex" and content_pattern:
            try:
                re.compile(content_pattern)
            except re.error as e:
                raise WaiverValidationError(
                    f"Invalid regex pattern: {e}", path=path, waiver_index=index
                ) from e

        # Create and return Waiver instance
        return Waiver(
            message_id=message_id,
            content_match=content_match,
            content_pattern=content_pattern,
            reason=reason,
            author=author,
            date=date,
            expires=entry.get("expires"),
            ticket=entry.get("ticket"),
        )

    def _extract_line_number(self, error_message: str) -> int | None:
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

    Matching is two-stage:
    1. Match message_id exactly (required for all waivers)
    2. If content_pattern is set, apply it as additional refinement:
       - content_match == "raw": substring match on message content/raw_text
       - content_match == "regex": regex search on message content/raw_text
    3. If no content_pattern: match all instances of this message_id

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

        # Index waivers by message_id for O(1) lookup
        self._by_message_id: dict[str, list[Waiver]] = {}
        for waiver in waivers:
            self._by_message_id.setdefault(waiver.message_id, []).append(waiver)

    @property
    def waivers(self) -> list[Waiver]:
        """Get the list of waivers."""
        return self._waivers

    def is_waived(self, message: Message) -> Waiver | None:
        """Check if a message is waived.

        Matching logic:
        1. Look up waivers by message_id (exact match)
        2. For each matching waiver, check content_pattern if present
        3. Waivers with content_pattern are checked first (more specific),
           then waivers without (catch-all)

        Args:
            message: The Message to check against waivers

        Returns:
            The matching Waiver if found, or None
        """
        if message.message_id is None:
            return None

        candidates = self._by_message_id.get(message.message_id, [])
        if not candidates:
            return None

        # Check waivers with content_pattern first (more specific)
        for waiver in candidates:
            if waiver.content_pattern and self._match_content(message, waiver):
                return waiver

        # Then check catch-all waivers (no content_pattern)
        for waiver in candidates:
            if not waiver.content_pattern:
                return waiver

        return None

    def _match_content(self, message: Message, waiver: Waiver) -> bool:
        """Check if message content matches a waiver's content pattern.

        Args:
            message: The message to check
            waiver: The waiver with a content_pattern to match against

        Returns:
            True if the content matches
        """
        pattern = waiver.content_pattern
        if not pattern:
            return True

        # Match against raw_text (includes full message content)
        text = message.raw_text

        if waiver.content_match == "regex":
            try:
                return bool(re.search(pattern, text, re.DOTALL))
            except re.error:
                return False
        else:
            # Default to raw (substring) match
            return pattern in text


class WaiverGenerator:
    """Generates waiver TOML from log messages.

    This class creates valid waiver TOML files from a list of messages,
    suitable for CI acceptance workflows. Generated waivers include
    placeholder values for author and reason that users should review
    and update.

    Generated waivers use message_id for all messages that have one.
    Messages without a message_id are skipped.

    The generator filters messages by severity level. By default, only messages
    with level >= 1 (above the lowest informational level 0) are included.
    This behavior can be customized via the min_waiver_level parameter, or
    all messages can be included by setting include_all=True.

    Example usage:
        generator = WaiverGenerator(severity_levels=plugin_levels)
        toml_content = generator.generate(messages)
        print(toml_content)  # Redirect to waivers.toml
    """

    def __init__(
        self,
        author: str = "<author>",
        reason: str = "<reason - explain why this is acceptable>",
        severity_levels: list[SeverityLevel] | None = None,
        min_waiver_level: int = 1,
        include_all: bool = False,
    ):
        """Initialize the waiver generator.

        Args:
            author: Default author to use in generated waivers.
            reason: Default reason placeholder for generated waivers.
            severity_levels: List of severity levels from the plugin.
                If provided, used for level-based filtering.
                If None, all non-None severity messages are included when include_all=True,
                otherwise no filtering can be applied and a warning is logged.
            min_waiver_level: Minimum severity level to include in waivers.
                Messages with severity.level >= min_waiver_level are included.
                Level 0 is informational; level 1+ are actionable. Default: 1.
            include_all: If True, include all severity levels regardless of min_waiver_level.
        """
        self._author = author
        self._reason = reason
        self._severity_levels = severity_levels
        self._min_waiver_level = min_waiver_level
        self._include_all = include_all

        # Build lookup dict from severity id to level for efficient filtering
        self._severity_level_map: dict[str, int] = {}
        if severity_levels:
            for level in severity_levels:
                self._severity_level_map[level.id.lower()] = level.level

    def generate(self, messages: list[Message], tool: str | None = None) -> str:
        """Generate waiver TOML content from messages.

        Only includes messages with severity level >= min_waiver_level
        (default 1, above informational level 0), unless include_all=True.

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
            lines.append(f'tool = "{escape_toml_basic_string(tool)}"')
        lines.append(f'generated = "{date.today().isoformat()}"')
        lines.append("")

        # Filter messages by severity
        filtered = self._filter_messages(messages)

        # Generate waiver entries
        for msg in filtered:
            entry = self._generate_waiver_entry(msg)
            if entry:
                lines.extend(entry)
                lines.append("")

        return "\n".join(lines)

    def _filter_messages(self, messages: list[Message]) -> list[Message]:
        """Filter messages to those that need waivers.

        Filtering is based on numeric severity level comparison. Messages
        with severity.level >= min_waiver_level are included, unless
        include_all=True which includes all severities.

        When severity_levels is not provided, all messages with a severity
        are included (no filtering possible without level information).

        Args:
            messages: All parsed messages.

        Returns:
            Messages that need waivers based on severity level.
        """
        result: list[Message] = []
        for msg in messages:
            if msg.severity is None:
                continue

            # If include_all is set, include all messages with a severity
            if self._include_all:
                result.append(msg)
                continue

            severity_id = msg.severity.lower()

            # Use level-based filtering if severity_levels were provided
            if self._severity_level_map:
                level = self._severity_level_map.get(severity_id)
                if level is not None and level >= self._min_waiver_level:
                    result.append(msg)
            else:
                # No severity_levels provided - include all messages
                # Caller should provide severity_levels for proper filtering
                result.append(msg)

        return result

    def _generate_waiver_entry(self, message: Message) -> list[str] | None:
        """Generate a single waiver entry for a message.

        Args:
            message: The message to generate a waiver for.

        Returns:
            List of TOML lines for this waiver entry, or None if message
            has no message_id.
        """
        from datetime import date

        # Skip messages without message_id
        if not message.message_id:
            return None

        waiver = Waiver(
            message_id=message.message_id,
            reason=self._reason,
            author=self._author,
            date=date.today().isoformat(),
        )
        lines = waiver_to_toml(waiver).splitlines()

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

    def _escape_comment(self, value: str) -> str:
        """Escape a string for use in a TOML comment.

        Args:
            value: The string to escape.

        Returns:
            String safe for TOML comments (no newlines).
        """
        # Replace newlines with spaces for comments
        return value.replace("\n", " ").replace("\r", "")
