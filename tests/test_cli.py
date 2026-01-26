"""Tests for the sawmill CLI log processing functionality.

These tests verify that the CLI correctly:
- Processes log files with auto-detected plugins
- Filters by severity level
- Applies regex filters
- Applies suppression patterns
- Suppresses messages by ID
"""

import pytest
from click.testing import CliRunner

from sawmill.cli import cli


class TestBasicCLI:
    """Tests for basic CLI log processing."""

    def test_cli_basic_output(self, tmp_path):
        """With Vivado plugin, basic output should work."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\nINFO: [Test 1-1] message\nERROR: [Test 2-1] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file)])

        assert result.exit_code == 0

    def test_cli_errors_without_plugin(self, tmp_path):
        """Without matching plugin, should error."""
        log_file = tmp_path / "unknown.log"
        log_file.write_text("some random content that no plugin recognizes\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file)])

        assert result.exit_code != 0
        assert "plugin" in result.output.lower()

    def test_cli_displays_messages(self, tmp_path):
        """CLI should display parsed messages."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] synthesis started\n"
            "WARNING: [Timing 38-2] timing constraint\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file)])

        assert result.exit_code == 0
        assert "synthesis" in result.output or "Synth" in result.output


class TestSeverityFilter:
    """Tests for severity filtering."""

    def test_cli_with_plugin_and_severity(self, tmp_path):
        """With Vivado plugin, severity filter should work."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] info message\n"
            "ERROR: [DRC 1-1] error message\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--plugin", "vivado", "--severity", "error"]
        )

        assert result.exit_code == 0
        assert "ERROR" in result.output
        # INFO should be filtered out
        assert "INFO" not in result.output or "info message" not in result.output

    def test_cli_severity_warning(self, tmp_path):
        """Severity warning should include warnings and above."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] info\n"
            "WARNING: [Timing 38-1] warning\n"
            "ERROR: [DRC 1-1] error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--severity", "warning"]
        )

        assert result.exit_code == 0
        assert "WARNING" in result.output or "warning" in result.output
        assert "ERROR" in result.output or "error" in result.output


class TestRegexFilter:
    """Tests for regex pattern filtering."""

    def test_cli_regex_filter(self, tmp_path):
        """--filter should include only matching messages."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: timing slack -0.5\n"
            "INFO: DRC violation\n"
            "INFO: timing slack -0.2\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--filter", "timing"])

        assert result.exit_code == 0
        assert "timing" in result.output
        assert "DRC" not in result.output

    def test_cli_filter_case_sensitive(self, tmp_path):
        """Regex filter should be case-sensitive by default."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] TIMING issue\n"
            "INFO: [Route 35-1] timing issue\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--filter", "timing"])

        assert result.exit_code == 0
        # Only lowercase 'timing' should match
        assert "timing issue" in result.output


class TestSuppressionPatterns:
    """Tests for suppression pattern filtering."""

    def test_cli_suppress_pattern(self, tmp_path):
        """--suppress should hide matching messages."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] starting\n"
            "INFO: [Synth 8-2] noisy message\n"
            "ERROR: [DRC 1-1] real error\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--suppress", "noisy"])

        assert result.exit_code == 0
        assert "noisy" not in result.output
        assert "real error" in result.output

    def test_cli_multiple_suppress(self, tmp_path):
        """Multiple --suppress options should accumulate."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [A 1-1] noise1\n"
            "INFO: [B 2-1] noise2\n"
            "ERROR: [C 3-1] important\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--suppress", "noise1", "--suppress", "noise2"]
        )

        assert result.exit_code == 0
        assert "noise1" not in result.output
        assert "noise2" not in result.output
        assert "important" in result.output

    def test_cli_suppress_regex(self, tmp_path):
        """--suppress should support regex patterns."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] noise123\n"
            "INFO: [Synth 8-2] noise456\n"
            "ERROR: [DRC 1-1] important\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--suppress", r"noise\d+"])

        assert result.exit_code == 0
        assert "noise123" not in result.output
        assert "noise456" not in result.output
        assert "important" in result.output


class TestSuppressById:
    """Tests for message ID suppression."""

    def test_cli_suppress_id(self, tmp_path):
        """--suppress-id should hide messages by ID."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Common 17-55] suppress this\n"
            "ERROR: [DRC 1-1] keep this\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--suppress-id", "Common 17-55"])

        assert result.exit_code == 0
        assert "Common 17-55" not in result.output
        assert "DRC 1-1" in result.output

    def test_cli_multiple_suppress_id(self, tmp_path):
        """Multiple --suppress-id options should accumulate."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Common 17-55] suppress1\n"
            "WARNING: [Vivado 12-3523] suppress2\n"
            "ERROR: [DRC 1-1] keep this\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                str(log_file),
                "--suppress-id", "Common 17-55",
                "--suppress-id", "Vivado 12-3523",
            ],
        )

        assert result.exit_code == 0
        assert "Common 17-55" not in result.output
        assert "Vivado 12-3523" not in result.output
        assert "DRC 1-1" in result.output


class TestPluginSelection:
    """Tests for plugin selection."""

    def test_cli_explicit_plugin(self, tmp_path):
        """--plugin should force a specific plugin."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Test 1-1] message\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "vivado"])

        assert result.exit_code == 0

    def test_cli_unknown_plugin(self, tmp_path):
        """Unknown --plugin should error."""
        log_file = tmp_path / "test.log"
        log_file.write_text("test content\n")

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file), "--plugin", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_cli_auto_detect_vivado(self, tmp_path):
        """Auto-detect should work for Vivado logs."""
        log_file = tmp_path / "build.log"
        log_file.write_text(
            "# Vivado v2025.2 (64-bit)\n"
            "INFO: [Synth 8-6157] synthesizing module\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(log_file)])

        assert result.exit_code == 0


class TestCombinedFilters:
    """Tests for combining multiple filter options."""

    def test_cli_severity_and_filter(self, tmp_path):
        """Combining --severity and --filter should work."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] timing info\n"
            "ERROR: [DRC 1-1] timing error\n"
            "ERROR: [Route 35-1] routing error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--severity", "error", "--filter", "timing"]
        )

        assert result.exit_code == 0
        assert "timing error" in result.output
        assert "timing info" not in result.output
        assert "routing error" not in result.output

    def test_cli_filter_and_suppress(self, tmp_path):
        """Combining --filter and --suppress should work."""
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Vivado v2025.2\n"
            "INFO: [Synth 8-1] DRC check passed\n"
            "WARNING: [DRC 23-20] DRC noisy warning\n"
            "ERROR: [DRC 1-1] DRC real error\n"
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, [str(log_file), "--filter", "DRC", "--suppress", "noisy"]
        )

        assert result.exit_code == 0
        assert "DRC check passed" in result.output
        assert "DRC real error" in result.output
        assert "noisy" not in result.output


class TestPluginEntryPointDiscovery:
    """Tests for plugin discovery via entry points."""

    def test_plugin_manager_discovers_vivado(self):
        """PluginManager.discover() should find vivado via entry point."""
        from sawmill.core.plugin import PluginManager

        manager = PluginManager()
        discovered = manager.discover()
        assert "vivado" in discovered

    def test_get_plugin_manager_has_vivado(self):
        """_get_plugin_manager() should have vivado registered."""
        from sawmill.__main__ import _get_plugin_manager

        manager = _get_plugin_manager()
        assert "vivado" in manager.list_plugins()

    def test_no_direct_vivado_import(self):
        """__main__.py should not directly import VivadoPlugin."""
        import inspect
        import sawmill.__main__ as main_module

        source = inspect.getsource(main_module)
        assert "from sawmill.plugins.vivado import" not in source


class TestGetFailOnLevel:
    """Tests for _get_fail_on_level() with various severity schemes."""

    def test_default_returns_second_lowest(self):
        """Default should return second-lowest severity level."""
        from sawmill.__main__ import _get_fail_on_level
        from sawmill.plugins.vivado import VivadoPlugin

        plugin = VivadoPlugin()
        level = _get_fail_on_level(None, plugin)
        # Vivado: info=0, warning=1, critical_warning=2, error=3
        # Second-lowest is warning (level 1)
        assert level == 1

    def test_default_with_custom_scheme(self):
        """Default should work with non-Vivado severity schemes."""
        from sawmill.__main__ import _get_fail_on_level

        class FakePlugin:
            def get_severity_levels(self):
                return [
                    {"id": "fatal", "name": "Fatal", "level": 2, "style": "red"},
                    {"id": "major", "name": "Major", "level": 1, "style": "yellow"},
                    {"id": "note", "name": "Note", "level": 0, "style": "dim"},
                ]

        plugin = FakePlugin()
        level = _get_fail_on_level(None, plugin)
        # Sorted: note=0, major=1, fatal=2
        # Second-lowest is major (level 1)
        assert level == 1

    def test_default_with_single_level(self):
        """Default with single severity should return that level."""
        from sawmill.__main__ import _get_fail_on_level

        class FakePlugin:
            def get_severity_levels(self):
                return [
                    {"id": "only", "name": "Only", "level": 1, "style": ""},
                ]

        plugin = FakePlugin()
        level = _get_fail_on_level(None, plugin)
        assert level == 1

    def test_explicit_fail_on(self):
        """Explicit --fail-on should return that severity's level."""
        from sawmill.__main__ import _get_fail_on_level
        from sawmill.plugins.vivado import VivadoPlugin

        plugin = VivadoPlugin()
        level = _get_fail_on_level("error", plugin)
        assert level == 3

    def test_invalid_fail_on_raises(self):
        """Invalid --fail-on should raise click.BadParameter."""
        import click
        from sawmill.__main__ import _get_fail_on_level
        from sawmill.plugins.vivado import VivadoPlugin

        plugin = VivadoPlugin()
        with pytest.raises(click.BadParameter, match="Unknown severity"):
            _get_fail_on_level("nonexistent", plugin)
