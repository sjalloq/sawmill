"""Tests for WaiverMatcher functionality."""

from sawmill.core.waiver import WaiverMatcher
from sawmill.models.message import Message
from sawmill.models.waiver import Waiver


class TestWaiverMatcherInit:
    """Tests for WaiverMatcher initialization."""

    def test_empty_waivers(self):
        """WaiverMatcher can be initialized with empty list."""
        matcher = WaiverMatcher([])
        assert matcher.waivers == []

    def test_waivers_property(self):
        """WaiverMatcher exposes waivers property."""
        waiver = Waiver(message_id="Test 1-1", reason="test", author="test", date="2026-01-18")
        matcher = WaiverMatcher([waiver])
        assert len(matcher.waivers) == 1
        assert matcher.waivers[0] == waiver

    def test_waivers_indexed_by_message_id(self):
        """WaiverMatcher indexes waivers by message_id internally."""
        waivers = [
            Waiver(message_id="id1", reason="r", author="a", date="d"),
            Waiver(message_id="id2", reason="r", author="a", date="d"),
            Waiver(
                message_id="id1",
                content_match="raw",
                content_pattern="specific",
                reason="r",
                author="a",
                date="d",
            ),
        ]
        matcher = WaiverMatcher(waivers)
        assert len(matcher._by_message_id["id1"]) == 2
        assert len(matcher._by_message_id["id2"]) == 1


class TestMessageIdMatching:
    """Tests for message_id waiver matching."""

    def test_message_id_match(self):
        """Waiver matches when message_id equals exactly."""
        waiver = Waiver(
            message_id="Vivado 12-3523", reason="test", author="test", date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Vivado 12-3523] some message",
            content="some message",
            message_id="Vivado 12-3523",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_no_match_different_id(self):
        """Waiver does not match when message_id differs."""
        waiver = Waiver(
            message_id="Vivado 12-9999", reason="test", author="test", date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Vivado 12-3523] different",
            content="different",
            message_id="Vivado 12-3523",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_no_match_missing_message_id(self):
        """Waiver does not match when message has no message_id."""
        waiver = Waiver(message_id="Test 1-1", reason="test", author="test", date="2026-01-18")
        message = Message(
            start_line=1, end_line=1, raw_text="Some message without ID", content="Some message"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_id_match_partial_no_match(self):
        """Waiver requires exact message_id match, not partial."""
        waiver = Waiver(message_id="Vivado 12", reason="test", author="test", date="2026-01-18")
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Vivado 12-3523] msg",
            content="msg",
            message_id="Vivado 12-3523",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None


class TestContentPatternMatching:
    """Tests for content_pattern matching."""

    def test_raw_content_match(self):
        """Raw content_match uses substring matching on raw_text."""
        waiver = Waiver(
            message_id="Test 1-1",
            content_match="raw",
            content_pattern="usb_fifo_clk",
            reason="async clock",
            author="test",
            date="2026-01-18",
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] set_input_delay usb_fifo_clk",
            content="set_input_delay usb_fifo_clk",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_raw_content_no_match(self):
        """Raw content_match does not match when substring is absent."""
        waiver = Waiver(
            message_id="Test 1-1",
            content_match="raw",
            content_pattern="different_clock",
            reason="test",
            author="test",
            date="2026-01-18",
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] set_input_delay usb_fifo_clk",
            content="set_input_delay usb_fifo_clk",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_regex_content_match(self):
        """Regex content_match uses regex search on raw_text."""
        waiver = Waiver(
            message_id="Test 1-1",
            content_match="regex",
            content_pattern=r"timing.*slack:\s*-\d+\.\d+",
            reason="timing slack",
            author="test",
            date="2026-01-18",
        )
        message = Message(
            start_line=1,
            end_line=2,
            raw_text="ERROR: [Test 1-1] timing violation\n  slack: -0.5ns",
            content="timing violation",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_regex_content_no_match(self):
        """Regex content_match does not match when regex doesn't match."""
        waiver = Waiver(
            message_id="Test 1-1",
            content_match="regex",
            content_pattern=r"different_pattern",
            reason="test",
            author="test",
            date="2026-01-18",
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] some content",
            content="some content",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_no_content_pattern_matches_all(self):
        """Waiver without content_pattern matches all instances of message_id."""
        waiver = Waiver(message_id="Test 1-1", reason="match all", author="test", date="2026-01-18")
        msg1 = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] first instance",
            content="first instance",
            message_id="Test 1-1",
        )
        msg2 = Message(
            start_line=2,
            end_line=2,
            raw_text="WARNING: [Test 1-1] different instance",
            content="different instance",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        assert matcher.is_waived(msg1) == waiver
        assert matcher.is_waived(msg2) == waiver

    def test_content_pattern_multiline_match(self):
        """Content pattern can match across multiple lines in raw_text."""
        waiver = Waiver(
            message_id="Test 1-1",
            content_match="regex",
            content_pattern=r"violation.*suggestion",
            reason="test",
            author="test",
            date="2026-01-18",
        )
        message = Message(
            start_line=1,
            end_line=4,
            raw_text=(
                "Error: [Test 1-1] timing violation\n  slack: -0.5ns\n"
                "  path: clk -> reg\n  suggestion: fix it"
            ),
            content="timing violation",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver


class TestMatchPriority:
    """Tests for waiver match priority (specific > catch-all)."""

    def test_specific_waiver_preferred_over_catchall(self):
        """Waiver with content_pattern is preferred over catch-all."""
        catchall = Waiver(
            message_id="Test 1-1", reason="catch-all", author="test", date="2026-01-18"
        )
        specific = Waiver(
            message_id="Test 1-1",
            content_match="raw",
            content_pattern="specific text",
            reason="specific match",
            author="test",
            date="2026-01-18",
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] some specific text here",
            content="some specific text here",
            message_id="Test 1-1",
        )

        # Order shouldn't matter — specific should win
        matcher = WaiverMatcher([catchall, specific])
        result = matcher.is_waived(message)

        assert result == specific
        assert result.reason == "specific match"

    def test_catchall_used_when_specific_does_not_match(self):
        """Catch-all waiver is used when specific waiver doesn't match content."""
        catchall = Waiver(
            message_id="Test 1-1", reason="catch-all", author="test", date="2026-01-18"
        )
        specific = Waiver(
            message_id="Test 1-1",
            content_match="raw",
            content_pattern="will not match",
            reason="specific match",
            author="test",
            date="2026-01-18",
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] different content entirely",
            content="different content entirely",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([catchall, specific])
        result = matcher.is_waived(message)

        assert result == catchall
        assert result.reason == "catch-all"


class TestNoMatch:
    """Tests for when no waivers match."""

    def test_no_match_returns_none(self):
        """is_waived returns None when no waivers match."""
        waiver = Waiver(
            message_id="Different 9-9999", reason="test", author="test", date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] message",
            content="message",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_empty_waivers_returns_none(self):
        """is_waived returns None when waiver list is empty."""
        message = Message(
            start_line=1, end_line=1, raw_text="ERROR: [Test 1-1] message", content="message"
        )

        matcher = WaiverMatcher([])
        result = matcher.is_waived(message)

        assert result is None


class TestMultipleWaivers:
    """Tests for matching with multiple waivers."""

    def test_first_matching_specific_waiver_returned(self):
        """When multiple specific waivers match, first one wins."""
        waiver1 = Waiver(
            message_id="Test 1-1",
            content_match="raw",
            content_pattern="ERROR",
            reason="first pattern",
            author="test",
            date="2026-01-18",
        )
        waiver2 = Waiver(
            message_id="Test 1-1",
            content_match="raw",
            content_pattern="message",
            reason="second pattern",
            author="test",
            date="2026-01-18",
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] some message",
            content="some message",
            message_id="Test 1-1",
        )

        matcher = WaiverMatcher([waiver1, waiver2])
        result = matcher.is_waived(message)

        assert result == waiver1
        assert result.reason == "first pattern"

    def test_multiple_messages_different_matches(self):
        """Different messages can match different waivers."""
        id_waiver = Waiver(
            message_id="Test 1-1", reason="id waiver", author="test", date="2026-01-18"
        )
        other_waiver = Waiver(
            message_id="Test 2-2",
            content_match="raw",
            content_pattern="timing",
            reason="timing waiver",
            author="test",
            date="2026-01-18",
        )

        message1 = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            message_id="Test 1-1",
        )
        message2 = Message(
            start_line=2,
            end_line=2,
            raw_text="WARNING: [Test 2-2] timing violation",
            content="timing violation",
            message_id="Test 2-2",
        )
        message3 = Message(
            start_line=3,
            end_line=3,
            raw_text="INFO: everything is fine",
            content="everything is fine",
        )

        matcher = WaiverMatcher([id_waiver, other_waiver])

        assert matcher.is_waived(message1) == id_waiver
        assert matcher.is_waived(message2) == other_waiver
        assert matcher.is_waived(message3) is None
