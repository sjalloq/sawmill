"""Tests for TUI persistence (save) and quit safety."""

import os
from unittest.mock import MagicMock, patch

import pytest
import tomli

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.waiver import Waiver
from sawmill.tui.app import SawmillApp
from sawmill.tui.widgets.quit_modal import QuitConfirmModal
from sawmill.utils.toml import escape_toml_basic_string


@pytest.fixture
def severity_levels():
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


def make_message(
    content: str,
    severity: str | None = None,
    message_id: str | None = None,
    line: int = 1,
) -> Message:
    return Message(
        start_line=line,
        end_line=line,
        raw_text=content,
        content=content,
        severity=severity,
        message_id=message_id,
    )


class TestEscapeToml:
    """Tests for TOML string escaping."""

    def test_plain_string(self):
        assert escape_toml_basic_string("hello") == "hello"

    def test_escape_backslash(self):
        assert escape_toml_basic_string("path\\to\\file") == "path\\\\to\\\\file"

    def test_escape_quotes(self):
        assert escape_toml_basic_string('say "hello"') == 'say \\"hello\\"'

    def test_escape_newline(self):
        assert escape_toml_basic_string("line1\nline2") == "line1\\nline2"


class TestQuitConfirmModalInit:
    """Tests for QuitConfirmModal initialization."""

    def test_init_basic(self):
        modal = QuitConfirmModal(suppression_count=3, waiver_count=2)
        assert modal._suppression_count == 3
        assert modal._waiver_count == 2

    def test_init_defaults(self):
        modal = QuitConfirmModal()
        assert modal._suppression_count == 0
        assert modal._waiver_count == 0

    def test_import_from_widgets(self):
        from sawmill.tui.widgets import QuitConfirmModal as QCM

        assert QCM is QuitConfirmModal


class TestActionQuit:
    """Tests for quit behavior with dirty state."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_quit_no_dirty_state(self, app):
        """Quit with no dirty state should exit immediately."""
        assert not app._suppressions_dirty
        assert not app._waivers_dirty
        # action_quit is async — can't easily test full flow without Textual runner,
        # but we can verify the dirty state detection
        assert not (app._suppressions_dirty or app._waivers_dirty)

    def test_quit_with_dirty_suppressions(self, app):
        """Dirty suppressions flag is detected."""
        app._suppressions_dirty = True
        assert app._suppressions_dirty or app._waivers_dirty

    def test_quit_with_dirty_waivers(self, app):
        """Dirty waivers flag is detected."""
        app._waivers_dirty = True
        assert app._suppressions_dirty or app._waivers_dirty


class TestOnQuitResult:
    """Tests for handling quit modal result."""

    @pytest.fixture
    def app(self, severity_levels):
        return SawmillApp(severity_levels)

    def test_cancel_returns_none(self, app):
        """Cancel result (None) keeps the app running."""
        # _on_quit_result with None should not exit
        # Since we can't easily test exit, just verify it doesn't crash
        app._on_quit_result(None)
        # App should still be alive (not crashed)

    def test_discard_quit_calls_exit(self, app):
        """'discard_quit' result calls exit() without saving."""
        app.exit = MagicMock()
        app._save_all = MagicMock()

        app._on_quit_result("discard_quit")

        app.exit.assert_called_once()
        app._save_all.assert_not_called()

    def test_save_quit_saves_then_exits(self, app):
        """'save_quit' result calls _save_all() then exit()."""
        call_order = []
        app.exit = MagicMock(side_effect=lambda: call_order.append("exit"))
        app._save_all = MagicMock(side_effect=lambda: call_order.append("save"))

        app._on_quit_result("save_quit")

        app._save_all.assert_called_once()
        app.exit.assert_called_once()
        # Save must happen before exit
        assert call_order == ["save", "exit"]


class TestSaveSuppressions:
    """Tests for saving suppressions to .sawmill/suppress.toml."""

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        """Create app and change to tmp_path for config file writing."""
        monkeypatch.chdir(tmp_path)
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_save_creates_suppress_file(self, app, tmp_path):
        """Saving suppressions creates .sawmill/suppress.toml."""
        app.suppressed_ids = {"E-001", "W-001"}
        app._suppressions_dirty = True
        app._save_suppressions()

        config_path = tmp_path / ".sawmill" / "suppress.toml"
        assert config_path.exists()
        data = tomli.loads(config_path.read_text())
        assert sorted(data["suppress"]["message_ids"]) == ["E-001", "W-001"]

    def test_save_replaces_existing(self, app, tmp_path):
        """Saving suppressions replaces existing IDs with session set."""
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        config_path = sawmill_dir / "suppress.toml"
        config_path.write_text('[suppress]\nmessage_ids = ["OLD-001"]\n')

        app.suppressed_ids = {"E-001"}
        app._suppressions_dirty = True
        app._save_suppressions()

        data = tomli.loads(config_path.read_text())
        # OLD-001 should NOT be present -- session set replaces, not merges
        assert sorted(data["suppress"]["message_ids"]) == ["E-001"]

    def test_save_replaces_and_deduplicates(self, app, tmp_path):
        """Saving replaces IDs with current session set (no duplicates)."""
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        config_path = sawmill_dir / "suppress.toml"
        config_path.write_text('[suppress]\nmessage_ids = ["E-001"]\n')

        app.suppressed_ids = {"E-001", "W-001"}
        app._suppressions_dirty = True
        app._save_suppressions()

        data = tomli.loads(config_path.read_text())
        assert sorted(data["suppress"]["message_ids"]) == ["E-001", "W-001"]


class TestSaveWaivers:
    """Tests for saving waivers to waiver file."""

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        waiver_path = tmp_path / "waivers.toml"
        return SawmillApp(
            severity_levels,
            waiver_file_path=waiver_path,
        )

    def test_save_creates_waiver_file(self, app, tmp_path):
        """Saving waivers creates the waiver file if it doesn't exist."""
        app._session_waivers = [
            Waiver(
                message_id="E-001",
                content_match="raw",
                content_pattern="specific text",
                reason="test reason",
                author="test@example.com",
                date="2026-02-08",
            ),
        ]
        app._waivers_dirty = True
        app._save_waivers()

        waiver_path = tmp_path / "waivers.toml"
        assert waiver_path.exists()
        content = waiver_path.read_text()
        assert "[[waiver]]" in content
        assert 'message_id = "E-001"' in content
        assert 'content_match = "raw"' in content
        assert 'content_pattern = "specific text"' in content
        assert 'reason = "test reason"' in content
        assert 'author = "test@example.com"' in content
        assert 'date = "2026-02-08"' in content

    def test_save_creates_file_with_header(self, app, tmp_path):
        """New waiver file includes header comment."""
        app._session_waivers = [
            Waiver(
                message_id="E-001",
                reason="test",
                author="test",
                date="2026-02-08",
            ),
        ]
        app._save_waivers()

        content = (tmp_path / "waivers.toml").read_text()
        assert "# Sawmill waiver file" in content

    def test_save_appends_to_existing(self, app, tmp_path):
        """Saving waivers appends to existing file."""
        waiver_path = tmp_path / "waivers.toml"
        waiver_path.write_text(
            '[[waiver]]\nmessage_id = "OLD-001"\n'
            'reason = "old"\nauthor = "old"\ndate = "2026-01-01"\n'
        )

        app._session_waivers = [
            Waiver(
                message_id="NEW-001",
                reason="new reason",
                author="new_author",
                date="2026-02-08",
            ),
        ]
        app._save_waivers()

        content = waiver_path.read_text()
        assert 'message_id = "OLD-001"' in content
        assert 'message_id = "NEW-001"' in content

    def test_save_waiver_without_content_pattern(self, app, tmp_path):
        """Waiver without content pattern omits content_match/content_pattern."""
        app._session_waivers = [
            Waiver(
                message_id="E-001",
                reason="catch all",
                author="test",
                date="2026-02-08",
            ),
        ]
        app._save_waivers()

        content = (tmp_path / "waivers.toml").read_text()
        assert "content_match" not in content
        assert "content_pattern" not in content

    def test_save_multiple_waivers(self, app, tmp_path):
        """Saving multiple waivers writes all of them."""
        app._session_waivers = [
            Waiver(message_id=f"E-{i:03d}", reason=f"reason {i}", author="test", date="2026-02-08")
            for i in range(3)
        ]
        app._save_waivers()

        content = (tmp_path / "waivers.toml").read_text()
        assert content.count("[[waiver]]") == 3


class TestSaveAll:
    """Tests for the complete save flow."""

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        waiver_path = tmp_path / "waivers.toml"
        return SawmillApp(
            severity_levels,
            waiver_file_path=waiver_path,
        )

    def test_save_resets_dirty_flags(self, app, tmp_path):
        """Save resets dirty flags on success."""
        app.suppressed_ids = {"E-001"}
        app._suppressions_dirty = True
        app._session_waivers = [
            Waiver(message_id="W-001", reason="test", author="test", date="2026-02-08"),
        ]
        app._waivers_dirty = True

        app._save_all()

        assert app._suppressions_dirty is False
        assert app._waivers_dirty is False

    def test_save_nothing_dirty(self, app):
        """Save with no dirty state notifies 'nothing to save'."""
        app._save_all()
        # No exception, nothing written

    def test_save_only_suppressions(self, app, tmp_path):
        """Save when only suppressions are dirty."""
        app.suppressed_ids = {"E-001"}
        app._suppressions_dirty = True

        app._save_all()

        assert (tmp_path / ".sawmill" / "suppress.toml").exists()
        assert not (tmp_path / "waivers.toml").exists()
        assert app._suppressions_dirty is False

    def test_save_only_waivers(self, app, tmp_path):
        """Save when only waivers are dirty."""
        app._session_waivers = [
            Waiver(message_id="W-001", reason="test", author="test", date="2026-02-08"),
        ]
        app._waivers_dirty = True

        app._save_all()

        assert (tmp_path / "waivers.toml").exists()
        assert not (tmp_path / ".sawmill" / "suppress.toml").exists()
        assert app._waivers_dirty is False

    def test_save_clears_session_waivers(self, app, tmp_path):
        """Session waivers list is cleared after successful save."""
        app._session_waivers = [
            Waiver(message_id="W-001", reason="test", author="test", date="2026-02-08"),
        ]
        app._waivers_dirty = True

        app._save_all()

        assert app._session_waivers == []


class TestSaveWaiversValidation:
    """Tests for waiver file validation before save."""

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        waiver_path = tmp_path / "waivers.toml"
        return SawmillApp(severity_levels, waiver_file_path=waiver_path)

    def test_save_validates_existing_file(self, app, tmp_path):
        """Saving validates existing waiver file before appending."""
        waiver_path = tmp_path / "waivers.toml"
        waiver_path.write_text("invalid toml [[[")

        app._session_waivers = [
            Waiver(message_id="E-001", reason="test", author="test", date="2026-02-08"),
        ]

        # Should raise an error due to invalid existing file
        from sawmill.core.waiver import WaiverValidationError

        with pytest.raises(WaiverValidationError):
            app._save_waivers()


class TestSaveWaiversRoundTrip:
    """Tests for save + load round-trip."""

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        waiver_path = tmp_path / "waivers.toml"
        return SawmillApp(severity_levels, waiver_file_path=waiver_path)

    def test_saved_waivers_loadable(self, app, tmp_path):
        """Saved waivers can be loaded back by WaiverLoader."""
        from sawmill.core.waiver import WaiverLoader

        app._session_waivers = [
            Waiver(
                message_id="E-001",
                content_match="raw",
                content_pattern="some content",
                reason="test reason",
                author="test@example.com",
                date="2026-02-08",
            ),
            Waiver(
                message_id="W-002",
                reason="catch all",
                author="test",
                date="2026-02-08",
            ),
        ]
        app._save_waivers()

        loader = WaiverLoader()
        waiver_file = loader.load(tmp_path / "waivers.toml")

        assert len(waiver_file.waivers) == 2
        assert waiver_file.waivers[0].message_id == "E-001"
        assert waiver_file.waivers[0].content_match == "raw"
        assert waiver_file.waivers[0].content_pattern == "some content"
        assert waiver_file.waivers[1].message_id == "W-002"
        assert waiver_file.waivers[1].content_match is None


class TestUnsuppressPersistence:
    """Tests for un-suppress persistence (Issue #02)."""

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_save_after_unsuppress_writes_reduced_set(self, app, tmp_path):
        """Saving after un-suppress writes only the current session set, not a union."""
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        config_path = sawmill_dir / "suppress.toml"
        # Pre-populate config with two suppressed IDs
        config_path.write_text('[suppress]\nmessage_ids = ["E-001", "W-001"]\n')

        # Session has only W-001 (user un-suppressed E-001)
        app.suppressed_ids = {"W-001"}
        app._suppressions_dirty = True
        app._save_suppressions()

        data = tomli.loads(config_path.read_text())
        # E-001 should be gone — replacement, not union merge
        assert data["suppress"]["message_ids"] == ["W-001"]

    def test_save_after_unsuppress_all_writes_empty_list(self, app, tmp_path):
        """Saving with empty suppressed_ids writes an empty list."""
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        config_path = sawmill_dir / "suppress.toml"
        config_path.write_text('[suppress]\nmessage_ids = ["E-001", "W-001"]\n')

        # User un-suppressed everything
        app.suppressed_ids = set()
        app._suppressions_dirty = True
        app._save_suppressions()

        data = tomli.loads(config_path.read_text())
        assert data["suppress"]["message_ids"] == []

    def test_quit_modal_triggers_on_unsuppress_dirty(self, app):
        """Quit dirty-state check detects un-suppress changes."""
        # Simulate: user un-suppressed something, so dirty flag is set
        app._suppressions_dirty = True
        app._waivers_dirty = False

        # The quit guard condition should trigger
        assert app._suppressions_dirty or app._waivers_dirty


class TestEmptySuppressedIdsSave:
    """Tests for Issue #03: Empty suppressed IDs + dirty flag = permanent unsaved state.

    When a user suppresses then un-suppresses ALL messages, suppressed_ids
    becomes an empty set while _suppressions_dirty is True. The _save_all()
    guard must still allow saving (writing message_ids = []) and clear the
    dirty flag, otherwise the user is trapped in a permanent dirty state.
    """

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_save_all_with_empty_suppressed_ids_clears_dirty_flag(self, app, tmp_path):
        """_save_all() with empty suppressed_ids and dirty flag clears the flag."""
        app.suppressed_ids = set()
        app._suppressions_dirty = True

        app._save_all()

        assert app._suppressions_dirty is False

    def test_save_all_with_empty_suppressed_ids_writes_config(self, app, tmp_path):
        """_save_all() with empty suppressed_ids writes .sawmill/suppress.toml with empty list."""
        app.suppressed_ids = set()
        app._suppressions_dirty = True

        app._save_all()

        config_path = tmp_path / ".sawmill" / "suppress.toml"
        assert config_path.exists()
        data = tomli.loads(config_path.read_text())
        assert data["suppress"]["message_ids"] == []

    def test_ctrl_s_after_full_unsuppress_clears_dirty(self, app, tmp_path):
        """Ctrl+S (action_save -> _save_all) after un-suppressing all clears dirty flag."""
        app.suppressed_ids = set()
        app._suppressions_dirty = True

        # action_save calls _save_all
        app.action_save()

        assert app._suppressions_dirty is False

    def test_quit_no_modal_after_save_with_empty_suppressions(self, app, tmp_path):
        """After saving empty suppressions, quit guard should not trigger modal."""
        app.suppressed_ids = set()
        app._suppressions_dirty = True

        app._save_all()

        # After save, both dirty flags should be False
        assert not app._suppressions_dirty
        assert not app._waivers_dirty
        # The quit guard condition: should NOT trigger the modal
        assert not (app._suppressions_dirty or app._waivers_dirty)

    def test_suppress_then_unsuppress_all_via_save_all(self, app, tmp_path):
        """Full workflow: suppress two IDs, un-suppress both, save clears state."""
        config_path = tmp_path / ".sawmill" / "suppress.toml"

        # Suppress two IDs
        app.suppressed_ids = {"E-001", "W-001"}
        app._suppressions_dirty = True
        app._save_all()

        # Verify first save worked
        assert app._suppressions_dirty is False
        data = tomli.loads(config_path.read_text())
        assert sorted(data["suppress"]["message_ids"]) == ["E-001", "W-001"]

        # Now un-suppress both
        app.suppressed_ids = set()
        app._suppressions_dirty = True
        app._save_all()

        # Dirty flag must be cleared
        assert app._suppressions_dirty is False
        # File must have empty list
        data = tomli.loads(config_path.read_text())
        assert data["suppress"]["message_ids"] == []


class TestAtomicWaiverWrite:
    """Tests for atomic waiver file writes (Issue #14).

    Verifies that _save_waivers() uses write-to-temp-then-rename
    for atomicity, so a crash mid-write cannot corrupt the waiver file.
    """

    @pytest.fixture
    def app(self, severity_levels, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        waiver_path = tmp_path / "waivers.toml"
        return SawmillApp(severity_levels, waiver_file_path=waiver_path)

    @pytest.fixture
    def sample_waiver(self):
        return Waiver(
            message_id="E-001",
            content_match="raw",
            content_pattern="specific text",
            reason="test reason",
            author="test@example.com",
            date="2026-02-08",
        )

    def test_atomic_write_creates_correct_content(self, app, tmp_path, sample_waiver):
        """Atomic write produces the same content as the old approach."""
        app._session_waivers = [sample_waiver]
        app._save_waivers()

        waiver_path = tmp_path / "waivers.toml"
        content = waiver_path.read_text()
        assert "# Sawmill waiver file" in content
        assert "[[waiver]]" in content
        assert 'message_id = "E-001"' in content
        assert 'content_match = "raw"' in content
        assert 'content_pattern = "specific text"' in content
        assert 'reason = "test reason"' in content
        assert 'author = "test@example.com"' in content

    def test_atomic_write_appends_to_existing(self, app, tmp_path, sample_waiver):
        """Atomic write preserves existing content when appending."""
        waiver_path = tmp_path / "waivers.toml"
        existing_content = (
            '[[waiver]]\nmessage_id = "OLD-001"\n'
            'reason = "old"\nauthor = "old"\ndate = "2026-01-01"\n'
        )
        waiver_path.write_text(existing_content)

        app._session_waivers = [sample_waiver]
        app._save_waivers()

        content = waiver_path.read_text()
        # Both old and new waivers present
        assert 'message_id = "OLD-001"' in content
        assert 'message_id = "E-001"' in content

    def test_atomic_write_preserves_original_on_write_failure(self, app, tmp_path, sample_waiver):
        """If the write fails, the original waiver file is preserved intact."""
        waiver_path = tmp_path / "waivers.toml"
        original_content = (
            '[[waiver]]\nmessage_id = "OLD-001"\n'
            'reason = "old"\nauthor = "old"\ndate = "2026-01-01"\n'
        )
        waiver_path.write_text(original_content)

        app._session_waivers = [sample_waiver]

        # Simulate a write failure by making os.rename raise an error
        with (
            patch("sawmill.tui.app.os.rename", side_effect=OSError("disk full")),
            pytest.raises(OSError, match="disk full"),
        ):
            app._save_waivers()

        # Original file must be preserved
        assert waiver_path.read_text() == original_content

    def test_atomic_write_cleans_up_temp_on_failure(self, app, tmp_path, sample_waiver):
        """Temp file is cleaned up when the rename fails."""
        app._session_waivers = [sample_waiver]

        # Simulate rename failure
        with (
            patch("sawmill.tui.app.os.rename", side_effect=OSError("disk full")),
            pytest.raises(OSError),
        ):
            app._save_waivers()

        # No temp files should remain in the directory
        remaining = list(tmp_path.glob("*.tmp"))
        assert remaining == [], f"Temp files not cleaned up: {remaining}"

    def test_atomic_write_cleans_up_temp_on_write_error(self, app, tmp_path, sample_waiver):
        """Temp file is cleaned up even when the write itself fails."""
        app._session_waivers = [sample_waiver]

        # Simulate a write error by making os.fdopen raise
        def failing_fdopen(fd, *args, **kwargs):
            # Close the fd to avoid resource leak, then raise
            os.close(fd)
            raise OSError("write failed")

        with (
            patch("sawmill.tui.app.os.fdopen", side_effect=failing_fdopen),
            pytest.raises(IOError, match="write failed"),
        ):
            app._save_waivers()

        # No temp files should remain
        remaining = list(tmp_path.glob("*.tmp"))
        assert remaining == [], f"Temp files not cleaned up: {remaining}"

    def test_atomic_write_no_temp_files_on_success(self, app, tmp_path, sample_waiver):
        """After a successful write, no temp files remain."""
        app._session_waivers = [sample_waiver]
        app._save_waivers()

        remaining = list(tmp_path.glob("*.tmp"))
        assert remaining == [], f"Temp files left behind: {remaining}"

    def test_atomic_write_round_trip_loadable(self, app, tmp_path, sample_waiver):
        """Atomically written waiver file is loadable by WaiverLoader."""
        from sawmill.core.waiver import WaiverLoader

        app._session_waivers = [sample_waiver]
        app._save_waivers()

        loader = WaiverLoader()
        waiver_file = loader.load(tmp_path / "waivers.toml")
        assert len(waiver_file.waivers) == 1
        assert waiver_file.waivers[0].message_id == "E-001"

    def test_atomic_write_with_plugin_name(self, severity_levels, tmp_path, monkeypatch):
        """Atomic write includes metadata section when plugin_name is set."""
        monkeypatch.chdir(tmp_path)
        waiver_path = tmp_path / "waivers.toml"
        app = SawmillApp(
            severity_levels,
            waiver_file_path=waiver_path,
            plugin_name="vivado",
        )
        app._session_waivers = [
            Waiver(message_id="E-001", reason="test", author="test", date="2026-02-08"),
        ]
        app._save_waivers()

        content = waiver_path.read_text()
        assert "[metadata]" in content
        assert 'tool = "vivado"' in content
