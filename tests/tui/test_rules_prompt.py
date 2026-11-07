"""Tests for the rules file prompt modal."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Static

from sawmill.tui.widgets.rules_prompt import RulesFilePrompt

RULES = Path("/proj/.sawmill/rules")


class ModalTestApp(App):
    """Minimal app for testing modals."""

    def compose(self) -> ComposeResult:
        yield Static("test")


def _prompt() -> RulesFilePrompt:
    return RulesFilePrompt(rules_dir=RULES, default_name="test.toml", log_name="a.log")


async def test_default_name_and_rules_only_default() -> None:
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(_prompt())
        await pilot.pause()
        assert app.screen.query_one("#rules-name-input", Input).value == "test.toml"
        assert app.screen.query_one("#btn-manifest-no", Button).has_class("waive-selected")
        assert not app.screen.query_one("#btn-manifest-yes", Button).has_class("waive-selected")


async def test_confirm_returns_path_and_flag() -> None:
    result: list = []
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(_prompt(), callback=result.append)
        await pilot.pause()
        app.screen.query_one("#rules-name-input", Input).value = "mine.toml"
        await pilot.press("enter")
        await pilot.pause()
    assert result == [{"path": RULES / "mine.toml", "create_manifest": False}]


async def test_create_manifest_button() -> None:
    result: list = []
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(_prompt(), callback=result.append)
        await pilot.pause()
        await pilot.click("#btn-manifest-yes")
        await pilot.pause()
        assert app.screen.query_one("#btn-manifest-yes", Button).has_class("waive-selected")
        await pilot.press("enter")
        await pilot.pause()
    assert result == [{"path": RULES / "test.toml", "create_manifest": True}]


async def test_rejects_non_toml_or_path_separator() -> None:
    result: list = []
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(_prompt(), callback=result.append)
        await pilot.pause()
        screen = app.screen
        for bad in ("rules.txt", "sub/rules.toml", ""):
            screen.query_one("#rules-name-input", Input).value = bad
            screen.action_confirm()  # type: ignore[attr-defined]
            await pilot.pause()
            assert app.screen is screen
            assert str(screen.query_one("#rules-prompt-error", Static).render())
    assert result == []


async def test_escape_dismisses_none() -> None:
    result: list = []
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(_prompt(), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
    assert result == [None]


async def test_has_modal_classes_and_f12() -> None:
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(_prompt())
        await pilot.pause()
        assert "modal-container" in app.screen.query_one("#rules-prompt-container").classes
        assert "modal-title" in app.screen.query_one("#rules-prompt-title").classes
        assert "modal-footer" in app.screen.query_one("#rules-prompt-footer").classes
    assert "f12" in [b[0] for b in RulesFilePrompt.BINDINGS]
