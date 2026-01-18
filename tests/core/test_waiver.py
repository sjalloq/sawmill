"""Tests for waiver loading and validation."""

import pytest
from pathlib import Path

from sawmill.core.waiver import WaiverLoader, WaiverValidationError
from sawmill.models.waiver import Waiver, WaiverFile


class TestWaiverLoader:
    """Tests for the WaiverLoader class."""

    def test_parse_waiver_file(self, tmp_path):
        """Parse a valid waiver file with metadata and waiver entry."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[metadata]
tool = "vivado"

[[waiver]]
type = "id"
pattern = "Vivado 12-3523"
reason = "Intentional"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 1
        assert waivers.waivers[0].type == "id"
        assert waivers.waivers[0].pattern == "Vivado 12-3523"
        assert waivers.tool == "vivado"

    def test_invalid_waiver_rejected(self, tmp_path):
        """Waiver missing required fields should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
# Missing required fields: pattern, reason, author, date
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        # Should mention missing fields
        assert "missing required" in str(exc.value).lower()

    def test_parse_multiple_waivers(self, tmp_path):
        """Parse file with multiple waiver entries."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Vivado 12-3523"
reason = "Intentional"
author = "alice"
date = "2026-01-18"

[[waiver]]
type = "pattern"
pattern = "timing.*violation"
reason = "Known issue"
author = "bob"
date = "2026-01-17"

[[waiver]]
type = "file"
pattern = "/path/to/file.v"
reason = "Legacy code"
author = "charlie"
date = "2026-01-16"
''')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 3
        assert waivers.waivers[0].type == "id"
        assert waivers.waivers[1].type == "pattern"
        assert waivers.waivers[2].type == "file"

    def test_all_waiver_types_supported(self, tmp_path):
        """Verify all four waiver types are supported: id, pattern, file, hash."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "ID match"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "pattern"
pattern = "error.*message"
reason = "Pattern match"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "file"
pattern = "/path/to/file.v"
reason = "File match"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "hash"
pattern = "abc123def456"
reason = "Hash match"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 4
        types = {w.type for w in waivers.waivers}
        assert types == {"id", "pattern", "file", "hash"}

    def test_invalid_waiver_type_rejected(self, tmp_path):
        """Invalid waiver type should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "invalid_type"
pattern = "test"
reason = "test"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "invalid waiver type" in str(exc.value).lower()

    def test_invalid_regex_pattern_rejected(self, tmp_path):
        """Invalid regex pattern should be rejected for pattern type."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "pattern"
pattern = "[invalid(regex"
reason = "test"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "invalid regex" in str(exc.value).lower()

    def test_invalid_toml_rejected(self, tmp_path):
        """Malformed TOML should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]
type = "id"  # Missing closing bracket above
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "invalid toml" in str(exc.value).lower()

    def test_optional_fields_loaded(self, tmp_path):
        """Optional fields (expires, ticket) should be loaded if present."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Temporary fix"
author = "test"
date = "2026-01-18"
expires = "2026-06-01"
ticket = "PROJ-123"
''')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].expires == "2026-06-01"
        assert waivers.waivers[0].ticket == "PROJ-123"

    def test_optional_fields_default_to_none(self, tmp_path):
        """Optional fields should default to None if not present."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "test"
author = "test"
date = "2026-01-18"
''')

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
        waiver_file.write_text('')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 0
        assert waivers.tool is None

    def test_metadata_only_file(self, tmp_path):
        """File with only metadata and no waivers should return empty list."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[metadata]
tool = "vivado"
''')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert len(waivers.waivers) == 0
        assert waivers.tool == "vivado"

    def test_path_stored_in_waiver_file(self, tmp_path):
        """The source path should be stored in WaiverFile."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "test"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.path == str(waiver_file)


class TestWaiverValidationError:
    """Tests for WaiverValidationError exception."""

    def test_error_message_includes_path(self, tmp_path):
        """Error message should include the file path."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)

        assert str(waiver_file) in str(exc.value)

    def test_error_message_includes_waiver_index(self, tmp_path):
        """Error message should indicate which waiver entry has the error."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Valid"
reason = "test"
author = "test"
date = "2026-01-18"

[[waiver]]
type = "id"
pattern = "Missing reason field"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)

        # Should mention entry 2 (1-indexed for user-friendliness)
        assert "waiver entry 2" in str(exc.value)

    def test_error_attributes_set(self):
        """WaiverValidationError should have expected attributes."""
        error = WaiverValidationError(
            "Test error",
            line=10,
            path=Path("/test/path.toml"),
            waiver_index=5
        )

        assert error.line == 10
        assert error.path == Path("/test/path.toml")
        assert error.waiver_index == 5


class TestLoadFromString:
    """Tests for loading waivers from string content."""

    def test_load_from_string(self):
        """Load waivers from string content."""
        content = '''
[metadata]
tool = "vivado"

[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "test"
author = "test"
date = "2026-01-18"
'''

        loader = WaiverLoader()
        waivers = loader.load_from_string(content)

        assert len(waivers.waivers) == 1
        assert waivers.tool == "vivado"

    def test_load_from_string_with_path(self):
        """Load from string with path for error reporting."""
        content = '''
[[waiver]]
type = "id"
# Missing fields
'''

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

    def test_empty_pattern_rejected(self, tmp_path):
        """Empty pattern should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = ""
reason = "test"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "pattern" in str(exc.value).lower()

    def test_empty_reason_rejected(self, tmp_path):
        """Empty reason should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = ""
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "reason" in str(exc.value).lower()

    def test_empty_author_rejected(self, tmp_path):
        """Empty author should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "test"
author = ""
date = "2026-01-18"
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "author" in str(exc.value).lower()

    def test_empty_date_rejected(self, tmp_path):
        """Empty date should be rejected."""
        waiver_file = tmp_path / "bad.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "test"
author = "test"
date = ""
''')

        loader = WaiverLoader()
        with pytest.raises(WaiverValidationError) as exc:
            loader.load(waiver_file)
        assert "date" in str(exc.value).lower()

    def test_non_pattern_type_skips_regex_validation(self, tmp_path):
        """Non-pattern types should not validate pattern as regex."""
        waiver_file = tmp_path / "waivers.toml"
        waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "[Vivado 12-3523]"
reason = "ID contains brackets"
author = "test"
date = "2026-01-18"
''')

        loader = WaiverLoader()
        # Should not raise - ID patterns are literal, not regex
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].pattern == "[Vivado 12-3523]"

    def test_valid_regex_in_pattern_type(self, tmp_path):
        """Valid regex should be accepted for pattern type."""
        waiver_file = tmp_path / "waivers.toml"
        # In TOML basic strings, backslashes must be escaped. Use literal string (single quotes).
        waiver_file.write_text("""
[[waiver]]
type = "pattern"
pattern = 'timing.*violation\\s+\\d+'
reason = "Complex regex"
author = "test"
date = "2026-01-18"
""")

        loader = WaiverLoader()
        waivers = loader.load(waiver_file)

        assert waivers.waivers[0].pattern == r"timing.*violation\s+\d+"
