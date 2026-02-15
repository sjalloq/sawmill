"""Tests for waiver loading, validation, and serialization."""

from pathlib import Path

import pytest
import tomli

from sawmill.core.waiver import WaiverLoader, WaiverValidationError, waiver_to_toml
from sawmill.models.waiver import Waiver


class TestWaiverLoader:
    """Tests for the WaiverLoader class."""

    def test_parse_waiver_file(self, tmp_path):
        """Parse a valid waiver file with metadata and waiver entry."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[metadata]
tool = "vivado"

[[waiver]]
message_id = "Vivado 12-3523"
reason = "Intentional"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 1
        assert waivers.waivers[0].message_id == "Vivado 12-3523"
        assert waivers.tool == "vivado"

    def test_invalid_waiver_rejected(self, tmp_path):
        """Waiver missing required fields should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
# Missing required fields: reason, author, date
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        # Should mention missing fields
        assert "missing required" in str(exc.value).lower()

    def test_parse_multiple_waivers(self, tmp_path):
        """Parse file with multiple waiver entries."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Vivado 12-3523"
reason = "Intentional"
author = "alice"
date = "2026-01-18"

[[waiver]]
message_id = "Synth 8-3332"
content_match = "regex"
content_pattern = "timing.*violation"
reason = "Known issue"
author = "bob"
date = "2026-01-17"

[[waiver]]
message_id = "DRC 1-100"
content_match = "raw"
content_pattern = "some specific text"
reason = "Legacy code"
author = "charlie"
date = "2026-01-16"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 3
        assert waivers.waivers[0].message_id == "Vivado 12-3523"
        assert waivers.waivers[0].content_match is None
        assert waivers.waivers[0].content_pattern is None
        assert waivers.waivers[1].content_match == "regex"
        assert waivers.waivers[1].content_pattern == "timing.*violation"
        assert waivers.waivers[2].content_match == "raw"

    def test_waiver_without_content_pattern(self, tmp_path):
        """Waiver without content_pattern matches all instances of message_id."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "Match all instances"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 1
        assert waivers.waivers[0].content_match is None
        assert waivers.waivers[0].content_pattern is None

    def test_invalid_content_match_rejected(self, tmp_path):
        """Invalid content_match value should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "invalid_type"
content_pattern = "test"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "invalid content_match" in str(exc.value).lower()

    def test_invalid_regex_content_pattern_rejected(self, tmp_path):
        """Invalid regex content_pattern should be rejected when content_match is regex."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "regex"
content_pattern = "[invalid(regex"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "invalid regex" in str(exc.value).lower()

    def test_invalid_toml_rejected(self, tmp_path):
        """Malformed TOML should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]
message_id = "Test 1-1"  # Missing closing bracket above
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "invalid toml" in str(exc.value).lower()

    def test_optional_fields_loaded(self, tmp_path):
        """Optional fields (expires, ticket) should be loaded if present."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "Temporary fix"
author = "test"
date = "2026-01-18"
expires = "2026-06-01"
ticket = "PROJ-123"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].expires == "2026-06-01"
        assert waivers.waivers[0].ticket == "PROJ-123"

    def test_optional_fields_default_to_none(self, tmp_path):
        """Optional fields should default to None if not present."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].expires is None
        assert waivers.waivers[0].ticket is None

    def test_file_not_found(self, tmp_path):
        """Loading a nonexistent file should raise FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.toml"

        loader = WaiverLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(nonexistent)

    def test_empty_waiver_file(self, tmp_path):
        """Empty waiver file should return empty waiver list."""
        waiver_file = tmp_path / "empty.toml"
        waiver_file.write_text("")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 0
        assert waivers.tool is None

    def test_metadata_only_file(self, tmp_path):
        """File with only metadata and no waivers should return empty list."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[metadata]
tool = "vivado"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 0
        assert waivers.tool == "vivado"

    def test_path_stored_in_waiver_file(self, tmp_path):
        """The source path should be stored in WaiverFile."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.path == str(waiver_file)


class TestWaiverValidationError:
    """Tests for WaiverValidationError exception."""

    def test_error_message_includes_path(self, tmp_path):
        """Error message should include the file path."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)

        assert str(waiver_file) in str(exc.value)

    def test_error_message_includes_waiver_index(self, tmp_path):
        """Error message should indicate which waiver entry has the error."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Valid"
reason = "test"
author = "test"
date = "2026-01-18"

[[waiver]]
message_id = "Missing reason field"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)

        # Should mention entry 2 (1-indexed for user-friendliness)
        assert "waiver entry 2" in str(exc.value)

    def test_error_attributes_set(self):
        """WaiverValidationError should have expected attributes."""
        error = WaiverValidationError(
            "Test error", line=10, path=Path("/test/path.toml"), waiver_index=5
        )

        assert error.line == 10
        assert error.path == Path("/test/path.toml")
        assert error.waiver_index == 5


class TestLoadFromString:
    """Tests for loading waivers from string content."""

    def test_load_from_string(self):
        """Load waivers from string content."""
        content = """
[metadata]
tool = "vivado"

[[waiver]]
message_id = "Test 1-1"
reason = "test"
author = "test"
date = "2026-01-18"
"""

        loader = WaiverLoader()
        waivers = loader.load_from_string(content)

        assert len(waivers.waivers) == 1
        assert waivers.tool == "vivado"

    def test_load_from_string_with_path(self):
        """Load from string with path for error reporting."""
        content = """
[[waiver]]
message_id = "Test 1-1"
# Missing fields
"""

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load_from_string(content, path=Path("/virtual/path.toml"))

        assert "/virtual/path.toml" in str(exc.value)

    def test_load_from_string_invalid_toml(self):
        """Invalid TOML string should raise error."""
        content = "[[waiver]\n"  # Missing closing bracket

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load_from_string(content)

        assert "invalid toml" in str(exc.value).lower()


class TestWaiverValidation:
    """Tests for specific waiver field validation."""

    def test_empty_message_id_rejected(self, tmp_path):
        """Empty message_id should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = ""
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "message_id" in str(exc.value).lower()

    def test_empty_reason_rejected(self, tmp_path):
        """Empty reason should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = ""
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "reason" in str(exc.value).lower()

    def test_empty_author_rejected(self, tmp_path):
        """Empty author should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "test"
author = ""
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "author" in str(exc.value).lower()

    def test_empty_date_rejected(self, tmp_path):
        """Empty date should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "test"
author = "test"
date = ""
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "date" in str(exc.value).lower()

    def test_raw_content_match_skips_regex_validation(self, tmp_path):
        """Raw content_match should not validate content_pattern as regex."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "raw"
content_pattern = "[not a valid regex"
reason = "Literal substring match"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        # Should not raise - raw patterns are literal, not regex
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].content_pattern == "[not a valid regex"

    def test_valid_regex_in_content_pattern(self, tmp_path):
        """Valid regex should be accepted for regex content_match."""
        waiver_file = tmp_path / "waivers.toml"
        # In TOML basic strings, backslashes must be escaped. Use literal string (single quotes).
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "regex"
content_pattern = 'timing.*violation\\s+\\d+'
reason = "Complex regex"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].content_pattern == r"timing.*violation\s+\d+"


class TestContentMatchPatternConsistency:
    """Tests for content_match / content_pattern validation consistency."""

    def test_content_match_without_content_pattern_raises_error(self, tmp_path):
        """content_match set without content_pattern should raise WaiverValidationError."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "raw"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "content_match" in str(exc.value).lower()
        assert "content_pattern" in str(exc.value).lower()

    def test_content_match_regex_without_content_pattern_raises_error(self, tmp_path):
        """content_match='regex' without content_pattern should raise WaiverValidationError."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "regex"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "content_match" in str(exc.value).lower()
        assert "content_pattern" in str(exc.value).lower()

    def test_content_pattern_without_content_match_defaults_to_raw(self, tmp_path):
        """content_pattern without content_match should default content_match to 'raw'."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_pattern = "some substring"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].content_match == "raw"
        assert waivers.waivers[0].content_pattern == "some substring"

    def test_both_content_match_and_pattern_set_works(self, tmp_path):
        """Both content_match and content_pattern set together should work fine."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
content_match = "raw"
content_pattern = "specific text"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].content_match == "raw"
        assert waivers.waivers[0].content_pattern == "specific text"

    def test_neither_content_match_nor_pattern_set_works(self, tmp_path):
        """Neither content_match nor content_pattern set should work fine (catch-all)."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Test 1-1"
reason = "match all instances"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].content_match is None
        assert waivers.waivers[0].content_pattern is None

    def test_content_match_without_pattern_error_includes_waiver_index(self, tmp_path):
        """Error for content_match without content_pattern should include waiver index."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text("""
[[waiver]]
message_id = "Valid"
reason = "test"
author = "test"
date = "2026-01-18"

[[waiver]]
message_id = "Test 1-1"
content_match = "raw"
reason = "test"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        # Second entry (index 1) should be reported as "waiver entry 2" (1-indexed)
        assert "waiver entry 2" in str(exc.value)

    def test_content_pattern_without_match_defaults_via_load_from_string(self):
        """content_pattern without content_match should default to raw via load_from_string."""
        content = """
[[waiver]]
message_id = "Test 1-1"
content_pattern = "substring match"
reason = "test"
author = "test"
date = "2026-01-18"
"""

        loader = WaiverLoader()
        waivers = loader.load_from_string(content)

        assert waivers.waivers[0].content_match == "raw"
        assert waivers.waivers[0].content_pattern == "substring match"


class TestWaiverToToml:
    """Tests for waiver_to_toml() serialization."""

    def test_basic_waiver(self):
        """Basic waiver should produce valid TOML."""
        waiver = Waiver(
            message_id="Vivado 12-3523",
            reason="Intentional",
            author="alice",
            date="2026-01-18",
        )
        result = waiver_to_toml(waiver)

        assert result.startswith("[[waiver]]")
        assert 'message_id = "Vivado 12-3523"' in result
        assert 'reason = "Intentional"' in result
        assert 'author = "alice"' in result
        assert 'date = "2026-01-18"' in result

    def test_roundtrip_via_toml_parser(self):
        """Serialized waiver should parse back correctly via TOML."""
        waiver = Waiver(
            message_id="Test 1-1",
            reason="Known issue",
            author="bob",
            date="2026-02-01",
        )
        toml_str = waiver_to_toml(waiver)
        parsed = tomli.loads(toml_str)

        assert parsed["waiver"][0]["message_id"] == "Test 1-1"
        assert parsed["waiver"][0]["reason"] == "Known issue"

    def test_with_content_match(self):
        """Waiver with content_match and content_pattern should include both."""
        waiver = Waiver(
            message_id="Test 1-1",
            content_match="regex",
            content_pattern="timing.*violation",
            reason="Acceptable",
            author="alice",
            date="2026-01-18",
        )
        result = waiver_to_toml(waiver)

        assert 'content_match = "regex"' in result
        assert 'content_pattern = "timing.*violation"' in result

    def test_without_content_match_omits_fields(self):
        """Waiver without content_match should omit content fields."""
        waiver = Waiver(
            message_id="Test 1-1",
            reason="Catch-all",
            author="alice",
            date="2026-01-18",
        )
        result = waiver_to_toml(waiver)

        assert "content_match" not in result
        assert "content_pattern" not in result

    def test_optional_expires_field(self):
        """Waiver with expires should include it."""
        waiver = Waiver(
            message_id="Test 1-1",
            reason="Temporary",
            author="alice",
            date="2026-01-18",
            expires="2026-06-01",
        )
        result = waiver_to_toml(waiver)

        assert 'expires = "2026-06-01"' in result

    def test_optional_ticket_field(self):
        """Waiver with ticket should include it."""
        waiver = Waiver(
            message_id="Test 1-1",
            reason="Tracked",
            author="alice",
            date="2026-01-18",
            ticket="PROJ-123",
        )
        result = waiver_to_toml(waiver)

        assert 'ticket = "PROJ-123"' in result

    def test_escapes_special_characters(self):
        """Special characters in fields should be properly escaped."""
        waiver = Waiver(
            message_id='Test "1-1"',
            reason='Has "quotes" and \\backslash',
            author="alice",
            date="2026-01-18",
        )
        result = waiver_to_toml(waiver)
        parsed = tomli.loads(result)

        assert parsed["waiver"][0]["message_id"] == 'Test "1-1"'
        assert parsed["waiver"][0]["reason"] == 'Has "quotes" and \\backslash'
