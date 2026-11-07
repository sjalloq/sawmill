"""Tests for the windowed LogViewer: the DataTable holds only rows near the cursor."""

from __future__ import annotations

import pytest

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.app import SORT_MODES, LogViewer, SawmillApp
from tests.tui.conftest import make_target_result

N = 1000
SIZE = (120, 40)


@pytest.fixture
def severity_levels():
    return [
        SeverityLevel(id="error", name="Error", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


def _messages(n: int = N) -> list[Message]:
    sevs = ["info", "warning", "error"]
    out = []
    for i in range(n):
        text = f"message number {i}" + (" needle" if i % 100 == 0 else "")
        out.append(
            Message(
                start_line=i + 1,
                end_line=i + 1,
                raw_text=f"RAW {i}: {text}",
                content=text,
                severity=sevs[i % 3],
                message_id=f"ID-{i % 7}",
            )
        )
    return out


@pytest.fixture
def app(severity_levels):
    return SawmillApp([make_target_result({"build.log": _messages()}, severity_levels)])


async def _settle(pilot, n: int = 3) -> None:
    for _ in range(n):
        await pilot.pause()


def _highlighted_message(app: SawmillApp) -> Message:
    table = app.query_one(LogViewer)
    row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
    return app.filtered_messages[int(row_key.value)]


def _detail(app: SawmillApp) -> str:
    return str(app._detail_content.render())


class TestWindowedTable:
    async def test_row_count_is_window(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            table = app.query_one(LogViewer)
            assert len(app.filtered_messages) == N
            assert table.row_count == app._window_size()
            assert table.row_count < N

    async def test_end_and_home(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            await pilot.press("end")
            await _settle(pilot)
            assert app._cursor_index == N - 1
            assert _highlighted_message(app) is app.filtered_messages[-1]
            assert f"RAW {N - 1}:" in _detail(app)
            await pilot.press("home")
            await _settle(pilot)
            assert app._cursor_index == 0
            assert _highlighted_message(app) is app.filtered_messages[0]
            assert "RAW 0:" in _detail(app)

    async def test_g_bindings(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            await pilot.press("G")
            await _settle(pilot)
            assert app._cursor_index == N - 1
            await pilot.press("g")
            await _settle(pilot)
            assert app._cursor_index == 0

    async def test_page_down_crosses_windows(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            last = 0
            while last < N - 1:
                await pilot.press("pagedown")
                await _settle(pilot, 1)
                assert app._cursor_index > last
                assert app._cursor_index >= last
                last = app._cursor_index
                assert _highlighted_message(app) is app.filtered_messages[last]
            assert last == N - 1
            assert f"RAW {N - 1}:" in _detail(app)
            while app._cursor_index > 0:
                before = app._cursor_index
                await pilot.press("pageup")
                await _settle(pilot, 1)
                assert app._cursor_index < before
                assert _highlighted_message(app) is app.filtered_messages[app._cursor_index]

    async def test_cursor_down_crosses_window(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            w = app._window_size()
            # Start near the bottom edge of the first window, then step across it.
            app._navigate_to(w - 40)
            await _settle(pilot)
            for _ in range(45):
                await pilot.press("down")
            await _settle(pilot)
            assert app._cursor_index == w + 5
            assert _highlighted_message(app) is app.filtered_messages[w + 5]
            assert f"RAW {w + 5}:" in _detail(app)

    async def test_filter_and_clear(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            table = app.query_one(LogViewer)
            app.filter_pattern = "needle"
            await _settle(pilot)
            assert len(app.filtered_messages) == N // 100
            assert table.row_count == N // 100
            app.filter_pattern = ""
            await _settle(pilot)
            assert len(app.filtered_messages) == N
            assert table.row_count == app._window_size()

    async def test_sort_cycle_keeps_valid_cursor(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            await pilot.press("end")
            await _settle(pilot)
            for _ in SORT_MODES:
                await pilot.press("o")
                await _settle(pilot)
                assert 0 <= app._cursor_index < N
                assert _highlighted_message(app) is app.filtered_messages[app._cursor_index]

    async def test_row_key_maps_to_message(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            app._navigate_to(600)
            await _settle(pilot)
            assert app._cursor_index == 600
            msg = _highlighted_message(app)
            assert msg is app.filtered_messages[600]
            assert app._current_message() is msg

    async def test_scroll_to_window_edge_slides_window(self, app):
        async with app.run_test(size=SIZE) as pilot:
            await _settle(pilot)
            table = app.query_one(LogViewer)
            assert app._window_start == 0
            table.scroll_to(y=table.max_scroll_y, animate=False)
            await _settle(pilot)
            assert app._window_start > 0
            assert table.window_start == app._window_start
            assert _highlighted_message(app) is app.filtered_messages[app._cursor_index]


async def test_switch_tabs_keeps_window_behaviour(severity_levels):
    app = SawmillApp(
        [
            make_target_result({"a.log": _messages()}, severity_levels),
            make_target_result({"b.log": _messages()}, severity_levels, name="u"),
        ]
    )
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.query_one(LogViewer).focus()
        await pilot.press("right")
        await _settle(pilot)
        assert app._active == 1
        await pilot.press("end")
        await _settle(pilot)
        table = app.query_one(LogViewer)
        assert table.row_count == app._window_size()
        assert app._cursor_index == N - 1
        assert _highlighted_message(app) is app.filtered_messages[-1]
