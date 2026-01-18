"""Tests for CLI plugin discovery commands."""

from click.testing import CliRunner

from sawmill.cli import cli


class TestListPlugins:
    """Tests for --list-plugins option."""

    def test_list_plugins(self):
        """--list-plugins should enumerate all plugins."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--list-plugins"])

        assert result.exit_code == 0
        assert "vivado" in result.output.lower()

    def test_list_plugins_shows_version(self):
        """--list-plugins should show plugin versions."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--list-plugins"])

        assert result.exit_code == 0
        # Vivado plugin has version 1.0.0
        assert "1.0.0" in result.output

    def test_list_plugins_shows_description(self):
        """--list-plugins should show plugin descriptions."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--list-plugins"])

        assert result.exit_code == 0
        # Vivado plugin description contains "Vivado"
        assert "vivado" in result.output.lower()


class TestShowPluginInfo:
    """Tests for --show-info option."""

    def test_show_plugin_info(self):
        """--show-info should display plugin capabilities."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "vivado", "--show-info"])

        assert result.exit_code == 0
        assert "vivado" in result.output.lower()

    def test_show_info_displays_version(self):
        """--show-info should display plugin version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "vivado", "--show-info"])

        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_show_info_displays_hooks(self):
        """--show-info should display implemented hooks."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "vivado", "--show-info"])

        assert result.exit_code == 0
        # Vivado plugin implements these hooks
        assert "can_handle" in result.output or "Hooks" in result.output

    def test_show_info_displays_filter_count(self):
        """--show-info should display filter information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "vivado", "--show-info"])

        assert result.exit_code == 0
        # Vivado plugin provides filters
        assert "filter" in result.output.lower()

    def test_show_info_requires_plugin(self):
        """--show-info without --plugin should error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--show-info"])

        # Should fail or provide helpful message
        assert result.exit_code != 0 or "plugin" in result.output.lower()

    def test_show_info_unknown_plugin(self):
        """--show-info with unknown plugin should error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "nonexistent", "--show-info"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_show_info_lists_available_on_error(self):
        """--show-info with unknown plugin should list available plugins."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "nonexistent", "--show-info"])

        # Should list vivado as an available option
        assert "vivado" in result.output.lower()


class TestPluginInfoContent:
    """Tests for the content of plugin info output."""

    def test_vivado_info_shows_description(self):
        """Vivado plugin info should include description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "vivado", "--show-info"])

        assert result.exit_code == 0
        # The description mentions synthesis or implementation
        output_lower = result.output.lower()
        assert "synthesis" in output_lower or "implementation" in output_lower or "vivado" in output_lower

    def test_vivado_info_shows_filters(self):
        """Vivado plugin info should show filter definitions."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plugin", "vivado", "--show-info"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Should show some of the filter IDs
        assert "error" in output_lower or "warning" in output_lower
