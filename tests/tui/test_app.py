"""Tests for the main TUI application."""

import pytest
from pathlib import Path

from sawmill.models.message import Message, FileRef
from sawmill.tui.app import SawmillApp, LogViewer, MessageStats, FilterInput


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

    def test_init_no_args(self):
        """Test app can be initialized without arguments."""
        app = SawmillApp()
        assert app.log_file is None
        assert app.messages == []

    def test_init_with_messages(self):
        """Test app can be initialized with pre-loaded messages."""
        messages = [
            make_message("Error message", severity="error"),
            make_message("Warning message", severity="warning"),
        ]
        app = SawmillApp(messages=messages)
        assert len(app.messages) == 2

    def test_init_with_log_file(self, tmp_path):
        """Test app can be initialized with a log file path."""
        log_file = tmp_path / "test.log"
        log_file.write_text("INFO: test\n")
        app = SawmillApp(log_file=log_file)
        assert app.log_file == log_file


class TestSawmillAppFiltering:
    """Tests for message filtering in the app."""

    @pytest.fixture
    def app_with_messages(self):
        """Create an app with test messages."""
        messages = [
            make_message("Error in module A", severity="error", message_id="E-001", line=1),
            make_message("Warning in module B", severity="warning", message_id="W-001", line=2),
            make_message("Info message", severity="info", message_id="I-001", line=3),
            make_message("Another error", severity="error", message_id="E-002", line=4),
        ]
        return SawmillApp(messages=messages)

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

    def test_min_severity_warning(self, app_with_messages):
        """Test severity filter for warnings and above."""
        app_with_messages.min_severity = "warning"
        app_with_messages._apply_filters()
        # Should include error, warning but not info
        assert len(app_with_messages.filtered_messages) == 3
        for msg in app_with_messages.filtered_messages:
            assert msg.severity.lower() in ("error", "warning")

    def test_min_severity_error(self, app_with_messages):
        """Test severity filter for errors only."""
        app_with_messages.min_severity = "error"
        app_with_messages._apply_filters()
        assert len(app_with_messages.filtered_messages) == 2
        for msg in app_with_messages.filtered_messages:
            assert msg.severity.lower() == "error"

    def test_combined_filters(self, app_with_messages):
        """Test combining severity and pattern filters."""
        app_with_messages.min_severity = "error"
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
        assert stats.errors == 0
        assert stats.warnings == 0
        assert stats.info == 0

    def test_render(self):
        """Test render method produces output."""
        stats = MessageStats()
        stats.total = 10
        stats.errors = 3
        stats.warnings = 5
        stats.info = 2
        output = stats.render()
        assert "Total: 10" in output
        assert "Errors: 3" in output
        assert "Warnings: 5" in output
        assert "Info: 2" in output


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
    def app(self):
        """Create a test app."""
        return SawmillApp(messages=[
            make_message("Test error", severity="error"),
            make_message("Test warning", severity="warning"),
        ])

    def test_action_filter_all(self, app):
        """Test action_filter_all clears severity filter."""
        app.min_severity = "error"
        app.action_filter_all()
        assert app.min_severity is None

    def test_action_filter_warning(self, app):
        """Test action_filter_warning sets severity to warning."""
        app.action_filter_warning()
        assert app.min_severity == "warning"

    def test_action_filter_error(self, app):
        """Test action_filter_error sets severity to error."""
        app.action_filter_error()
        assert app.min_severity == "error"

    def test_action_clear_filter(self, app):
        """Test action_clear_filter clears all filters."""
        app.filter_pattern = "test"
        app.min_severity = "error"
        app.action_clear_filter()
        assert app.filter_pattern == ""
        assert app.min_severity is None


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
