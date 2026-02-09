"""Tests for TUI suppress functionality."""

from unittest.mock import MagicMock

import pytest

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.app import MessageStats, SawmillApp


@pytest.fixture
def severity_levels():
    """Standard Vivado-like severity levels for tests."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


def make_message(
    content: str,
    severity: str | None = None,
    message_id: str | None = None,
    line: int = 1,
) -> Message:
    """Create a test message."""
    return Message(
        start_line=line,
        end_line=line,
        raw_text=content,
        content=content,
        severity=severity,
        message_id=message_id,
    )


class TestSuppressState:
    """Tests for suppress state management."""

    def test_initial_suppressed_ids_empty(self, severity_levels):
        """Suppressed IDs set starts empty."""
        app = SawmillApp(severity_levels)
        assert app.suppressed_ids == set()

    def test_initial_show_suppressed_false(self, severity_levels):
        """show_suppressed starts as False."""
        app = SawmillApp(severity_levels)
        assert app.show_suppressed is False

    def test_initial_suppressions_dirty_false(self, severity_levels):
        """Suppressions dirty flag starts as False."""
        app = SawmillApp(severity_levels)
        assert app._suppressions_dirty is False


class TestActionSuppress:
    """Tests for the suppress action."""

    @pytest.fixture
    def app(self, severity_levels):
        """Create an app with test messages."""
        messages = [
            make_message("Error in module A", severity="error", message_id="E-001", line=1),
            make_message("Warning in module B", severity="warning", message_id="W-001", line=2),
            make_message("Info message", severity="info", message_id="I-001", line=3),
            make_message("No ID message", severity="info", line=4),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_suppress_adds_id(self, app):
        """Pressing suppress adds message ID to suppressed set via action_suppress()."""
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        # Patch _populate_table to prevent cascading into real widget methods
        app._populate_table = lambda: None

        assert "E-001" not in app.suppressed_ids
        app.action_suppress()
        assert "E-001" in app.suppressed_ids

    def test_suppress_sets_dirty_flag(self, app):
        """Suppressing via action_suppress() marks state as dirty."""
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None

        assert app._suppressions_dirty is False
        app.action_suppress()
        assert app._suppressions_dirty is True

    def test_suppress_notification_contains_message_id(self, app):
        """action_suppress() notifies with the suppressed message ID."""
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None
        app.notify = MagicMock()

        app.action_suppress()

        app.notify.assert_called_once()
        notification_text = app.notify.call_args[0][0]
        assert "E-001" in notification_text

    def test_unsuppress_notification_contains_message_id(self, app):
        """action_suppress() on already-suppressed ID notifies with the un-suppressed ID."""
        app.suppressed_ids = {"E-001"}
        app.show_suppressed = True
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app._populate_table = lambda: None
        app.notify = MagicMock()

        app.action_suppress()

        app.notify.assert_called_once()
        notification_text = app.notify.call_args[0][0]
        assert "E-001" in notification_text
        assert "Un-suppressed" in notification_text

    def test_suppress_message_without_id(self, app):
        """Cannot suppress a message that has no message_id."""
        app._apply_filters()
        # Row 3 has no message_id
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 3})()
        app.action_suppress()
        assert len(app.suppressed_ids) == 0
        assert app._suppressions_dirty is False

    def test_suppress_hides_message(self, app):
        """Suppressed messages are hidden from filtered results."""
        app._apply_filters()
        assert len(app.filtered_messages) == 4
        app.suppressed_ids = {"E-001"}
        app._apply_filters()
        assert len(app.filtered_messages) == 3
        assert all(m.message_id != "E-001" for m in app.filtered_messages)

    def test_suppress_multiple_ids(self, app):
        """Can suppress multiple different message IDs."""
        app.suppressed_ids = {"E-001", "W-001"}
        app._apply_filters()
        assert len(app.filtered_messages) == 2
        remaining_ids = {m.message_id for m in app.filtered_messages}
        assert "E-001" not in remaining_ids
        assert "W-001" not in remaining_ids

    def test_unsuppress_removes_id(self, app):
        """Un-suppressing via action_suppress() removes the ID from the set."""
        app.suppressed_ids = {"E-001"}
        app.show_suppressed = True
        app._apply_filters()
        # Patch _populate_table to prevent cascading into real widget methods
        app._populate_table = lambda: None

        # E-001 should be visible (show_suppressed is True) and in suppressed set
        assert "E-001" in app.suppressed_ids
        assert app._filtered_messages[0].message_id == "E-001"

        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app.action_suppress()
        assert "E-001" not in app.suppressed_ids

    def test_unsuppress_sets_dirty_flag(self, app):
        """Un-suppressing a message sets _suppressions_dirty = True.

        Exercises the actual action_suppress() code path. We patch
        _populate_table to avoid needing a fully mounted Textual widget tree.
        """
        # Suppress E-001 and make it visible so we can un-suppress it
        app.suppressed_ids = {"E-001"}
        app.show_suppressed = True
        app._apply_filters()
        # Reset dirty flag to simulate a previously-saved state
        app._suppressions_dirty = False

        # Verify E-001 is visible in filtered messages
        assert app._filtered_messages[0].message_id == "E-001"

        # Provide a fake log viewer with the right cursor position
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()

        # Patch _populate_table to prevent cascading into real widget methods
        app._populate_table = lambda: None

        app.action_suppress()

        assert "E-001" not in app.suppressed_ids
        assert app._suppressions_dirty is True


class TestToggleSuppressed:
    """Tests for show_suppressed toggle."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error msg", severity="error", message_id="E-001", line=1),
            make_message("Warning msg", severity="warning", message_id="W-001", line=2),
            make_message("Info msg", severity="info", message_id="I-001", line=3),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_toggle_show_suppressed(self, app):
        """action_toggle_suppressed flips show_suppressed."""
        assert app.show_suppressed is False
        app.action_toggle_suppressed()
        assert app.show_suppressed is True
        app.action_toggle_suppressed()
        assert app.show_suppressed is False

    def test_show_suppressed_includes_suppressed(self, app):
        """When show_suppressed is True, suppressed messages are included."""
        app.suppressed_ids = {"E-001"}
        app.show_suppressed = False
        app._apply_filters()
        assert len(app.filtered_messages) == 2

        app.show_suppressed = True
        app._apply_filters()
        assert len(app.filtered_messages) == 3

    def test_suppressed_visible_with_no_suppressed_ids(self, app):
        """Toggling show_suppressed with no suppressions changes nothing."""
        app._apply_filters()
        count_before = len(app.filtered_messages)
        app.show_suppressed = True
        app._apply_filters()
        assert len(app.filtered_messages) == count_before


class TestSuppressedFiltering:
    """Tests for suppression filtering integration."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Error B", severity="error", message_id="E-001", line=2),
            make_message("Warning C", severity="warning", message_id="W-001", line=3),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_suppress_id_hides_all_instances(self, app):
        """Suppressing an ID hides all messages with that ID."""
        app.suppressed_ids = {"E-001"}
        app._apply_filters()
        # Both E-001 messages should be hidden
        assert len(app.filtered_messages) == 1
        assert app.filtered_messages[0].message_id == "W-001"

    def test_suppress_combines_with_severity_filter(self, app):
        """Suppression works together with severity filtering."""
        app.suppressed_ids = {"E-001"}
        app.severity_filter = {
            "error": True,
            "warning": False,
            "info": False,
            "critical_warning": False,
        }
        app._apply_filters()
        # E-001 suppressed + only errors visible = nothing
        assert len(app.filtered_messages) == 0

    def test_suppress_combines_with_pattern_filter(self, app):
        """Suppression works together with pattern filtering."""
        app.suppressed_ids = {"W-001"}
        app.filter_pattern = "Error"
        app._apply_filters()
        # W-001 suppressed + pattern "Error" = only the two E-001 messages
        assert len(app.filtered_messages) == 2


class TestMessageStatsSuppressed:
    """Tests for suppressed count in MessageStats widget."""

    def test_suppressed_count_default(self, severity_levels):
        """Suppressed count defaults to 0."""
        stats = MessageStats(severity_levels=severity_levels)
        assert stats.suppressed_count == 0

    def test_suppressed_count_in_render(self, severity_levels):
        """Suppressed count appears in render when > 0."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3, "warning": 5, "info": 2}
        stats.suppressed_count = 5
        output = stats.render()
        assert "5 suppressed" in output

    def test_suppressed_count_hidden_when_zero(self, severity_levels):
        """Suppressed count not shown when 0."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3}
        stats.suppressed_count = 0
        output = stats.render()
        assert "suppressed" not in output

    def test_suppressed_count_styled_dim(self, severity_levels):
        """Suppressed count is rendered with dim style."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.suppressed_count = 3
        output = stats.render()
        assert "[dim]3 suppressed[/dim]" in output


class TestKeybindingChanges:
    """Tests for keybinding changes (sort moved from s to o)."""

    def test_sort_binding_is_o(self, severity_levels):
        """Sort is now bound to 'o', not 's'."""
        app = SawmillApp(severity_levels)
        binding_keys = {b.key: b.action for b in app.BINDINGS}
        assert binding_keys.get("o") == "cycle_sort"

    def test_suppress_binding_is_s(self, severity_levels):
        """Suppress is bound to 's'."""
        app = SawmillApp(severity_levels)
        binding_keys = {b.key: b.action for b in app.BINDINGS}
        assert binding_keys.get("s") == "suppress"

    def test_toggle_suppressed_binding_is_v(self, severity_levels):
        """Toggle suppressed visibility is bound to 'v'."""
        app = SawmillApp(severity_levels)
        binding_keys = {b.key: b.action for b in app.BINDINGS}
        assert binding_keys.get("v") == "toggle_suppressed"
