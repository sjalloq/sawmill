"""Tests for WaiverMatcher functionality."""

import hashlib

import pytest

from sawmill.core.waiver import WaiverMatcher
from sawmill.models.message import FileRef, Message
from sawmill.models.waiver import Waiver


class TestWaiverMatcherInit:
    """Tests for WaiverMatcher initialization."""

    def test_empty_waivers(self):
        """WaiverMatcher can be initialized with empty list."""
        matcher = WaiverMatcher([])
        assert matcher.waivers == []

    def test_waivers_property(self):
        """WaiverMatcher exposes waivers property."""
        waiver = Waiver(
            type="id",
            pattern="Test 1-1",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        matcher = WaiverMatcher([waiver])
        assert len(matcher.waivers) == 1
        assert matcher.waivers[0] == waiver

    def test_waivers_organized_by_type(self):
        """WaiverMatcher organizes waivers by type internally."""
        waivers = [
            Waiver(type="id", pattern="id1", reason="r", author="a", date="d"),
            Waiver(type="pattern", pattern="pat", reason="r", author="a", date="d"),
            Waiver(type="file", pattern="f.v", reason="r", author="a", date="d"),
            Waiver(type="hash", pattern="abc", reason="r", author="a", date="d"),
        ]
        matcher = WaiverMatcher(waivers)
        assert len(matcher._hash_waivers) == 1
        assert len(matcher._id_waivers) == 1
        assert len(matcher._pattern_waivers) == 1
        assert len(matcher._file_waivers) == 1


class TestIdMatching:
    """Tests for ID waiver matching."""

    def test_id_match(self):
        """ID waiver matches when message_id equals pattern exactly."""
        waiver = Waiver(
            type="id",
            pattern="Vivado 12-3523",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Vivado 12-3523] some message",
            content="some message",
            message_id="Vivado 12-3523"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_id_no_match_different_id(self):
        """ID waiver does not match when message_id differs."""
        waiver = Waiver(
            type="id",
            pattern="Vivado 12-9999",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Vivado 12-3523] different",
            content="different",
            message_id="Vivado 12-3523"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_id_no_match_missing_message_id(self):
        """ID waiver does not match when message has no message_id."""
        waiver = Waiver(
            type="id",
            pattern="Test 1-1",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="Some message without ID",
            content="Some message"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_id_match_partial_no_match(self):
        """ID waiver requires exact match, not partial."""
        waiver = Waiver(
            type="id",
            pattern="Vivado 12",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Vivado 12-3523] msg",
            content="msg",
            message_id="Vivado 12-3523"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None


class TestPatternMatching:
    """Tests for pattern (regex) waiver matching."""

    def test_pattern_match(self):
        """Pattern waiver matches when regex matches raw_text."""
        waiver = Waiver(
            type="pattern",
            pattern="usb_fifo_clk",
            reason="async clock",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: set_input_delay usb_fifo_clk",
            content="set_input_delay usb_fifo_clk"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_pattern_match_regex(self):
        """Pattern waiver supports full regex."""
        waiver = Waiver(
            type="pattern",
            pattern=r"timing.*slack:\s*-\d+\.\d+",
            reason="timing slack",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=2,
            raw_text="ERROR: timing violation\n  slack: -0.5ns",
            content="timing violation"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_pattern_no_match(self):
        """Pattern waiver does not match when regex doesn't match."""
        waiver = Waiver(
            type="pattern",
            pattern="different_clock",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: set_input_delay usb_fifo_clk",
            content="set_input_delay usb_fifo_clk"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_pattern_multiline_match(self):
        """Pattern waiver can match across multiple lines."""
        waiver = Waiver(
            type="pattern",
            pattern=r"violation.*suggestion",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=4,
            raw_text="Error: timing violation\n  slack: -0.5ns\n  path: clk -> reg\n  suggestion: fix it",
            content="timing violation"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_pattern_case_sensitive(self):
        """Pattern waiver is case sensitive by default."""
        waiver = Waiver(
            type="pattern",
            pattern="ERROR",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="error: something failed",
            content="something failed"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_pattern_case_insensitive_regex(self):
        """Pattern waiver can use regex flags for case insensitivity."""
        waiver = Waiver(
            type="pattern",
            pattern="(?i)error",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="error: something failed",
            content="something failed"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver


class TestFileMatching:
    """Tests for file waiver matching."""

    def test_file_exact_match(self):
        """File waiver matches when file path matches exactly."""
        waiver = Waiver(
            type="file",
            pattern="/path/to/file.v",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error in file",
            content="error in file",
            file_ref=FileRef(path="/path/to/file.v", line=53)
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_file_end_match(self):
        """File waiver matches when pattern matches end of path."""
        waiver = Waiver(
            type="file",
            pattern="file.v",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error in file",
            content="error in file",
            file_ref=FileRef(path="/path/to/file.v", line=53)
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_file_glob_match(self):
        """File waiver supports glob-style wildcards."""
        waiver = Waiver(
            type="file",
            pattern="*/generated/*.v",
            reason="generated files",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] warning in generated file",
            content="warning in generated file",
            file_ref=FileRef(path="/project/generated/output.v", line=10)
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_file_no_match_different_path(self):
        """File waiver does not match when path differs."""
        waiver = Waiver(
            type="file",
            pattern="/path/to/other.v",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            file_ref=FileRef(path="/path/to/file.v", line=53)
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_file_no_match_missing_file_ref(self):
        """File waiver does not match when message has no file_ref."""
        waiver = Waiver(
            type="file",
            pattern="/path/to/file.v",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error without file ref",
            content="error without file ref"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None


class TestHashMatching:
    """Tests for hash waiver matching."""

    def test_hash_match(self):
        """Hash waiver matches when SHA-256 of raw_text matches."""
        raw_text = "ERROR: [Test 1-1] specific error message"
        message_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        waiver = Waiver(
            type="hash",
            pattern=message_hash,
            reason="exact message waiver",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text=raw_text,
            content="specific error message"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver

    def test_hash_no_match_different_text(self):
        """Hash waiver does not match when raw_text differs."""
        waiver = Waiver(
            type="hash",
            pattern="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] different message",
            content="different message"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_hash_multiline_match(self):
        """Hash waiver matches multi-line messages."""
        raw_text = "ERROR: multi-line\n  detail 1\n  detail 2"
        message_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        waiver = Waiver(
            type="hash",
            pattern=message_hash,
            reason="multi-line waiver",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=3,
            raw_text=raw_text,
            content="multi-line"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result == waiver


class TestPriorityOrder:
    """Tests for waiver priority ordering."""

    def test_hash_has_highest_priority(self):
        """Hash waiver takes precedence over all other types."""
        raw_text = "ERROR: [Test 1-1] message"
        message_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        hash_waiver = Waiver(
            type="hash",
            pattern=message_hash,
            reason="hash match",
            author="test",
            date="2026-01-18"
        )
        id_waiver = Waiver(
            type="id",
            pattern="Test 1-1",
            reason="id match",
            author="test",
            date="2026-01-18"
        )
        pattern_waiver = Waiver(
            type="pattern",
            pattern="ERROR",
            reason="pattern match",
            author="test",
            date="2026-01-18"
        )
        file_waiver = Waiver(
            type="file",
            pattern="file.v",
            reason="file match",
            author="test",
            date="2026-01-18"
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text=raw_text,
            content="message",
            message_id="Test 1-1",
            file_ref=FileRef(path="/path/to/file.v", line=1)
        )

        # Order matters - hash should win regardless of order in list
        matcher = WaiverMatcher([file_waiver, pattern_waiver, id_waiver, hash_waiver])
        result = matcher.is_waived(message)

        assert result == hash_waiver
        assert result.reason == "hash match"

    def test_id_has_priority_over_pattern_and_file(self):
        """ID waiver takes precedence over pattern and file types."""
        id_waiver = Waiver(
            type="id",
            pattern="Test 1-1",
            reason="id match",
            author="test",
            date="2026-01-18"
        )
        pattern_waiver = Waiver(
            type="pattern",
            pattern="ERROR",
            reason="pattern match",
            author="test",
            date="2026-01-18"
        )
        file_waiver = Waiver(
            type="file",
            pattern="file.v",
            reason="file match",
            author="test",
            date="2026-01-18"
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] message",
            content="message",
            message_id="Test 1-1",
            file_ref=FileRef(path="/path/to/file.v", line=1)
        )

        matcher = WaiverMatcher([file_waiver, pattern_waiver, id_waiver])
        result = matcher.is_waived(message)

        assert result == id_waiver
        assert result.reason == "id match"

    def test_pattern_has_priority_over_file(self):
        """Pattern waiver takes precedence over file type."""
        pattern_waiver = Waiver(
            type="pattern",
            pattern="WARNING",
            reason="pattern match",
            author="test",
            date="2026-01-18"
        )
        file_waiver = Waiver(
            type="file",
            pattern="file.v",
            reason="file match",
            author="test",
            date="2026-01-18"
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] message",
            content="message",
            file_ref=FileRef(path="/path/to/file.v", line=1)
        )

        matcher = WaiverMatcher([file_waiver, pattern_waiver])
        result = matcher.is_waived(message)

        assert result == pattern_waiver
        assert result.reason == "pattern match"

    def test_file_matches_when_only_file_applies(self):
        """File waiver matches when no higher priority types match."""
        id_waiver = Waiver(
            type="id",
            pattern="Different 9-9999",
            reason="id match",
            author="test",
            date="2026-01-18"
        )
        pattern_waiver = Waiver(
            type="pattern",
            pattern="CRITICAL",
            reason="pattern match",
            author="test",
            date="2026-01-18"
        )
        file_waiver = Waiver(
            type="file",
            pattern="file.v",
            reason="file match",
            author="test",
            date="2026-01-18"
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] message",
            content="message",
            message_id="Test 1-1",
            file_ref=FileRef(path="/path/to/file.v", line=1)
        )

        matcher = WaiverMatcher([id_waiver, pattern_waiver, file_waiver])
        result = matcher.is_waived(message)

        assert result == file_waiver
        assert result.reason == "file match"


class TestNoMatch:
    """Tests for when no waivers match."""

    def test_no_match_returns_none(self):
        """is_waived returns None when no waivers match."""
        waiver = Waiver(
            type="id",
            pattern="Different 9-9999",
            reason="test",
            author="test",
            date="2026-01-18"
        )
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="WARNING: [Test 1-1] message",
            content="message",
            message_id="Test 1-1"
        )

        matcher = WaiverMatcher([waiver])
        result = matcher.is_waived(message)

        assert result is None

    def test_empty_waivers_returns_none(self):
        """is_waived returns None when waiver list is empty."""
        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] message",
            content="message"
        )

        matcher = WaiverMatcher([])
        result = matcher.is_waived(message)

        assert result is None


class TestMultipleWaivers:
    """Tests for matching with multiple waivers."""

    def test_first_matching_waiver_returned(self):
        """When multiple waivers of same type match, first one wins."""
        waiver1 = Waiver(
            type="pattern",
            pattern="ERROR",
            reason="first pattern",
            author="test",
            date="2026-01-18"
        )
        waiver2 = Waiver(
            type="pattern",
            pattern="message",
            reason="second pattern",
            author="test",
            date="2026-01-18"
        )

        message = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: some message",
            content="some message"
        )

        matcher = WaiverMatcher([waiver1, waiver2])
        result = matcher.is_waived(message)

        assert result == waiver1
        assert result.reason == "first pattern"

    def test_multiple_messages_different_matches(self):
        """Different messages can match different waivers."""
        id_waiver = Waiver(
            type="id",
            pattern="Test 1-1",
            reason="id waiver",
            author="test",
            date="2026-01-18"
        )
        pattern_waiver = Waiver(
            type="pattern",
            pattern="timing",
            reason="timing waiver",
            author="test",
            date="2026-01-18"
        )

        message1 = Message(
            start_line=1,
            end_line=1,
            raw_text="ERROR: [Test 1-1] error",
            content="error",
            message_id="Test 1-1"
        )
        message2 = Message(
            start_line=2,
            end_line=2,
            raw_text="WARNING: timing violation",
            content="timing violation"
        )
        message3 = Message(
            start_line=3,
            end_line=3,
            raw_text="INFO: everything is fine",
            content="everything is fine"
        )

        matcher = WaiverMatcher([id_waiver, pattern_waiver])

        assert matcher.is_waived(message1) == id_waiver
        assert matcher.is_waived(message2) == pattern_waiver
        assert matcher.is_waived(message3) is None
