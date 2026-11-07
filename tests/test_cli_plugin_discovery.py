"""Tests for the ``sawmill plugins`` command group."""

from __future__ import annotations

import re
from unittest.mock import patch

from click.testing import CliRunner

from sawmill.cli import cli
from sawmill.core.plugin import PluginManager


class TestPluginsList:
    """Tests for ``plugins list``."""

    def test_list_plugins(self) -> None:
        result = CliRunner().invoke(cli, ["plugins", "list"], terminal_width=200)
        assert result.exit_code == 0, result.output
        assert "vivado" in result.output.lower()
        assert re.search(r"\d+\.\d+", result.output)
        assert "Vivado" in result.output

    def test_list_plugins_none_found(self) -> None:
        with patch("sawmill.cli.plugins.get_plugin_manager", return_value=PluginManager()):
            result = CliRunner().invoke(cli, ["plugins", "list"])
        assert result.exit_code == 0
        assert "No plugins found" in result.output


class TestPluginsInfo:
    """Tests for ``plugins info NAME``."""

    def test_info_vivado(self) -> None:
        result = CliRunner().invoke(cli, ["plugins", "info", "vivado"], terminal_width=200)
        assert result.exit_code == 0, result.output
        out = result.output
        assert re.search(r"Version: \S*\d", out)
        assert "Implemented Hooks" in out
        assert "load_and_parse" in out
        assert "Filters" in out
        assert "Severity Levels" in out
        assert "Grouping Fields" in out
        assert "critical_warning" in out

    def test_info_unknown_plugin(self) -> None:
        result = CliRunner().invoke(cli, ["plugins", "info", "nope"])
        assert result.exit_code == 2
        assert "vivado" in result.output

    def test_info_requires_name(self) -> None:
        result = CliRunner().invoke(cli, ["plugins", "info"])
        assert result.exit_code == 2


def test_plugins_info_lists_configure_only_when_overridden() -> None:
    from sawmill.plugin import SawmillPlugin, hookimpl

    class Plain(SawmillPlugin):
        name = "plain"
        version = "1.0"

        @hookimpl
        def get_severity_levels(self) -> list[dict]:
            return [{"id": "error", "name": "Error", "level": 1}]

    class Conf(Plain):
        name = "conf"

        @hookimpl
        def configure(self, options: dict) -> None:
            pass

    manager = PluginManager()
    manager.register(Plain())
    manager.register(Conf())
    with patch("sawmill.cli.plugins.get_plugin_manager", return_value=manager):
        plain = CliRunner().invoke(cli, ["plugins", "info", "plain"], terminal_width=200)
        conf = CliRunner().invoke(cli, ["plugins", "info", "conf"], terminal_width=200)
    assert plain.exit_code == 0, plain.output
    assert conf.exit_code == 0, conf.output
    assert "- configure" not in plain.output
    assert "- configure" in conf.output
