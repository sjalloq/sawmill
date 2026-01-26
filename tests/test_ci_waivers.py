"""Tests for CI mode waiver integration."""

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli


class TestCIModeWithWaivers:
    """Tests for CI mode with --waivers option."""

    def test_ci_pass_with_waiver(self, tmp_path):
        """CI mode should pass when error is waived."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_ci_fail_when_waiver_does_not_match(self, tmp_path):
        """CI mode should fail when error is not waived."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] unknown issue\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 2-2"
reason = "Different issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 1

    def test_ci_pass_with_pattern_waiver(self, tmp_path):
        """CI mode should pass with pattern-based waiver."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] expected timing failure\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "pattern"
pattern = "expected.*failure"
reason = "Known timing issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_ci_with_multiple_waivers(self, tmp_path):
        """CI mode with multiple waivers should pass when all errors are waived."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] first error\n"
            "ERROR: [Test 2-2] second error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "First known issue"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "id"
pattern = "Test 2-2"
reason = "Second known issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_ci_fail_with_partial_waivers(self, tmp_path):
        """CI mode should fail if some errors are not waived."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] first error\n"
            "ERROR: [Test 2-2] second error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Only first is waived"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 1

    def test_ci_strict_with_waived_warning(self, tmp_path):
        """CI strict mode should pass when warning is waived."""
        log_file = tmp_path / "warnings.log"
        log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] known warning\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Acceptable warning"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--fail-on', 'warning', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_ci_waiver_with_critical_warning(self, tmp_path):
        """CI mode should pass when critical warning is waived."""
        log_file = tmp_path / "critical.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "CRITICAL WARNING: [Test 1-1] critical but acceptable\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Accepted critical warning"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_ci_waiver_with_missing_file(self, tmp_path):
        """CI mode should error if waiver file doesn't exist."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] test\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(tmp_path / "nonexistent.toml"),
            str(log_file)
        ])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_ci_waiver_with_invalid_toml(self, tmp_path):
        """CI mode should error if waiver file has invalid TOML."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] test\n")

        waiver_file = tmp_path / "invalid.toml"
        waiver_file.write_text("this is not valid toml [[[")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code != 0
        assert "error" in result.output.lower() or "invalid" in result.output.lower()


class TestShowWaived:
    """Tests for --show-waived option."""

    def test_show_waived_displays_waived_messages(self, tmp_path):
        """--show-waived should display waived messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            '--show-waived',
            str(log_file)
        ])

        # Output should contain the waived message or waiver indication
        assert "waived" in result.output.lower() or "Test 1-1" in result.output

    def test_show_waived_with_multiple_waivers(self, tmp_path):
        """--show-waived should display all waived messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] first error\n"
            "ERROR: [Test 2-2] second error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "First known issue"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "id"
pattern = "Test 2-2"
reason = "Second known issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            '--show-waived',
            str(log_file)
        ])

        # Should show both waived messages
        assert "Test 1-1" in result.output
        assert "Test 2-2" in result.output

    def test_show_waived_without_waivers_shows_nothing(self, tmp_path):
        """--show-waived without waivers should show no waived messages."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] error\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--show-waived',
            str(log_file)
        ])

        # Should indicate no waivers or no waived messages
        # The output still shows the error because it's not waived
        assert result.exit_code == 1

    def test_show_waived_includes_waiver_reason(self, tmp_path):
        """--show-waived should include the waiver reason."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Intentional for testing"
author = "engineer"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            '--show-waived',
            str(log_file)
        ])

        # Should include the reason
        assert "Intentional" in result.output or "reason" in result.output.lower()


class TestReportUnused:
    """Tests for --report-unused option."""

    def test_report_unused_shows_stale_waivers(self, tmp_path):
        """--report-unused should show waivers that didn't match anything."""
        log_file = tmp_path / "clean.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] info message\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "NonExistent 1-1"
reason = "This waiver is stale"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            '--report-unused',
            str(log_file)
        ])

        # Should report the unused waiver
        assert "NonExistent 1-1" in result.output or "unused" in result.output.lower()

    def test_report_unused_no_output_when_all_used(self, tmp_path):
        """--report-unused should not report waivers that matched."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            '--report-unused',
            str(log_file)
        ])

        # Should pass and not mention unused waivers
        assert result.exit_code == 0
        # If "unused" appears, it should say "no unused" or similar
        if "unused" in result.output.lower():
            # Check that there's no actual unused waiver listed
            assert "Test 1-1" not in result.output.split("unused")[0].lower() or "0" in result.output

    def test_report_unused_with_multiple_waivers(self, tmp_path):
        """--report-unused should identify which waivers are unused."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Used waiver"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "id"
pattern = "Stale 9-9"
reason = "Unused waiver"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            '--report-unused',
            str(log_file)
        ])

        # Should report only the unused waiver
        assert "Stale 9-9" in result.output

    def test_report_unused_empty_when_no_waivers(self, tmp_path):
        """--report-unused without waivers should not error."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] test\n")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--report-unused',
            str(log_file)
        ])

        assert result.exit_code == 0


class TestWaiverWithFilters:
    """Tests for waivers combined with other filters."""

    def test_waiver_with_severity_filter(self, tmp_path):
        """Waivers should work with severity filter."""
        log_file = tmp_path / "mixed.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Info 1-1] info message\n"
            "WARNING: [Warn 2-2] warning message\n"
            "ERROR: [Err 3-3] error message\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Err 3-3"
reason = "Known error"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--severity', 'error',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        # Error is waived, should pass
        assert result.exit_code == 0

    def test_waiver_with_suppression(self, tmp_path):
        """Waivers should work with suppression patterns."""
        log_file = tmp_path / "errors.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "ERROR: [Test 1-1] first error\n"
            "ERROR: [Test 2-2] second error\n"
        )

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "First is waived"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--suppress', 'second error',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        # Both errors handled: one waived, one suppressed
        assert result.exit_code == 0


class TestWaiverEdgeCases:
    """Edge cases for waiver integration."""

    def test_waiver_without_ci_mode(self, tmp_path):
        """--waivers should work without --check mode."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] error\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        # Should run without error (exit code 0 since not in CI mode)
        assert result.exit_code == 0

    def test_waiver_with_hash_type(self, tmp_path):
        """Waivers with hash type should work."""
        log_file = tmp_path / "errors.log"
        log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] specific error\n")

        # Calculate hash of the raw message
        import hashlib
        raw_text = "ERROR: [Test 1-1] specific error"
        msg_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text(f'''
[[waiver]]
type = "hash"
pattern = "{msg_hash}"
reason = "Known issue by hash"
author = "test"
date = "2026-01-18"
''')

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_empty_waiver_file(self, tmp_path):
        """Empty waiver file should not cause error."""
        log_file = tmp_path / "test.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] test\n")

        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("")

        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            '--waivers', str(waiver_file),
            str(log_file)
        ])

        assert result.exit_code == 0

    def test_waiver_info_messages_not_needed(self, tmp_path):
        """Info messages shouldn't need waivers to pass CI."""
        log_file = tmp_path / "info.log"
        log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] info only\n")

        # No waiver file provided
        runner = CliRunner()
        result = runner.invoke(cli, [
            '--check', '--plugin', 'vivado',
            str(log_file)
        ])

        assert result.exit_code == 0
