"""Tests for the aggregation module."""

import pytest

from sawmill.core.aggregation import (
    Aggregator,
    MessageStats,
    SeverityStats,
    make_severity_sort_key,
)
from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.message import FileRef, Message


# Module-level fixture for standard severity levels
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


class TestMessageStats:
    """Tests for MessageStats dataclass."""

    def test_init_defaults(self):
        """Test default initialization."""
        stats = MessageStats(key="test")
        assert stats.key == "test"
        assert stats.severity is None
        assert stats.count == 0
        assert stats.messages == []
        assert stats.files_affected == set()

    def test_init_with_values(self):
        """Test initialization with values."""
        stats = MessageStats(key="WARN-123", severity="warning", count=5)
        assert stats.key == "WARN-123"
        assert stats.severity == "warning"
        assert stats.count == 5

    def test_add_message(self):
        """Test adding a message updates count."""
        stats = MessageStats(key="test")
        msg = make_message("Test message")
        stats.add_message(msg)
        assert stats.count == 1
        assert len(stats.messages) == 1
        assert stats.messages[0] is msg

    def test_add_message_tracks_files(self):
        """Test that add_message tracks affected files."""
        stats = MessageStats(key="test")
        msg1 = make_message("Error in file1", file_path="/src/file1.v")
        msg2 = make_message("Error in file2", file_path="/src/file2.v")
        msg3 = make_message("Another in file1", file_path="/src/file1.v")
        stats.add_message(msg1)
        stats.add_message(msg2)
        stats.add_message(msg3)
        assert stats.count == 3
        assert stats.files_affected == {"/src/file1.v", "/src/file2.v"}

    def test_add_message_no_file_ref(self):
        """Test adding message without file reference."""
        stats = MessageStats(key="test")
        msg = make_message("No file reference")
        stats.add_message(msg)
        assert stats.count == 1
        assert stats.files_affected == set()


class TestSeverityStats:
    """Tests for SeverityStats dataclass."""

    def test_init(self):
        """Test initialization."""
        stats = SeverityStats(severity="error")
        assert stats.severity == "error"
        assert stats.total == 0
        assert stats.by_id == {}

    def test_init_with_values(self):
        """Test initialization with values."""
        stats = SeverityStats(
            severity="warning",
            total=10,
            by_id={"WARN-1": 5, "WARN-2": 5},
        )
        assert stats.severity == "warning"
        assert stats.total == 10
        assert stats.by_id == {"WARN-1": 5, "WARN-2": 5}


class TestMakeSeveritySortKey:
    """Tests for make_severity_sort_key function."""

    def test_requires_severity_levels(self):
        """Test that severity_levels is required."""
        with pytest.raises(ValueError, match="severity_levels is required"):
            make_severity_sort_key([])

    def test_known_severities_order(self, severity_levels):
        """Test that known severities are ordered correctly."""
        sort_key = make_severity_sort_key(severity_levels)
        # error < critical_warning < warning < info (lower sort key = higher severity)
        assert sort_key("error") < sort_key("critical_warning")
        assert sort_key("critical_warning") < sort_key("warning")
        assert sort_key("warning") < sort_key("info")

    def test_case_insensitive(self, severity_levels):
        """Test that sorting is case insensitive."""
        sort_key = make_severity_sort_key(severity_levels)
        assert sort_key("ERROR") == sort_key("error")
        assert sort_key("Warning") == sort_key("warning")

    def test_none_sorts_last(self, severity_levels):
        """Test that None sorts after all known severities."""
        sort_key = make_severity_sort_key(severity_levels)
        assert sort_key(None) > sort_key("info")

    def test_unknown_severity(self, severity_levels):
        """Test that unknown severities sort before None."""
        sort_key = make_severity_sort_key(severity_levels)
        unknown_key = sort_key("unknown")
        assert unknown_key < sort_key(None)
        assert unknown_key > sort_key("info")


class TestAggregatorInit:
    """Tests for Aggregator initialization."""

    def test_requires_severity_levels(self):
        """Test that severity_levels is required."""
        with pytest.raises(ValueError, match="severity_levels is required"):
            Aggregator(severity_levels=[])

    def test_accepts_severity_levels(self, severity_levels):
        """Test that Aggregator accepts valid severity_levels."""
        aggregator = Aggregator(severity_levels=severity_levels)
        assert aggregator.severity_levels == severity_levels


class TestAggregatorGetSummary:
    """Tests for Aggregator.get_summary()."""

    def test_empty_messages(self, severity_levels):
        """Test summary with no messages."""
        aggregator = Aggregator(severity_levels=severity_levels)
        summary = aggregator.get_summary([])
        assert summary == {}

    def test_single_message(self, severity_levels):
        """Test summary with one message."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [make_message("Error", severity="error", message_id="E-001")]
        summary = aggregator.get_summary(messages)
        assert "error" in summary
        assert summary["error"].total == 1
        assert summary["error"].by_id == {"E-001": 1}

    def test_multiple_severities(self, severity_levels):
        """Test summary groups by severity."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Error 1", severity="error", message_id="E-001"),
            make_message("Warning 1", severity="warning", message_id="W-001"),
            make_message("Error 2", severity="error", message_id="E-001"),
        ]
        summary = aggregator.get_summary(messages)
        assert summary["error"].total == 2
        assert summary["warning"].total == 1
        assert summary["error"].by_id == {"E-001": 2}

    def test_multiple_ids_same_severity(self, severity_levels):
        """Test summary counts multiple IDs within severity."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Error 1", severity="error", message_id="E-001"),
            make_message("Error 2", severity="error", message_id="E-002"),
            make_message("Error 3", severity="error", message_id="E-001"),
        ]
        summary = aggregator.get_summary(messages)
        assert summary["error"].total == 3
        assert summary["error"].by_id == {"E-001": 2, "E-002": 1}

    def test_no_id_messages(self, severity_levels):
        """Test summary handles messages without IDs."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Error without ID", severity="error"),
        ]
        summary = aggregator.get_summary(messages)
        assert summary["error"].by_id == {"(no id)": 1}

    def test_no_severity_messages(self, severity_levels):
        """Test summary handles messages without severity."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Message without severity"),
        ]
        summary = aggregator.get_summary(messages)
        assert "other" in summary
        assert summary["other"].total == 1


class TestAggregatorGroupBySeverity:
    """Tests for Aggregator.group_by_severity()."""

    def test_empty_messages(self, severity_levels):
        """Test grouping empty list."""
        aggregator = Aggregator(severity_levels=severity_levels)
        groups = aggregator.group_by_severity([])
        assert groups == {}

    def test_groups_by_severity(self, severity_levels):
        """Test messages are grouped by severity."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Error 1", severity="error"),
            make_message("Warning 1", severity="warning"),
            make_message("Error 2", severity="error"),
        ]
        groups = aggregator.group_by_severity(messages)
        assert "error" in groups
        assert "warning" in groups
        assert groups["error"].count == 2
        assert groups["warning"].count == 1

    def test_no_severity_grouped_as_other(self, severity_levels):
        """Test messages without severity go to 'other'."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [make_message("No severity")]
        groups = aggregator.group_by_severity(messages)
        assert "other" in groups
        assert groups["other"].count == 1


class TestAggregatorGroupById:
    """Tests for Aggregator.group_by_id()."""

    def test_groups_by_id(self, severity_levels):
        """Test messages are grouped by ID."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Msg 1", message_id="ID-001", severity="error"),
            make_message("Msg 2", message_id="ID-002", severity="warning"),
            make_message("Msg 3", message_id="ID-001", severity="error"),
        ]
        groups = aggregator.group_by_id(messages)
        assert "ID-001" in groups
        assert "ID-002" in groups
        assert groups["ID-001"].count == 2
        assert groups["ID-002"].count == 1

    def test_preserves_first_severity(self, severity_levels):
        """Test group uses severity from first message."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Msg 1", message_id="ID-001", severity="error"),
            make_message("Msg 2", message_id="ID-001", severity="warning"),
        ]
        groups = aggregator.group_by_id(messages)
        # First message was error, so group severity should be error
        assert groups["ID-001"].severity == "error"

    def test_no_id_grouped(self, severity_levels):
        """Test messages without ID are grouped together."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("No ID 1"),
            make_message("No ID 2"),
        ]
        groups = aggregator.group_by_id(messages)
        assert "(no id)" in groups
        assert groups["(no id)"].count == 2


class TestAggregatorGroupByFile:
    """Tests for Aggregator.group_by_file()."""

    def test_groups_by_file(self, severity_levels):
        """Test messages are grouped by file."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Msg 1", file_path="/src/a.v"),
            make_message("Msg 2", file_path="/src/b.v"),
            make_message("Msg 3", file_path="/src/a.v"),
        ]
        groups = aggregator.group_by_file(messages)
        assert "/src/a.v" in groups
        assert "/src/b.v" in groups
        assert groups["/src/a.v"].count == 2
        assert groups["/src/b.v"].count == 1

    def test_no_file_grouped(self, severity_levels):
        """Test messages without file refs are grouped together."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("No file 1"),
            make_message("No file 2"),
        ]
        groups = aggregator.group_by_file(messages)
        assert "(no file)" in groups
        assert groups["(no file)"].count == 2


class TestAggregatorGroupByCategory:
    """Tests for Aggregator.group_by_category()."""

    def test_groups_by_category(self, severity_levels):
        """Test messages are grouped by category."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Msg 1", category="timing"),
            make_message("Msg 2", category="drc"),
            make_message("Msg 3", category="timing"),
        ]
        groups = aggregator.group_by_category(messages)
        assert "timing" in groups
        assert "drc" in groups
        assert groups["timing"].count == 2
        assert groups["drc"].count == 1

    def test_category_case_insensitive(self, severity_levels):
        """Test categories are normalized to lowercase."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("Msg 1", category="Timing"),
            make_message("Msg 2", category="TIMING"),
        ]
        groups = aggregator.group_by_category(messages)
        assert "timing" in groups
        assert groups["timing"].count == 2

    def test_no_category_grouped(self, severity_levels):
        """Test messages without category are grouped together."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [
            make_message("No category 1"),
            make_message("No category 2"),
        ]
        groups = aggregator.group_by_category(messages)
        assert "(no category)" in groups
        assert groups["(no category)"].count == 2


class TestAggregatorGroupBy:
    """Tests for Aggregator.group_by() dispatcher."""

    def test_group_by_severity(self, severity_levels):
        """Test group_by dispatches to group_by_severity."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [make_message("Test", severity="error")]
        groups = aggregator.group_by(messages, "severity")
        assert "error" in groups

    def test_group_by_id(self, severity_levels):
        """Test group_by dispatches to group_by_id."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [make_message("Test", message_id="ID-001")]
        groups = aggregator.group_by(messages, "id")
        assert "ID-001" in groups

    def test_group_by_file(self, severity_levels):
        """Test group_by dispatches to group_by_file."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [make_message("Test", file_path="/src/test.v")]
        groups = aggregator.group_by(messages, "file")
        assert "/src/test.v" in groups

    def test_group_by_category(self, severity_levels):
        """Test group_by dispatches to group_by_category."""
        aggregator = Aggregator(severity_levels=severity_levels)
        messages = [make_message("Test", category="timing")]
        groups = aggregator.group_by(messages, "category")
        assert "timing" in groups

    def test_group_by_unknown_raises(self, severity_levels):
        """Test group_by raises for unknown field."""
        aggregator = Aggregator(severity_levels=severity_levels)
        with pytest.raises(ValueError, match="Unknown grouping field"):
            aggregator.group_by([], "unknown")


class TestAggregatorSortedGroups:
    """Tests for Aggregator.sorted_groups()."""

    def test_sort_by_count(self, severity_levels):
        """Test sorting by count descending."""
        aggregator = Aggregator(severity_levels=severity_levels)
        groups = {
            "a": MessageStats(key="a", count=5),
            "b": MessageStats(key="b", count=10),
            "c": MessageStats(key="c", count=3),
        }
        sorted_list = aggregator.sorted_groups(groups, by_count=True)
        keys = [k for k, v in sorted_list]
        assert keys == ["b", "a", "c"]

    def test_sort_by_key(self, severity_levels):
        """Test sorting by key alphabetically."""
        aggregator = Aggregator(severity_levels=severity_levels)
        groups = {
            "zebra": MessageStats(key="zebra", count=1),
            "apple": MessageStats(key="apple", count=100),
            "mango": MessageStats(key="mango", count=50),
        }
        sorted_list = aggregator.sorted_groups(groups, by_count=False)
        keys = [k for k, v in sorted_list]
        assert keys == ["apple", "mango", "zebra"]

    def test_sort_by_count_tiebreaker(self, severity_levels):
        """Test that ties in count are broken by key."""
        aggregator = Aggregator(severity_levels=severity_levels)
        groups = {
            "b": MessageStats(key="b", count=5),
            "a": MessageStats(key="a", count=5),
            "c": MessageStats(key="c", count=5),
        }
        sorted_list = aggregator.sorted_groups(groups, by_count=True)
        keys = [k for k, v in sorted_list]
        assert keys == ["a", "b", "c"]


class TestAggregatorSortedSummary:
    """Tests for Aggregator.sorted_summary()."""

    def test_sorts_by_severity_order(self, severity_levels):
        """Test summary is sorted by severity order."""
        aggregator = Aggregator(severity_levels=severity_levels)
        summary = {
            "info": SeverityStats(severity="info", total=1),
            "error": SeverityStats(severity="error", total=1),
            "warning": SeverityStats(severity="warning", total=1),
            "critical_warning": SeverityStats(severity="critical_warning", total=1),
        }
        sorted_list = aggregator.sorted_summary(summary)
        severities = [s for s, _ in sorted_list]
        assert severities == ["error", "critical_warning", "warning", "info"]

    def test_unknown_severity_sorts_near_end(self, severity_levels):
        """Test unknown severities sort after known ones."""
        aggregator = Aggregator(severity_levels=severity_levels)
        summary = {
            "info": SeverityStats(severity="info", total=1),
            "unknown": SeverityStats(severity="unknown", total=1),
        }
        sorted_list = aggregator.sorted_summary(summary)
        severities = [s for s, _ in sorted_list]
        assert severities == ["info", "unknown"]
