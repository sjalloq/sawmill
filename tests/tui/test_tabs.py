"""Tests for tabbed message panels.

Tests the three-tab system (Messages, Waived, Suppressed) including
message bucketing, tab switching, context-sensitive keys, tab labels,
and removal of legacy features.
"""

from unittest.mock import MagicMock

import pytest

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.app import SawmillApp


@pytest.fixture
def severity_levels():
    """Standard Vivado-like severity levels for tests."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style=""),
    ]


def make_message(
    content: str,
    severity: str = "info",
    message_id: str | None = None,
    line: int = 1,
) -> Message:
    return Message(
        start_line=line,
        end_line=line,
        raw_text=content,
        content=content,
        severity=severity,
        message_id=message_id,
    )


class TestActiveTabState:
    """Tests for active_tab reactive property."""

    def test_initial_active_tab_is_messages(self, severity_levels):
        app = SawmillApp(severity_levels)
        assert app.active_tab == "messages"

    def test_active_tab_values(self, severity_levels):
        """active_tab can be set to all three valid values."""
        app = SawmillApp(severity_levels)
        for tab in ("messages", "waived", "suppressed"):
            app.active_tab = tab
            assert app.active_tab == tab

    def test_active_tab_reactive_triggers_watcher(self, severity_levels):
        """Changing active_tab calls watch_active_tab."""
        app = SawmillApp(
            severity_levels,
            messages=[make_message("test", severity="error", message_id="E-001")],
        )
        app._apply_filters()
        app._populate_table = lambda: None

        # Suppress E-001 so it moves to suppressed tab
        app.suppressed_ids = {"E-001"}
        app._apply_filters()
        assert len(app._main_messages) == 0
        assert len(app._suppressed_messages) == 1

        # Switch tab — filtered_messages should change
        app.active_tab = "suppressed"
        app._filtered_messages = app._active_message_list()
        assert len(app._filtered_messages) == 1


class TestMessageBucketing:
    """Tests for the three-way message bucketing in _apply_filters."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
            make_message("Info C", severity="info", message_id="I-001", line=3),
            make_message("No ID msg", severity="info", line=4),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_main_excludes_waived_and_suppressed(self, app):
        app.suppressed_ids = {"E-001"}
        app.waived_ids = {"W-001"}
        app._apply_filters()
        main_ids = {m.message_id for m in app._main_messages}
        assert "E-001" not in main_ids
        assert "W-001" not in main_ids
        assert "I-001" in main_ids

    def test_waived_tab_contains_waived_only(self, app):
        app.waived_ids = {"W-001"}
        app._apply_filters()
        assert len(app._waived_messages) == 1
        assert app._waived_messages[0].message_id == "W-001"

    def test_suppressed_tab_contains_suppressed_only(self, app):
        app.suppressed_ids = {"E-001"}
        app._apply_filters()
        assert len(app._suppressed_messages) == 1
        assert app._suppressed_messages[0].message_id == "E-001"

    def test_suppressed_takes_precedence_over_waived(self, app):
        """If a message is both suppressed and waived, it goes to Suppressed only."""
        app.suppressed_ids = {"E-001"}
        app.waived_ids = {"E-001"}
        app._apply_filters()
        assert len(app._suppressed_messages) == 1
        assert app._suppressed_messages[0].message_id == "E-001"
        assert all(m.message_id != "E-001" for m in app._waived_messages)

    def test_empty_suppressed_ids_no_suppressed_messages(self, app):
        app._apply_filters()
        assert len(app._suppressed_messages) == 0

    def test_empty_waived_ids_no_waived_messages(self, app):
        app._apply_filters()
        assert len(app._waived_messages) == 0

    def test_all_three_lists_sum_to_filtered_total(self, app):
        """Main + waived + suppressed should equal the total after filtering."""
        app.suppressed_ids = {"E-001"}
        app.waived_ids = {"W-001"}
        app._apply_filters()
        total = len(app._main_messages) + len(app._waived_messages) + len(app._suppressed_messages)
        # Should equal all 4 messages (all pass severity/regex filters)
        assert total == 4

    def test_severity_filter_applies_to_all_tabs(self, app):
        """Severity filtering applies before bucketing — affects all tabs."""
        app.suppressed_ids = {"E-001"}
        app.waived_ids = {"W-001"}
        # Only show errors
        app.severity_filter = {
            "error": True,
            "warning": False,
            "info": False,
            "critical_warning": False,
        }
        app._apply_filters()
        # E-001 is error but suppressed → suppressed tab
        assert len(app._suppressed_messages) == 1
        # W-001 is warning, filtered out by severity → not in waived
        assert len(app._waived_messages) == 0
        # I-001 and no-id are info, filtered out
        assert len(app._main_messages) == 0

    def test_regex_filter_applies_to_all_tabs(self, app):
        app.suppressed_ids = {"E-001"}
        app.filter_pattern = "Error"
        app._apply_filters()
        # Only E-001 matches "Error" and it's suppressed
        assert len(app._suppressed_messages) == 1
        assert len(app._main_messages) == 0

    def test_id_filter_applies_to_all_tabs(self, app):
        app.waived_ids = {"W-001"}
        app.filter_pattern = "id:W-*"
        app._apply_filters()
        # Only W-001 matches id:W-* and it's waived
        assert len(app._waived_messages) == 1
        assert len(app._main_messages) == 0


class TestTabSwitching:
    """Tests for switching between tabs."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
            make_message("Info C", severity="info", message_id="I-001", line=3),
        ]
        app = SawmillApp(severity_levels, messages=messages)
        app.suppressed_ids = {"E-001"}
        app.waived_ids = {"W-001"}
        app._apply_filters()
        return app

    def test_switch_to_waived_shows_waived_messages(self, app):
        app.active_tab = "waived"
        msgs = app._active_message_list()
        assert len(msgs) == 1
        assert msgs[0].message_id == "W-001"

    def test_switch_to_suppressed_shows_suppressed_messages(self, app):
        app.active_tab = "suppressed"
        msgs = app._active_message_list()
        assert len(msgs) == 1
        assert msgs[0].message_id == "E-001"

    def test_switch_back_to_messages_restores_main(self, app):
        app.active_tab = "waived"
        app.active_tab = "messages"
        msgs = app._active_message_list()
        assert len(msgs) == 1
        assert msgs[0].message_id == "I-001"

    def test_tab_switch_updates_filtered_messages(self, app):
        """Switching tab via reactive updates _filtered_messages."""
        assert len(app._filtered_messages) == 1  # messages tab: only I-001
        app._populate_table = lambda: None
        app.active_tab = "suppressed"
        assert len(app._filtered_messages) == 1
        assert app._filtered_messages[0].message_id == "E-001"


class TestTabNavigation:
    """Tests for left/right tab cycling."""

    @pytest.fixture
    def app(self, severity_levels):
        return SawmillApp(severity_levels)

    def test_next_tab_from_messages(self, app):
        app._populate_table = lambda: None
        assert app.active_tab == "messages"
        app.action_next_tab()
        assert app.active_tab == "waived"

    def test_next_tab_from_suppressed_wraps_to_messages(self, app):
        app._populate_table = lambda: None
        app.active_tab = "suppressed"
        app.action_next_tab()
        assert app.active_tab == "messages"

    def test_prev_tab_from_messages_wraps_to_suppressed(self, app):
        app._populate_table = lambda: None
        app.action_prev_tab()
        assert app.active_tab == "suppressed"

    def test_prev_tab_cycles_correctly(self, app):
        """Full backward cycle: messages → suppressed → waived → messages."""
        app._populate_table = lambda: None
        app.action_prev_tab()
        assert app.active_tab == "suppressed"
        app.action_prev_tab()
        assert app.active_tab == "waived"
        app.action_prev_tab()
        assert app.active_tab == "messages"

    def test_next_tab_cycles_correctly(self, app):
        """Full forward cycle: messages → waived → suppressed → messages."""
        app._populate_table = lambda: None
        app.action_next_tab()
        assert app.active_tab == "waived"
        app.action_next_tab()
        assert app.active_tab == "suppressed"
        app.action_next_tab()
        assert app.active_tab == "messages"

    def test_tab_nav_noop_when_filter_has_focus(self, app):
        """Left/right do nothing when the filter input has focus."""
        app._filter_input = type("FakeInput", (), {"has_focus": True})()
        app._populate_table = lambda: None
        app.action_next_tab()
        assert app.active_tab == "messages"
        app.action_prev_tab()
        assert app.active_tab == "messages"


class TestContextSensitiveKeys:
    """Tests for context-sensitive suppress/waive per tab."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_suppress_on_messages_tab_adds_to_suppressed(self, app):
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None
        app.notify = MagicMock()
        app.action_suppress()
        assert "E-001" in app.suppressed_ids

    def test_suppress_on_suppressed_tab_unsuppresses(self, app):
        app.suppressed_ids = {"E-001"}
        app.active_tab = "suppressed"
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None
        app.notify = MagicMock()
        app.action_suppress()
        assert "E-001" not in app.suppressed_ids

    def test_waive_on_waived_tab_unwaives(self, app):
        app.waived_ids = {"E-001"}
        app.active_tab = "waived"
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None
        app.notify = MagicMock()
        app.action_waive()
        assert "E-001" not in app.waived_ids

    def test_waive_on_suppressed_tab_noop_with_notify(self, app):
        app.suppressed_ids = {"E-001"}
        app.active_tab = "suppressed"
        app._apply_filters()
        app.notify = MagicMock()
        app.action_waive()
        app.notify.assert_called_once()
        assert "Un-suppress first" in app.notify.call_args[0][0]

    def test_suppress_on_waived_tab_moves_to_suppressed(self, app):
        app.waived_ids = {"E-001"}
        app.active_tab = "waived"
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None
        app.notify = MagicMock()
        app.action_suppress()
        assert "E-001" in app.suppressed_ids
        # Re-apply filters to verify bucketing
        app._apply_filters()
        assert len(app._suppressed_messages) == 1
        assert app._suppressed_messages[0].message_id == "E-001"


class TestRemovals:
    """Tests verifying legacy features have been removed."""

    def test_no_show_suppressed_reactive(self, severity_levels):
        """show_suppressed reactive property should not exist."""
        app = SawmillApp(severity_levels)
        assert not hasattr(app, "show_suppressed")

    def test_no_toggle_suppressed_binding(self, severity_levels):
        """No 'v' binding for toggle_suppressed."""
        app = SawmillApp(severity_levels)
        binding_keys = {b.key: b.action for b in app.BINDINGS}
        assert "v" not in binding_keys

    def test_no_waived_tag_in_severity_column(self, severity_levels):
        """Waived messages on the main tab don't get [waived] tag (they're on their own tab)."""
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
        ]
        app = SawmillApp(severity_levels, messages=messages)
        app.waived_ids = {"E-001"}
        app._apply_filters()
        # E-001 should not be in main messages at all
        assert len(app._main_messages) == 0
        # It should be in waived
        assert len(app._waived_messages) == 1
