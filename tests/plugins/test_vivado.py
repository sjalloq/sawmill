"""Tests for the Vivado plugin."""

from pathlib import Path

import pytest

from sawmill.plugins.vivado import VivadoPlugin


class TestVivadoCanHandle:
    """Tests for VivadoPlugin.can_handle()."""

    def test_vivado_detects_vivado_logs(self, tmp_path: Path) -> None:
        """Plugin should detect Vivado logs with high confidence."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text("# Vivado v2025.2 (64-bit)\nINFO: [Synth 8-6157] test")

        confidence = plugin.can_handle(log_file)
        assert confidence >= 0.9

    def test_vivado_does_not_detect_other_logs(self, tmp_path: Path) -> None:
        """Plugin should not detect non-Vivado logs."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "other.log"
        log_file.write_text("Some random log file content\nWith no Vivado patterns")

        confidence = plugin.can_handle(log_file)
        assert confidence < 0.5

    def test_vivado_detects_by_message_ids(self, tmp_path: Path) -> None:
        """Plugin should detect logs with Vivado message IDs."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "build.log"
        log_file.write_text(
            "INFO: [Synth 8-6157] message 1\n"
            "WARNING: [Vivado 12-3523] message 2\n"
            "INFO: [IP_Flow 19-234] message 3\n"
        )

        confidence = plugin.can_handle(log_file)
        assert confidence >= 0.8

    def test_vivado_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Plugin should return 0.0 for nonexistent files."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "nonexistent.log"

        confidence = plugin.can_handle(log_file)
        assert confidence == 0.0

    def test_vivado_low_confidence_for_name_only(self, tmp_path: Path) -> None:
        """Plugin should have low confidence based only on filename."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text("plain text without any patterns")

        confidence = plugin.can_handle(log_file)
        # Filename matches but content doesn't - should be low confidence
        assert 0.0 < confidence < 0.5


class TestVivadoLoadAndParse:
    """Tests for VivadoPlugin.load_and_parse()."""

    def test_vivado_load_and_parse(self, tmp_path: Path) -> None:
        """Plugin should parse basic Vivado messages."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "WARNING: [Vivado 12-3523] Component name change\n"
            "INFO: [Synth 8-1] Done\n"
        )

        messages = plugin.load_and_parse(log_file)

        assert len(messages) == 2
        assert messages[0].severity == "warning"
        assert messages[0].message_id == "Vivado 12-3523"
        assert messages[1].severity == "info"

    def test_vivado_parses_critical_warning(self, tmp_path: Path) -> None:
        """Plugin should correctly parse critical warnings."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text("CRITICAL WARNING: [Constraints 18-4427] Override warning\n")

        messages = plugin.load_and_parse(log_file)

        assert len(messages) == 1
        assert messages[0].severity == "critical_warning"
        assert messages[0].message_id == "Constraints 18-4427"

    def test_vivado_parses_error(self, tmp_path: Path) -> None:
        """Plugin should correctly parse errors."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text("ERROR: [Route 35-9] Routing failed\n")

        messages = plugin.load_and_parse(log_file)

        assert len(messages) == 1
        assert messages[0].severity == "error"
        assert messages[0].message_id == "Route 35-9"

    def test_vivado_multiline_message(self, tmp_path: Path) -> None:
        """Plugin should group multi-line messages into single Message objects."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "WARNING: [Vivado 12-3523] Some warning\n"
            "  with continuation line\n"
            "  and another line\n"
            "INFO: [Synth 8-1] Next message\n"
        )

        messages = plugin.load_and_parse(log_file)

        # Should be 2 messages, not 4 lines
        assert len(messages) == 2
        # First message should span multiple lines
        assert messages[0].start_line == 1
        assert messages[0].end_line >= 3
        assert "continuation" in messages[0].raw_text

    def test_vivado_extracts_category(self, tmp_path: Path) -> None:
        """Plugin should extract category from message ID."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text("INFO: [Synth 8-6157] synthesizing module\n")

        messages = plugin.load_and_parse(log_file)

        assert len(messages) == 1
        assert messages[0].category == "synth"

    def test_vivado_handles_empty_file(self, tmp_path: Path) -> None:
        """Plugin should handle empty files gracefully."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "empty.log"
        log_file.write_text("")

        messages = plugin.load_and_parse(log_file)
        assert messages == []

    def test_vivado_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Plugin should handle nonexistent files gracefully."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "nonexistent.log"

        messages = plugin.load_and_parse(log_file)
        assert messages == []

    def test_vivado_extracts_content(self, tmp_path: Path) -> None:
        """Plugin should extract message content without prefix."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text("WARNING: [Vivado 12-3523] Component name change attempted\n")

        messages = plugin.load_and_parse(log_file)

        assert len(messages) == 1
        assert "Component name change attempted" in messages[0].content
        # Content should not have the severity prefix
        assert not messages[0].content.startswith("WARNING")

    def test_vivado_parses_file_with_mixed_content(self, tmp_path: Path) -> None:
        """Plugin should skip non-message lines."""
        plugin = VivadoPlugin()
        log_file = tmp_path / "vivado.log"
        log_file.write_text(
            "# Comment line\n"
            "Some random text\n"
            "INFO: [Synth 8-6157] First message\n"
            "Plain text between messages\n"
            "WARNING: [Vivado 12-3523] Second message\n"
        )

        messages = plugin.load_and_parse(log_file)

        # Should only have the two actual messages
        assert len(messages) == 2
        assert messages[0].severity == "info"
        assert messages[1].severity == "warning"


class TestVivadoExtractFileReference:
    """Tests for VivadoPlugin.extract_file_reference()."""

    def test_vivado_extracts_file_reference(self) -> None:
        """Plugin should extract file:line from bracketed format."""
        plugin = VivadoPlugin()

        ref = plugin.extract_file_reference("synthesizing module 'top' [/path/to/file.v:53]")

        assert ref is not None
        assert ref.path == "/path/to/file.v"
        assert ref.line == 53

    def test_vivado_extracts_inline_file_reference(self) -> None:
        """Plugin should extract inline file:line references."""
        plugin = VivadoPlugin()

        ref = plugin.extract_file_reference(
            "INFO: [Synth 8-6157] synthesizing module /home/user/design.v:100"
        )

        assert ref is not None
        assert ref.path == "/home/user/design.v"
        assert ref.line == 100

    def test_vivado_no_file_reference(self) -> None:
        """Plugin should return None when no file reference exists."""
        plugin = VivadoPlugin()

        ref = plugin.extract_file_reference("WARNING: [Vivado 12-3523] some message")

        assert ref is None

    def test_vivado_file_reference_with_spaces_in_path(self) -> None:
        """Plugin should handle paths with spaces (bracketed format)."""
        plugin = VivadoPlugin()

        # Bracketed format can include spaces
        ref = plugin.extract_file_reference("[/path/to/my file.v:42]")

        assert ref is not None
        assert ref.path == "/path/to/my file.v"
        assert ref.line == 42


class TestVivadoGetFilters:
    """Tests for VivadoPlugin.get_filters()."""

    def test_vivado_filters_cover_common_cases(self) -> None:
        """Plugin should provide filters for common severity levels."""
        plugin = VivadoPlugin()
        filters = plugin.get_filters()

        filter_ids = [f.id for f in filters]
        assert "errors" in filter_ids
        assert "critical-warnings" in filter_ids
        assert "warnings" in filter_ids

    def test_vivado_filters_have_required_fields(self) -> None:
        """All filters should have required fields."""
        plugin = VivadoPlugin()
        filters = plugin.get_filters()

        for f in filters:
            assert f.id
            assert f.name
            assert f.pattern
            assert f.source == "plugin:vivado"

    def test_vivado_filters_include_category_filters(self) -> None:
        """Plugin should provide category-specific filters."""
        plugin = VivadoPlugin()
        filters = plugin.get_filters()

        filter_ids = [f.id for f in filters]
        assert "synthesis" in filter_ids
        assert "drc" in filter_ids
        assert "timing-issues" in filter_ids

    def test_vivado_filters_patterns_are_valid(self) -> None:
        """All filter patterns should be valid regex."""
        import re

        plugin = VivadoPlugin()
        filters = plugin.get_filters()

        for f in filters:
            # This should not raise
            re.compile(f.pattern)


class TestVivadoPluginAttributes:
    """Tests for VivadoPlugin class attributes."""

    def test_vivado_has_name(self) -> None:
        """Plugin should have a name attribute."""
        plugin = VivadoPlugin()
        assert plugin.name == "vivado"

    def test_vivado_has_version(self) -> None:
        """Plugin should have a version attribute."""
        plugin = VivadoPlugin()
        assert plugin.version == "1.0.0"

    def test_vivado_has_description(self) -> None:
        """Plugin should have a description attribute."""
        plugin = VivadoPlugin()
        assert "Vivado" in plugin.description


class TestVivadoIntegration:
    """Integration tests using real Vivado log fixtures."""

    def test_vivado_parses_real_log(self, vivado_log: Path) -> None:
        """Plugin should parse the real Vivado log file."""
        plugin = VivadoPlugin()
        messages = plugin.load_and_parse(vivado_log)

        # Should have many messages
        assert len(messages) > 100

        # Should have various severities
        severities = {m.severity for m in messages}
        assert "info" in severities
        assert "warning" in severities

    def test_vivado_detects_real_log(self, vivado_log: Path) -> None:
        """Plugin should detect real Vivado log with high confidence."""
        plugin = VivadoPlugin()
        confidence = plugin.can_handle(vivado_log)

        assert confidence >= 0.9

    def test_vivado_extracts_file_refs_from_real_log(self, vivado_log: Path) -> None:
        """Plugin should extract file references from real log."""
        plugin = VivadoPlugin()
        messages = plugin.load_and_parse(vivado_log)

        # Find messages with file references
        messages_with_refs = [m for m in messages if m.file_ref is not None]

        # Should have some messages with file refs
        assert len(messages_with_refs) > 0

        # File refs should have valid paths
        for m in messages_with_refs[:5]:  # Check first 5
            assert m.file_ref is not None
            assert m.file_ref.path
            assert m.file_ref.line is not None
            assert m.file_ref.line > 0
