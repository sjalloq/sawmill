"""Tests for the grouped message list widget."""

import pytest

from sawmill.models.message import Message, FileRef
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.widgets.message_list import (
    GroupedMessageList,
    MessageSelected,
    GroupSelected,
    MessageTree,
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
    category: str | None = None,
    file_path: str | None = None,
    line: int = 1,
) -> Message:
    """Create a test message."""
    file_ref = FileRef(path=file_path, line=line) if file_path else None
    return Message(
        start_line=line,
        end_line=line,
        raw_text=content,
        content=content,
        severity=severity,
        message_id=message_id,
        category=category,
        file_ref=file_ref,
    )


class TestMessageSelected:
    """Tests for MessageSelected message."""

    def test_init(self):
        """Test message initialization."""
        log_msg = make_message("Test error", severity="error")
        msg = MessageSelected(message=log_msg)
        assert msg.message is log_msg


class TestGroupSelected:
    """Tests for GroupSelected message."""

    def test_init(self):
        """Test message initialization."""
        msg = GroupSelected(group_key="error", group_by="severity")
        assert msg.group_key == "error"
        assert msg.group_by == "severity"


class TestMessageTree:
    """Tests for MessageTree widget."""

    def test_init(self):
        """Test widget initialization."""
        tree = MessageTree()
        assert tree.show_root is False


class TestGroupedMessageList:
    """Tests for GroupedMessageList widget."""

    def test_init_empty(self, severity_levels):
        """Test initialization without messages."""
        widget = GroupedMessageList(severity_levels)
        assert widget.messages == []
        assert widget.group_by == "severity"
        assert widget.max_per_group == 5

    def test_init_with_messages(self, severity_levels):
        """Test initialization with messages."""
        messages = [
            make_message("Error 1", severity="error"),
            make_message("Warning 1", severity="warning"),
        ]
        widget = GroupedMessageList(severity_levels, messages=messages)
        assert len(widget.messages) == 2

    def test_init_with_group_by(self, severity_levels):
        """Test initialization with group_by parameter."""
        widget = GroupedMessageList(severity_levels, group_by="id")
        assert widget.group_by == "id"

    def test_init_with_max_per_group(self, severity_levels):
        """Test initialization with max_per_group parameter."""
        widget = GroupedMessageList(severity_levels, max_per_group=10)
        assert widget.max_per_group == 10

    def test_set_messages(self, severity_levels):
        """Test setting messages property."""
        widget = GroupedMessageList(severity_levels)
        messages = [make_message("Test", severity="error")]
        widget.messages = messages
        assert len(widget.messages) == 1

    def test_set_grouping(self, severity_levels):
        """Test setting grouping mode."""
        widget = GroupedMessageList(severity_levels)
        widget.set_grouping("file")
        assert widget.group_by == "file"

    def test_set_max_per_group(self, severity_levels):
        """Test setting max per group."""
        widget = GroupedMessageList(severity_levels)
        widget.set_max_per_group(20)
        assert widget.max_per_group == 20

    def test_format_message_label_with_file_ref(self, severity_levels):
        """Test message label formatting with file reference."""
        widget = GroupedMessageList(severity_levels)
        msg = make_message(
            "Error in module",
            severity="error",
            file_path="/src/test.v",
            line=42,
        )
        label = widget._format_message_label(msg)
        assert "/src/test.v:42" in label
        assert "Error in module" in label

    def test_format_message_label_without_file_ref(self, severity_levels):
        """Test message label formatting without file reference."""
        widget = GroupedMessageList(severity_levels)
        msg = make_message("Error in module", severity="error", line=10)
        label = widget._format_message_label(msg)
        assert "L10" in label

    def test_format_message_label_truncates_long_content(self, severity_levels):
        """Test message label truncates long content."""
        widget = GroupedMessageList(severity_levels)
        long_content = "x" * 100
        msg = make_message(long_content, severity="error")
        label = widget._format_message_label(msg)
        assert "..." in label
        assert len(label) < 100

    def test_format_group_label_severity(self, severity_levels):
        """Test group label formatting for severity."""
        widget = GroupedMessageList(severity_levels, group_by="severity")
        # Create a mock stats object
        class MockStats:
            count = 5
            severity = None
        label = widget._format_group_label("error", MockStats())
        assert "Error" in label
        assert "(5)" in label

    def test_format_group_label_id(self, severity_levels):
        """Test group label formatting for ID."""
        widget = GroupedMessageList(severity_levels, group_by="id")
        class MockStats:
            count = 3
            severity = "warning"
        label = widget._format_group_label("E-001", MockStats())
        assert "E-001" in label
        assert "(3)" in label
        assert "Warning" in label


class TestGroupedMessageListImports:
    """Tests for widget imports."""

    def test_import_from_widgets_package(self):
        """Test widgets can be imported from the widgets package."""
        from sawmill.tui.widgets import GroupedMessageList, MessageSelected, GroupSelected

        assert GroupedMessageList is not None
        assert MessageSelected is not None
        assert GroupSelected is not None
