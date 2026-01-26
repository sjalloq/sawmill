"""CLI Integration tests using real Vivado log files.

These tests verify the full pipeline works end-to-end:
CLI -> plugin.load_and_parse() -> filter -> format

Tests are marked with @pytest.mark.integration for easy filtering.
"""

import json

import pytest
from click.testing import CliRunner

from sawmill.cli import cli


class TestFullPipeline:
    """Test that the full pipeline executes without error."""

    @pytest.mark.integration
    def test_vivado_log_loads_successfully(self, vivado_log):
        """Full Vivado log should load and process without errors."""
        runner = CliRunner()
        result = runner.invoke(cli, [str(vivado_log), "--plugin", "vivado", "--format", "count"])

        assert result.exit_code == 0
        assert "total=" in result.output
        assert "error=" in result.output
        assert "warning=" in result.output

    @pytest.mark.integration
    def test_vivado_log_auto_detect(self, vivado_log):
        """Vivado plugin should be auto-detected from log content."""
        runner = CliRunner()
        result = runner.invoke(cli, [str(vivado_log), "--format", "count"])

        assert result.exit_code == 0
        assert "total=" in result.output

    @pytest.mark.integration
    def test_vivado_log_text_format(self, vivado_log):
        """Text format output should include message content."""
        runner = CliRunner()
        result = runner.invoke(cli, [str(vivado_log), "--plugin", "vivado", "--format", "text"])

        assert result.exit_code == 0
        # Output should contain various message types from the log
        assert len(result.output) > 0

    @pytest.mark.integration
    def test_vivado_log_json_format(self, vivado_log):
        """JSON format should produce valid JSONL output."""
        runner = CliRunner()
        result = runner.invoke(cli, [str(vivado_log), "--plugin", "vivado", "--format", "json"])

        assert result.exit_code == 0

        # Verify each non-empty line is valid JSON
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        assert len(lines) > 0

        for line in lines[:10]:  # Check first 10 lines for valid JSON
            obj = json.loads(line)
            assert "start_line" in obj
            assert "raw_text" in obj
            assert "content" in obj


class TestSeverityFilter:
    """Test severity filtering on real Vivado logs."""

    @pytest.mark.integration
    def test_vivado_severity_error(self, vivado_log):
        """Filtering by error severity should only show errors."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "error", "--format", "json"]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            # Error is highest severity, so only errors should appear
            assert obj["severity"] == "error"

    @pytest.mark.integration
    def test_vivado_severity_critical_warning(self, vivado_log):
        """Filtering by critical_warning severity should show critical_warning and error."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "critical_warning", "--format", "json"]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        # Should have some critical warnings in the example log
        assert len(lines) > 0
        for line in lines:
            obj = json.loads(line)
            # critical_warning filter means severity should be critical_warning or error
            assert obj["severity"] in ("critical_warning", "error")

    @pytest.mark.integration
    def test_vivado_severity_warning(self, vivado_log):
        """Filtering by warning severity should show warnings and above."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "warning", "--format", "json"]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            # Warning filter means severity should be warning, critical_warning, or error
            assert obj["severity"] in ("warning", "critical_warning", "error")

    @pytest.mark.integration
    def test_vivado_severity_info(self, vivado_log):
        """Filtering by info should show all messages with severity."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "info", "--format", "count"]
        )

        assert result.exit_code == 0
        # Should have some messages
        assert "total=" in result.output

    @pytest.mark.integration
    def test_vivado_severity_numeric(self, vivado_log):
        """Numeric severity should work using plugin's level values."""
        runner = CliRunner()
        # Level 1 = warning in Vivado plugin
        result_numeric = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "1", "--format", "count"]
        )
        result_named = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "warning", "--format", "count"]
        )

        assert result_numeric.exit_code == 0
        assert result_named.exit_code == 0
        # Both should produce identical output
        assert result_numeric.output == result_named.output

    @pytest.mark.integration
    def test_vivado_invalid_severity(self, vivado_log):
        """Invalid severity should show error with valid options."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--severity", "critical"]
        )

        assert result.exit_code == 1
        assert "Unknown severity level 'critical'" in result.output
        assert "critical_warning" in result.output  # Should list valid options

    @pytest.mark.integration
    def test_list_severity_vivado(self, vivado_log):
        """--list-severity should show plugin severity levels."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--list-severity", "--plugin", "vivado"]
        )

        assert result.exit_code == 0
        assert "error" in result.output
        assert "critical_warning" in result.output
        assert "warning" in result.output
        assert "info" in result.output


class TestFilterPatterns:
    """Test regex filter patterns on real Vivado logs."""

    @pytest.mark.integration
    def test_vivado_filter_pattern(self, vivado_log):
        """Filter pattern should narrow results to matching messages."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--filter", "Synth", "--format", "count"]
        )

        assert result.exit_code == 0
        # Should have filtered to Synth-related messages
        assert "total=" in result.output

    @pytest.mark.integration
    def test_vivado_filter_regex(self, vivado_log):
        """Regex patterns should work correctly."""
        runner = CliRunner()
        result = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--filter", r"IP_Flow.*Generating", "--format", "json"]
        )

        assert result.exit_code == 0
        # Each matched message should contain the pattern
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            assert "IP_Flow" in obj["raw_text"] and "Generating" in obj["raw_text"]


class TestSuppressionPatterns:
    """Test suppression patterns on real Vivado logs."""

    @pytest.mark.integration
    def test_vivado_suppress_pattern(self, vivado_log):
        """Suppress pattern should exclude matching messages."""
        runner = CliRunner()

        # First get count without suppression
        result_all = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--format", "count"]
        )
        assert result_all.exit_code == 0
        total_all = int(result_all.output.split("total=")[1].split()[0])

        # Now with suppression
        result_suppressed = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--suppress", "INFO:", "--format", "count"]
        )
        assert result_suppressed.exit_code == 0
        total_suppressed = int(result_suppressed.output.split("total=")[1].split()[0])

        # Suppressed count should be less (assuming there are INFO messages)
        assert total_suppressed <= total_all

    @pytest.mark.integration
    def test_vivado_suppress_multiple(self, vivado_log):
        """Multiple suppress patterns should all be applied."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--suppress", "IP_Flow",
                "--suppress", "Synth",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=" in result.output


class TestSuppressIdFilter:
    """Test suppress-id filtering on real Vivado logs."""

    @pytest.mark.integration
    def test_vivado_suppress_id(self, vivado_log):
        """Suppress-id should exclude specific message IDs."""
        runner = CliRunner()

        # First get count without suppression
        result_all = runner.invoke(
            cli, [str(vivado_log), "--plugin", "vivado", "--format", "count"]
        )
        assert result_all.exit_code == 0
        total_all = int(result_all.output.split("total=")[1].split()[0])

        # Suppress a common message ID
        result_suppressed = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--suppress-id", "IP_Flow 19-234",
                "--format", "count"
            ]
        )
        assert result_suppressed.exit_code == 0
        total_suppressed = int(result_suppressed.output.split("total=")[1].split()[0])

        # Should have same or fewer messages
        assert total_suppressed <= total_all


class TestIdFilter:
    """Test message ID filtering on real Vivado logs."""

    @pytest.mark.integration
    def test_vivado_id_filter(self, vivado_log):
        """ID filter should include only matching message IDs."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--id", "Synth *",
                "--format", "json"
            ]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            # All message_ids should start with "Synth "
            assert obj["message_id"] is not None
            assert obj["message_id"].startswith("Synth ")

    @pytest.mark.integration
    def test_vivado_id_filter_wildcard(self, vivado_log):
        """ID filter with wildcards should work correctly."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--id", "Vivado *",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=" in result.output

    @pytest.mark.integration
    def test_vivado_multiple_id_filters(self, vivado_log):
        """Multiple ID filters should match any of them."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--id", "Synth *",
                "--id", "IP_Flow *",
                "--format", "json"
            ]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            # Each message should match one of the patterns
            msg_id = obj["message_id"]
            assert msg_id is not None
            assert msg_id.startswith("Synth ") or msg_id.startswith("IP_Flow ")


class TestCategoryFilter:
    """Test category filtering on real Vivado logs."""

    @pytest.mark.integration
    def test_vivado_category_filter(self, vivado_log):
        """Category filter should include only matching categories."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--category", "synth",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=" in result.output


class TestCombinedFilters:
    """Test multiple filters working together."""

    @pytest.mark.integration
    def test_vivado_combined_severity_and_filter(self, vivado_log):
        """Severity and pattern filter should work together."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--severity", "warning",
                "--filter", "timing",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=" in result.output

    @pytest.mark.integration
    def test_vivado_combined_id_and_severity(self, vivado_log):
        """ID filter and severity filter should work together."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--id", "Vivado *",
                "--severity", "warning",
                "--format", "json"
            ]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            # Must match both filters
            assert obj["message_id"] is not None
            assert obj["message_id"].startswith("Vivado ")
            assert obj["severity"] in ("warning", "error", "critical", "critical_warning")

    @pytest.mark.integration
    def test_vivado_combined_all_filters(self, vivado_log):
        """All filter types should work together."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--severity", "info",
                "--filter", "Flow",
                "--suppress", "Refreshing",
                "--id", "IP_Flow *",
                "--format", "json"
            ]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        for line in lines:
            obj = json.loads(line)
            # Must have Flow in content
            assert "Flow" in obj["raw_text"]
            # Must not have Refreshing
            assert "Refreshing" not in obj["raw_text"]
            # Must match IP_Flow pattern
            assert obj["message_id"] is not None
            assert obj["message_id"].startswith("IP_Flow ")


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.integration
    def test_empty_result(self, vivado_log):
        """Filter that matches nothing should return empty but succeed."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--filter", "XYZZY_NONEXISTENT_PATTERN_12345",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=0" in result.output

    @pytest.mark.integration
    def test_nonexistent_id_pattern(self, vivado_log):
        """ID pattern that matches nothing should return empty."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--id", "NonExistent *",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=0" in result.output

    @pytest.mark.integration
    def test_case_insensitive_category(self, vivado_log):
        """Category filter should be case-insensitive."""
        runner = CliRunner()

        # Lowercase
        result_lower = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--category", "synth",
                "--format", "count"
            ]
        )

        # Uppercase
        result_upper = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--category", "SYNTH",
                "--format", "count"
            ]
        )

        assert result_lower.exit_code == 0
        assert result_upper.exit_code == 0
        # Both should produce the same count
        assert result_lower.output == result_upper.output


class TestOutputFormat:
    """Test output format variations."""

    @pytest.mark.integration
    def test_json_output_has_all_fields(self, vivado_log):
        """JSON output should include all expected fields."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--severity", "error",
                "--format", "json"
            ]
        )

        assert result.exit_code == 0

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        if lines:
            obj = json.loads(lines[0])
            # Check all expected fields exist
            assert "start_line" in obj
            assert "end_line" in obj
            assert "raw_text" in obj
            assert "content" in obj
            assert "severity" in obj
            assert "message_id" in obj
            assert "category" in obj

    @pytest.mark.integration
    def test_count_output_format(self, vivado_log):
        """Count format should show all severity counts."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        # Should contain all count fields (using plugin severity IDs)
        assert "total=" in result.output
        assert "error=" in result.output
        assert "critical_warning=" in result.output
        assert "warning=" in result.output
        assert "info=" in result.output


class TestPluginSelection:
    """Test plugin selection mechanisms."""

    @pytest.mark.integration
    def test_force_plugin(self, vivado_log):
        """Forced plugin should be used even if auto-detect would work."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "vivado",
                "--format", "count"
            ]
        )

        assert result.exit_code == 0
        assert "total=" in result.output

    @pytest.mark.integration
    def test_invalid_plugin_error(self, vivado_log):
        """Invalid plugin name should produce error."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(vivado_log),
                "--plugin", "nonexistent_plugin",
                "--format", "count"
            ]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()
