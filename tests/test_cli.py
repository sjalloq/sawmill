"""Tests for the sawmill CLI group skeleton and LOGFILE alias."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sawmill.cli import cli

FIXTURES = Path(__file__).parent / "fixtures"
VIVADO_LOG = FIXTURES / "vivado.log"


class TestPluginEntryPointDiscovery:
    """Tests for plugin discovery via entry points."""

    def test_plugin_manager_discovers_vivado(self):
        """PluginManager.discover() should find vivado via entry point."""
        from sawmill.core.plugin import PluginManager

        manager = PluginManager()
        discovered = manager.discover()
        assert "vivado" in discovered

    def test_get_plugin_manager_has_vivado(self):
        """get_plugin_manager() should have vivado registered."""
        from sawmill.core.plugin import get_plugin_manager

        manager = get_plugin_manager()
        assert "vivado" in manager.list_plugins()

    def test_no_direct_vivado_import(self):
        """__main__.py should not directly import VivadoPlugin."""
        import inspect

        import sawmill.__main__ as main_module

        source = inspect.getsource(main_module)
        assert "from sawmill.plugins.vivado import" not in source


class TestGroupSkeleton:
    """Tests for the top-level command group."""

    def test_version_flag(self) -> None:
        result = CliRunner().invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("sawmill ")

    def test_help_lists_subcommands(self) -> None:
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "view" in result.output
        assert "plugins" in result.output

    def test_no_args_prints_help_exit_zero(self) -> None:
        result = CliRunner().invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage" in result.output

    @pytest.mark.parametrize("flag", ["--check", "--list-plugins", "--severity", "--format"])
    def test_removed_flat_flags_are_errors(self, flag: str) -> None:
        result = CliRunner().invoke(cli, [flag, str(VIVADO_LOG)])
        assert result.exit_code == 2
        assert "No such option" in result.output

    def test_logfile_alias_invokes_view(self) -> None:
        with patch("sawmill.tui.run_tui") as run_tui:
            result = CliRunner().invoke(cli, [str(VIVADO_LOG)])
        assert result.exit_code == 0, result.output
        run_tui.assert_called_once()
        (targets,) = run_tui.call_args.args
        assert targets[0].plugin_name == "vivado"
        assert run_tui.call_args.kwargs == {"single_log": True}

    def test_alias_passes_plugin_option(self) -> None:
        with patch("sawmill.tui.run_tui") as run_tui:
            result = CliRunner().invoke(cli, [str(VIVADO_LOG), "--plugin", "vivado"])
        assert result.exit_code == 0, result.output
        run_tui.assert_called_once()
        assert run_tui.call_args.args[0][0].plugin_name == "vivado"
        assert run_tui.call_args.kwargs == {"single_log": True}

    def test_unknown_command_is_error(self) -> None:
        result = CliRunner().invoke(cli, ["frobnicate"])
        assert result.exit_code == 2
