"""Tests for waiving in single-log mode with no rules file or manifest."""

from __future__ import annotations

from pathlib import Path

from textual.widgets import Input

from sawmill.core.manifest import ManifestLoader
from sawmill.core.plugin import PluginManager
from sawmill.core.rules import RuleLoader
from sawmill.core.runner import run_single_log
from sawmill.tui.app import SawmillApp
from sawmill.tui.widgets.rules_prompt import RulesFilePrompt
from sawmill.tui.widgets.waive_modal import WaiveModal
from tests.tui.conftest import LOG, FakePlugin, Recorder


def _setup(tmp_path: Path) -> tuple[SawmillApp, FakePlugin, Path]:
    log = tmp_path / "a.log"
    log.write_text(LOG)
    plugin = FakePlugin("test")
    manager = PluginManager()
    manager.register(plugin)
    result = run_single_log(log, "test", manager)
    return SawmillApp([result], single_log=True), plugin, log


def _select_id(app: SawmillApp, message_id: str) -> None:
    idx = next(i for i, m in enumerate(app.filtered_messages) if m.message_id == message_id)
    app._navigate_to(idx)


async def _open_prompt(app: SawmillApp, pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    _select_id(app, "X-1")
    await pilot.press("w")
    await pilot.pause()


async def _confirm_prompt(app: SawmillApp, pilot, create: bool = False) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(app.screen, RulesFilePrompt)
    if create:
        await pilot.click("#btn-manifest-yes")
        await pilot.pause()
    app.screen.action_confirm()
    await pilot.pause()


async def test_w_without_rules_file_opens_rules_prompt(tmp_path: Path) -> None:
    app, _, _ = _setup(tmp_path)
    async with app.run_test() as pilot:
        await _open_prompt(app, pilot)
        assert isinstance(app.screen, RulesFilePrompt)
        assert app.screen.query_one("#rules-name-input", Input).value == "test.toml"


async def test_prompt_rules_only_creates_file_and_opens_waive_modal(tmp_path: Path) -> None:
    app, _, _ = _setup(tmp_path)
    path = tmp_path / ".sawmill" / "rules" / "test.toml"
    async with app.run_test() as pilot:
        await _open_prompt(app, pilot)
        await _confirm_prompt(app, pilot)
        assert path.read_text() == '[rules]\nplugin = "test"\n'
        modal = app.screen
        assert isinstance(modal, WaiveModal)
        assert modal.target_files == [path]
        assert app._active_state().result.target.rules == ["test.toml"]
    assert not (tmp_path / ".sawmill" / "manifest.toml").exists()


async def test_prompt_create_manifest_scaffolds_and_opens_waive_modal(tmp_path: Path) -> None:
    app, _, _ = _setup(tmp_path)
    mpath = tmp_path / ".sawmill" / "manifest.toml"
    async with app.run_test() as pilot:
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        await _open_prompt(app, pilot)
        await _confirm_prompt(app, pilot, create=True)
        assert mpath.is_file()
        manifest = ManifestLoader().load(mpath)
        assert len(manifest.targets) == 1
        target = manifest.targets[0]
        assert target.logs == ["a.log"]
        assert target.plugin == "test"
        assert target.rules == ["test.toml"]
        assert (tmp_path / ".sawmill" / "rules" / "test.toml").is_file()
        assert app._active_state().result.manifest.path == mpath
        assert app._active_state().result.manifest.path.exists()
        modal = app.screen
        assert isinstance(modal, WaiveModal)
        assert modal.target_files == [tmp_path / ".sawmill" / "rules" / "test.toml"]
        assert any("manifest.toml" in msg for msg, _ in rec.calls)


async def test_full_flow_waive_after_prompt_hides_message(tmp_path: Path) -> None:
    app, plugin, _ = _setup(tmp_path)
    calls = plugin.parse_calls
    path = tmp_path / ".sawmill" / "rules" / "test.toml"
    async with app.run_test() as pilot:
        await _open_prompt(app, pilot)
        await _confirm_prompt(app, pilot)
        assert isinstance(app.screen, WaiveModal)
        app.screen.query_one("#waive-comment-input", Input).value = "known"
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, WaiveModal)
        rules = RuleLoader().load(path).rules
        assert [r.id for r in rules] == ["X-1"]
        assert all(m.message_id != "X-1" for m in app.filtered_messages)
    assert plugin.parse_calls == calls


async def test_prompt_only_once_per_session(tmp_path: Path) -> None:
    app, _, _ = _setup(tmp_path)
    async with app.run_test() as pilot:
        await _open_prompt(app, pilot)
        await _confirm_prompt(app, pilot)
        assert isinstance(app.screen, WaiveModal)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, WaiveModal)
        await pilot.press("w")
        await pilot.pause()
        assert not isinstance(app.screen, RulesFilePrompt)
        assert isinstance(app.screen, WaiveModal)


async def test_prompt_cancel_does_nothing(tmp_path: Path) -> None:
    app, _, _ = _setup(tmp_path)
    async with app.run_test() as pilot:
        await _open_prompt(app, pilot)
        assert isinstance(app.screen, RulesFilePrompt)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, RulesFilePrompt | WaiveModal)
    assert not (tmp_path / ".sawmill").exists()


async def test_r_after_create_manifest_works(tmp_path: Path) -> None:
    app, _, _ = _setup(tmp_path)
    async with app.run_test() as pilot:
        await _open_prompt(app, pilot)
        await _confirm_prompt(app, pilot, create=True)
        app.screen.query_one("#waive-comment-input", Input).value = "known"
        await pilot.press("enter")
        await pilot.pause()
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        await pilot.press("r")
        await pilot.pause()
        assert not any(kw.get("severity") == "error" for _, kw in rec.calls)
        assert all(m.message_id != "X-1" for m in app.filtered_messages)
        assert app._active_state().result.waived_count == 1


async def test_manifest_mode_never_prompts(tmp_path: Path) -> None:
    from sawmill.core.discovery import TargetRef
    from sawmill.core.runner import run_target

    (tmp_path / ".sawmill").mkdir()
    mpath = tmp_path / ".sawmill" / "manifest.toml"
    mpath.write_text(
        '[manifest]\nname = "proj"\n\n[[target]]\nname = "t"\nplugin = "test"\nlogs = ["a.log"]\n'
    )
    (tmp_path / "a.log").write_text(LOG)
    manager = PluginManager()
    manager.register(FakePlugin("test"))
    manifest = ManifestLoader().load(mpath)
    target = manifest.get_target("t")
    assert target is not None
    app = SawmillApp([run_target(TargetRef(manifest, target), manager)], single_log=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._active == 0
        rec = Recorder()
        app.notify = rec  # type: ignore[method-assign]
        await pilot.pause()
        _select_id(app, "X-1")
        await pilot.press("w")
        await pilot.pause()
        assert not isinstance(app.screen, RulesFilePrompt | WaiveModal)
        assert any("No rule file listed" in msg for msg, _ in rec.calls)
