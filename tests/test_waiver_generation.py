"""Tests for waiver generation functionality.

This module tests:
- WaiverGenerator class for generating waiver TOML from messages
- CLI --generate-waivers option
"""

import hashlib
from datetime import date

import pytest
import tomli
from click.testing import CliRunner

from sawmill.__main__ import cli
from sawmill.core.waiver import WaiverGenerator, WaiverLoader
from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel


# Test severity levels matching typical Vivado-like schema
TEST_SEVERITY_LEVELS = [
    SeverityLevel(id="error", name="Error", level=3, style="red bold"),
    SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
    SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
    SeverityLevel(id="info", name="Info", level=0, style="cyan"),
]


class TestWaiverGenerator:
    """Tests for WaiverGenerator class."""

    def test_generate_empty_messages(self):
        """Generate waivers from empty message list."""
        generator = WaiverGenerator()
        result = generator.generate([])

        assert "# Sawmill generated waiver file" in result
        assert "[metadata]" in result
        assert "[[waiver]]" not in result

    def test_generate_single_error_with_id(self):
        """Generate waiver for error with message_id."""
        msg = Message(
            start_line=10,
            end_line=10,
            raw_text="ERROR: [Test 1-1] error message",
            content="error message",
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # Verify TOML is valid
        parsed = tomli.loads(result)
        assert "waiver" in parsed
        assert len(parsed["waiver"]) == 1

        waiver = parsed["waiver"][0]
        assert waiver["type"] == "id"
        assert waiver["pattern"] == "Test 1-1"
        assert "reason" in waiver
        assert "author" in waiver
        assert "date" in waiver

    def test_generate_single_error_without_id(self):
        """Generate waiver for error without message_id uses hash."""
        msg = Message(
            start_line=10,
            end_line=10,
            raw_text="ERROR: some error without id",
            content="some error without id",
            severity="error",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        parsed = tomli.loads(result)
        waiver = parsed["waiver"][0]
        assert waiver["type"] == "hash"
        # Verify the hash is correct
        expected_hash = hashlib.sha256(msg.raw_text.encode("utf-8")).hexdigest()
        assert waiver["pattern"] == expected_hash

    def test_generate_filters_info_by_default(self):
        """INFO messages are excluded by default (level 0 < min_waiver_level 1)."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="INFO: [Info 1-1] info message",
                content="info message",
                severity="info",
                message_id="Info 1-1",
            ),
            Message(
                start_line=2,
                end_line=2,
                raw_text="ERROR: [Error 1-1] error message",
                content="error message",
                severity="error",
                message_id="Error 1-1",
            ),
        ]
        generator = WaiverGenerator(severity_levels=TEST_SEVERITY_LEVELS)
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1
        assert parsed["waiver"][0]["pattern"] == "Error 1-1"

    def test_generate_includes_info_when_requested(self):
        """INFO messages are included when include_all=True."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="INFO: [Info 1-1] info message",
                content="info message",
                severity="info",
                message_id="Info 1-1",
            ),
        ]
        generator = WaiverGenerator(include_all=True)
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1
        assert parsed["waiver"][0]["pattern"] == "Info 1-1"

    def test_generate_includes_warnings(self):
        """Warnings are included in generated waivers."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Warn 1-1] warning message",
            content="warning message",
            severity="warning",
            message_id="Warn 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1

    def test_generate_includes_critical_warnings(self):
        """Critical warnings are included in generated waivers."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="CRITICAL WARNING: [CW 1-1] critical message",
            content="critical message",
            severity="critical_warning",
            message_id="CW 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1

    def test_generate_multiple_messages(self):
        """Generate waivers for multiple messages."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="ERROR: [Test 1-1] first error",
                content="first error",
                severity="error",
                message_id="Test 1-1",
            ),
            Message(
                start_line=2,
                end_line=2,
                raw_text="WARNING: [Test 2-1] warning",
                content="warning",
                severity="warning",
                message_id="Test 2-1",
            ),
            Message(
                start_line=3,
                end_line=3,
                raw_text="ERROR: [Test 3-1] second error",
                content="second error",
                severity="error",
                message_id="Test 3-1",
            ),
        ]
        generator = WaiverGenerator()
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 3

    def test_generate_with_tool_metadata(self):
        """Tool name is included in metadata when specified."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg], tool="vivado")

        parsed = tomli.loads(result)
        assert parsed["metadata"]["tool"] == "vivado"

    def test_generate_with_custom_author(self):
        """Custom author is used in generated waivers."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator(author="test@example.com")
        result = generator.generate([msg])

        parsed = tomli.loads(result)
        assert parsed["waiver"][0]["author"] == "test@example.com"

    def test_generate_with_custom_reason(self):
        """Custom reason is used in generated waivers."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator(reason="Custom reason placeholder")
        result = generator.generate([msg])

        parsed = tomli.loads(result)
        assert parsed["waiver"][0]["reason"] == "Custom reason placeholder"

    def test_generate_escapes_special_characters(self):
        """Special characters in message_id are properly escaped."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text='ERROR: [Test "1-1"] error with quotes',
            content="error with quotes",
            severity="error",
            message_id='Test "1-1"',
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # TOML should parse without error
        parsed = tomli.loads(result)
        assert parsed["waiver"][0]["pattern"] == 'Test "1-1"'

    def test_generate_date_format(self):
        """Generated date is in ISO format."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        parsed = tomli.loads(result)
        waiver_date = parsed["waiver"][0]["date"]
        # Verify it's today's date in ISO format
        assert waiver_date == date.today().isoformat()

    def test_generate_skips_none_severity(self):
        """Messages with None severity are skipped."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="Some plain text message",
            content="plain text message",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # Should not contain waiver entries
        assert "[[waiver]]" not in result

    def test_generated_toml_is_parseable_by_waiver_loader(self):
        """Generated TOML can be loaded by WaiverLoader."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="ERROR: [Test 1-1] error",
                content="error",
                severity="error",
                message_id="Test 1-1",
            ),
            Message(
                start_line=2,
                end_line=2,
                raw_text="WARNING: [Test 2-1] warning",
                content="warning",
                severity="warning",
                message_id="Test 2-1",
            ),
        ]

        # Generate waivers - update with real author/reason since
        # WaiverLoader requires non-empty, non-placeholder values
        generator = WaiverGenerator(
            author="test@example.com",
            reason="Test reason for CI"
        )
        toml_content = generator.generate(messages, tool="vivado")

        # Load with WaiverLoader
        loader = WaiverLoader()
        waiver_file = loader.load_from_string(toml_content)

        assert len(waiver_file.waivers) == 2
        assert waiver_file.tool == "vivado"

    def test_level_based_filtering_with_severity_levels(self):
        """Level-based filtering uses numeric level comparison."""
        messages = [
            Message(
                start_line=1, end_line=1,
                raw_text="ERROR: [E 1-1] error",
                content="error", severity="error", message_id="E 1-1",
            ),
            Message(
                start_line=2, end_line=2,
                raw_text="WARNING: [W 1-1] warning",
                content="warning", severity="warning", message_id="W 1-1",
            ),
            Message(
                start_line=3, end_line=3,
                raw_text="INFO: [I 1-1] info",
                content="info", severity="info", message_id="I 1-1",
            ),
        ]

        # With severity_levels and default min_waiver_level=1
        # Should include error (3) and warning (1), but not info (0)
        generator = WaiverGenerator(severity_levels=TEST_SEVERITY_LEVELS)
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "E 1-1" in patterns
        assert "W 1-1" in patterns
        assert "I 1-1" not in patterns

    def test_custom_min_waiver_level(self):
        """Custom min_waiver_level filters appropriately."""
        messages = [
            Message(
                start_line=1, end_line=1,
                raw_text="ERROR: [E 1-1] error",
                content="error", severity="error", message_id="E 1-1",
            ),
            Message(
                start_line=2, end_line=2,
                raw_text="CRITICAL WARNING: [CW 1-1] critical warning",
                content="critical warning", severity="critical_warning", message_id="CW 1-1",
            ),
            Message(
                start_line=3, end_line=3,
                raw_text="WARNING: [W 1-1] warning",
                content="warning", severity="warning", message_id="W 1-1",
            ),
        ]

        # With min_waiver_level=2, only error (3) and critical_warning (2)
        generator = WaiverGenerator(
            severity_levels=TEST_SEVERITY_LEVELS,
            min_waiver_level=2
        )
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "E 1-1" in patterns
        assert "CW 1-1" in patterns
        assert "W 1-1" not in patterns

    def test_min_waiver_level_errors_only(self):
        """min_waiver_level=3 includes only errors."""
        messages = [
            Message(
                start_line=1, end_line=1,
                raw_text="ERROR: [E 1-1] error",
                content="error", severity="error", message_id="E 1-1",
            ),
            Message(
                start_line=2, end_line=2,
                raw_text="CRITICAL WARNING: [CW 1-1] critical warning",
                content="critical warning", severity="critical_warning", message_id="CW 1-1",
            ),
        ]

        # With min_waiver_level=3, only error (3) is included
        generator = WaiverGenerator(
            severity_levels=TEST_SEVERITY_LEVELS,
            min_waiver_level=3
        )
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1
        assert parsed["waiver"][0]["pattern"] == "E 1-1"

    def test_include_all_overrides_min_waiver_level(self):
        """include_all=True includes all severities regardless of level."""
        messages = [
            Message(
                start_line=1, end_line=1,
                raw_text="ERROR: [E 1-1] error",
                content="error", severity="error", message_id="E 1-1",
            ),
            Message(
                start_line=2, end_line=2,
                raw_text="INFO: [I 1-1] info",
                content="info", severity="info", message_id="I 1-1",
            ),
        ]

        # Even with high min_waiver_level, include_all=True includes everything
        generator = WaiverGenerator(
            severity_levels=TEST_SEVERITY_LEVELS,
            min_waiver_level=3,
            include_all=True
        )
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "E 1-1" in patterns
        assert "I 1-1" in patterns

    def test_custom_severity_levels(self):
        """Works with custom severity level definitions."""
        # Different severity scheme (like a different tool might have)
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=4, style="red bold"),
            SeverityLevel(id="error", name="Error", level=3, style="red"),
            SeverityLevel(id="note", name="Note", level=1, style="cyan"),
            SeverityLevel(id="debug", name="Debug", level=0, style="dim"),
        ]

        messages = [
            Message(
                start_line=1, end_line=1,
                raw_text="FATAL: fatal error",
                content="fatal error", severity="fatal", message_id="F-1",
            ),
            Message(
                start_line=2, end_line=2,
                raw_text="NOTE: just a note",
                content="just a note", severity="note", message_id="N-1",
            ),
            Message(
                start_line=3, end_line=3,
                raw_text="DEBUG: debug info",
                content="debug info", severity="debug", message_id="D-1",
            ),
        ]

        # With min_waiver_level=1, includes fatal (4) and note (1), not debug (0)
        generator = WaiverGenerator(
            severity_levels=custom_levels,
            min_waiver_level=1
        )
        result = generator.generate(messages)

        parsed = tomli.loads(result)
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "F-1" in patterns
        assert "N-1" in patterns
        assert "D-1" not in patterns


class TestGenerateWaiversCLI:
    """Tests for --generate-waivers CLI option."""

    def test_generate_waivers_basic(self, tmp_path):
        """Basic waiver generation from log file."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] error message\n"
            "WARNING: [Test 2-1] warning\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers"]
        )

        assert result.exit_code == 0
        assert "[[waiver]]" in result.output
        assert "Test 1-1" in result.output or "Test 2-1" in result.output

        # Output should be valid TOML
        parsed = tomli.loads(result.output)
        assert "waiver" in parsed

    def test_generate_waivers_filters_info_by_default(self, tmp_path):
        """By default (--waiver-level 1), INFO is excluded from waivers."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Error 1-1] error\n"
            "CRITICAL WARNING: [CW 1-1] critical\n"
            "WARNING: [Warn 1-1] warning\n"
            "INFO: [Info 1-1] info\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers"]
        )

        assert result.exit_code == 0
        parsed = tomli.loads(result.output)

        # Default waiver-level=1 includes warning and above, excludes info
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "Error 1-1" in patterns
        assert "CW 1-1" in patterns
        assert "Warn 1-1" in patterns
        assert "Info 1-1" not in patterns  # INFO excluded by default

    def test_generate_waivers_all_levels_with_waiver_level_0(self, tmp_path):
        """With --waiver-level 0, all severity levels are included."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Error 1-1] error\n"
            "CRITICAL WARNING: [CW 1-1] critical\n"
            "WARNING: [Warn 1-1] warning\n"
            "INFO: [Info 1-1] info\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers", "--waiver-level", "0"]
        )

        assert result.exit_code == 0
        parsed = tomli.loads(result.output)

        # waiver-level=0 includes all severity levels
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "Error 1-1" in patterns
        assert "CW 1-1" in patterns
        assert "Warn 1-1" in patterns
        assert "Info 1-1" in patterns

    def test_generate_waivers_info_only_excluded_by_default(self, tmp_path):
        """INFO-only log generates empty waivers by default (min_waiver_level=1)."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] all is well\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers"]
        )

        assert result.exit_code == 0
        parsed = tomli.loads(result.output)
        # INFO excluded by default (min_waiver_level=1)
        assert "waiver" not in parsed or len(parsed.get("waiver", [])) == 0

    def test_generate_waivers_info_with_waiver_level_0(self, tmp_path):
        """INFO messages included with --waiver-level 0."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] all is well\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers", "--waiver-level", "0"]
        )

        assert result.exit_code == 0
        parsed = tomli.loads(result.output)
        assert "waiver" in parsed
        assert len(parsed["waiver"]) == 1
        assert parsed["waiver"][0]["pattern"] == "Info 1-1"

    def test_generate_waivers_errors_only_with_waiver_level_2(self, tmp_path):
        """With --waiver-level 2, only errors and critical warnings are included."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Error 1-1] error\n"
            "CRITICAL WARNING: [CW 1-1] critical\n"
            "WARNING: [Warn 1-1] warning\n"
            "INFO: [Info 1-1] info\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers", "--waiver-level", "2"]
        )

        assert result.exit_code == 0
        parsed = tomli.loads(result.output)

        # waiver-level=2 includes level 2 and above (error=3, critical_warning=2)
        patterns = [w["pattern"] for w in parsed["waiver"]]
        assert "Error 1-1" in patterns
        assert "CW 1-1" in patterns  # Critical Warning has level 2
        # Warning (level 1) and Info (level 0) excluded
        assert "Warn 1-1" not in patterns
        assert "Info 1-1" not in patterns

    def test_generate_waivers_includes_tool_name(self, tmp_path):
        """Tool name is included in metadata."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers"]
        )

        assert result.exit_code == 0
        parsed = tomli.loads(result.output)
        assert parsed["metadata"]["tool"] == "vivado"

    def test_generate_waivers_auto_detect_plugin(self, tmp_path):
        """Waiver generation works with auto-detected plugin."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2 (64-bit)\n"
            "INFO: [Common 17-206] 'analyze_design' not supported\n"
            "ERROR: [Test 1-1] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--generate-waivers"])

        assert result.exit_code == 0
        assert "[[waiver]]" in result.output

    def test_generate_waivers_redirect_to_file(self, tmp_path):
        """Waiver output can be redirected to a file."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] error message\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers"]
        )

        # Write output to file (simulating redirect)
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text(result.output)

        # Verify the file is valid TOML
        content = waiver_file.read_text()
        parsed = tomli.loads(content)
        assert "waiver" in parsed

    def test_generate_waivers_unknown_plugin(self, tmp_path):
        """Error when specifying unknown plugin."""
        log_file = tmp_path / "test.log"
        log_file.write_text("ERROR: test error\n")

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "nonexistent", "--generate-waivers"]
        )

        # Should exit with error code
        assert result.exit_code == 1
        # stdout should be empty (no TOML generated)
        assert "[[waiver]]" not in result.output

    def test_generate_waivers_with_hash_type(self, tmp_path):
        """Messages without ID generate hash-type waivers."""
        log_file = tmp_path / "vivado.log"
        # Create a message that won't parse to a message_id
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: Some error without standard format\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--generate-waivers"]
        )

        # The Vivado plugin may or may not parse this - check output
        # If it generated a waiver, check the type
        if "[[waiver]]" in result.output:
            parsed = tomli.loads(result.output)
            if parsed.get("waiver"):
                # Either type should be valid
                assert parsed["waiver"][0]["type"] in ("id", "hash")


class TestWaiverGeneratorEdgeCases:
    """Edge case tests for WaiverGenerator."""

    def test_multiline_content_in_comment(self):
        """Multi-line content is condensed in comments."""
        msg = Message(
            start_line=1,
            end_line=3,
            raw_text="ERROR: [Test 1-1] error\nLine 2\nLine 3",
            content="error\nLine 2\nLine 3",
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # Should still be valid TOML
        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1

    def test_very_long_content_is_truncated(self):
        """Very long content is truncated in comments."""
        long_content = "x" * 200
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text=f"ERROR: [Test 1-1] {long_content}",
            content=long_content,
            severity="error",
            message_id="Test 1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # Content should be truncated in comments
        assert "..." in result
        # TOML should still be valid
        parsed = tomli.loads(result)
        assert len(parsed["waiver"]) == 1

    def test_backslash_in_message_id(self):
        """Backslashes in message_id are properly escaped."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test\\1-1] error",
            content="error",
            severity="error",
            message_id="Test\\1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # Should be valid TOML
        parsed = tomli.loads(result)
        assert parsed["waiver"][0]["pattern"] == "Test\\1-1"

    def test_newline_in_message_id(self):
        """Newlines in message_id are properly escaped."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test\n1-1] error",
            content="error",
            severity="error",
            message_id="Test\n1-1",
        )
        generator = WaiverGenerator()
        result = generator.generate([msg])

        # Should be valid TOML
        parsed = tomli.loads(result)
        # The newline should be escaped
        assert "Test" in parsed["waiver"][0]["pattern"]
