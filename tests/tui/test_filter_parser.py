"""Tests for the search bar filter parser."""

from sawmill.tui.filter_parser import ParsedFilter, parse_filter


class TestParsedFilter:
    """Tests for the ParsedFilter dataclass."""

    def test_defaults(self):
        """Test default values."""
        pf = ParsedFilter()
        assert pf.severities == []
        assert pf.message_id is None
        assert pf.pattern is None


class TestParseFilter:
    """Tests for parse_filter function."""

    def test_empty_string(self):
        """Test empty input returns empty filter."""
        result = parse_filter("")
        assert result.severities == []
        assert result.message_id is None
        assert result.pattern is None

    def test_whitespace_only(self):
        """Test whitespace-only input returns empty filter."""
        result = parse_filter("   ")
        assert result.severities == []
        assert result.message_id is None
        assert result.pattern is None

    def test_plain_text(self):
        """Test plain text becomes regex pattern."""
        result = parse_filter("module A")
        assert result.pattern == "module A"
        assert result.severities == []
        assert result.message_id is None

    def test_severity_prefix_short(self):
        """Test sev: prefix."""
        result = parse_filter("sev:error")
        assert result.severities == ["error"]
        assert result.pattern is None

    def test_severity_prefix_long(self):
        """Test severity: prefix."""
        result = parse_filter("severity:warning")
        assert result.severities == ["warning"]

    def test_severity_case_insensitive(self):
        """Test severity prefix is case insensitive."""
        result = parse_filter("SEV:Error")
        assert result.severities == ["error"]

    def test_id_prefix(self):
        """Test id: prefix."""
        result = parse_filter("id:Synth 8-*")
        # With shlex, "Synth 8-*" would need quotes; without quotes
        # "Synth" and "8-*" are separate tokens
        assert result.message_id == "Synth"

    def test_id_prefix_quoted(self):
        """Test id: prefix with quoted value."""
        result = parse_filter('id:"Synth 8-*"')
        assert result.message_id == "Synth 8-*"

    def test_id_prefix_simple(self):
        """Test id: prefix with simple value."""
        result = parse_filter("id:E-001")
        assert result.message_id == "E-001"

    def test_combined_severity_and_pattern(self):
        """Test severity prefix combined with plain text."""
        result = parse_filter("sev:error module")
        assert result.severities == ["error"]
        assert result.pattern == "module"

    def test_combined_severity_and_id(self):
        """Test severity and id prefixes combined."""
        result = parse_filter("sev:error id:E-001")
        assert result.severities == ["error"]
        assert result.message_id == "E-001"
        assert result.pattern is None

    def test_all_three(self):
        """Test severity + id + text combined."""
        result = parse_filter("sev:warning id:W-001 module")
        assert result.severities == ["warning"]
        assert result.message_id == "W-001"
        assert result.pattern == "module"

    def test_multiple_severities(self):
        """Test multiple severity prefixes."""
        result = parse_filter("sev:error sev:warning")
        assert result.severities == ["error", "warning"]

    def test_unbalanced_quotes_fallback(self):
        """Test fallback to split on unbalanced quotes."""
        result = parse_filter('sev:error "unclosed')
        assert result.severities == ["error"]
        # Should not crash
