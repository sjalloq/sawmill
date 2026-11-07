"""Tests for the main TUI application."""

from __future__ import annotations

import inspect

import pytest

from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.rule import Rule
from sawmill.tui.app import (
    SORT_COUNT,
    SORT_ID,
    SORT_LINE,
    SORT_SEVERITY,
    FilterInput,
    LogViewer,
    MessageStats,
    SawmillApp,
)
from tests.tui.conftest import make_message, make_target_result


def make_app(messages, severity_levels, **kwargs) -> SawmillApp:
    """Build an app over one target holding ``messages`` in one log."""
    return SawmillApp([make_target_result({"a.log": messages}, severity_levels, **kwargs)])


class TestSawmillAppInit:
    """Tests for SawmillApp initialisation."""

    def test_init_requires_targets(self):
        with pytest.raises(ValueError):
            SawmillApp([])

    def test_init_uses_first_target_levels(self, severity_levels):
        other = [SeverityLevel(id="fatal", name="Fatal", level=9)]
        app = SawmillApp(
            [
                make_target_result({"a.log": []}, severity_levels),
                make_target_result({"b.log": []}, other, name="u"),
            ]
        )
        assert app._severity_levels == severity_levels
        assert app._key_to_severity == {
            1: "info",
            2: "warning",
            3: "critical_warning",
            4: "error",
        }

    def test_filtered_messages_merge_logs_with_log_path(self, severity_levels):
        result = make_target_result(
            {
                "a.log": [make_message("a1", "error", line=2)],
                "b.log": [make_message("b1", "warning", line=1)],
            },
            severity_levels,
        )
        app = SawmillApp([result])
        app._apply_filters()
        assert {(m.content, m.log_path) for m in app.filtered_messages} == {
            ("a1", "a.log"),
            ("b1", "b.log"),
        }

    def test_waived_messages_hidden_from_table(self, severity_levels):
        app = make_app(
            [
                make_message("e", "error", "E-1", line=1),
                make_message("w", "warning", "W-1", line=2),
            ],
            severity_levels,
            rules=[Rule(id="W-1", comment="fine")],
        )
        app._apply_filters()
        assert [m.message_id for m in app.filtered_messages] == ["E-1"]

    def test_hidden_ids_hidden_from_table(self, severity_levels):
        app = make_app(
            [
                make_message("e", "error", "E-1", line=1),
                make_message("w", "warning", "W-1", line=2),
            ],
            severity_levels,
        )
        app._active_state().hidden_ids = {"E-1"}
        app._apply_filters()
        assert [m.message_id for m in app.filtered_messages] == ["W-1"]


class TestSawmillAppFiltering:
    """Tests for message filtering in the app."""

    @pytest.fixture
    def app_with_messages(self, severity_levels):
        """Create an app with test messages."""
        messages = [
            make_message("Error in module A", severity="error", message_id="E-001", line=1),
            make_message("Warning in module B", severity="warning", message_id="W-001", line=2),
            make_message("Info message", severity="info", message_id="I-001", line=3),
            make_message("Another error", severity="error", message_id="E-002", line=4),
        ]
        return make_app(messages, severity_levels)

    def test_filter_pattern_empty(self, app_with_messages):
        """Test that empty filter shows all messages."""
        app_with_messages.filter_pattern = ""
        app_with_messages._apply_filters()
        assert len(app_with_messages.filtered_messages) == 4

    def test_filter_pattern_matches(self, app_with_messages):
        """Test regex filter matches correctly."""
        app_with_messages.filter_pattern = "module A"
        app_with_messages._apply_filters()
        assert len(app_with_messages.filtered_messages) == 1
        assert "module A" in app_with_messages.filtered_messages[0].content

    def test_filter_pattern_case_insensitive(self, app_with_messages):
        """Test filter is case insensitive."""
        app_with_messages.filter_pattern = "ERROR"
        app_with_messages._apply_filters()
        # Should match both "Error" messages
        assert len(app_with_messages.filtered_messages) == 2

    def test_filter_pattern_invalid_regex(self, app_with_messages):
        """Test invalid regex doesn't crash."""
        app_with_messages.filter_pattern = "[invalid"
        app_with_messages._apply_filters()
        # Should still show all messages (invalid regex ignored)
        assert len(app_with_messages.filtered_messages) == 4

    def test_severity_filter_hide_info(self, app_with_messages):
        """Test severity filter hides unchecked severities."""
        app_with_messages.severity_filter = {
            "error": True,
            "critical_warning": True,
            "warning": True,
            "info": False,
        }
        app_with_messages._apply_filters()
        # Should include error, warning but not info
        assert len(app_with_messages.filtered_messages) == 3
        for msg in app_with_messages.filtered_messages:
            assert msg.severity.lower() in ("error", "warning")

    def test_severity_filter_errors_only(self, app_with_messages):
        """Test severity filter for errors only."""
        app_with_messages.severity_filter = {
            "error": True,
            "critical_warning": False,
            "warning": False,
            "info": False,
        }
        app_with_messages._apply_filters()
        assert len(app_with_messages.filtered_messages) == 2
        for msg in app_with_messages.filtered_messages:
            assert msg.severity.lower() == "error"

    def test_severity_filter_empty_shows_all(self, app_with_messages):
        """Test empty severity filter shows all messages."""
        app_with_messages.severity_filter = {}
        app_with_messages._apply_filters()
        assert len(app_with_messages.filtered_messages) == 4

    def test_combined_filters(self, app_with_messages):
        """Test combining severity and pattern filters."""
        app_with_messages.severity_filter = {
            "error": True,
            "critical_warning": False,
            "warning": False,
            "info": False,
        }
        app_with_messages.filter_pattern = "module"
        app_with_messages._apply_filters()
        # Only error + contains "module"
        assert len(app_with_messages.filtered_messages) == 1
        assert app_with_messages.filtered_messages[0].content == "Error in module A"


class TestMessageStatsWidget:
    """Tests for the MessageStats widget."""

    def test_init_defaults(self):
        """Test default values."""
        stats = MessageStats()
        assert stats.total == 0
        assert stats.counts == {}

    def test_init_with_severity_levels(self, severity_levels):
        """Test initialization with severity levels."""
        stats = MessageStats(severity_levels=severity_levels)
        assert stats.total == 0
        assert stats.counts == {}

    def test_render_with_counts(self, severity_levels):
        """Test render method produces output with plugin-driven severity counts."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3, "warning": 5, "info": 2}
        output = stats.render()
        assert "Total: 10" in output
        assert "Error: 3" in output
        assert "Warning: 5" in output
        assert "Info: 2" in output

    def test_render_uses_severity_styles(self, severity_levels):
        """Test render includes style markup from severity levels."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 5
        stats.counts = {"error": 2, "warning": 3}
        output = stats.render()
        # Verify styles are applied (red bold for error, yellow for warning)
        assert "red bold" in output
        assert "yellow" in output

    def test_render_custom_severity_scheme(self):
        """Test render with a non-Vivado severity scheme."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=3, style="red bold"),
            SeverityLevel(id="major", name="Major", level=2, style="red"),
            SeverityLevel(id="minor", name="Minor", level=1, style="yellow"),
            SeverityLevel(id="note", name="Note", level=0, style="dim"),
        ]
        stats = MessageStats(severity_levels=custom_levels)
        stats.total = 4
        stats.counts = {"fatal": 1, "major": 1, "minor": 1, "note": 1}
        output = stats.render()
        assert "Fatal: 1" in output
        assert "Major: 1" in output
        assert "Minor: 1" in output
        assert "Note: 1" in output


class TestLogViewerWidget:
    """Tests for the LogViewer widget."""

    def test_init(self):
        """Test widget initialization."""
        viewer = LogViewer()
        assert viewer.cursor_type == "row"
        assert viewer.zebra_stripes is True


class TestFilterInputWidget:
    """Tests for the FilterInput widget."""

    def test_init_default_placeholder(self):
        """Test default placeholder text."""
        input_widget = FilterInput()
        assert "filter" in input_widget.placeholder.lower()


class TestAppActions:
    """Tests for app action methods."""

    @pytest.fixture
    def app(self, severity_levels):
        """Create a test app."""
        return make_app(
            [
                make_message("Test error", severity="error"),
                make_message("Test warning", severity="warning"),
            ],
            severity_levels,
        )

    def test_action_clear_filter(self, app):
        """Test action_clear_filter clears all filters."""
        app.filter_pattern = "test"
        app.severity_filter = {"error": True, "warning": False}
        app.action_clear_filter()
        assert app.filter_pattern == ""
        assert app.severity_filter == {}

    def test_severity_toggle_keybindings(self, app):
        """Test that number keys 1-4 exist for severity toggles."""
        binding_keys = [b.key for b in app.BINDINGS]
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "3" in binding_keys
        assert "4" in binding_keys


class TestSeverityToggles:
    """Tests for severity toggle actions."""

    @pytest.fixture
    def app(self, severity_levels):
        """Create an app with test messages."""
        messages = [
            make_message("Error msg", severity="error", message_id="E-001", line=1),
            make_message("Warning msg", severity="warning", message_id="W-001", line=2),
            make_message("Info msg", severity="info", message_id="I-001", line=3),
        ]
        return make_app(messages, severity_levels)

    def test_key_to_severity_mapping(self, app):
        """Test that number keys map to severity levels sorted by level ascending."""
        # level 0 = info → key 1, level 1 = warning → key 2, etc.
        assert app._key_to_severity[1] == "info"
        assert app._key_to_severity[2] == "warning"
        assert app._key_to_severity[3] == "critical_warning"
        assert app._key_to_severity[4] == "error"

    def test_toggle_severity_first_time(self, app):
        """Test toggling a severity when no filter is set initializes all and flips one."""
        app.action_toggle_sev_1()
        # Key 1 = info, should now be hidden
        assert app.severity_filter["info"] is False
        # Others should remain True
        assert app.severity_filter["error"] is True

    def test_toggle_severity_back(self, app):
        """Test toggling same severity twice returns to visible."""
        app.action_toggle_sev_1()
        app.action_toggle_sev_1()
        assert app.severity_filter["info"] is True

    def test_toggle_filters_messages(self, app):
        """Test toggling a severity actually filters messages."""
        app.action_toggle_sev_1()  # Hide info
        app._apply_filters()
        for msg in app.filtered_messages:
            assert msg.severity.lower() != "info"


class TestSortModes:
    """Tests for sort mode cycling."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error B", severity="error", message_id="E-002", line=10),
            make_message("Warning A", severity="warning", message_id="W-001", line=5),
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Info C", severity="info", message_id="I-001", line=20),
        ]
        return make_app(messages, severity_levels)

    def test_default_sort_is_line(self, app):
        assert app.sort_mode == SORT_LINE

    def test_cycle_sort(self, app):
        """Test cycling through sort modes."""
        app.action_cycle_sort()
        assert app.sort_mode == SORT_SEVERITY
        app.action_cycle_sort()
        assert app.sort_mode == SORT_ID
        app.action_cycle_sort()
        assert app.sort_mode == SORT_COUNT
        app.action_cycle_sort()
        assert app.sort_mode == SORT_LINE

    def test_sort_by_line(self, app):
        """Test sort by line number (default)."""
        app.sort_mode = SORT_LINE
        app._apply_filters()
        lines = [m.start_line for m in app.filtered_messages]
        assert lines == sorted(lines)

    def test_sort_by_severity(self, app):
        """Test sort by severity (most severe first)."""
        app.sort_mode = SORT_SEVERITY
        app._apply_filters()
        # Errors (level 3) should come before warnings (level 1) before info (level 0)
        sevs = [m.severity for m in app.filtered_messages]
        assert sevs[0] == "error"
        assert sevs[-1] == "info"

    def test_sort_by_id(self, app):
        """Test sort by message ID (alphabetical)."""
        app.sort_mode = SORT_ID
        app._apply_filters()
        ids = [m.message_id for m in app.filtered_messages]
        assert ids == sorted(ids)

    def test_sort_by_count(self, app):
        """Test sort by ID frequency (most frequent first)."""
        # Add duplicate ID
        app._states[0].result.logs[0].messages.append(
            make_message("Error A dup", severity="error", message_id="E-001", line=2)
        )
        app.sort_mode = SORT_COUNT
        app._apply_filters()
        # E-001 appears twice, so its messages should come first
        assert app.filtered_messages[0].message_id == "E-001"


class TestSearchBarPrefixFiltering:
    """Tests for search bar prefix filtering in _apply_filters."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error in module A", severity="error", message_id="E-001", line=1),
            make_message("Warning in module B", severity="warning", message_id="W-001", line=2),
            make_message("Info message", severity="info", message_id="I-001", line=3),
        ]
        return make_app(messages, severity_levels)

    def test_sev_prefix_filters(self, app):
        """Test sev: prefix in search bar filters by severity."""
        app.filter_pattern = "sev:error"
        app._apply_filters()
        assert all(m.severity == "error" for m in app.filtered_messages)

    def test_id_prefix_filters(self, app):
        """Test id: prefix in search bar filters by message ID."""
        app.filter_pattern = "id:E-001"
        app._apply_filters()
        assert len(app.filtered_messages) == 1
        assert app.filtered_messages[0].message_id == "E-001"

    def test_plain_text_regex(self, app):
        """Test plain text in search bar acts as regex on raw_text."""
        app.filter_pattern = "module B"
        app._apply_filters()
        assert len(app.filtered_messages) == 1
        assert "module B" in app.filtered_messages[0].raw_text


class TestMessageStatsActive:
    """Tests for active/dimmed severity display in stats widget."""

    def test_render_dimmed_severity(self, severity_levels):
        """Test that inactive severities are rendered with dim style."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3, "warning": 5, "info": 2}
        stats.active = {"error": True, "warning": True, "info": False, "critical_warning": True}
        output = stats.render()
        assert "[dim]\\[1] Info: 2[/dim]" in output

    def test_render_all_active(self, severity_levels):
        """Test that all-active renders normally."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 5
        stats.counts = {"error": 2, "warning": 3}
        stats.active = {"error": True, "warning": True, "info": True, "critical_warning": True}
        output = stats.render()
        assert "[dim]" not in output


class TestMessageStatsOrderAndHints:
    """Tests for ascending severity order and key hints in stats bar."""

    def test_ascending_order(self, severity_levels):
        """Test severities render in ascending order (low→high)."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3, "critical_warning": 1, "warning": 5, "info": 1}
        output = stats.render()
        # Info (level 0) should appear before Warning (level 1) before Error (level 3)
        info_pos = output.index("Info")
        warning_pos = output.index("Warning")
        error_pos = output.index("Error")
        assert info_pos < warning_pos < error_pos

    def test_key_hints_present(self, severity_levels):
        """Test key number hints are present in rendered output."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 4
        stats.counts = {"error": 1, "critical_warning": 1, "warning": 1, "info": 1}
        output = stats.render()
        assert "\\[1] Info" in output
        assert "\\[2] Warning" in output
        assert "\\[3] Critical Warning" in output
        assert "\\[4] Error" in output

    def test_key_hints_with_custom_scheme(self):
        """Test key hints work with a non-Vivado severity scheme."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=3, style="red bold"),
            SeverityLevel(id="major", name="Major", level=2, style="red"),
            SeverityLevel(id="minor", name="Minor", level=1, style="yellow"),
            SeverityLevel(id="note", name="Note", level=0, style="dim"),
        ]
        stats = MessageStats(severity_levels=custom_levels)
        stats.total = 4
        stats.counts = {"fatal": 1, "major": 1, "minor": 1, "note": 1}
        output = stats.render()
        assert "\\[1] Note" in output
        assert "\\[2] Minor" in output
        assert "\\[3] Major" in output
        assert "\\[4] Fatal" in output
        # Verify ascending order
        note_pos = output.index("Note")
        minor_pos = output.index("Minor")
        major_pos = output.index("Major")
        fatal_pos = output.index("Fatal")
        assert note_pos < minor_pos < major_pos < fatal_pos


class TestRunTui:
    """Tests for the run_tui function."""

    def test_run_tui_import(self):
        """Test run_tui can be imported."""
        from sawmill.tui import run_tui

        assert callable(run_tui)

    def test_sawmill_app_import(self):
        """Test SawmillApp can be imported from tui package."""
        from sawmill.tui import SawmillApp

        assert SawmillApp is not None


class TestVivadoFixtureRendering:
    """Integration test: real Vivado log renders without markup errors."""

    async def test_vivado_fixture_renders_without_markup_error(self, vivado_log):
        """Loading the real Vivado fixture must not raise MarkupError.

        Vivado messages contain file paths like [/home/.../file.xdc] which
        Rich can misinterpret as markup tags if not escaped.
        """
        from sawmill.core.plugin import get_plugin_manager
        from sawmill.core.runner import run_single_log

        result = run_single_log(vivado_log, "vivado", get_plugin_manager())
        app = SawmillApp([result], single_log=True)
        async with app.run_test(size=(200, 50)) as pilot:
            # Allow multiple render cycles so DataTable processes all rows
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            table = app.query_one(LogViewer)
            assert table.row_count > 0
            # Scroll through rows to force rendering of all cells
            for _ in range(min(table.row_count, 50)):
                await pilot.press("down")
            await pilot.pause()


def _two_targets(severity_levels):
    return [
        make_target_result({"a.log": [make_message("a", "error", line=1)]}, severity_levels),
        make_target_result(
            {"b.log": [make_message("b", "info", line=1)]}, severity_levels, name="u"
        ),
    ]


class TestTargetTabs:
    """Header tabs, log column and panel titles."""

    async def test_header_shows_overview_and_target_tabs(self, severity_levels):
        app = SawmillApp(_two_targets(severity_levels))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.query("#tab-overview")
            first = app.query_one("#tab-target-0")
            second = app.query_one("#tab-target-1")
            assert "active-tab" in first.classes
            assert "active-tab" not in second.classes
            assert "m:t" in str(first.render())
            assert "m:u" in str(second.render())

    async def test_single_log_has_no_overview_tab(self, severity_levels):
        result = make_target_result({"a.log": [make_message("a", "error")]}, severity_levels)
        app = SawmillApp([result], single_log=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert not app.query("#tab-overview")
            assert app.query_one("#tab-target-0")

    async def test_detail_subtitle_shows_log_path(self, severity_levels):
        long_path = "very/long/directory/name/with/many/levels/build.log"
        result = make_target_result(
            {long_path: [make_message("a", "error", line=1)]}, severity_levels
        )
        app = SawmillApp([result])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            panel = app.query_one("#detail-panel")
            assert panel.border_title == "Message Detail"
            assert panel.border_subtitle == long_path
            await pilot.press("right")
            await _settle(pilot)
            assert app._active == app.OVERVIEW
            assert panel.border_subtitle == ""

    async def test_panel_title_is_qualified_name(self, severity_levels):
        app = SawmillApp(_two_targets(severity_levels))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app.query_one("#messages-panel").border_title == "m:t"

    async def test_q_quits_without_modal(self, severity_levels):
        app = SawmillApp(_two_targets(severity_levels))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            depth = len(app.screen_stack)
            await pilot.press("q")
            await pilot.pause()
            assert len(app.screen_stack) <= depth
        assert app.return_code == 0

    async def test_no_suppress_or_save_bindings(self, severity_levels):
        keys = {b.key for b in SawmillApp.BINDINGS}
        assert not keys & {"s", "ctrl+s"}

    def test_run_tui_signature(self):
        from sawmill.tui import run_tui

        params = list(inspect.signature(run_tui).parameters)
        assert params == ["targets", "single_log"]


def _two_level_scheme() -> list[SeverityLevel]:
    return [
        SeverityLevel(id="bad", name="Bad", level=1, style="red"),
        SeverityLevel(id="ok", name="Ok", level=0, style="green"),
    ]


async def _settle(pilot, n: int = 3) -> None:
    for _ in range(n):
        await pilot.pause()


class TestLogFilter:
    """The log: search prefix."""

    def test_log_filter_matches_log_path_with_wildcards(self, severity_levels):
        result = make_target_result(
            {
                "build/a.log": [make_message("a", "error", line=1)],
                "build/b1.log": [make_message("b", "error", line=2)],
            },
            severity_levels,
        )
        app = SawmillApp([result])
        app.filter_pattern = "log:build/b*"
        app._apply_filters()
        assert [m.content for m in app.filtered_messages] == ["b"]

    def test_log_filter_none_log_path_only_matches_star(self, severity_levels):
        result = make_target_result({"a.log": [make_message("a", "error")]}, severity_levels)
        app = SawmillApp([result])
        result.logs[0].unwaived[0].log_path = None
        app.filter_pattern = "log:a*"
        app._apply_filters()
        assert app.filtered_messages == []
        app.filter_pattern = "log:*"
        app._apply_filters()
        assert [m.content for m in app.filtered_messages] == ["a"]


class TestTabSwitching:
    """Left/right tab switching and per-target state."""

    async def test_right_left_cycle_overview_and_targets(self, severity_levels):
        app = SawmillApp(_two_targets(severity_levels))
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            assert app._active == 0
            await pilot.press("right")
            await _settle(pilot)
            assert app._active == 1
            assert "active-tab" in app.query_one("#tab-target-1").classes
            assert "active-tab" not in app.query_one("#tab-target-0").classes
            await pilot.press("right")
            await _settle(pilot)
            assert app._active == -1
            assert "active-tab" in app.query_one("#tab-overview").classes
            assert "active-tab" not in app.query_one("#tab-target-1").classes
            assert app.query_one(LogViewer).row_count == 0
            assert app.query_one("#messages-panel").border_title == "Overview"
            assert app.query_one(MessageStats).total == 0
            await pilot.press("right")
            await _settle(pilot)
            assert app._active == 0
            await pilot.press("left")
            await _settle(pilot)
            assert app._active == -1

    async def test_single_log_left_right_noop(self, severity_levels):
        result = make_target_result({"a.log": [make_message("a", "error")]}, severity_levels)
        app = SawmillApp([result], single_log=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("left")
            await _settle(pilot)
            assert app._active == 0
            await pilot.press("right")
            await _settle(pilot)
            assert app._active == 0

    async def test_switching_tabs_preserves_per_target_filter_sort_and_cursor(
        self, severity_levels
    ):
        msgs = [make_message(f"m{i} needle", "error", f"E-{i}", line=i) for i in range(1, 6)]
        msgs.append(make_message("other", "error", "E-9", line=9))
        targets = [
            make_target_result({"a.log": msgs}, severity_levels),
            make_target_result(
                {"b.log": [make_message("b", "info", line=1)]}, severity_levels, name="u"
            ),
        ]
        app = SawmillApp(targets)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            app.query_one(FilterInput).value = "needle"
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            await pilot.press("o")
            await _settle(pilot)
            await pilot.press("down", "down")
            await _settle(pilot)
            assert app._cursor_index == 2
            assert app.sort_mode == SORT_SEVERITY

            calls = 0
            original = app._apply_filters

            def counting() -> None:
                nonlocal calls
                calls += 1
                original()

            app._apply_filters = counting  # type: ignore[method-assign]
            await pilot.press("right")
            await _settle(pilot)
            assert calls <= 1
            assert app._active == 1
            assert app.filter_pattern == ""
            assert app.query_one(FilterInput).value == ""
            assert app.sort_mode == SORT_LINE
            assert app._cursor_index == 0

            calls = 0
            await pilot.press("left")
            await _settle(pilot)
            assert calls <= 1
            assert app._active == 0
            assert app.query_one(FilterInput).value == "needle"
            assert app.filter_pattern == "needle"
            assert app.sort_mode == SORT_SEVERITY
            assert app._cursor_index == 2
            assert len(app.filtered_messages) == 5
            assert all("needle" in m.content for m in app.filtered_messages)

    async def test_switching_tabs_rebuilds_severity_bar_and_key_map(self, severity_levels):
        two = _two_level_scheme()
        targets = [
            make_target_result({"a.log": [make_message("a", "error")]}, severity_levels),
            make_target_result(
                {"b.log": [make_message("b", "bad"), make_message("c", "ok", line=2)]},
                two,
                name="u",
            ),
        ]
        app = SawmillApp(targets)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            await pilot.press("right")
            await _settle(pilot)
            assert app._key_to_severity == {1: "ok", 2: "bad"}
            assert app.query_one(MessageStats)._severity_levels == two
            await pilot.press("1")
            await _settle(pilot)
            assert app.severity_filter == {"bad": True, "ok": False}
            assert [m.content for m in app.filtered_messages] == ["b"]

    async def test_header_right_shows_active_fail_on(self, severity_levels):
        targets = [
            make_target_result({"a.log": []}, severity_levels, fail_on="error"),
            make_target_result({"b.log": []}, severity_levels, name="u", fail_on="warning"),
        ]
        app = SawmillApp(targets)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            right = app.query_one("#header-right")
            assert "fail_on: error" in str(right.render())
            await pilot.press("right")
            await _settle(pilot)
            assert "fail_on: warning" in str(right.render())

    async def test_v_toggle_shows_waived_and_hidden_with_status_column(self, severity_levels):
        app = make_app(
            [
                make_message("e", "error", "E-1", line=1),
                make_message("w", "warning", "W-1", line=2),
                make_message("i", "info", "I-1", line=3),
            ],
            severity_levels,
            rules=[Rule(id="W-1", comment="fine")],
        )
        app._active_state().hidden_ids = {"I-1"}

        def statuses() -> dict[str, str]:
            table = app.query_one(LogViewer)
            out = {}
            for r in range(table.row_count):
                key = table.coordinate_to_cell_key((r, 0)).row_key
                out[str(table.get_cell(key, "msg_id"))] = str(table.get_cell(key, "status"))
            return out

        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            assert statuses() == {"E-1": ""}
            app.query_one(LogViewer).focus()
            await pilot.press("v")
            await _settle(pilot)
            assert statuses() == {"E-1": "", "W-1": "W", "I-1": "H"}
            assert "all" in app.query_one("#messages-panel").border_subtitle
            await pilot.press("v")
            await _settle(pilot)
            assert statuses() == {"E-1": ""}
            assert "all" not in app.query_one("#messages-panel").border_subtitle

    async def test_show_all_is_per_target(self, severity_levels):
        app = SawmillApp(_two_targets(severity_levels), single_log=False)
        async with app.run_test(size=(120, 40)) as pilot:
            await _settle(pilot)
            app.query_one(LogViewer).focus()
            await pilot.press("v")
            await _settle(pilot)
            assert app._states[0].show_all
            await pilot.press("right")
            await _settle(pilot)
            assert not app._active_state().show_all
            await pilot.press("left")
            await _settle(pilot)
            assert app._active_state().show_all

    def test_status_column_first_in_fixed_columns(self):
        assert LogViewer.FIXED_COLUMNS[0] == ("status", "St", 4)
        assert [k for k, _, _ in LogViewer.FIXED_COLUMNS] == [
            "status",
            "line",
            "severity",
            "msg_id",
        ]

    async def test_footer_and_help_mention_tab_and_v(self, severity_levels):
        from sawmill.tui.widgets.footer import SawmillFooter
        from sawmill.tui.widgets.help_modal import HELP_TEXT

        assert "Switch tab" in HELP_TEXT
        assert "Show/hide waived & hidden" in HELP_TEXT
        app = SawmillApp(_two_targets(severity_levels))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            keys = [k for k, _ in app.query_one(SawmillFooter)._footer_bindings]
            assert "v" in keys
            assert "←→" in keys
