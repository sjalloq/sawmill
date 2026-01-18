"""
Reference implementation for the Vivado plugin.

This file serves as documentation and a template for the built-in Vivado plugin.
The actual implementation will be in sawmill/plugins/vivado.py
"""

from pathlib import Path
from dataclasses import dataclass
import re

# These would be imported from sawmill.plugin
# from sawmill.plugin import SawmillPlugin, hookimpl
# from sawmill.models import FilterDefinition, MessageBoundary, ParsedMessage, FileRef


@dataclass
class ParsedMessage:
    """Structured representation of a parsed log message."""
    severity: str  # info, warning, critical_warning, error
    message_id: str  # e.g., "Vivado 12-3523", "Synth 8-6157"
    content: str  # The message text
    raw: str  # Original line
    category: str | None = None  # e.g., "Synth", "Vivado", "Timing"
    file_ref: "FileRef | None" = None


@dataclass
class FileRef:
    """Reference to a source file location."""
    path: str
    line: int


@dataclass
class FilterDefinition:
    """Definition of a log filter."""
    id: str
    name: str
    pattern: str
    severity: str = "info"
    enabled_by_default: bool = False
    category: str | None = None
    description: str | None = None


@dataclass
class MessageBoundary:
    """Rules for grouping multi-line messages."""
    start_pattern: str
    continuation_pattern: str
    max_lines: int = 20
    name: str | None = None


class VivadoPlugin:
    """
    Plugin for Xilinx Vivado synthesis and implementation logs.

    Handles log formats from:
    - Vivado synthesis (synth_design)
    - Vivado implementation (place_design, route_design)
    - Vivado timing reports
    - Vivado bitstream generation
    """

    name = "vivado"
    version = "1.0.0"
    description = "Xilinx Vivado synthesis and implementation logs"

    # Message ID pattern: [Category Number-Number]
    MESSAGE_PATTERN = re.compile(
        r'^(INFO|WARNING|CRITICAL WARNING|ERROR):\s*\[([^\]]+)\]\s*(.+?)(?:\s*\[([^\]]+:\d+)\])?$'
    )

    # File reference pattern: [/path/to/file.v:123]
    FILE_REF_PATTERN = re.compile(r'\[([^\]]+\.(v|vhd|sv|xdc|tcl)):(\d+)\]')

    # @hookimpl
    def can_handle(self, path: Path, content: str) -> float:
        """
        Return confidence score for handling this file.

        High confidence indicators:
        - "Vivado v" in header
        - Vivado-style message IDs like [Synth 8-xxxx]
        """
        score = 0.0

        # Check for Vivado header
        if "Vivado v" in content[:500]:
            score = 0.9
        elif "# Vivado" in content[:500]:
            score = 0.85

        # Check for Vivado-style message IDs
        if re.search(r'\[(Synth|Vivado|Timing|IP_Flow|Constraints)\s+\d+-\d+\]', content[:2000]):
            score = max(score, 0.8)

        return score

    # @hookimpl
    def get_filters(self) -> list[FilterDefinition]:
        """Return filter definitions for Vivado logs."""
        return [
            # Severity-based filters
            FilterDefinition(
                id="errors",
                name="Errors",
                pattern=r"^ERROR:",
                severity="error",
                enabled_by_default=True,
                category="severity",
                description="All error messages",
            ),
            FilterDefinition(
                id="critical-warnings",
                name="Critical Warnings",
                pattern=r"^CRITICAL WARNING:",
                severity="critical",
                enabled_by_default=True,
                category="severity",
                description="Critical warning messages requiring attention",
            ),
            FilterDefinition(
                id="warnings",
                name="Warnings",
                pattern=r"^WARNING:",
                severity="warning",
                enabled_by_default=False,
                category="severity",
                description="All warning messages",
            ),

            # Timing-related filters
            FilterDefinition(
                id="timing-failures",
                name="Timing Failures",
                pattern=r"(WNS|TNS).*-\d+\.\d+|TNS Failing Endpoints\s+[1-9]",
                severity="error",
                enabled_by_default=True,
                category="timing",
                description="Timing paths with negative slack",
            ),
            FilterDefinition(
                id="timing-summary",
                name="Timing Summary",
                pattern=r"(Design Timing Summary|Clock Summary|All user specified timing constraints)",
                severity="info",
                enabled_by_default=False,
                category="timing",
                description="Timing summary and status",
            ),

            # Synthesis filters
            FilterDefinition(
                id="synthesis-warnings",
                name="Synthesis Warnings",
                pattern=r"^WARNING: \[Synth",
                severity="warning",
                enabled_by_default=True,
                category="synthesis",
                description="Warnings from synthesis",
            ),
            FilterDefinition(
                id="ram-inference",
                name="RAM Inference",
                pattern=r"\[Synth 8-3354\]|inferred.*RAM|BRAM",
                severity="info",
                enabled_by_default=False,
                category="synthesis",
                description="Inferred RAM/ROM blocks",
            ),
            FilterDefinition(
                id="fsm-encoding",
                name="FSM Encoding",
                pattern=r"\[Synth 8-802\]|FSM|state machine",
                severity="info",
                enabled_by_default=False,
                category="synthesis",
                description="State machine encoding",
            ),

            # Constraint filters
            FilterDefinition(
                id="constraint-issues",
                name="Constraint Issues",
                pattern=r"\[(Constraints|Vivado 12-4739)\]",
                severity="warning",
                enabled_by_default=True,
                category="constraints",
                description="XDC constraint problems",
            ),

            # DRC filters
            FilterDefinition(
                id="drc-issues",
                name="DRC Issues",
                pattern=r"\[DRC|DRC finished with \d+ Errors",
                severity="warning",
                enabled_by_default=True,
                category="drc",
                description="Design Rule Check messages",
            ),

            # IP filters
            FilterDefinition(
                id="ip-generation",
                name="IP Generation",
                pattern=r"\[IP_Flow|Generating.*target for IP",
                severity="info",
                enabled_by_default=False,
                category="ip",
                description="IP core generation messages",
            ),
        ]

    # @hookimpl
    def get_message_boundaries(self) -> list[MessageBoundary]:
        """Return rules for grouping multi-line messages."""
        return [
            # Standard Vivado messages with indented continuation
            MessageBoundary(
                name="standard_message",
                start_pattern=r"^(INFO|WARNING|CRITICAL WARNING|ERROR):\s*\[",
                continuation_pattern=r"^(\s{2,}|\t)",
                max_lines=10,
            ),
            # Timing tables
            MessageBoundary(
                name="timing_table",
                start_pattern=r"^-{20,}$",
                continuation_pattern=r"^(\||[-=\s]|\w)",
                max_lines=50,
            ),
        ]

    # @hookimpl
    def parse_message(self, line: str) -> ParsedMessage | None:
        """Parse a Vivado log line into structured data."""
        match = self.MESSAGE_PATTERN.match(line)
        if not match:
            return None

        severity_raw = match.group(1)
        message_id = match.group(2)
        content = match.group(3)
        file_ref_str = match.group(4)

        # Normalize severity
        severity_map = {
            "INFO": "info",
            "WARNING": "warning",
            "CRITICAL WARNING": "critical_warning",
            "ERROR": "error",
        }
        severity = severity_map.get(severity_raw, "info")

        # Extract category from message ID (e.g., "Synth" from "Synth 8-6157")
        category = message_id.split()[0] if " " in message_id else None

        # Parse file reference if present
        file_ref = None
        if file_ref_str:
            ref_match = re.match(r'(.+):(\d+)', file_ref_str)
            if ref_match:
                file_ref = FileRef(path=ref_match.group(1), line=int(ref_match.group(2)))

        return ParsedMessage(
            severity=severity,
            message_id=message_id,
            content=content,
            raw=line,
            category=category,
            file_ref=file_ref,
        )

    # @hookimpl
    def extract_file_reference(self, content: str) -> FileRef | None:
        """Extract source file references from message content."""
        match = self.FILE_REF_PATTERN.search(content)
        if match:
            return FileRef(path=match.group(1), line=int(match.group(3)))
        return None


# Quick filter presets for common use cases
QUICK_FILTERS = {
    "problems": ["errors", "critical-warnings", "timing-failures"],
    "synthesis": ["errors", "critical-warnings", "synthesis-warnings", "ram-inference"],
    "timing": ["errors", "timing-failures", "timing-summary", "constraint-issues"],
    "verbose": ["errors", "critical-warnings", "warnings", "timing-summary"],
}
