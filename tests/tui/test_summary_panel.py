"""Tests for the summary panel widget."""

import pytest

from sawmill.models.message import Message
from sawmill.tui.widgets.summary_panel import (
    SummaryPanel,
    SeveritySelected,
    IdSelected,
    SummaryTree,
)


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


class TestSeveritySelected:
    """Tests for SeveritySelected message."""

    def test_init(self):
        """Test message initialization."""
        msg = SeveritySelected(severity="error")
        assert msg.severity == "error"


class TestIdSelected:
    """Tests for IdSelected message."""

    def test_init(self):
        """Test message initialization."""
        msg = IdSelected(message_id="E-001")
        assert msg.message_id == "E-001"


class TestSummaryTree:
    """Tests for SummaryTree widget."""

    def test_init(self):
        """Test widget initialization."""
        tree = SummaryTree()
        assert tree.show_root is False


class TestSummaryPanel:
    """Tests for SummaryPanel widget."""

    def test_init_empty(self):
        """Test initialization without messages."""
        panel = SummaryPanel()
        assert panel.messages == []
        assert panel.total_count == 0

    def test_init_with_messages(self):
        """Test initialization with messages."""
        messages = [
            make_message("Error 1", severity="error", message_id="E-001"),
            make_message("Warning 1", severity="warning", message_id="W-001"),
        ]
        panel = SummaryPanel(messages=messages)
        assert len(panel.messages) == 2

    def test_set_messages(self):
        """Test setting messages property."""
        panel = SummaryPanel()
        messages = [
            make_message("Error 1", severity="error"),
        ]
        panel.messages = messages
        assert len(panel.messages) == 1

    def test_get_severity_counts(self):
        """Test getting severity counts."""
        messages = [
            make_message("Error 1", severity="error"),
            make_message("Error 2", severity="error"),
            make_message("Warning 1", severity="warning"),
        ]
        panel = SummaryPanel(messages=messages)
        counts = panel.get_severity_counts()

        assert counts["error"] == 2
        assert counts["warning"] == 1

    def test_get_id_counts_all(self):
        """Test getting ID counts for all severities."""
        messages = [
            make_message("Error 1", severity="error", message_id="E-001"),
            make_message("Error 2", severity="error", message_id="E-001"),
            make_message("Warning 1", severity="warning", message_id="W-001"),
        ]
        panel = SummaryPanel(messages=messages)
        counts = panel.get_id_counts()

        assert counts["E-001"] == 2
        assert counts["W-001"] == 1

    def test_get_id_counts_filtered_by_severity(self):
        """Test getting ID counts filtered by severity."""
        messages = [
            make_message("Error 1", severity="error", message_id="E-001"),
            make_message("Error 2", severity="error", message_id="E-002"),
            make_message("Warning 1", severity="warning", message_id="W-001"),
        ]
        panel = SummaryPanel(messages=messages)
        counts = panel.get_id_counts(severity="error")

        assert counts["E-001"] == 1
        assert counts["E-002"] == 1
        assert "W-001" not in counts

    def test_get_id_counts_nonexistent_severity(self):
        """Test getting ID counts for nonexistent severity."""
        messages = [
            make_message("Error 1", severity="error", message_id="E-001"),
        ]
        panel = SummaryPanel(messages=messages)
        counts = panel.get_id_counts(severity="critical")

        assert counts == {}


class TestSummaryPanelImports:
    """Tests for widget imports."""

    def test_import_from_widgets_package(self):
        """Test widgets can be imported from the widgets package."""
        from sawmill.tui.widgets import SummaryPanel, SeveritySelected, IdSelected

        assert SummaryPanel is not None
        assert SeveritySelected is not None
        assert IdSelected is not None
