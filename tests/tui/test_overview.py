"""Tests for the overview tab and OverviewTable widget."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input, Static

from sawmill.models.rule import Rule
from sawmill.tui.app import LogViewer, SawmillApp
from sawmill.tui.state import TargetState
from sawmill.tui.widgets.footer import SawmillFooter
from sawmill.tui.widgets.help_modal import HELP_TEXT
from sawmill.tui.widgets.overview import OverviewTable
from tests.tui.conftest import make_message, make_target_result


def _targets(levels):
    a = make_target_result(
        {
            "a1": [
                make_message("w1", "warning", "W-1", 1),
                make_message("w2", "warning", "W-2", 2),
                make_message("i1", "info", "I-1", 3),
            ],
            "a2": [
                make_message("e1", "error", "E-1", 1),
                make_message("w3", "warning", "W-2", 2),
            ],
        },
        levels,
        name="A",
        rules=[Rule(id="W-1", comment="fine")],
        fail_on="error",
    )
    b = make_target_result(
        {"b1": [make_message("w", "warning", "W-9", 1), make_message("w", "warning", "W-9", 2)]},
        levels,
        name="B",
    )
    c = make_target_result({}, levels, name="C")
    return [a, b, c]


class _Host(App):
    def __init__(self, states):
        super().__init__()
        self.states = states

    def compose(self) -> ComposeResult:
        yield OverviewTable()

    def on_mount(self) -> None:
        self.query_one(OverviewTable).populate(self.states)


def _cell(table: OverviewTable, row: str, col: str) -> str:
    return str(table.get_cell(row, col))


async def _run_host(levels, mutate=None):
    states = [TargetState(t) for t in _targets(levels)]
    if mutate:
        mutate(states)
    host = _Host(states)
    async with host.run_test(size=(140, 30)) as pilot:
        await pilot.pause()
        table = host.query_one(OverviewTable)
        keys = [r.key.value for r in table.ordered_rows]
        cells = {
            k: {c: _cell(table, k, c) for c in ("name", "counts", "waived", "hidden", "result")}
            for k in keys
        }
        styles = {k: table.get_cell(k, "result").style for k in keys}
    return keys, cells, styles


async def test_populate_rows_order_and_keys(severity_levels):
    keys, cells, _ = await _run_host(severity_levels)
    assert keys == ["t:0", "l:0:0", "l:0:1", "t:1", "l:1:0", "t:2", "l:2:none"]
    assert cells["t:0"]["name"] == "m:A"
    assert cells["l:0:1"]["name"] == "  a2"


async def test_counts_text_most_severe_first_skips_zeros(severity_levels):
    _, cells, _ = await _run_host(severity_levels)
    assert cells["t:0"]["counts"] == "error=1 warning=3 info=1"
    assert cells["l:0:0"]["counts"] == "warning=2 info=1"
    assert cells["l:1:0"]["counts"] == "warning=2"
    assert cells["t:2"]["counts"] == "error=0"


async def test_waived_and_hidden_counts(severity_levels):
    def hide(states):
        states[0].hidden_ids = {"W-2"}

    _, cells, _ = await _run_host(severity_levels, hide)
    assert cells["l:0:0"]["waived"] == "1"
    assert cells["l:0:1"]["waived"] == "0"
    assert cells["t:0"]["waived"] == "1"
    assert cells["l:0:0"]["hidden"] == "1"
    assert cells["l:0:1"]["hidden"] == "1"
    assert cells["t:0"]["hidden"] == "2"
    assert cells["t:1"]["hidden"] == "0"


async def test_result_pass_fail_per_log_and_target(severity_levels):
    _, cells, styles = await _run_host(severity_levels)
    assert cells["l:0:0"]["result"] == "PASS"
    assert cells["l:0:1"]["result"] == "FAIL"
    assert cells["t:0"]["result"] == "FAIL"
    assert cells["t:1"]["result"] == "PASS"
    assert cells["t:2"]["result"] == "FAIL"
    assert cells["l:2:none"]["name"] == "  (no logs matched)"
    assert cells["l:2:none"]["result"] == "FAIL"
    assert "green" in str(styles["t:1"])
    assert "red" in str(styles["t:0"])


async def _settle(pilot, n: int = 3) -> None:
    for _ in range(n):
        await pilot.pause()


async def _to_overview(app, pilot):
    while app._active != SawmillApp.OVERVIEW:
        await pilot.press("right")
        await _settle(pilot)


async def test_overview_shown_on_overview_tab_and_hidden_on_target(severity_levels):
    app = SawmillApp(_targets(severity_levels))
    async with app.run_test(size=(140, 40)) as pilot:
        await _settle(pilot)
        assert app.query_one(OverviewTable).display is False
        assert app.query_one(LogViewer).display is True
        await _to_overview(app, pilot)
        assert app.query_one(OverviewTable).display is True
        assert app.query_one(LogViewer).display is False
        await pilot.press("right")
        await _settle(pilot)
        assert app._active == 0
        assert app.query_one(OverviewTable).display is False
        assert app.query_one(LogViewer).display is True


async def _move_to(app, pilot, key: str) -> None:
    table = app.query_one(OverviewTable)
    table.focus()
    table.move_cursor(row=table.get_row_index(key))
    await _settle(pilot)


async def test_enter_on_log_row_opens_target_filtered_to_log(severity_levels):
    app = SawmillApp(_targets(severity_levels))
    async with app.run_test(size=(140, 40)) as pilot:
        await _settle(pilot)
        await _to_overview(app, pilot)
        await _move_to(app, pilot, "l:0:1")
        await pilot.press("enter")
        await _settle(pilot)
        assert app._active == 0
        assert app.filter_pattern == "log:a2"
        assert app.filtered_messages
        assert all(m.log_path == "a2" for m in app.filtered_messages)
        assert app.query_one("#filter-input", Input).value == "log:a2"


async def test_enter_on_target_row_opens_target_without_changing_filter(severity_levels):
    app = SawmillApp(_targets(severity_levels))
    async with app.run_test(size=(140, 40)) as pilot:
        await _settle(pilot)
        app.filter_pattern = "w"
        await _settle(pilot)
        await _to_overview(app, pilot)
        await _move_to(app, pilot, "t:0")
        await pilot.press("enter")
        await _settle(pilot)
        assert app._active == 0
        assert app.filter_pattern == "w"


async def test_overview_repopulates_after_hidden_change(severity_levels):
    app = SawmillApp(_targets(severity_levels))
    async with app.run_test(size=(140, 40)) as pilot:
        await _settle(pilot)
        await _to_overview(app, pilot)
        table = app.query_one(OverviewTable)
        assert str(table.get_cell("t:0", "hidden")) == "0"
        await pilot.press("right")
        await _settle(pilot)
        app._states[0].hidden_ids = {"W-2"}
        await _to_overview(app, pilot)
        assert str(table.get_cell("t:0", "hidden")) == "2"


async def test_number_keys_and_v_ignored_on_overview(severity_levels):
    app = SawmillApp(_targets(severity_levels))
    async with app.run_test(size=(140, 40)) as pilot:
        await _settle(pilot)
        await _to_overview(app, pilot)
        for key in ("1", "2", "3", "4", "v", "o"):
            await pilot.press(key)
            await _settle(pilot)
        assert app._active == SawmillApp.OVERVIEW
        assert app._states[0].severity_filter == {}
        assert app._states[0].show_all is False
        assert app.severity_filter == {}


async def test_footer_and_detail_text_on_overview(severity_levels):
    app = SawmillApp(_targets(severity_levels))
    async with app.run_test(size=(140, 40)) as pilot:
        await _settle(pilot)
        await _to_overview(app, pilot)
        await pilot.pause()
        footer = app.query_one(SawmillFooter)
        labels = [label for _, label in footer._footer_bindings]
        assert labels == ["Quit", "Tab", "Open", "Help"]
        detail = app.query_one("#detail-content", Static)
        assert str(detail.render()) == "Select a target or log and press Enter"
        assert app.query_one("#messages-panel").border_subtitle == ""


def test_help_mentions_enter():
    assert "Enter" in HELP_TEXT
    assert "Open target/log (overview)" in HELP_TEXT


async def _name_width(levels, path):
    states = [TargetState(make_target_result({path: [make_message("a", "error")]}, levels))]
    host = _Host(states)
    async with host.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        table = host.query_one(OverviewTable)
        width = table.columns["name"].width  # type: ignore[index]
        cell = _cell(table, "l:0:0", "name")
        rendered = "".join(
            seg.text for y in range(table.size.height) for seg in table.render_line(y)
        )
    return width, cell, rendered


async def test_name_column_fits_long_log_path(severity_levels):
    path = "run.pcie/pnr/synth_1/impl/" + "x" * 30 + "/vivado.log"
    path = path[-60:]
    assert len(path) == 60
    width, cell, rendered = await _name_width(severity_levels, path)
    assert width >= 62
    assert cell == f"  {path}"
    assert path in rendered
    assert "…" not in rendered


async def test_name_column_minimum_width(severity_levels):
    width, _, _ = await _name_width(severity_levels, "a.log")
    assert width == 40
