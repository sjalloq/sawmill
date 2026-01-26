"""Tests for message ID and category filtering CLI options (Task 4.3)."""

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli


class TestExactIdFilter:
    """Tests for exact message ID filtering."""

    def test_exact_id_filter(self, tmp_path):
        """Filter by exact message ID."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Vivado 12-3523] msg1\n"
            "WARNING: [Vivado 12-4739] msg2\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--id", "Vivado 12-3523"]
        )

        assert result.exit_code == 0
        assert "12-3523" in result.output
        assert "12-4739" not in result.output

    def test_exact_id_filter_no_match(self, tmp_path):
        """Filter with ID that doesn't match produces no output."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Vivado 12-3523] msg1\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--id", "Synth 8-1234"]
        )

        assert result.exit_code == 0
        assert "12-3523" not in result.output

    def test_exact_id_filter_multiple_matches(self, tmp_path):
        """Filter by exact ID matches all occurrences."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Vivado 12-3523] first occurrence\n"
            "INFO: [Synth 8-1234] other message\n"
            "WARNING: [Vivado 12-3523] second occurrence\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--id", "Vivado 12-3523"]
        )

        assert result.exit_code == 0
        assert "first occurrence" in result.output
        assert "second occurrence" in result.output
        assert "Synth" not in result.output


class TestWildcardIdFilter:
    """Tests for wildcard message ID filtering."""

    def test_wildcard_id_filter(self, tmp_path):
        """Filter by wildcard pattern matches multiple IDs."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-6157] a\n"
            "INFO: [Synth 8-6155] b\n"
            "INFO: [Vivado 12-1] c\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--id", "Synth 8-*"]
        )

        assert result.exit_code == 0
        assert "8-6157" in result.output
        assert "8-6155" in result.output
        # Vivado 12-1 should not be in filtered output
        assert "Vivado 12-1" not in result.output

    def test_wildcard_prefix_match(self, tmp_path):
        """Wildcard at end matches varying suffixes."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [DRC 1-100] drc1\n"
            "WARNING: [DRC 1-200] drc2\n"
            "WARNING: [DRC 2-100] drc3\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--id", "DRC 1-*"]
        )

        assert result.exit_code == 0
        assert "DRC 1-100" in result.output
        assert "DRC 1-200" in result.output
        assert "DRC 2-100" not in result.output

    def test_wildcard_question_mark(self, tmp_path):
        """Question mark matches single character."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-10] ten\n"
            "INFO: [Synth 8-11] eleven\n"
            "INFO: [Synth 8-100] hundred\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--id", "Synth 8-1?"]
        )

        assert result.exit_code == 0
        assert "Synth 8-10" in result.output
        assert "Synth 8-11" in result.output
        assert "Synth 8-100" not in result.output


class TestMultipleIdPatterns:
    """Tests for multiple --id options."""

    def test_multiple_id_patterns(self, tmp_path):
        """Multiple --id options match any of them."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] synth\n"
            "WARNING: [DRC 1-1] drc\n"
            "ERROR: [Route 35-9] route\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--plugin",
                "vivado",
                "--id",
                "Synth 8-*",
                "--id",
                "Route 35-*",
            ],
        )

        assert result.exit_code == 0
        assert "Synth" in result.output
        assert "Route" in result.output
        assert "DRC" not in result.output


class TestCategoryFilter:
    """Tests for category filtering."""

    def test_category_filter_single(self, tmp_path):
        """Filter by single category."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-6157] synthesizing\n"
            "INFO: [Synth 8-6155] synthesis done\n"
            "WARNING: [DRC 1-100] design rule check\n"
            "INFO: [Route 35-1] routing\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--category", "synth"]
        )

        assert result.exit_code == 0
        assert "Synth 8-6157" in result.output
        assert "Synth 8-6155" in result.output
        assert "DRC" not in result.output
        assert "Route" not in result.output

    def test_category_filter_case_insensitive(self, tmp_path):
        """Category filter is case-insensitive."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] message\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--category", "SYNTH"]
        )

        assert result.exit_code == 0
        assert "Synth" in result.output

    def test_multiple_categories(self, tmp_path):
        """Multiple --category options match any of them."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] synth msg\n"
            "WARNING: [DRC 1-1] drc msg\n"
            "ERROR: [Route 35-9] route msg\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--plugin",
                "vivado",
                "--category",
                "synth",
                "--category",
                "route",
            ],
        )

        assert result.exit_code == 0
        assert "Synth" in result.output
        assert "Route" in result.output
        assert "DRC" not in result.output

    def test_category_no_match(self, tmp_path):
        """Category filter with no matches produces no output."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] message\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--category", "timing"]
        )

        assert result.exit_code == 0
        assert "Synth" not in result.output


class TestIdAndCategoryCombined:
    """Tests for combining --id and --category filters."""

    def test_id_and_category_both_must_match(self, tmp_path):
        """When both --id and --category are specified, both must match."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] synth message 1\n"
            "INFO: [Synth 8-2] synth message 2\n"
            "WARNING: [DRC 1-1] drc message\n"
        )

        runner = CliRunner()
        # Filter by ID pattern AND category - both must match
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--plugin",
                "vivado",
                "--id",
                "Synth 8-1",
                "--category",
                "synth",
            ],
        )

        assert result.exit_code == 0
        assert "Synth 8-1" in result.output
        assert "Synth 8-2" not in result.output
        assert "DRC" not in result.output


class TestIdFilterWithOtherFilters:
    """Tests for --id combined with other filter options."""

    def test_id_filter_with_severity(self, tmp_path):
        """--id combined with --severity."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] info\n"
            "WARNING: [Synth 8-2] warning\n"
            "ERROR: [Synth 8-3] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--plugin",
                "vivado",
                "--id",
                "Synth 8-*",
                "--severity",
                "warning",
            ],
        )

        assert result.exit_code == 0
        assert "Synth 8-1" not in result.output  # INFO filtered out
        assert "Synth 8-2" in result.output
        assert "Synth 8-3" in result.output

    def test_id_filter_with_json_format(self, tmp_path):
        """--id with JSON output format."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Vivado 12-3523] test message\n"
            "INFO: [Synth 8-1] other\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--plugin",
                "vivado",
                "--id",
                "Vivado 12-3523",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert '"message_id": "Vivado 12-3523"' in result.output
        assert "Synth" not in result.output

    def test_id_filter_with_count_format(self, tmp_path):
        """--id with count output format."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Synth 8-1] a\n"
            "WARNING: [Synth 8-2] b\n"
            "ERROR: [Synth 8-3] c\n"
            "INFO: [DRC 1-1] d\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--plugin",
                "vivado",
                "--id",
                "Synth 8-*",
                "--format",
                "count",
            ],
        )

        assert result.exit_code == 0
        assert "total=3" in result.output
        assert "warning=2" in result.output
        assert "error=1" in result.output


class TestHelp:
    """Tests for help output."""

    def test_id_option_in_help(self):
        """--id option appears in help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--id" in result.output
        assert "wildcard" in result.output.lower()

    def test_category_option_in_help(self):
        """--category option appears in help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--category" in result.output
