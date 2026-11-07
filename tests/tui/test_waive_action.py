"""Tests for the TUI waive action and live re-apply."""

from __future__ import annotations

from pathlib import Path

from sawmill.core.discovery import TargetRef
from sawmill.core.manifest import ManifestLoader
from sawmill.core.plugin import PluginManager
from sawmill.core.runner import TargetResult, run_target
from sawmill.models.rule import Rule
from sawmill.tui.app import SawmillApp
from sawmill.tui.widgets.help_modal import HELP_TEXT
from sawmill.tui.widgets.waive_modal import WaiveModal
from tests.tui.conftest import LOG, FakePlugin, Recorder

MANIFEST = """\
[manifest]
name = "proj"
rules = ["wide.toml", "otherwide.toml"]

[[target]]
name = "t"
plugin = "test"
logs = ["a.log"]
rules = ["t.toml"]

[[target]]
name = "u"
plugin = "test"
logs = ["a.log"]

[[target]]
name = "v"
plugin = "other"
logs = ["a.log"]

[[target]]
name = "bare"
plugin = "test"
logs = ["a.log"]
rules = ["bad.toml"]
"""


def _project(tmp_path: Path, manifest: str = MANIFEST) -> Path:
    rules = tmp_path / ".sawmill" / "rules"
    rules.mkdir(parents=True)
    (tmp_path / ".sawmill" / "manifest.toml").write_text(manifest)
    (rules / "t.toml").write_text('# keep me\n[rules]\nplugin = "test"\n')
    (rules / "wide.toml").write_text('[rules]\nplugin = "test"\n')
    (rules / "otherwide.toml").write_text('[rules]\nplugin = "other"\n')
    (rules / "bad.toml").write_text('[rules]\nplugin = "other"\n')
    (tmp_path / "a.log").write_text(LOG)
    return tmp_path


def _run(root: Path, names: list[str]) -> tuple[list[TargetResult], dict[str, FakePlugin]]:
    plugins = {"test": FakePlugin("test"), "other": FakePlugin("other")}
    manager = PluginManager()
    for p in plugins.values():
        manager.register(p)
    manifest = ManifestLoader().load(root / ".sawmill" / "manifest.toml")
    results = []
    for name in names:
        target = manifest.get_target(name)
        assert target is not None
        results.append(run_target(TargetRef(manifest, target), manager))
    return results, plugins


def _app(results: list[TargetResult], single_log: bool = True) -> SawmillApp:
    return SawmillApp(results, single_log=single_log)


def _select_id(app: SawmillApp, message_id: str | None) -> None:
    idx = next(i for i, m in enumerate(app.filtered_messages) if m.message_id == message_id)
    app._navigate_to(idx)


async def test_w_on_message_without_id_notifies(tmp_path: Path) -> None:
    results, _ = _run(_project(tmp_path), ["t"])
    app = _app(results)
    async with app.run_test() as pilot:
        await pilot.pause()
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        _select_id(app, None)
        await pilot.press("w")
        await pilot.pause()
        assert not isinstance(app.screen, WaiveModal)
        assert any("no ID" in msg for msg, _ in rec.calls)


async def test_w_opens_modal_with_target_and_plugin_files(tmp_path: Path) -> None:
    root = _project(tmp_path)
    results, _ = _run(root, ["t"])
    app = _app(results)
    rules = root / ".sawmill" / "rules"
    async with app.run_test() as pilot:
        await pilot.pause()
        _select_id(app, "X-1")
        await pilot.press("w")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, WaiveModal)
        assert modal.target_files == [rules / "t.toml"]
        assert modal.plugin_files == [rules / "wide.toml"]


async def test_w_without_rule_files_notifies_and_does_not_open(tmp_path: Path) -> None:
    manifest = (
        '[manifest]\nname = "proj"\n\n[[target]]\nname = "t"\nplugin = "test"\nlogs = ["a.log"]\n'
    )
    results, _ = _run(_project(tmp_path, manifest), ["t"])
    app = _app(results)
    async with app.run_test() as pilot:
        await pilot.pause()
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        _select_id(app, "X-1")
        await pilot.press("w")
        await pilot.pause()
        assert not isinstance(app.screen, WaiveModal)
        assert any(
            "No rule file" in msg and kw.get("severity") == "warning" for msg, kw in rec.calls
        )


async def test_waive_result_appends_rule_and_hides_message_live(tmp_path: Path) -> None:
    root = _project(tmp_path)
    results, plugins = _run(root, ["t"])
    calls_before = plugins["test"].parse_calls
    app = _app(results)
    path = root / ".sawmill" / "rules" / "t.toml"
    async with app.run_test() as pilot:
        await pilot.pause()
        _select_id(app, "Y-2")
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        app._on_waive_result(
            {"rule": Rule(id="X-1", comment="known"), "path": path, "scope": "target"}
        )
        await pilot.pause()
        text = path.read_text()
        assert text.startswith("# keep me\n")
        assert "[[rule]]" in text and 'id = "X-1"' in text
        assert all(m.message_id != "X-1" for m in app.filtered_messages)
        state = app._active_state()
        waived = [m for m in state.result.all_messages if m.message_id == "X-1"]
        assert waived and all(id(m) in state.waived_ids for m in waived)
        assert 0 <= app._current_index() < len(app.filtered_messages)
        assert any("t.toml" in msg and "X-1" in msg for msg, _ in rec.calls)
    assert plugins["test"].parse_calls == calls_before


async def test_waive_plugin_scope_reapplies_all_targets_with_plugin(tmp_path: Path) -> None:
    root = _project(tmp_path)
    results, plugins = _run(root, ["t", "u", "v"])
    app = _app(results, single_log=False)
    path = root / ".sawmill" / "rules" / "wide.toml"
    async with app.run_test() as pilot:
        await pilot.pause()
        app._on_waive_result(
            {"rule": Rule(id="X-1", comment="known"), "path": path, "scope": "plugin"}
        )
        await pilot.pause()
        for i in (0, 1):
            state = app._states[i]
            assert state.result.waived_count == 1
            assert all(m.message_id != "X-1" for m in state.base_messages())
        assert app._states[2].result.waived_count == 0
        assert any(m.message_id == "X-1" for m in app._states[2].base_messages())
    assert plugins["test"].parse_calls == 2


async def test_waive_append_error_notifies_and_keeps_table(tmp_path: Path) -> None:
    root = _project(tmp_path)
    results, _ = _run(root, ["t"])
    app = _app(results)
    path = root / ".sawmill" / "rules" / "otherwide.toml"
    async with app.run_test() as pilot:
        await pilot.pause()
        before = list(app.filtered_messages)
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        app._on_waive_result(
            {"rule": Rule(id="X-1", comment="known"), "path": path, "scope": "plugin"}
        )
        await pilot.pause()
        assert any(kw.get("severity") == "error" for _, kw in rec.calls)
        assert app.filtered_messages == before
        assert app._active_state().waived_ids == frozenset()
        assert "[[rule]]" not in path.read_text()


async def test_w_on_overview_is_noop(tmp_path: Path) -> None:
    results, _ = _run(_project(tmp_path), ["t"])
    app = _app(results, single_log=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active = SawmillApp.OVERVIEW
        app._load_active_target()
        await pilot.pause()
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        await pilot.press("w")
        await pilot.pause()
        assert not isinstance(app.screen, WaiveModal)
        assert rec.calls == []


def test_footer_and_help_mention_w() -> None:
    assert ("w", "Waive") in SawmillApp.TARGET_HINTS
    assert "Waive" in HELP_TEXT
    assert any(b.key == "w" and b.action == "waive" for b in SawmillApp.BINDINGS)
