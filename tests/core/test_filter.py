"""Tests for FilterEngine.

Tests cover single filter matching, AND/OR modes, suppressions,
suppress-by-ID, severity toggle filtering, and edge cases.
"""

from sawmill.core.filter import FilterEngine, filter_by_severity_toggles
from sawmill.models.filter_def import FilterDefinition
from sawmill.models.message import Message


class TestApplyFilter:
    """Tests for single filter matching."""

    def test_single_filter_match(self):
        """Single filter should match against raw_text."""
        messages = [
            Message(
                start_line=1, end_line=1, raw_text="Error: test", content="test", severity="error"
            ),
            Message(
                start_line=2, end_line=2, raw_text="Info: test", content="test", severity="info"
            ),
            Message(
                start_line=3,
                end_line=3,
                raw_text="Error: another",
                content="another",
                severity="error",
            ),
        ]
        engine = FilterEngine()
        results = engine.apply_filter(r"^Error:", messages)

        assert len(results) == 2
        assert all("Error:" in m.raw_text for m in results)

    def test_filter_case_insensitive(self):
        """Case-insensitive filter should match both cases."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="ERROR: test", content="test"),
            Message(start_line=2, end_line=2, raw_text="error: test", content="test"),
        ]
        engine = FilterEngine()
        results = engine.apply_filter(r"error:", messages, case_sensitive=False)

        assert len(results) == 2

    def test_filter_case_sensitive_default(self):
        """Default case-sensitive filter should only match exact case."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="ERROR: test", content="test"),
            Message(start_line=2, end_line=2, raw_text="error: test", content="test"),
        ]
        engine = FilterEngine()
        results = engine.apply_filter(r"ERROR:", messages)

        assert len(results) == 1
        assert results[0].raw_text == "ERROR: test"

    def test_filter_no_matches(self):
        """Filter with no matches should return empty list."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Info: test", content="test"),
        ]
        engine = FilterEngine()
        results = engine.apply_filter(r"Error:", messages)

        assert len(results) == 0

    def test_filter_empty_messages(self):
        """Filter on empty message list should return empty list."""
        engine = FilterEngine()
        results = engine.apply_filter(r"Error:", [])

        assert len(results) == 0

    def test_filter_invalid_regex_returns_empty(self):
        """Invalid regex pattern should return empty results."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test"),
        ]
        engine = FilterEngine()
        # Unclosed bracket is invalid regex
        results = engine.apply_filter(r"[invalid(regex", messages)

        assert len(results) == 0

    def test_filter_matches_multiline_raw_text(self):
        """Filter should match against full raw_text including newlines."""
        messages = [
            Message(
                start_line=1,
                end_line=3,
                raw_text="Error: timing violation\n  slack: -0.5ns\n  path: clk -> reg",
                content="timing violation",
            ),
        ]
        engine = FilterEngine()
        results = engine.apply_filter(r"slack.*-0\.5", messages)

        assert len(results) == 1


class TestApplyFiltersAndMode:
    """Tests for multi-filter AND mode."""

    def test_multiple_filters_and_mode(self):
        """AND mode should require all enabled filters to match."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="Error: timing slack -0.5",
                content="timing slack -0.5",
                severity="error",
            ),
            Message(
                start_line=2,
                end_line=2,
                raw_text="Error: DRC violation",
                content="DRC violation",
                severity="error",
            ),
            Message(
                start_line=3,
                end_line=3,
                raw_text="Warning: timing slack -0.2",
                content="timing slack -0.2",
                severity="warning",
            ),
        ]
        filters = [
            FilterDefinition(id="1", name="Errors", pattern=r"^Error:"),
            FilterDefinition(id="2", name="Timing", pattern=r"timing"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="AND")

        assert len(results) == 1  # Only first matches both
        assert results[0].raw_text == "Error: timing slack -0.5"

    def test_inactive_filters_ignored_in_and_mode(self):
        """Filters not in active_ids should not affect AND mode results."""
        messages = [Message(start_line=1, end_line=1, raw_text="Error: test", content="test")]
        filters = [
            FilterDefinition(id="1", name="Inactive", pattern=r"Error"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="AND", active_ids=set())

        # No active filters - all messages returned
        assert len(results) == 1

    def test_no_active_filters_returns_all(self):
        """No active filters should return all messages."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test"),
            Message(start_line=2, end_line=2, raw_text="Info: test", content="test"),
        ]
        filters = [
            FilterDefinition(id="1", name="Filter1", pattern=r"Error"),
            FilterDefinition(id="2", name="Filter2", pattern=r"Info"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="AND", active_ids=set())

        assert len(results) == 2

    def test_and_mode_with_complex_pattern(self):
        """Complex regex patterns should work in AND mode."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="ERROR: [Vivado 12-3523] timing slack -0.5ns",
                content="test",
            ),
            Message(
                start_line=2, end_line=2, raw_text="ERROR: [DRC 1-1] simple error", content="test"
            ),
        ]
        filters = [
            FilterDefinition(id="1", name="Vivado ID", pattern=r"\[Vivado \d+-\d+\]"),
            FilterDefinition(id="2", name="Timing", pattern=r"timing"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="AND")

        # Only first message has both Vivado ID and "timing"
        assert len(results) == 1
        assert "Vivado 12-3523" in results[0].raw_text

    def test_and_mode_all_filters_match(self):
        """Message matching all enabled filters should be included."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="ERROR: timing critical",
                content="timing critical",
            ),
        ]
        filters = [
            FilterDefinition(id="1", name="Errors", pattern=r"ERROR"),
            FilterDefinition(id="2", name="Timing", pattern=r"timing"),
            FilterDefinition(id="3", name="Critical", pattern=r"critical"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="AND")

        assert len(results) == 1


class TestApplyFiltersOrMode:
    """Tests for multi-filter OR mode."""

    def test_multiple_filters_or_mode(self):
        """OR mode should match messages that match any enabled filter."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: timing", content="timing"),
            Message(start_line=2, end_line=2, raw_text="Error: DRC", content="DRC"),
            Message(start_line=3, end_line=3, raw_text="Info: done", content="done"),
        ]
        filters = [
            FilterDefinition(id="1", name="Timing", pattern=r"timing"),
            FilterDefinition(id="2", name="DRC", pattern=r"DRC"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="OR")

        assert len(results) == 2  # First two match
        assert results[0].raw_text == "Error: timing"
        assert results[1].raw_text == "Error: DRC"

    def test_or_mode_matches_any(self):
        """OR mode should include message if any filter matches."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Warning: test only", content="test"),
        ]
        filters = [
            FilterDefinition(id="1", name="Error", pattern=r"^Error"),
            FilterDefinition(id="2", name="Warning", pattern=r"^Warning"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="OR")

        assert len(results) == 1

    def test_or_mode_no_match(self):
        """OR mode with no matches should return empty list."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Info: test", content="test"),
        ]
        filters = [
            FilterDefinition(id="1", name="Error", pattern=r"^Error"),
            FilterDefinition(id="2", name="Warning", pattern=r"^Warning"),
        ]

        engine = FilterEngine()
        results = engine.apply_filters(filters, messages, mode="OR")

        assert len(results) == 0


class TestApplySuppressions:
    """Tests for suppression patterns."""

    def test_suppressions_remove_matches(self):
        """Suppression patterns should remove matching messages."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="Error: important",
                content="important",
                severity="error",
            ),
            Message(
                start_line=2,
                end_line=2,
                raw_text="Info: noisy startup",
                content="noisy startup",
                severity="info",
            ),
            Message(
                start_line=3,
                end_line=3,
                raw_text="Warning: also important",
                content="also important",
                severity="warning",
            ),
        ]

        engine = FilterEngine()
        results = engine.apply_suppressions([r"noisy"], messages)

        assert len(results) == 2
        assert all("noisy" not in m.raw_text for m in results)

    def test_multiple_suppressions(self):
        """Multiple suppression patterns should all be applied."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: important", content="important"),
            Message(start_line=2, end_line=2, raw_text="Info: noise1", content="noise1"),
            Message(start_line=3, end_line=3, raw_text="Info: noise2", content="noise2"),
            Message(start_line=4, end_line=4, raw_text="Warning: keep this", content="keep this"),
        ]

        engine = FilterEngine()
        results = engine.apply_suppressions([r"noise1", r"noise2"], messages)

        assert len(results) == 2
        assert "important" in results[0].raw_text
        assert "keep this" in results[1].raw_text

    def test_empty_suppressions_returns_all(self):
        """Empty suppression list should return all messages."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test"),
            Message(start_line=2, end_line=2, raw_text="Info: test", content="test"),
        ]

        engine = FilterEngine()
        results = engine.apply_suppressions([], messages)

        assert len(results) == 2

    def test_invalid_suppression_pattern_ignored(self):
        """Invalid suppression patterns should be skipped."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: test", content="test"),
        ]

        engine = FilterEngine()
        # All invalid patterns - should return all messages
        results = engine.apply_suppressions([r"[invalid"], messages)

        assert len(results) == 1

    def test_suppressions_with_regex(self):
        """Suppression patterns should support full regex."""
        messages = [
            Message(
                start_line=1,
                end_line=1,
                raw_text="INFO: [Common 17-55] startup noise",
                content="startup noise",
            ),
            Message(
                start_line=2,
                end_line=2,
                raw_text="ERROR: [DRC 1-1] real error",
                content="real error",
            ),
        ]

        engine = FilterEngine()
        results = engine.apply_suppressions([r"Common 17-\d+"], messages)

        assert len(results) == 1
        assert "DRC" in results[0].raw_text


class TestApplySuppressIds:
    """Tests for suppress-by-ID partitioning."""

    def test_partitions_by_message_id(self):
        """Messages with matching IDs go to suppressed list."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="E: a", content="a", message_id="ID-1"),
            Message(start_line=2, end_line=2, raw_text="E: b", content="b", message_id="ID-2"),
            Message(start_line=3, end_line=3, raw_text="E: c", content="c", message_id="ID-3"),
        ]
        engine = FilterEngine()
        kept, suppressed = engine.apply_suppress_ids({"ID-2"}, messages)

        assert len(kept) == 2
        assert len(suppressed) == 1
        assert suppressed[0].message_id == "ID-2"

    def test_empty_suppress_ids_keeps_all(self):
        """Empty suppress set returns all messages as kept."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="E: a", content="a", message_id="ID-1"),
        ]
        engine = FilterEngine()
        kept, suppressed = engine.apply_suppress_ids(set(), messages)

        assert len(kept) == 1
        assert len(suppressed) == 0

    def test_none_message_id_always_kept(self):
        """Messages with no message_id are always kept."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="E: a", content="a", message_id=None),
            Message(start_line=2, end_line=2, raw_text="E: b", content="b", message_id="ID-1"),
        ]
        engine = FilterEngine()
        kept, suppressed = engine.apply_suppress_ids({"ID-1"}, messages)

        assert len(kept) == 1
        assert kept[0].message_id is None
        assert len(suppressed) == 1

    def test_preserves_order(self):
        """Kept and suppressed lists preserve original order."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="1", content="1", message_id="A"),
            Message(start_line=2, end_line=2, raw_text="2", content="2", message_id="B"),
            Message(start_line=3, end_line=3, raw_text="3", content="3", message_id="A"),
        ]
        engine = FilterEngine()
        kept, suppressed = engine.apply_suppress_ids({"A"}, messages)

        assert [m.start_line for m in kept] == [2]
        assert [m.start_line for m in suppressed] == [1, 3]


class TestFilterBySeverityToggles:
    """Tests for severity toggle filtering."""

    def test_filters_by_toggle(self):
        """Messages with disabled severity are excluded."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="E", content="", severity="error"),
            Message(start_line=2, end_line=2, raw_text="W", content="", severity="warning"),
            Message(start_line=3, end_line=3, raw_text="I", content="", severity="info"),
        ]
        result = filter_by_severity_toggles(
            messages, {"error": True, "warning": False, "info": True}
        )

        assert len(result) == 2
        assert result[0].severity == "error"
        assert result[1].severity == "info"

    def test_none_severity_always_included(self):
        """Messages with None severity are always kept."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="N", content="", severity=None),
            Message(start_line=2, end_line=2, raw_text="E", content="", severity="error"),
        ]
        result = filter_by_severity_toggles(messages, {"error": False})

        assert len(result) == 1
        assert result[0].severity is None

    def test_unknown_id_defaults_to_true(self):
        """Severity IDs not in toggles default to visible."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="X", content="", severity="unknown"),
        ]
        result = filter_by_severity_toggles(messages, {"error": True})

        assert len(result) == 1

    def test_empty_toggles_returns_all(self):
        """Empty toggles dict returns all messages."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="E", content="", severity="error"),
        ]
        result = filter_by_severity_toggles(messages, {})

        assert len(result) == 1

    def test_case_insensitive_matching(self):
        """Severity matching should be case-insensitive."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="E", content="", severity="ERROR"),
        ]
        result = filter_by_severity_toggles(messages, {"error": False})

        assert len(result) == 0


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_message_list(self):
        """All methods should handle empty message lists."""
        engine = FilterEngine()

        assert engine.apply_filter(r"test", []) == []
        assert engine.apply_filters([], [], mode="AND") == []
        assert engine.apply_suppressions([r"test"], []) == []

    def test_empty_filters_list(self):
        """Empty filter list should return all messages."""
        messages = [Message(start_line=1, end_line=1, raw_text="test", content="test")]
        engine = FilterEngine()

        results = engine.apply_filters([], messages, mode="AND")
        assert len(results) == 1

        results = engine.apply_filters([], messages, mode="OR")
        assert len(results) == 1

    def test_filter_preserves_order(self):
        """Filtered results should preserve original message order."""
        messages = [
            Message(start_line=1, end_line=1, raw_text="Error: first", content="first"),
            Message(start_line=2, end_line=2, raw_text="Info: middle", content="middle"),
            Message(start_line=3, end_line=3, raw_text="Error: last", content="last"),
        ]
        engine = FilterEngine()
        results = engine.apply_filter(r"Error:", messages)

        assert len(results) == 2
        assert results[0].start_line == 1
        assert results[1].start_line == 3
