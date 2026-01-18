"""Tests for CI mode exit code logic."""

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli


class TestCIModeBasic:
    """Basic tests for CI mode pass/fail behavior."""

    def test_ci_pass_on_clean_log(self, tmp_path):
        """CI mode should exit 0 on a clean log (info only)."""
        log_file = tmp_path / "clean.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0

    def test_ci_fail_on_error(self, tmp_path):
        """CI mode should exit 1 on error messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_fail_on_critical_warning(self, tmp_path):
        """CI mode should exit 1 on critical warning messages."""
        log_file = tmp_path / "critical.log"
        log_file.write_text("# Vivado v2025.2\nCRITICAL WARNING: [Test 1-1] important\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_pass_on_warning_without_strict(self, tmp_path):
        """CI mode should pass on warnings when --strict is not used."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0


class TestCIModeStrict:
    """Tests for CI mode with --strict flag."""

    def test_ci_strict_fails_on_warning(self, tmp_path):
        """CI mode with --strict should exit 1 on warnings."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_strict_fails_on_error(self, tmp_path):
        """CI mode with --strict should still fail on errors."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_strict_fails_on_critical_warning(self, tmp_path):
        """CI mode with --strict should still fail on critical warnings."""
        log_file = tmp_path / "critical.log"
        log_file.write_text("# Vivado v2025.2\nCRITICAL WARNING: [Test 1-1] important\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_strict_pass_on_clean_log(self, tmp_path):
        """CI mode with --strict should pass on a clean log."""
        log_file = tmp_path / "clean.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0


class TestCIModeWithFilters:
    """Tests for CI mode combined with filters."""

    def test_ci_with_severity_filter_error_passes_on_warning(self, tmp_path):
        """CI mode with --severity=error should pass when only warnings exist."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--severity', 'error', '--plugin', 'vivado', str(log_file)
        ])

        # Severity filter removes warnings, so no failures
        assert result.exit_code == 0

    def test_ci_with_severity_filter_still_sees_errors(self, tmp_path):
        """CI mode with --severity=error should still fail on errors."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Test 1-1] minor issue\n"
            "ERROR: [Test 1-2] something failed\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--severity', 'error', '--plugin', 'vivado', str(log_file)
        ])

        assert result.exit_code == 1

    def test_ci_with_suppress_pattern(self, tmp_path):
        """CI mode with --suppress should exclude matched errors from failure check."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--suppress', 'known issue', '--plugin', 'vivado', str(log_file)
        ])

        # Error is suppressed, so should pass
        assert result.exit_code == 0

    def test_ci_with_suppress_id(self, tmp_path):
        """CI mode with --suppress-id should exclude specific message IDs."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--suppress-id', 'Test 1-1', '--plugin', 'vivado', str(log_file)
        ])

        # Error is suppressed by ID, so should pass
        assert result.exit_code == 0

    def test_ci_strict_with_category_filter(self, tmp_path):
        """CI mode with category filter affects what is counted."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "WARNING: [Synth 8-1] synth warning\n"
            "WARNING: [Timing 38-1] timing warning\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--strict', '--category', 'Synth', '--plugin', 'vivado', str(log_file)
        ])

        # Only Synth messages considered, still has a warning
        assert result.exit_code == 1


class TestCIModeAutoDetect:
    """Tests for CI mode with auto-detection."""

    def test_ci_with_auto_detect(self, tmp_path):
        """CI mode should work with plugin auto-detection."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', str(log_file)])

        assert result.exit_code == 0

    def test_ci_auto_detect_fails_on_error(self, tmp_path):
        """CI mode with auto-detection should fail on errors."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', str(log_file)])

        assert result.exit_code == 1


class TestCIModeMixedSeverities:
    """Tests for CI mode with mixed severity messages."""

    def test_ci_mixed_pass_info_warning_no_strict(self, tmp_path):
        """CI mode should pass with info and warnings (no --strict)."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] good stuff\n"
            "WARNING: [Synth 8-1] minor warning\n"
            "INFO: [Info 1-2] more good stuff\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0

    def test_ci_mixed_fail_with_one_error(self, tmp_path):
        """CI mode should fail if any error exists."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] good stuff\n"
            "WARNING: [Synth 8-1] minor warning\n"
            "ERROR: [Test 1-1] one error\n"
            "INFO: [Info 1-2] more good stuff\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_multiple_errors_still_exit_1(self, tmp_path):
        """CI mode should exit 1 regardless of error count."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] first error\n"
            "ERROR: [Test 1-2] second error\n"
            "ERROR: [Test 1-3] third error\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1

    def test_ci_strict_mixed_fail_with_warning(self, tmp_path):
        """CI strict mode should fail with mixed info and warnings."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] good stuff\n"
            "WARNING: [Synth 8-1] minor warning\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1


class TestCIModeEmptyLogs:
    """Tests for CI mode with empty or minimal logs."""

    def test_ci_empty_log_passes(self, tmp_path):
        """CI mode should pass on an empty log (detected as Vivado by header)."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("# Vivado v2025.2\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0

    def test_ci_strict_empty_log_passes(self, tmp_path):
        """CI strict mode should pass on an empty log."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("# Vivado v2025.2\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 0


class TestCIModeOutput:
    """Tests for CI mode output behavior."""

    def test_ci_mode_still_outputs_messages(self, tmp_path):
        """CI mode should still output messages to stdout."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

        assert result.exit_code == 1
        assert "ERROR:" in result.output or "something failed" in result.output

    def test_ci_mode_with_json_format(self, tmp_path):
        """CI mode should work with --format json."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--format', 'json', '--plugin', 'vivado', str(log_file)
        ])

        assert result.exit_code == 1
        # Should still output JSON
        assert '"severity": "error"' in result.output

    def test_ci_mode_with_count_format(self, tmp_path):
        """CI mode should work with --format count."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--format', 'count', '--plugin', 'vivado', str(log_file)
        ])

        assert result.exit_code == 1
        assert "errors=1" in result.output


class TestStrictWithoutCI:
    """Tests for --strict flag behavior without --ci."""

    def test_strict_without_ci_has_no_effect(self, tmp_path):
        """--strict without --ci should not affect exit code."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

        runner = CliRunner()
        result = runner.invoke(cli, ['--strict', '--plugin', 'vivado', str(log_file)])

        # Without --ci, exit code should be 0 (normal operation)
        assert result.exit_code == 0


class TestCIModeEdgeCases:
    """Edge case tests for CI mode."""

    def test_ci_with_id_filter_reduces_failures(self, tmp_path):
        """CI mode with --id filter should only count filtered messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] error one\n"
            "ERROR: [Other 2-1] error two\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--id', 'Other *', '--plugin', 'vivado', str(log_file)
        ])

        # Only "Other 2-1" matches, which is an error
        assert result.exit_code == 1

    def test_ci_with_id_filter_removes_all_failures(self, tmp_path):
        """CI mode with --id filter can result in no failures if filter matches non-errors."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] just info\n"
            "ERROR: [Test 1-1] error one\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--ci', '--id', 'Info *', '--plugin', 'vivado', str(log_file)
        ])

        # Only "Info 1-1" matches, which is just info
        assert result.exit_code == 0
