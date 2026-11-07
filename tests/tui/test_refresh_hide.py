"""Tests for the TUI ``h`` session hide and ``r``/``R`` refresh actions."""

from __future__ import annotations

from pathlib import Path

import pytest

from sawmill.core.discovery import TargetRef
from sawmill.core.manifest import ManifestLoader
from sawmill.core.plugin import PluginManager
from sawmill.core.runner import TargetResult, run_single_log, run_target
from sawmill.tui.app import SawmillApp
from sawmill.tui.widgets.help_modal import HELP_TEXT
from sawmill.tui.widgets.overview import OverviewTable
from tests.tui.conftest import LOG, FakePlugin, Recorder

MANIFEST = """\
[manifest]
name = "proj"

[[target]]
name = "t"
plugin = "test"
logs = ["a.log"]
rules = ["t.toml"]

[[target]]
name = "u"
plugin = "test"
logs = ["a.log"]
rules = ["u.toml"]
"""

EMPTY_RULES = '[rules]\nplugin = "test"\n'


def _waive(*ids: str) -> str:
    out = EMPTY_RULES
    for i in ids:
        out += f'\n[[rule]]\nid = "{i}"\ncomment = "c"\n'
    return out


def _project(tmp_path: Path) -> Path:
    rules = tmp_path / ".sawmill" / "rules"
    rules.mkdir(parents=True)
    (tmp_path / ".sawmill" / "manifest.toml").write_text(MANIFEST)
    (rules / "t.toml").write_text(EMPTY_RULES)
    (rules / "u.toml").write_text(EMPTY_RULES)
    (tmp_path / "a.log").write_text(LOG)
    return tmp_path


@pytest.fixture
def plugin(monkeypatch: pytest.MonkeyPatch) -> FakePlugin:
    """A fake plugin, also returned by the runner's default plugin manager."""
    p = FakePlugin("test")
    manager = PluginManager()
    manager.register(p)
    monkeypatch.setattr("sawmill.core.runner.get_plugin_manager", lambda: manager)
    return p


def _run(root: Path, names: list[str]) -> list[TargetResult]:
    manifest = ManifestLoader().load(root / ".sawmill" / "manifest.toml")
    results = []
    for name in names:
        target = manifest.get_target(name)
        assert target is not None
        results.append(run_target(TargetRef(manifest, target)))
    return results


def _ids(app: SawmillApp) -> list[str | None]:
    return [m.message_id for m in app.filtered_messages]


def _select_id(app: SawmillApp, message_id: str | None) -> None:
    idx = next(i for i, m in enumerate(app.filtered_messages) if m.message_id == message_id)
    app._navigate_to(idx)


def _cursor_valid(app: SawmillApp) -> bool:
    return 0 <= app._current_index() < max(1, len(app.filtered_messages))


async def _start(app: SawmillApp, pilot) -> Recorder:  # type: ignore[no-untyped-def]
    await pilot.pause()
    rec = Recorder()
    app.notify = rec  # type: ignore[method-assign]
    return rec


# --- h ---------------------------------------------------------------------


async def test_h_hides_selected_id_and_keeps_cursor_valid(
    tmp_path: Path, plugin: FakePlugin
) -> None:
    app = SawmillApp(_run(_project(tmp_path), ["t"]), single_log=True)
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        _select_id(app, "Y-2")
        await pilot.press("h")
        await pilot.pause()
        assert "Y-2" not in _ids(app)
        assert "Y-2" in app._active_state().hidden_ids
        assert _cursor_valid(app)
        assert any("Hidden" in msg and "Y-2" in msg for msg, _ in rec.calls)


async def test_h_toggles_back_under_show_all(tmp_path: Path, plugin: FakePlugin) -> None:
    app = SawmillApp(_run(_project(tmp_path), ["t"]), single_log=True)
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        _select_id(app, "X-1")
        await pilot.press("h")
        await pilot.pause()
        assert "X-1" not in _ids(app)
        await pilot.press("v")
        await pilot.pause()
        _select_id(app, "X-1")
        await pilot.press("h")
        await pilot.pause()
        assert "X-1" not in app._active_state().hidden_ids
        assert any("Unhidden" in msg and "X-1" in msg for msg, _ in rec.calls)
        await pilot.press("v")
        await pilot.pause()
        assert "X-1" in _ids(app)


async def test_h_without_id_notifies(tmp_path: Path, plugin: FakePlugin) -> None:
    app = SawmillApp(_run(_project(tmp_path), ["t"]), single_log=True)
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        _select_id(app, None)
        await pilot.press("h")
        await pilot.pause()
        assert app._active_state().hidden_ids == set()
        assert any("no ID" in msg for msg, _ in rec.calls)


async def test_h_on_overview_noop(tmp_path: Path, plugin: FakePlugin) -> None:
    app = SawmillApp(_run(_project(tmp_path), ["t"]), single_log=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active = SawmillApp.OVERVIEW
        app._load_active_target()
        rec = await _start(app, pilot)
        await pilot.press("h")
        await pilot.pause()
        assert rec.calls == []
        assert app._states[0].hidden_ids == set()


# --- r ---------------------------------------------------------------------


async def test_r_picks_up_rule_file_edit_without_reparse(
    tmp_path: Path, plugin: FakePlugin
) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t"]), single_log=True)
    calls = plugin.parse_calls
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        _select_id(app, None)
        (root / ".sawmill" / "rules" / "t.toml").write_text(_waive("X-1"))
        await pilot.press("r")
        await pilot.pause()
        assert "X-1" not in _ids(app)
        assert _cursor_valid(app)
        assert any("re-applied" in msg for msg, _ in rec.calls)
    assert plugin.parse_calls == calls


async def test_r_picks_up_manifest_rules_change(tmp_path: Path, plugin: FakePlugin) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t"]), single_log=True)
    calls = plugin.parse_calls
    async with app.run_test() as pilot:
        await _start(app, pilot)
        (root / ".sawmill" / "rules" / "extra.toml").write_text(_waive("Y-2"))
        manifest = root / ".sawmill" / "manifest.toml"
        manifest.write_text(
            manifest.read_text().replace('rules = ["t.toml"]', 'rules = ["t.toml", "extra.toml"]')
        )
        await pilot.press("r")
        await pilot.pause()
        assert "Y-2" not in _ids(app)
        assert app._active_state().result.target.rules == ["t.toml", "extra.toml"]
    assert plugin.parse_calls == calls


async def test_r_manifest_error_notifies_and_keeps_result(
    tmp_path: Path, plugin: FakePlugin
) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t"]), single_log=True)
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        before = list(app.filtered_messages)
        result = app._active_state().result
        (root / ".sawmill" / "manifest.toml").write_text("[manifest\nbroken")
        await pilot.press("r")
        await pilot.pause()
        assert any(kw.get("severity") == "error" for _, kw in rec.calls)
        assert app.filtered_messages == before
        assert app._active_state().result is result


async def test_r_target_removed_from_manifest_notifies(tmp_path: Path, plugin: FakePlugin) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t"]), single_log=True)
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        result = app._active_state().result
        (root / ".sawmill" / "manifest.toml").write_text(
            '[manifest]\nname = "proj"\n\n[[target]]\nname = "z"\nplugin = "test"\n'
            'logs = ["a.log"]\n'
        )
        await pilot.press("r")
        await pilot.pause()
        assert any("target 't' no longer in manifest" in msg for msg, _ in rec.calls)
        assert app._active_state().result is result


async def test_r_single_log_picks_up_new_rules_file_beside_log(
    tmp_path: Path, plugin: FakePlugin
) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG)
    app = SawmillApp([run_single_log(log, "test")], single_log=True)
    calls = plugin.parse_calls
    async with app.run_test() as pilot:
        await _start(app, pilot)
        assert "X-1" in _ids(app)
        rules = tmp_path / ".sawmill" / "rules"
        rules.mkdir(parents=True)
        (rules / "test.toml").write_text(_waive("X-1"))
        await pilot.press("r")
        await pilot.pause()
        assert "X-1" not in _ids(app)
        (rules / "test.toml").unlink()
        await pilot.press("r")
        await pilot.pause()
        assert "X-1" in _ids(app)
    assert plugin.parse_calls == calls


# --- R ---------------------------------------------------------------------


async def test_R_rereads_logs(tmp_path: Path, plugin: FakePlugin) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t"]), single_log=True)
    calls = plugin.parse_calls
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        _select_id(app, "Y-2")
        await pilot.press("h")
        await pilot.pause()
        _select_id(app, None)
        (root / "a.log").write_text(LOG + "ERROR [Z-9] new\n")
        await pilot.press("R")
        await pilot.pause()
        assert plugin.parse_calls > calls
        assert "Z-9" in _ids(app)
        assert "Y-2" not in _ids(app)
        assert _cursor_valid(app)
        assert any("re-read" in msg for msg, _ in rec.calls)


async def test_r_and_R_refresh_all_targets_and_overview(tmp_path: Path, plugin: FakePlugin) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t", "u"]), single_log=False)
    async with app.run_test() as pilot:
        await _start(app, pilot)
        assert app._active == 0
        rules = root / ".sawmill" / "rules"
        (rules / "u.toml").write_text(_waive("X-1"))
        await pilot.press("r")
        await pilot.pause()
        assert app._states[1].result.waived_count == 1
        app._save_active_target()
        app._active = 1
        app._load_active_target()
        await pilot.pause()
        assert "X-1" not in _ids(app)
        (rules / "u.toml").write_text(_waive("X-1", "Y-2"))
        app._active = SawmillApp.OVERVIEW
        app._load_active_target()
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        assert app._states[1].result.waived_count == 2
        overview = app.query_one("#overview-table", OverviewTable)
        assert str(overview.get_row("t:1")[2]) == "2"
        (rules / "u.toml").write_text(EMPTY_RULES)
        await pilot.press("r")
        await pilot.pause()
        assert str(overview.get_row("t:1")[2]) == "0"


async def test_R_rule_file_error_notifies_and_keeps_result(
    tmp_path: Path, plugin: FakePlugin
) -> None:
    root = _project(tmp_path)
    app = SawmillApp(_run(root, ["t"]), single_log=True)
    async with app.run_test() as pilot:
        rec = await _start(app, pilot)
        before = list(app.filtered_messages)
        result = app._active_state().result
        (root / ".sawmill" / "rules" / "t.toml").write_text(
            '[rules]\nplugin = "test"\n[[rule]]\nid = "X"\n'
        )
        await pilot.press("R")
        await pilot.pause()
        assert any(kw.get("severity") == "error" for _, kw in rec.calls)
        assert app.filtered_messages == before
        assert app._active_state().result is result


def test_footer_and_help_mention_h_and_refresh() -> None:
    assert ("h", "Hide") in SawmillApp.TARGET_HINTS
    assert ("r/R", "Refresh") in SawmillApp.TARGET_HINTS
    assert "Hide/unhide message ID (session)" in HELP_TEXT
    assert "Re-read manifest & rules" in HELP_TEXT
    assert "Re-read logs too" in HELP_TEXT
    keys = {b.key: b.action for b in SawmillApp.BINDINGS}
    assert keys.get("h") == "hide_id"
    assert keys.get("r") == "refresh_rules"
    assert keys.get("R") == "refresh_all"
