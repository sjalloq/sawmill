"""Tests for the ``sawmill view`` command."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner, Result

from sawmill.cli import cli
from sawmill.core.plugin import PluginManager, get_plugin_manager
from sawmill.models.message import Message
from sawmill.plugin import SawmillPlugin, hookimpl

VIVADO_LOG = Path(__file__).parent / "fixtures" / "vivado.log"

_LINE_RE = re.compile(r"^(ERROR|WARNING|INFO)(?: \[([^\]]+)\])? (.*)$")


class FakePlugin(SawmillPlugin):
    """Minimal line-per-message plugin."""

    name = "fake"
    version = "1.0.0"

    @hookimpl
    def can_handle(self, path: Path) -> float:
        return 0.0

    @hookimpl
    def get_severity_levels(self) -> list[dict]:
        return [
            {"id": "error", "name": "Error", "level": 2},
            {"id": "warning", "name": "Warning", "level": 1},
            {"id": "info", "name": "Info", "level": 0},
        ]

    @hookimpl
    def load_and_parse(self, path: Path) -> Iterator[Message]:
        for n, line in enumerate(Path(path).read_text().splitlines(), start=1):
            m = _LINE_RE.match(line)
            if m is None:
                continue
            yield Message(n, n, line, m.group(3), m.group(1).lower(), m.group(2), None, None)


@pytest.fixture(autouse=True)
def _no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLoader:
        def load_resolved(self) -> SimpleNamespace:
            return SimpleNamespace(general=SimpleNamespace(roots=[]))

    monkeypatch.setattr("sawmill.cli.common.ConfigLoader", FakeLoader)


@pytest.fixture
def fake_manager(monkeypatch: pytest.MonkeyPatch) -> PluginManager:
    manager = PluginManager()
    manager.register(FakePlugin())
    monkeypatch.setattr("sawmill.cli.view.get_plugin_manager", lambda: manager)
    return manager


def _project(tmp_path: Path, targets: str, logs: dict[str, str]) -> None:
    sawmill_dir = tmp_path / ".sawmill"
    (sawmill_dir / "rules").mkdir(parents=True)
    (sawmill_dir / "manifest.toml").write_text(f'[manifest]\nname = "proj"\n\n{targets}')
    for name, content in logs.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


_TWO_TARGETS = (
    '[[target]]\nname = "a"\nplugin = "fake"\nlogs = ["a/*.log"]\n\n'
    '[[target]]\nname = "b"\nplugin = "fake"\nlogs = ["b/*.log"]\n'
)
_LOGS = {"a/x.log": "ERROR [E-1] bad\n", "b/y.log": "WARNING [W-1] meh\n"}


def _view(*args: str) -> tuple[Result, MagicMock]:
    with patch("sawmill.tui.run_tui") as run_tui:
        result = CliRunner().invoke(cli, ["view", *args])
    return result, run_tui


def test_view_logfile_runs_single_log() -> None:
    result, run_tui = _view(str(VIVADO_LOG))
    assert result.exit_code == 0, result.output
    run_tui.assert_called_once()
    (targets,) = run_tui.call_args.args
    assert len(targets) == 1
    assert targets[0].plugin_name == "vivado"
    assert targets[0].all_messages
    assert run_tui.call_args.kwargs == {"single_log": True}


def test_view_explicit_plugin() -> None:
    manager = get_plugin_manager()
    with (
        patch.object(manager, "auto_detect") as auto_detect,
        patch("sawmill.cli.view.get_plugin_manager", return_value=manager),
    ):
        result, run_tui = _view(str(VIVADO_LOG), "--plugin", "vivado")
    assert result.exit_code == 0, result.output
    auto_detect.assert_not_called()
    assert run_tui.call_args.args[0][0].plugin_name == "vivado"


def test_view_unknown_plugin_exit_2_lists_plugins() -> None:
    result, run_tui = _view(str(VIVADO_LOG), "--plugin", "nope")
    assert result.exit_code == 2
    assert "vivado" in result.output
    run_tui.assert_not_called()


def test_view_no_plugin_can_handle_exit_2(tmp_path: Path) -> None:
    log = tmp_path / "plain.txt"
    log.write_text("nothing here\n")
    result, run_tui = _view(str(log))
    assert result.exit_code == 2
    run_tui.assert_not_called()


def test_view_target(tmp_path: Path, fake_manager: PluginManager) -> None:
    _project(tmp_path, _TWO_TARGETS, _LOGS)
    result, run_tui = _view("b", "--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    (targets,) = run_tui.call_args.args
    assert [t.qualified_name for t in targets] == ["proj:b"]
    assert run_tui.call_args.kwargs.get("single_log", False) is False


def test_view_no_args_runs_all_targets(tmp_path: Path, fake_manager: PluginManager) -> None:
    _project(tmp_path, _TWO_TARGETS, _LOGS)
    result, run_tui = _view("--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    (targets,) = run_tui.call_args.args
    assert [t.qualified_name for t in targets] == ["proj:a", "proj:b"]


def test_view_unknown_target_exit_2(tmp_path: Path, fake_manager: PluginManager) -> None:
    _project(tmp_path, _TWO_TARGETS, _LOGS)
    result, run_tui = _view("nope", "--root", str(tmp_path))
    assert result.exit_code == 2
    run_tui.assert_not_called()


def test_view_no_manifest_no_file_exit_2(tmp_path: Path) -> None:
    result, run_tui = _view("--root", str(tmp_path))
    assert result.exit_code == 2
    run_tui.assert_not_called()
    result, run_tui = _view("does_not_exist.log", "--root", str(tmp_path))
    assert result.exit_code == 2
    run_tui.assert_not_called()


def test_view_fail_on_propagated(tmp_path: Path, fake_manager: PluginManager) -> None:
    _project(tmp_path, _TWO_TARGETS, _LOGS)
    result, run_tui = _view("a", "--root", str(tmp_path), "--fail-on", "warning")
    assert result.exit_code == 0, result.output
    assert run_tui.call_args.args[0][0].fail_on == "warning"


def test_view_target_with_no_logs_opens(tmp_path: Path, fake_manager: PluginManager) -> None:
    _project(tmp_path, _TWO_TARGETS, {})
    result, run_tui = _view("a", "--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert run_tui.call_args.args[0][0].no_logs is True


def test_view_rejects_old_options() -> None:
    result, run_tui = _view(str(VIVADO_LOG), "--severity", "error")
    assert result.exit_code == 2
    run_tui.assert_not_called()


def test_view_var_passed_to_run_selected(tmp_path: Path, fake_manager: PluginManager) -> None:
    _project(tmp_path, _TWO_TARGETS, _LOGS)
    with patch("sawmill.cli.view.run_selected", return_value=[MagicMock()]) as rs:
        result, _ = _view("a", "--root", str(tmp_path), "--var", "build=sub")
    assert result.exit_code == 0, result.output
    assert rs.call_args.kwargs["overrides"] == {"build": "sub"}
