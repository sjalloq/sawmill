"""Tests for the shared TOML basic-string escape utility."""

import tomli

from sawmill.utils.toml import escape_toml_basic_string


class TestEscapeBackslash:
    """Backslash must be escaped first to avoid double-escaping."""

    def test_single_backslash(self):
        assert escape_toml_basic_string("a\\b") == "a\\\\b"

    def test_multiple_backslashes(self):
        assert escape_toml_basic_string("\\\\") == "\\\\\\\\"

    def test_backslash_before_other_special(self):
        # backslash followed by a quote
        assert escape_toml_basic_string('\\"') == '\\\\\\"'


class TestEscapeQuotes:
    """Double quotes must be escaped in basic strings."""

    def test_double_quote(self):
        assert escape_toml_basic_string('say "hello"') == 'say \\"hello\\"'

    def test_only_quotes(self):
        assert escape_toml_basic_string('""') == '\\"\\"'


class TestEscapeNewlineTabCarriageReturn:
    """Common whitespace control characters."""

    def test_newline(self):
        assert escape_toml_basic_string("line1\nline2") == "line1\\nline2"

    def test_tab(self):
        assert escape_toml_basic_string("col1\tcol2") == "col1\\tcol2"

    def test_carriage_return(self):
        assert escape_toml_basic_string("line1\rline2") == "line1\\rline2"

    def test_crlf(self):
        assert escape_toml_basic_string("line1\r\nline2") == "line1\\r\\nline2"


class TestEscapeBackspaceFormFeed:
    """Less common but TOML-required escape sequences."""

    def test_backspace(self):
        assert escape_toml_basic_string("a\bb") == "a\\bb"

    def test_form_feed(self):
        assert escape_toml_basic_string("a\fb") == "a\\fb"


class TestEscapeControlCharacters:
    """Remaining control characters (U+0000-U+001F, U+007F) as \\uXXXX."""

    def test_null_byte(self):
        assert escape_toml_basic_string("\x00") == "\\u0000"

    def test_soh(self):
        """U+0001 (Start of Heading)."""
        assert escape_toml_basic_string("\x01") == "\\u0001"

    def test_bel(self):
        """U+0007 (Bell)."""
        assert escape_toml_basic_string("\x07") == "\\u0007"

    def test_vertical_tab(self):
        """U+000B (Vertical Tab) -- not one of the named escapes."""
        assert escape_toml_basic_string("\x0b") == "\\u000B"

    def test_escape_char(self):
        """U+001B (Escape)."""
        assert escape_toml_basic_string("\x1b") == "\\u001B"

    def test_unit_separator(self):
        """U+001F (Unit Separator) -- last char in U+0000-U+001F range."""
        assert escape_toml_basic_string("\x1f") == "\\u001F"

    def test_delete(self):
        """U+007F (DEL)."""
        assert escape_toml_basic_string("\x7f") == "\\u007F"


class TestNormalTextPassthrough:
    """Normal ASCII and Unicode text should pass through unchanged."""

    def test_plain_ascii(self):
        assert escape_toml_basic_string("hello world") == "hello world"

    def test_digits(self):
        assert escape_toml_basic_string("12345") == "12345"

    def test_empty_string(self):
        assert escape_toml_basic_string("") == ""

    def test_unicode_text(self):
        assert escape_toml_basic_string("cafe\u0301") == "cafe\u0301"

    def test_emoji(self):
        assert escape_toml_basic_string("hello \U0001f600") == "hello \U0001f600"

    def test_printable_special_chars(self):
        """Characters like !, @, #, $, etc. should not be escaped."""
        text = "!@#$%^&*()_+-=[]{}|;':,.<>/?"
        assert escape_toml_basic_string(text) == text


class TestRoundTrip:
    """Escaped strings must survive a TOML parse round-trip.

    The invariant is:
        tomli.loads(f'x = "{escape_toml_basic_string(s)}"')["x"] == s
    """

    def _roundtrip(self, value: str) -> str:
        """Escape, embed in TOML, parse back, and return the result."""
        escaped = escape_toml_basic_string(value)
        toml_doc = f'x = "{escaped}"'
        parsed = tomli.loads(toml_doc)
        return parsed["x"]

    def test_plain_text(self):
        assert self._roundtrip("hello world") == "hello world"

    def test_backslash(self):
        assert self._roundtrip("path\\to\\file") == "path\\to\\file"

    def test_double_quote(self):
        assert self._roundtrip('say "hello"') == 'say "hello"'

    def test_newline(self):
        assert self._roundtrip("line1\nline2") == "line1\nline2"

    def test_tab(self):
        assert self._roundtrip("col1\tcol2") == "col1\tcol2"

    def test_carriage_return(self):
        assert self._roundtrip("before\rafter") == "before\rafter"

    def test_backspace(self):
        assert self._roundtrip("a\bb") == "a\bb"

    def test_form_feed(self):
        assert self._roundtrip("a\fb") == "a\fb"

    def test_null_byte(self):
        assert self._roundtrip("\x00") == "\x00"

    def test_control_char_u0001(self):
        assert self._roundtrip("\x01") == "\x01"

    def test_delete_u007f(self):
        assert self._roundtrip("\x7f") == "\x7f"

    def test_mixed_special_chars(self):
        """A string with many special characters at once."""
        original = 'path\\to\t"file"\nwith\rstuff\b\f\x00\x1b\x7f'
        assert self._roundtrip(original) == original

    def test_vivado_table_line(self):
        """Realistic Vivado log line with tabs in table output."""
        original = "| Cell\t| Count\t| Area\t|"
        assert self._roundtrip(original) == original

    def test_empty_string(self):
        assert self._roundtrip("") == ""

    def test_unicode_text(self):
        assert self._roundtrip("cafe\u0301 \U0001f600") == "cafe\u0301 \U0001f600"
