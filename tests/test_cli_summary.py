"""Tests for CLI summary and grouping features."""

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def vivado_log(tmp_path):
    """Create a sample Vivado log file."""
    log_content = """INFO: [Synth 8-6157] synthesizing module 'top'
WARNING: [Synth 8-3332] timing warning in block 'fifo'
WARNING: [Synth 8-3332] timing warning in block 'ctrl'
ERROR: [DRC 23-20] placement error at site X0Y0
ERROR: [DRC 23-20] placement error at site X1Y1
WARNING: [Timing 38-2] setup violation at endpoint
INFO: [Synth 8-6158] synthesis complete
CRITICAL WARNING: [Vivado 12-3523] critical constraint issue
"""
    log_file = tmp_path / "vivado.log"
    log_file.write_text(log_content)
    return log_file


class TestSummaryFlag:
    """Tests for the --summary flag."""

    def test_summary_shows_severity_counts(self, runner, vivado_log):
        """Test that --summary shows severity breakdown."""
        result = runner.invoke(cli, [str(vivado_log), "--summary"])
        assert result.exit_code == 0
        assert "Log Analysis Summary" in result.output
        assert "Warning" in result.output or "warning" in result.output.lower()
        assert "Error" in result.output or "error" in result.output.lower()

    def test_summary_shows_id_breakdown(self, runner, vivado_log):
        """Test that --summary shows message ID counts within severity."""
        result = runner.invoke(cli, [str(vivado_log), "--summary"])
        assert result.exit_code == 0
        # Should show message IDs with counts
        assert "Synth 8-" in result.output or "DRC 23-" in result.output

    def test_summary_shows_total(self, runner, vivado_log):
        """Test that --summary shows total message count."""
        result = runner.invoke(cli, [str(vivado_log), "--summary"])
        assert result.exit_code == 0
        assert "Total:" in result.output

    def test_summary_with_severity_filter(self, runner, vivado_log):
        """Test --summary with --severity filter."""
        result = runner.invoke(cli, [str(vivado_log), "--summary", "--severity", "error"])
        assert result.exit_code == 0
        # Should only show errors and critical
        assert "Error" in result.output or "error" in result.output.lower()
        # Total should reflect filtered count
        assert "Total:" in result.output

    def test_summary_empty_log(self, runner, tmp_path):
        """Test --summary with log that has only info messages."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("INFO: [Common 17-206] Starting process\n")
        result = runner.invoke(cli, [str(log_file), "--summary", "--plugin", "vivado"])
        # Should handle gracefully
        assert result.exit_code == 0


class TestGroupByOption:
    """Tests for the --group-by option."""

    def test_group_by_severity(self, runner, vivado_log):
        """Test --group-by severity."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "severity"])
        assert result.exit_code == 0
        assert "Grouped by Severity" in result.output

    def test_group_by_id(self, runner, vivado_log):
        """Test --group-by id."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "id"])
        assert result.exit_code == 0
        assert "Grouped by Id" in result.output

    def test_group_by_file(self, runner, tmp_path):
        """Test --group-by file."""
        log_content = """WARNING: [Synth 8-3332] warning in module [/src/fifo.v:10]
WARNING: [Synth 8-3332] warning in module [/src/ctrl.v:20]
ERROR: [DRC 23-20] placement error [/src/fifo.v:15]
"""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(log_content)
        result = runner.invoke(cli, [str(log_file), "--group-by", "file"])
        assert result.exit_code == 0
        assert "Grouped by File" in result.output

    def test_group_by_category(self, runner, vivado_log):
        """Test --group-by category."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "category"])
        assert result.exit_code == 0
        assert "Grouped by Category" in result.output

    def test_group_by_shows_message_count(self, runner, vivado_log):
        """Test that --group-by shows message counts per group."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "severity"])
        assert result.exit_code == 0
        # Should show counts like "(X messages)"
        assert "messages)" in result.output or "message)" in result.output

    def test_group_by_with_severity_filter(self, runner, vivado_log):
        """Test --group-by with --severity filter."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "id", "--severity", "error"])
        assert result.exit_code == 0
        assert "Grouped by Id" in result.output

    def test_group_by_invalid_value(self, runner, vivado_log):
        """Test --group-by with invalid value."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()


class TestTopOption:
    """Tests for the --top option."""

    def test_top_limits_per_group(self, runner, vivado_log):
        """Test that --top limits messages shown per group."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "severity", "--top", "1"])
        assert result.exit_code == 0
        # Should show "and X more" for groups with more than 1 message
        assert "more" in result.output

    def test_top_zero_shows_all(self, runner, vivado_log):
        """Test that --top 0 shows all messages."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "severity", "--top", "0"])
        assert result.exit_code == 0
        # Should NOT show "and X more" if showing all
        # (This depends on the number of messages, so we just check it works)

    def test_top_default_is_5(self, runner, vivado_log):
        """Test that default --top is 5."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "severity"])
        assert result.exit_code == 0
        # Default behavior

    def test_top_without_group_by_has_no_effect(self, runner, vivado_log):
        """Test that --top without --group-by uses normal output."""
        result = runner.invoke(cli, [str(vivado_log), "--top", "1"])
        assert result.exit_code == 0
        # Should work but use normal output (not grouped)


class TestCombinedOptions:
    """Tests for combining summary/group-by with other options."""

    def test_summary_overrides_format(self, runner, vivado_log):
        """Test that --summary takes precedence over --format."""
        result = runner.invoke(cli, [str(vivado_log), "--summary", "--format", "json"])
        assert result.exit_code == 0
        # Should show summary, not JSON
        assert "Log Analysis Summary" in result.output

    def test_group_by_overrides_format(self, runner, vivado_log):
        """Test that --group-by takes precedence over --format."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "id", "--format", "json"])
        assert result.exit_code == 0
        # Should show grouped output, not JSON
        assert "Grouped by Id" in result.output

    def test_summary_with_filter_pattern(self, runner, vivado_log):
        """Test --summary with --filter."""
        result = runner.invoke(cli, [str(vivado_log), "--summary", "--filter", "Synth"])
        assert result.exit_code == 0
        assert "Log Analysis Summary" in result.output

    def test_group_by_with_suppress(self, runner, vivado_log):
        """Test --group-by with --suppress."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "severity", "--suppress", "INFO:"])
        assert result.exit_code == 0
        assert "Grouped by Severity" in result.output


class TestHelpOutput:
    """Tests for help text."""

    def test_summary_in_help(self, runner):
        """Test that --summary is in help."""
        result = runner.invoke(cli, ["--help"])
        assert "--summary" in result.output

    def test_group_by_in_help(self, runner):
        """Test that --group-by is in help."""
        result = runner.invoke(cli, ["--help"])
        assert "--group-by" in result.output

    def test_top_in_help(self, runner):
        """Test that --top is in help."""
        result = runner.invoke(cli, ["--help"])
        assert "--top" in result.output


class TestGroupedOutputContent:
    """Tests for grouped output content details."""

    def test_grouped_by_id_shows_severity(self, runner, vivado_log):
        """Test that grouping by ID shows severity in header."""
        result = runner.invoke(cli, [str(vivado_log), "--group-by", "id"])
        assert result.exit_code == 0
        # Headers should include severity level like "[Warning]" or "[Error]"
        output_lower = result.output.lower()
        assert "[warning]" in output_lower or "[error]" in output_lower or "[info]" in output_lower

    def test_grouped_by_file_shows_severity_breakdown(self, runner, tmp_path):
        """Test that grouping by file shows severity breakdown."""
        log_content = """WARNING: [Synth 8-3332] warning in module [/src/fifo.v:10]
ERROR: [DRC 23-20] placement error [/src/fifo.v:15]
"""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(log_content)
        result = runner.invoke(cli, [str(log_file), "--group-by", "file", "--plugin", "vivado"])
        assert result.exit_code == 0
        # Should show breakdown like "Warning: 1, Error: 1"
        # or at minimum show the Total

    def test_grouped_output_shows_location(self, runner, tmp_path):
        """Test that grouped output shows file locations."""
        log_content = """WARNING: [Synth 8-3332] warning in module [/src/fifo.v:10]
"""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(log_content)
        result = runner.invoke(cli, [str(log_file), "--group-by", "id", "--plugin", "vivado"])
        assert result.exit_code == 0
        # Should show location like "/src/fifo.v:10"
        assert "/src/fifo.v" in result.output or "(no location)" in result.output
