"""Tests for the waive modal."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Select, Static

from sawmill.tui.widgets.waive_modal import WaiveModal

T1 = Path("/p/.sawmill/rules/t1.toml")
T2 = Path("/p/.sawmill/rules/t2.toml")
W1 = Path("/p/.sawmill/rules/wide.toml")


class Host(App):
    """Minimal host app for the modal."""

    def compose(self) -> ComposeResult:
        yield Static("host")


def _modal(
    content: str = "bad thing (here)",
    target_files: list[Path] | None = None,
    plugin_files: list[Path] | None = None,
    author: str = "me@x",
) -> WaiveModal:
    return WaiveModal(
        message_id="X-1",
        severity="error",
        content=content,
        log_rel_path="build/a.log",
        target_files=[T1, T2] if target_files is None else target_files,
        plugin_files=[W1] if plugin_files is None else plugin_files,
        author=author,
    )


async def _run(modal: WaiveModal, steps) -> list:
    results: list = []
    app = Host()
    async with app.run_test() as pilot:
        await app.push_screen(modal, callback=results.append)
        await pilot.pause()
        await steps(app, pilot)
        await pilot.pause()
    return results


def _q(app, selector, cls):
    return app.screen.query_one(selector, cls)


async def _set(app, pilot, selector: str, value: str) -> None:
    _q(app, selector, Input).value = value
    await pilot.pause()


async def _click(app, pilot, button_id: str) -> None:
    _q(app, f"#{button_id}", Button).press()
    await pilot.pause()


async def _confirm(app, pilot) -> None:
    app.screen.action_confirm()
    await pilot.pause()


def _selected(app, button_id: str) -> bool:
    return _q(app, f"#{button_id}", Button).has_class("waive-selected")


def _errors(app) -> str:
    return " ".join(str(s.render()) for s in app.screen.query(".waive-error"))


async def test_defaults_target_scope_id_match_last_file_preselected() -> None:
    async def steps(app, pilot):
        assert _selected(app, "btn-scope-target")
        assert _selected(app, "btn-match-id")
        assert _q(app, "#waive-dest-select", Select).value == T2

    await _run(_modal(), steps)


async def test_scope_switch_repopulates_destination() -> None:
    async def steps(app, pilot):
        await _click(app, pilot, "btn-scope-plugin")
        assert _selected(app, "btn-scope-plugin")
        sel = _q(app, "#waive-dest-select", Select)
        assert sel.value == W1
        assert [v for _, v in sel._options if isinstance(v, Path)] == [W1]
        await _click(app, pilot, "btn-scope-target")
        sel = _q(app, "#waive-dest-select", Select)
        assert sel.value == T2
        assert [v for _, v in sel._options if isinstance(v, Path)] == [T1, T2]

    await _run(_modal(), steps)


async def test_scopes_disabled_when_no_files() -> None:
    async def steps1(app, pilot):
        assert _q(app, "#btn-scope-plugin", Button).disabled
        assert not _q(app, "#btn-scope-target", Button).disabled

    await _run(_modal(plugin_files=[]), steps1)

    async def steps2(app, pilot):
        assert _q(app, "#btn-scope-log", Button).disabled
        assert _q(app, "#btn-scope-target", Button).disabled
        assert _selected(app, "btn-scope-plugin")
        assert _q(app, "#waive-dest-select", Select).value == W1

    await _run(_modal(target_files=[]), steps2)


async def test_pattern_input_disabled_for_id_only_and_enabled_for_substring() -> None:
    async def steps(app, pilot):
        pattern = _q(app, "#waive-pattern-input", Input)
        assert pattern.disabled
        assert pattern.value == "bad thing (here)"
        await _click(app, pilot, "btn-match-substring")
        assert not pattern.disabled
        await _click(app, pilot, "btn-match-id")
        assert pattern.disabled

    await _run(_modal(), steps)


async def test_confirm_id_only_returns_rule_without_regex_or_logs() -> None:
    async def steps(app, pilot):
        await _set(app, pilot, "#waive-comment-input", "known issue")
        await _confirm(app, pilot)

    results = await _run(_modal(), steps)
    assert len(results) == 1
    out = results[0]
    rule = out["rule"]
    assert rule.id == "X-1"
    assert rule.comment == "known issue"
    assert rule.author == "me@x"
    assert rule.date == date.today().isoformat()
    assert rule.regex is None
    assert rule.logs is None
    assert rule.max_count is None
    assert out["path"] == T2
    assert out["scope"] == "target"


async def test_confirm_log_scope_sets_logs() -> None:
    async def steps(app, pilot):
        await _click(app, pilot, "btn-scope-log")
        await _set(app, pilot, "#waive-comment-input", "c")
        await _confirm(app, pilot)

    results = await _run(_modal(), steps)
    assert results[0]["scope"] == "log"
    assert results[0]["rule"].logs == ["build/a.log"]
    assert results[0]["path"] == T2


async def test_confirm_substring_escapes_pattern() -> None:
    async def steps(app, pilot):
        await _click(app, pilot, "btn-match-substring")
        await _set(app, pilot, "#waive-comment-input", "c")
        await _confirm(app, pilot)

    results = await _run(_modal(content="  bad thing (here)\nsecond line"), steps)
    assert results[0]["rule"].regex == re.escape("bad thing (here)")


async def test_confirm_regex_invalid_shows_error_and_stays_open() -> None:
    async def steps(app, pilot):
        await _click(app, pilot, "btn-match-regex")
        await _set(app, pilot, "#waive-pattern-input", "bad (")
        await _set(app, pilot, "#waive-comment-input", "c")
        await _confirm(app, pilot)
        assert isinstance(app.screen, WaiveModal)
        assert "regex" in _errors(app).lower()

    results = await _run(_modal(), steps)
    assert results == []


async def test_confirm_regex_valid() -> None:
    async def steps(app, pilot):
        await _click(app, pilot, "btn-match-regex")
        await _set(app, pilot, "#waive-pattern-input", r"bad \w+")
        await _set(app, pilot, "#waive-comment-input", "c")
        await _confirm(app, pilot)

    results = await _run(_modal(), steps)
    assert results[0]["rule"].regex == r"bad \w+"


async def test_confirm_requires_comment() -> None:
    async def steps(app, pilot):
        await _confirm(app, pilot)
        assert isinstance(app.screen, WaiveModal)
        assert "comment" in _errors(app).lower()

    results = await _run(_modal(), steps)
    assert results == []


async def test_count_validation() -> None:
    async def bad(app, pilot):
        await _set(app, pilot, "#waive-comment-input", "c")
        for value in ("0", "x"):
            await _set(app, pilot, "#waive-count-input", value)
            await _confirm(app, pilot)
            assert isinstance(app.screen, WaiveModal)
            assert "count" in _errors(app).lower()

    assert await _run(_modal(), bad) == []

    async def per_log(app, pilot):
        assert _q(app, "#btn-per-log", Button).disabled
        await _set(app, pilot, "#waive-comment-input", "c")
        await _set(app, pilot, "#waive-count-input", "3")
        assert not _q(app, "#btn-per-log", Button).disabled
        await _confirm(app, pilot)

    results = await _run(_modal(), per_log)
    assert results[0]["rule"].max_count == 3
    assert results[0]["rule"].per == "log"

    async def per_target(app, pilot):
        await _set(app, pilot, "#waive-comment-input", "c")
        await _set(app, pilot, "#waive-count-input", "3")
        await _click(app, pilot, "btn-per-target")
        await _confirm(app, pilot)

    results = await _run(_modal(), per_target)
    assert results[0]["rule"].per == "target"


async def test_empty_author_omitted() -> None:
    async def steps(app, pilot):
        await _set(app, pilot, "#waive-author-input", "  ")
        await _set(app, pilot, "#waive-comment-input", "c")
        await _confirm(app, pilot)

    results = await _run(_modal(), steps)
    assert results[0]["rule"].author is None


async def test_escape_dismisses_none() -> None:
    async def steps(app, pilot):
        await pilot.press("escape")

    assert await _run(_modal(), steps) == [None]


async def test_enter_in_comment_confirms() -> None:
    async def steps(app, pilot):
        _q(app, "#waive-comment-input", Input).focus()
        await pilot.press("o", "k", "enter")

    results = await _run(_modal(), steps)
    assert results[0]["rule"].comment == "ok"
