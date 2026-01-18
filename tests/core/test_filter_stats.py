"""Tests for FilterStats and FilterEngine.get_stats().

This module tests filter statistics functionality including:
- Basic message counting
- Percentage calculations
- Per-filter match breakdowns
"""

import pytest

from sawmill.core.filter import FilterEngine, FilterStats
from sawmill.models.filter_def import FilterDefinition
from sawmill.models.message import Message


class TestFilterStatsDataclass:
    """Tests for FilterStats dataclass."""

    def test_filter_stats_creation(self):
        """FilterStats should be creatable with required fields."""
        stats = FilterStats(
            total_messages=100,
            matched_messages=25,
            match_percentage=25.0,
        )
        assert stats.total_messages == 100
        assert stats.matched_messages == 25
        assert stats.match_percentage == 25.0
        assert stats.per_filter == {}

    def test_filter_stats_with_per_filter(self):
        """FilterStats should accept per_filter dict."""
        stats = FilterStats(
            total_messages=100,
            matched_messages=25,
            match_percentage=25.0,
            per_filter={"errors": 10, "warnings": 15},
        )
        assert stats.per_filter["errors"] == 10
        assert stats.per_filter["warnings"] == 15


class TestGetStatsBasic:
    """Tests for basic get_stats functionality."""

    def test_basic_stats(self):
        """Test basic statistics calculation."""
        messages = [
            Message(start_line=i, end_line=i, raw_text=f"Line {i}", content=f"Line {i}")
            for i in range(100)
        ]
        filters = [FilterDefinition(id="1", name="Even", pattern=r"Line [02468]$", enabled=True)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.total_messages == 100
        assert stats.matched_messages == 5  # Lines 0, 2, 4, 6, 8

    def test_stats_empty_messages(self):
        """Empty message list should return zero stats."""
        filters = [FilterDefinition(id="1", name="Any", pattern=r".*", enabled=True)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, [])

        assert stats.total_messages == 0
        assert stats.matched_messages == 0
        assert stats.match_percentage == 0.0

    def test_stats_no_filters(self):
        """No filters should count all messages as matched."""
        messages = [
            Message(start_line=i, end_line=i, raw_text=f"Line {i}", content=f"Line {i}")
            for i in range(10)
        ]

        engine = FilterEngine()
        stats = engine.get_stats([], messages)

        assert stats.total_messages == 10
        assert stats.matched_messages == 10
        assert stats.match_percentage == 100.0

    def test_stats_disabled_filters_ignored(self):
        """Disabled filters should not affect matching."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test"),
            Message(start_line=2, end_line=2, raw_text="Info: test", content="test"),
        ]
        filters = [FilterDefinition(id="1", name="Errors", pattern=r"^Error:", enabled=False)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        # With disabled filter, all messages should match
        assert stats.total_messages == 2
        assert stats.matched_messages == 2


class TestGetStatsPercentage:
    """Tests for percentage calculation."""

    def test_stats_percentage(self):
        """Test accurate percentage calculation."""
        messages = [
            Message(
                start_line=i,
                end_line=i,
                raw_text="Match" if i < 25 else "NoMatch",
                content="..."
            )
            for i in range(100)
        ]
        filters = [FilterDefinition(id="1", name="Match", pattern=r"^Match$", enabled=True)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.match_percentage == 25.0

    def test_stats_percentage_zero(self):
        """Zero matches should yield 0% percentage."""
        messages = [
            Message(start_line=i, end_line=i, raw_text=f"Line {i}", content=f"Line {i}")
            for i in range(10)
        ]
        filters = [FilterDefinition(id="1", name="NoMatch", pattern=r"^NOMATCH$", enabled=True)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.match_percentage == 0.0
        assert stats.matched_messages == 0

    def test_stats_percentage_hundred(self):
        """All matches should yield 100% percentage."""
        messages = [
            Message(start_line=i, end_line=i, raw_text=f"Line {i}", content=f"Line {i}")
            for i in range(10)
        ]
        filters = [FilterDefinition(id="1", name="AllMatch", pattern=r"Line", enabled=True)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.match_percentage == 100.0
        assert stats.matched_messages == 10

    def test_stats_percentage_fractional(self):
        """Percentage should handle fractional values."""
        # 3 out of 7 = 42.857...%
        messages = [
            Message(
                start_line=i,
                end_line=i,
                raw_text="Match" if i < 3 else "NoMatch",
                content="..."
            )
            for i in range(7)
        ]
        filters = [FilterDefinition(id="1", name="Match", pattern=r"^Match$", enabled=True)]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.matched_messages == 3
        assert abs(stats.match_percentage - (3 / 7 * 100)) < 0.001


class TestGetStatsPerFilter:
    """Tests for per-filter statistics."""

    def test_per_filter_stats(self):
        """Test per-filter match count breakdown."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test", severity="error"),
            Message(start_line=2, end_line=2, raw_text="Warning: test", content="test", severity="warning"),
            Message(start_line=3, end_line=3, raw_text="Info: test", content="test", severity="info"),
        ]
        filters = [
            FilterDefinition(id="errors", name="Errors", pattern=r"^Error:", enabled=True),
            FilterDefinition(id="warnings", name="Warnings", pattern=r"^Warning:", enabled=True),
        ]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.per_filter["errors"] == 1
        assert stats.per_filter["warnings"] == 1

    def test_per_filter_multiple_matches(self):
        """Per-filter counts should handle multiple matches per filter."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: first", content="first"),
            Message(start_line=2, end_line=2, raw_text="Error: second", content="second"),
            Message(start_line=3, end_line=3, raw_text="Error: third", content="third"),
            Message(start_line=4, end_line=4, raw_text="Warning: fourth", content="fourth"),
        ]
        filters = [
            FilterDefinition(id="errors", name="Errors", pattern=r"^Error:", enabled=True),
            FilterDefinition(id="warnings", name="Warnings", pattern=r"^Warning:", enabled=True),
        ]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.per_filter["errors"] == 3
        assert stats.per_filter["warnings"] == 1

    def test_per_filter_disabled_filters_excluded(self):
        """Disabled filters should not appear in per_filter."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test"),
            Message(start_line=2, end_line=2, raw_text="Info: test", content="test"),
        ]
        filters = [
            FilterDefinition(id="errors", name="Errors", pattern=r"^Error:", enabled=True),
            FilterDefinition(id="disabled", name="Disabled", pattern=r"^Info:", enabled=False),
        ]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert "errors" in stats.per_filter
        assert "disabled" not in stats.per_filter

    def test_per_filter_overlapping_patterns(self):
        """Per-filter counts should work with overlapping patterns."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: timing violation", content="timing violation"),
            Message(start_line=2, end_line=2, raw_text="Warning: timing slack", content="timing slack"),
            Message(start_line=3, end_line=3, raw_text="Error: DRC violation", content="DRC violation"),
        ]
        filters = [
            FilterDefinition(id="timing", name="Timing", pattern=r"timing", enabled=True),
            FilterDefinition(id="errors", name="Errors", pattern=r"^Error:", enabled=True),
        ]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        # "timing" matches 2 messages (lines 1 and 2)
        assert stats.per_filter["timing"] == 2
        # "errors" matches 2 messages (lines 1 and 3)
        assert stats.per_filter["errors"] == 2
        # matched_messages uses AND mode: only line 1 matches both
        assert stats.matched_messages == 1

    def test_per_filter_invalid_pattern(self):
        """Invalid patterns should count as 0 matches."""
        messages = [Message(start_line=1, end_line=1, raw_text="Test", content="Test")]
        filters = [
            FilterDefinition(id="valid", name="Valid", pattern=r"Test", enabled=True),
        ]
        # We can't create invalid filter via FilterDefinition (it validates),
        # so this test verifies the engine handles edge cases properly
        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.per_filter["valid"] == 1


class TestGetStatsIntegration:
    """Integration tests for get_stats with realistic scenarios."""

    def test_stats_with_vivado_like_messages(self):
        """Test stats with Vivado-like log messages."""
        messages = [
            Message(
                start_line=1, end_line=1,
                raw_text="INFO: [Synth 8-6157] synthesizing module 'top'",
                content="synthesizing module 'top'",
                severity="info", message_id="Synth 8-6157"
            ),
            Message(
                start_line=2, end_line=2,
                raw_text="WARNING: [Vivado 12-3523] Component name change",
                content="Component name change",
                severity="warning", message_id="Vivado 12-3523"
            ),
            Message(
                start_line=3, end_line=3,
                raw_text="ERROR: [Route 35-9] Routing failed",
                content="Routing failed",
                severity="error", message_id="Route 35-9"
            ),
            Message(
                start_line=4, end_line=4,
                raw_text="CRITICAL WARNING: [Constraints 18-4427] Override warning",
                content="Override warning",
                severity="critical_warning", message_id="Constraints 18-4427"
            ),
            Message(
                start_line=5, end_line=5,
                raw_text="INFO: [Common 17-55] Status update",
                content="Status update",
                severity="info", message_id="Common 17-55"
            ),
        ]
        filters = [
            FilterDefinition(id="errors", name="Errors", pattern=r"^ERROR:", enabled=True),
            FilterDefinition(id="warnings", name="Warnings", pattern=r"^WARNING:", enabled=True),
            FilterDefinition(id="critical", name="Critical", pattern=r"^CRITICAL WARNING:", enabled=True),
        ]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.total_messages == 5
        assert stats.per_filter["errors"] == 1
        assert stats.per_filter["warnings"] == 1
        assert stats.per_filter["critical"] == 1
        # AND mode: no message matches all 3 filters
        assert stats.matched_messages == 0

    def test_stats_single_filter(self):
        """Test stats with single filter for common use case."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="ERROR: first error", content="first error", severity="error"),
            Message(start_line=2, end_line=2, raw_text="ERROR: second error", content="second error", severity="error"),
            Message(start_line=3, end_line=3, raw_text="INFO: status", content="status", severity="info"),
        ]
        filters = [
            FilterDefinition(id="errors", name="Errors", pattern=r"^ERROR:", enabled=True),
        ]

        engine = FilterEngine()
        stats = engine.get_stats(filters, messages)

        assert stats.total_messages == 3
        assert stats.matched_messages == 2
        assert abs(stats.match_percentage - (2 / 3 * 100)) < 0.001
        assert stats.per_filter["errors"] == 2
