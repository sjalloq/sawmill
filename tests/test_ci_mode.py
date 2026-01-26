"""Tests for check mode exit code logic."""

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli


class TestCheckModeBasic:
    """Basic tests for check mode pass/fail behavior."""

    def test_check_pass_on_clean_log(self, tmp_path):
        """Check mode should exit 0 on a clean log (info only)."""
        log_file = tmp_path / "clean.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0

    def test_check_fail_on_error(self, tmp_path):
        """Check mode should exit 1 on error messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_check_fail_on_critical_warning(self, tmp_path):
        """Check mode should exit 1 on critical warning messages."""
        log_file = tmp_path / "critical.log"
        log_file.write_text("# Vivado v2025.2\nCRITICAL WARNING: [Test 1-1] important\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_check_fail_on_warning_by_default(self, tmp_path):
        """Check mode should fail on warnings by default (level >= 1)."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        # Default is level >= 1 (warning+), so warnings cause failure
        assert result.exit_code == 1

    def test_check_pass_on_warning_with_fail_on_error(self, tmp_path):
        """Check mode with --fail-on error should pass on warnings."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'error', '--plugin', 'vivado', str(log_file)])

        # With --fail-on error, only errors cause failure
        assert result.exit_code == 0


class TestCheckModeFailOn:
    """Tests for check mode with --fail-on option."""

    def test_check_fail_on_warning(self, tmp_path):
        """Check mode with --fail-on warning should exit 1 on warnings."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'warning', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_check_fail_on_error_still_fails_on_error(self, tmp_path):
        """Check mode with --fail-on error should still fail on errors."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'error', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_check_fail_on_critical_warning(self, tmp_path):
        """Check mode with --fail-on critical_warning should fail on critical warnings."""
        log_file = tmp_path / "critical.log"
        log_file.write_text("# Vivado v2025.2\nCRITICAL WARNING: [Test 1-1] important\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'critical_warning', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_check_fail_on_critical_warning_passes_on_warning(self, tmp_path):
        """Check mode with --fail-on critical_warning should pass on regular warnings."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'critical_warning', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0

    def test_check_pass_on_clean_log(self, tmp_path):
        """Check mode with --fail-on warning should pass on a clean log."""
        log_file = tmp_path / "clean.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'warning', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0


class TestCheckModeWithFilters:
    """Tests for check mode combined with filters."""

    def test_check_with_severity_filter_error_passes_on_warning(self, tmp_path):
        """Check mode with --severity=error should pass when only warnings exist."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--severity', 'error', '--plugin', 'vivado', str(log_file)
        ])

        # Severity filter removes warnings, so no failures
        assert result.exit_code == 0

    def test_check_with_severity_filter_still_sees_errors(self, tmp_path):
        """Check mode with --severity=error should still fail on errors."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Test 1-1] minor issue\n"
            "ERROR: [Test 1-2] something failed\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--severity', 'error', '--plugin', 'vivado', str(log_file)
        ])

        assert result.exit_code == 1

    def test_check_with_suppress_pattern(self, tmp_path):
        """Check mode with --suppress should exclude matched errors from failure check."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--suppress', 'known issue', '--plugin', 'vivado', str(log_file)
        ])

        # Error is suppressed, so should pass
        assert result.exit_code == 0

    def test_check_with_suppress_id(self, tmp_path):
        """Check mode with --suppress-id should exclude specific message IDs."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--suppress-id', 'Test 1-1', '--plugin', 'vivado', str(log_file)
        ])

        # Error is suppressed by ID, so should pass
        assert result.exit_code == 0

    def test_check_with_category_filter(self, tmp_path):
        """Check mode with category filter affects what is counted."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Synth 8-1] synth warning\n"
            "WARNING: [Timing 38-1] timing warning\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--category', 'Synth', '--plugin', 'vivado', str(log_file)
        ])

        # Only Synth messages considered, still has a warning
        assert result.exit_code == 1


class TestCheckModeAutoDetect:
    """Tests for check mode with auto-detection."""

    def test_check_with_auto_detect(self, tmp_path):
        """Check mode should work with plugin auto-detection."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', str(log_file)])

        assert result.exit_code == 0

    def test_check_auto_detect_fails_on_error(self, tmp_path):
        """Check mode with auto-detection should fail on errors."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', str(log_file)])

        assert result.exit_code == 1


class TestCheckModeMixedSeverities:
    """Tests for check mode with mixed severity messages."""

    def test_check_mixed_info_warning_fails_by_default(self, tmp_path):
        """Check mode should fail with warnings by default (level >= 1)."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] good stuff\n"
            "WARNING: [Synth 8-1] minor warning\n"
            "INFO: [Info 1-2] more good stuff\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        # Default is level >= 1, so warning causes failure
        assert result.exit_code == 1

    def test_check_mixed_pass_with_fail_on_error(self, tmp_path):
        """Check mode with --fail-on error should pass with only warnings."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] good stuff\n"
            "WARNING: [Synth 8-1] minor warning\n"
            "INFO: [Info 1-2] more good stuff\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'error', '--plugin', 'vivado', str(log_file)])

        # With --fail-on error, warnings don't cause failure
        assert result.exit_code == 0

    def test_check_mixed_fail_with_one_error(self, tmp_path):
        """Check mode should fail if any error exists."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] good stuff\n"
            "WARNING: [Synth 8-1] minor warning\n"
            "ERROR: [Test 1-1] one error\n"
            "INFO: [Info 1-2] more good stuff\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_check_multiple_errors_still_exit_1(self, tmp_path):
        """Check mode should exit 1 regardless of error count."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] first error\n"
            "ERROR: [Test 1-2] second error\n"
            "ERROR: [Test 1-3] third error\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1


class TestCheckModeEmptyLogs:
    """Tests for check mode with empty or minimal logs."""

    def test_check_empty_log_passes(self, tmp_path):
        """Check mode should pass on an empty log (detected as Vivado by header)."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("# Vivado v2025.2\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0

    def test_check_with_fail_on_empty_log_passes(self, tmp_path):
        """Check mode with --fail-on should pass on an empty log."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("# Vivado v2025.2\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--fail-on', 'warning', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0


class TestCheckModeOutput:
    """Tests for check mode output behavior."""

    def test_check_mode_still_outputs_messages(self, tmp_path):
        """Check mode should still output messages to stdout."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--check', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1
        assert "ERROR:" in result.output or "something failed" in result.output

    def test_check_mode_with_json_format(self, tmp_path):
        """Check mode should work with --format json."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--format', 'json', '--plugin', 'vivado', str(log_file)
        ])

        assert result.exit_code == 1
        # Should still output JSON
        assert '"severity": "error"' in result.output

    def test_check_mode_with_count_format(self, tmp_path):
        """Check mode should work with --format count."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--format', 'count', '--plugin', 'vivado', str(log_file)
        ])

        assert result.exit_code == 1
        assert "error=1" in result.output


class TestFailOnWithoutCheck:
    """Tests for --fail-on flag behavior without --check."""

    def test_fail_on_without_check_has_no_effect(self, tmp_path):
        """--fail-on without --check should not affect exit code."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--fail-on', 'warning', '--plugin', 'vivado', str(log_file)])

        # Without --check, exit code should be 0 (normal operation)
        assert result.exit_code == 0


class TestCheckModeEdgeCases:
    """Edge case tests for check mode."""

    def test_check_with_id_filter_reduces_failures(self, tmp_path):
        """Check mode with --id filter should only count filtered messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] error one\n"
            "ERROR: [Other 2-1] error two\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--id', 'Other *', '--plugin', 'vivado', str(log_file)
        ])

        # Only "Other 2-1" matches, which is an error
        assert result.exit_code == 1

    def test_check_with_id_filter_removes_all_failures(self, tmp_path):
        """Check mode with --id filter can result in no failures if filter matches non-errors."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] just info\n"
            "ERROR: [Test 1-1] error one\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--id', 'Info *', '--plugin', 'vivado', str(log_file)
        ])

        # Only "Info 1-1" matches, which is just info
        assert result.exit_code == 0
