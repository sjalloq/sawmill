"""Tests for CLI output formats (Task 4.2)."""

import json

from click.testing import CliRunner

from sawmill.__main__ import cli


class TestJsonFormat:
    """Tests for JSON (JSONL) output format."""

    def test_json_format_basic(self, tmp_path):
        """JSON format outputs valid JSONL."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "json"])

        assert result.exit_code == 0
        # Should have JSON output
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) > 0
        data = json.loads(lines[-1])
        assert "severity" in data or "content" in data

    def test_json_format_multiple_messages(self, tmp_path):
        """JSON format outputs one JSON object per line."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [E1 1-1] error msg\n"
            "WARNING: [W1 2-1] warning msg\n"
            "INFO: [I1 3-1] info msg\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "json"])

        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 3

        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "severity" in data
            assert "raw_text" in data
            assert "content" in data

    def test_json_format_fields(self, tmp_path):
        """JSON output includes all message fields."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] message content\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "json"])

        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        data = json.loads(lines[-1])

        # Check required fields
        assert "start_line" in data
        assert "end_line" in data
        assert "raw_text" in data
        assert "content" in data
        assert "severity" in data
        assert "message_id" in data

    def test_json_format_severity(self, tmp_path):
        """JSON format correctly captures severity."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] error message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "json"])

        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        data = json.loads(lines[-1])
        assert data["severity"] == "error"

    def test_json_format_case_insensitive(self, tmp_path):
        """--format JSON should work (case insensitive)."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "JSON"])

        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) > 0


class TestCountFormat:
    """Tests for count (summary) output format."""

    def test_count_format_basic(self, tmp_path):
        """Count format outputs summary statistics."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [E1 1-1] e1\n"
            "ERROR: [E2 1-2] e2\n"
            "WARNING: [W1 2-1] w1\n"
            "INFO: [I1 3-1] i1\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "error" in output_lower

    def test_count_format_counts_errors(self, tmp_path):
        """Count format correctly counts errors."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [E1 1-1] e1\n"
            "ERROR: [E2 1-2] e2\n"
            "ERROR: [E3 1-3] e3\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        assert "errors=3" in result.output

    def test_count_format_counts_warnings(self, tmp_path):
        """Count format correctly counts warnings."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [W1 1-1] w1\n"
            "WARNING: [W2 1-2] w2\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        assert "warnings=2" in result.output

    def test_count_format_mixed_severities(self, tmp_path):
        """Count format shows all severity counts."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [E1 1-1] error\n"
            "WARNING: [W1 2-1] warning\n"
            "INFO: [I1 3-1] info\n"
            "INFO: [I2 3-2] info2\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        assert "errors=1" in result.output
        assert "warnings=1" in result.output
        assert "info=2" in result.output

    def test_count_format_total(self, tmp_path):
        """Count format includes total message count."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [E1 1-1] e1\n"
            "WARNING: [W1 2-1] w1\n"
            "INFO: [I1 3-1] i1\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        assert "total=3" in result.output

    def test_count_format_critical_warnings(self, tmp_path):
        """Count format counts critical warnings."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "CRITICAL WARNING: [CW1 1-1] critical warning\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        assert "critical_warnings=1" in result.output

    def test_count_format_case_insensitive(self, tmp_path):
        """--format COUNT should work (case insensitive)."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "COUNT"])

        assert result.exit_code == 0
        assert "total=" in result.output


class TestTextFormat:
    """Tests for text (default) output format."""

    def test_text_format_default(self, tmp_path):
        """Text format is the default."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado"])

        assert result.exit_code == 0
        # Should have raw text output, not JSON
        assert "ERROR: [Test 1-1] message" in result.output

    def test_text_format_explicit(self, tmp_path):
        """Text format can be explicitly specified."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] warning message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "text"])

        assert result.exit_code == 0
        assert "WARNING: [Test 1-1] warning message" in result.output

    def test_text_format_preserves_raw_text(self, tmp_path):
        """Text format preserves original message text."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Synth 8-6157] synthesizing module 'top'\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "text"])

        assert result.exit_code == 0
        assert "INFO: [Synth 8-6157] synthesizing module 'top'" in result.output

    def test_text_format_multiple_messages(self, tmp_path):
        """Text format outputs multiple messages."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [I1 1-1] first\n"
            "WARNING: [W1 2-1] second\n"
            "ERROR: [E1 3-1] third\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "text"])

        assert result.exit_code == 0
        assert "INFO: [I1 1-1] first" in result.output
        assert "WARNING: [W1 2-1] second" in result.output
        assert "ERROR: [E1 3-1] third" in result.output


class TestFormatWithFilters:
    """Tests that formats work correctly with filters."""

    def test_json_with_severity_filter(self, tmp_path):
        """JSON format respects severity filter."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [I1 1-1] info\n"
            "ERROR: [E1 2-1] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--format", "json", "--severity", "error"]
        )

        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["severity"] == "error"

    def test_count_with_severity_filter(self, tmp_path):
        """Count format respects severity filter."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [I1 1-1] info\n"
            "INFO: [I2 1-2] info2\n"
            "ERROR: [E1 2-1] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--format", "count", "--severity", "error"]
        )

        assert result.exit_code == 0
        assert "total=1" in result.output
        assert "errors=1" in result.output

    def test_json_with_suppress(self, tmp_path):
        """JSON format respects suppression patterns."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [I1 1-1] keep this\n"
            "INFO: [I2 1-2] suppress this\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--format", "json", "--suppress", "suppress"]
        )

        assert result.exit_code == 0
        lines = [l for l in result.output.strip().split("\n") if l.startswith("{")]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert "keep this" in data["raw_text"]


class TestFormatHelpAndErrors:
    """Tests for format option in help and error cases."""

    def test_format_in_help(self):
        """--format option appears in help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--format" in result.output
        assert "text" in result.output.lower()
        assert "json" in result.output.lower()
        assert "count" in result.output.lower()

    def test_invalid_format_rejected(self, tmp_path):
        """Invalid format choice is rejected."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] message\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado", "--format", "invalid"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()
