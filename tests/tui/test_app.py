"""Tests for the main TUI application."""

import pytest
from pathlib import Path

from sawmill.models.message import Message, FileRef
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.app import (
    SawmillApp, LogViewer, MessageStats, FilterInput,
    SORT_LINE, SORT_SEVERITY, SORT_ID, SORT_COUNT, SORT_MODES,
)


@pytest.fixture
def severity_levels():
    """Standard Vivado-like severity levels for tests."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


# Helper to create test messages
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


class TestSawmillAppInit:
    """Tests for SawmillApp initialization."""

    def test_init_no_args(self, severity_levels):
        """Test app can be initialized without arguments."""
        app = SawmillApp(severity_levels)
        assert app.log_file is None
        assert app.messages == []

    def test_init_with_messages(self, severity_levels):
        """Test app can be initialized with pre-loaded messages."""
        messages = [
            make_message("Error message", severity="error"),
            make_message("Warning message", severity="warning"),
        ]
        app = SawmillApp(severity_levels, messages=messages)
        assert len(app.messages) == 2

    def test_init_with_log_file(self, severity_levels, tmp_path):
        """Test app can be initialized with a log file path."""
        log_file = tmp_path / "test.log"
        log_file.write_text("INFO: test\n")
        app = SawmillApp(severity_levels, log_file=log_file)
        assert app.log_file == log_file


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
        return SawmillApp(severity_levels, messages=messages)

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
        return SawmillApp(severity_levels, messages=[
            make_message("Test error", severity="error"),
            make_message("Test warning", severity="warning"),
        ])

    def test_action_clear_filter(self, app):
        """Test action_clear_filter clears all filters."""
        app.filter_pattern = "test"
        app.severity_filter = {"error": True, "warning": False}
        app.action_clear_filter()
        assert app.filter_pattern == ""
        assert app.severity_filter == {}

    def test_on_filter_modal_result_apply(self, app):
        """Test modal result is applied correctly."""
        result = {
            "severity_filter": {"error": True, "warning": False, "info": False},
            "pattern": "test pattern",
        }
        app._on_filter_modal_result(result)
        assert app.severity_filter == {"error": True, "warning": False, "info": False}
        assert app.filter_pattern == "test pattern"

    def test_on_filter_modal_result_cancel(self, app):
        """Test modal cancel does nothing."""
        app.severity_filter = {"error": True}
        app.filter_pattern = "existing"
        app._on_filter_modal_result(None)
        assert app.severity_filter == {"error": True}
        assert app.filter_pattern == "existing"

    def test_severity_toggle_keybindings(self, app):
        """Test that number keys 1-4 exist for severity toggles."""
        binding_keys = [b.key for b in app.BINDINGS]
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "3" in binding_keys
        assert "4" in binding_keys

    def test_keybinding_f_exists(self, app):
        """Test that 'f' keybinding for filter modal exists."""
        binding_keys = [b.key for b in app.BINDINGS]
        assert "f" in binding_keys


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
        return SawmillApp(severity_levels, messages=messages)

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
        return SawmillApp(severity_levels, messages=messages)

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
        app._messages.append(
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
        return SawmillApp(severity_levels, messages=messages)

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
        stats.active = {"error": True, "warning": True, "info": False,
                        "critical_warning": True}
        output = stats.render()
        assert "[dim]Info: 2[/dim]" in output

    def test_render_all_active(self, severity_levels):
        """Test that all-active renders normally."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 5
        stats.counts = {"error": 2, "warning": 3}
        stats.active = {"error": True, "warning": True, "info": True,
                        "critical_warning": True}
        output = stats.render()
        assert "[dim]" not in output


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
