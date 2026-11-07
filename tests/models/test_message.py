"""Tests for Message and FileRef models."""

from sawmill.models.message import FileRef, Message


def test_message_single_line():
    """Single-line message has same start and end line."""
    msg = Message(
        start_line=1, end_line=1, raw_text="ERROR: [Test 1-1] error msg", content="error msg"
    )
    assert msg.start_line == 1
    assert msg.end_line == 1
    assert msg.severity is None  # Plugin didn't set it


def test_message_with_metadata():
    """Message with all metadata populated."""
    msg = Message(
        start_line=5,
        end_line=5,
        raw_text="WARNING: [Vivado 12-3523] deprecated",
        content="deprecated",
        severity="warning",
        message_id="Vivado 12-3523",
        category="general",
    )
    assert msg.severity == "warning"
    assert msg.message_id == "Vivado 12-3523"


def test_message_multiline():
    """Multi-line message spans multiple lines."""
    msg = Message(
        start_line=10,
        end_line=13,
        raw_text=(
            "Error: timing violation\n  slack: -0.5ns\n  path: clk -> reg\n  suggestion: fix it"
        ),
        content="timing violation",
        severity="error",
    )
    assert msg.start_line == 10
    assert msg.end_line == 13
    assert "\n" in msg.raw_text


def test_message_matches_filter():
    """Message.matches_filter should match against raw_text."""
    msg = Message(
        start_line=1,
        end_line=2,
        raw_text="Error: timing violation\n  slack: -0.5ns",
        content="timing violation",
    )
    assert msg.matches_filter(r"slack.*-\d+\.\d+") is True
    assert msg.matches_filter(r"DRC violation") is False


def test_file_ref_creation():
    ref = FileRef(path="/path/to/file.v", line=53)
    assert ref.path == "/path/to/file.v"
    assert ref.line == 53


def test_file_ref_without_line():
    """FileRef can be created without a line number."""
    ref = FileRef(path="/path/to/file.v")
    assert ref.path == "/path/to/file.v"
    assert ref.line is None


def test_message_with_file_ref():
    """Message can include a file reference."""
    ref = FileRef(path="/src/top.v", line=42)
    msg = Message(
        start_line=1,
        end_line=1,
        raw_text="INFO: synthesizing 'top' [/src/top.v:42]",
        content="synthesizing 'top'",
        file_ref=ref,
    )
    assert msg.file_ref is not None
    assert msg.file_ref.path == "/src/top.v"
    assert msg.file_ref.line == 42


def test_message_matches_filter_case_insensitive():
    """matches_filter should support case-insensitive matching."""
    msg = Message(start_line=1, end_line=1, raw_text="ERROR: Test message", content="Test message")
    assert msg.matches_filter(r"error", case_sensitive=False) is True
    assert msg.matches_filter(r"error", case_sensitive=True) is False


def test_message_matches_filter_invalid_regex():
    """Invalid regex patterns should return False, not raise."""
    msg = Message(start_line=1, end_line=1, raw_text="Some message", content="Some message")
    assert msg.matches_filter(r"[invalid(regex") is False


def test_message_equality():
    """Messages with same values should be equal."""
    msg1 = Message(
        start_line=1, end_line=1, raw_text="ERROR: test", content="test", severity="error"
    )
    msg2 = Message(
        start_line=1, end_line=1, raw_text="ERROR: test", content="test", severity="error"
    )
    assert msg1 == msg2


def test_message_inequality():
    """Messages with different values should not be equal."""
    msg1 = Message(start_line=1, end_line=1, raw_text="ERROR: test1", content="test1")
    msg2 = Message(start_line=1, end_line=1, raw_text="ERROR: test2", content="test2")
    assert msg1 != msg2


def test_message_coerces_line_numbers():
    """String line numbers are coerced to int."""
    msg = Message(start_line="3", end_line="4", raw_text="x", content="x")
    assert msg.start_line == 3 and isinstance(msg.start_line, int)
    assert msg.end_line == 4 and isinstance(msg.end_line, int)


def test_message_int_line_numbers_unchanged():
    msg = Message(start_line=7, end_line=8, raw_text="x", content="x")
    assert (msg.start_line, msg.end_line) == (7, 8)


def test_fileref_coerces_line():
    ref = FileRef(path="a.v", line="12")
    assert ref.line == 12 and isinstance(ref.line, int)
    assert FileRef(path="a.v", line=5).line == 5
    assert FileRef(path="a.v").line is None


def test_log_path_defaults_none():
    msg = Message(start_line=1, end_line=1, raw_text="x", content="x")
    assert msg.log_path is None


def test_log_path_settable():
    msg = Message(start_line=1, end_line=1, raw_text="x", content="x")
    msg.log_path = "build/a.log"
    assert msg.log_path == "build/a.log"


def test_log_path_is_last_field_positional_construction_unchanged():
    ref = FileRef("a.v", 3)
    msg = Message(1, 2, "raw", "content", "error", "X-1", "cat", ref, {"k": "v"})
    assert msg.severity == "error"
    assert msg.message_id == "X-1"
    assert msg.category == "cat"
    assert msg.file_ref is ref
    assert msg.metadata == {"k": "v"}
    assert msg.log_path is None
