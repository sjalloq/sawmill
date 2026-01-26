"""Tests for CI summary report generation (Task 7.3)."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli


class TestCIReportGeneration:
    """Test --report option for generating JSON reports."""

    def test_ci_report_generation(self, tmp_path):
        """Basic CI report generation with errors and warnings."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] e1\n"
            "WARNING: [Vivado 12-1] w1\n"
            "WARNING: [Vivado 12-2] w2\n"
            "INFO: [Common 17-1] i1\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        assert report_file.exists()

        report = json.loads(report_file.read_text())

        assert "summary" in report
        assert report["exit_code"] == 1  # Has error

    def test_ci_report_includes_counts(self, tmp_path):
        """Report should include message counts by severity."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error1\n"
            "ERROR: [Route 35-1] error2\n"
            "CRITICAL WARNING: [Constraints 18-1] critical warning\n"
            "WARNING: [Vivado 12-1] warning1\n"
            "WARNING: [Vivado 12-2] warning2\n"
            "WARNING: [Vivado 12-3] warning3\n"
            "INFO: [Common 17-1] info1\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        summary = report["summary"]
        assert summary["total"] == 7
        assert summary["by_severity"]["error"] == 2
        assert summary["by_severity"]["critical_warning"] == 1
        assert summary["by_severity"]["warning"] == 3
        assert summary["by_severity"]["info"] == 1

    def test_ci_report_includes_unwaived_issues(self, tmp_path):
        """Report should include list of unwaived issues."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] first error\n"
            "ERROR: [Route 35-1] second error\n"
            "WARNING: [Vivado 12-1] a warning\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        assert "issues" in report
        issues = report["issues"]
        assert len(issues) == 3

        # Check that issues contain expected fields
        for issue in issues:
            assert "message_id" in issue
            assert "severity" in issue
            assert "content" in issue
            assert "line" in issue

    def test_ci_report_exit_code_zero(self, tmp_path):
        """Report shows exit_code 0 when no errors (with --fail-on error)."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Common 17-1] info message\n"
            "WARNING: [Vivado 12-1] just a warning\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        # Use --fail-on error since default now fails on warning+
        result = runner.invoke(
            cli,
            ["--check", "--fail-on", "error", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        assert report["exit_code"] == 0

    def test_ci_report_exit_code_with_strict(self, tmp_path):
        """Report shows exit_code 1 with --fail-on warning."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Common 17-1] info message\n"
            "WARNING: [Vivado 12-1] just a warning\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--fail-on",
                "warning",
                "--plugin",
                "vivado",
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        assert report["exit_code"] == 1  # --fail-on warning, warnings cause failure

    def test_ci_report_with_waivers(self, tmp_path):
        """Report should show waived and unwaived counts separately."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error to waive\n"
            "ERROR: [Route 35-1] error to keep\n"
            "WARNING: [Vivado 12-1] warning\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text(
            '[[waiver]]\npattern = "Synth 8-1"\n'
            'type = "id"\n'
            'reason = "Known issue"\n'
            'author = "test"\n'
            'date = "2025-01-01"\n'
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--plugin",
                "vivado",
                "--waivers",
                str(waiver_file),
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        assert report["summary"]["waived"] == 1
        # by_severity counts unwaived messages only
        assert report["summary"]["by_severity"]["error"] == 1

    def test_ci_report_includes_waived_list(self, tmp_path):
        """Report should include list of waived messages."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] waived error\n"
            "ERROR: [Route 35-1] another error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text(
            '[[waiver]]\npattern = "Synth 8-1"\n'
            'type = "id"\n'
            'reason = "Known issue"\n'
            'author = "test"\n'
            'date = "2025-01-01"\n'
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--plugin",
                "vivado",
                "--waivers",
                str(waiver_file),
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        assert "waived" in report
        assert len(report["waived"]) == 1
        assert report["waived"][0]["message_id"] == "Synth 8-1"
        assert report["waived"][0]["waiver_reason"] == "Known issue"


class TestReportFileCreation:
    """Test report file writing behavior."""

    def test_report_creates_parent_directory(self, tmp_path):
        """Report should create parent directories if they don't exist."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Common 17-1] test\n")

        report_file = tmp_path / "subdir" / "nested" / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        assert report_file.exists()

    def test_report_is_valid_json(self, tmp_path):
        """Report file should be valid JSON."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Common 17-1] test\n")

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        # Should not raise json.JSONDecodeError
        report = json.loads(report_file.read_text())
        assert isinstance(report, dict)


class TestReportWithFilters:
    """Test report generation with various filters applied."""

    def test_report_respects_severity_filter(self, tmp_path):
        """Report should only count messages at or above severity level."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error\n"
            "WARNING: [Vivado 12-1] warning\n"
            "INFO: [Common 17-1] info\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--plugin",
                "vivado",
                "--severity",
                "warning",
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        # Only error and warning should be counted
        assert report["summary"]["total"] == 2
        assert report["summary"]["by_severity"]["error"] == 1
        assert report["summary"]["by_severity"]["warning"] == 1
        assert report["summary"]["by_severity"]["info"] == 0

    def test_report_respects_suppress_id(self, tmp_path):
        """Report should not count suppressed messages."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error1\n"
            "ERROR: [Route 35-1] error2\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--plugin",
                "vivado",
                "--suppress-id",
                "Synth 8-1",
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        assert report["summary"]["total"] == 1
        assert report["summary"]["by_severity"]["error"] == 1


class TestReportMetadata:
    """Test report metadata fields."""

    def test_report_includes_metadata(self, tmp_path):
        """Report should include metadata about the run."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Common 17-1] test\n")

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        assert "metadata" in report
        assert "log_file" in report["metadata"]
        assert "plugin" in report["metadata"]

    def test_report_includes_timestamp(self, tmp_path):
        """Report should include a timestamp."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Common 17-1] test\n")

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        assert "timestamp" in report["metadata"]


class TestReportWithoutCI:
    """Test --report behavior without --check flag."""

    def test_report_works_without_ci(self, tmp_path):
        """Report can be generated even without --check mode."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error\n"
            "INFO: [Common 17-1] info\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        assert report_file.exists()
        report = json.loads(report_file.read_text())

        # exit_code should still be calculated
        assert "exit_code" in report
        assert report["exit_code"] == 1  # Has error

    def test_report_without_ci_doesnt_affect_exit_code(self, tmp_path):
        """Without --check, CLI exit code should be 0 even with errors."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        # CLI exit code is 0 (no --check)
        assert result.exit_code == 0

        # But report shows what would be the CI exit code
        report = json.loads(report_file.read_text())
        assert report["exit_code"] == 1


class TestReportEdgeCases:
    """Test edge cases in report generation."""

    def test_report_empty_log(self, tmp_path):
        """Report handles empty log files."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\n")

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        assert report["summary"]["total"] == 0
        assert report["exit_code"] == 0

    def test_report_only_info_messages(self, tmp_path):
        """Report handles logs with only info messages."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Common 17-1] info1\n"
            "INFO: [Common 17-2] info2\n"
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--check", "--plugin", "vivado", "--report", str(report_file), str(log_file)],
        )

        report = json.loads(report_file.read_text())

        assert report["summary"]["total"] == 2
        assert report["summary"]["by_severity"]["error"] == 0
        assert report["exit_code"] == 0

    def test_report_all_errors_waived(self, tmp_path):
        """When all errors are waived, exit_code should be 0."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text(
            '[[waiver]]\npattern = "Synth 8-1"\n'
            'type = "id"\n'
            'reason = "Known issue"\n'
            'author = "test"\n'
            'date = "2025-01-01"\n'
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--plugin",
                "vivado",
                "--waivers",
                str(waiver_file),
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        assert report["summary"]["waived"] == 1
        # by_severity counts unwaived messages, so errors should be 0
        assert report["summary"]["by_severity"]["error"] == 0
        assert report["exit_code"] == 0


class TestReportUnusedWaivers:
    """Test unused waivers in report."""

    def test_report_includes_unused_waivers(self, tmp_path):
        """Report should include unused waivers."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Synth 8-1] error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text(
            '[[waiver]]\npattern = "Synth 8-1"\n'
            'type = "id"\n'
            'reason = "Used waiver"\n'
            'author = "test"\n'
            'date = "2025-01-01"\n\n'
            '[[waiver]]\npattern = "Route 99-99"\n'
            'type = "id"\n'
            'reason = "Unused waiver"\n'
            'author = "test"\n'
            'date = "2025-01-01"\n'
        )

        report_file = tmp_path / "report.json"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--check",
                "--plugin",
                "vivado",
                "--waivers",
                str(waiver_file),
                "--report",
                str(report_file),
                str(log_file),
            ],
        )

        report = json.loads(report_file.read_text())

        assert "unused_waivers" in report
        assert len(report["unused_waivers"]) == 1
        assert report["unused_waivers"][0]["pattern"] == "Route 99-99"
