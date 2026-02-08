"""Tests for TUI waive functionality."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.app import MessageStats, SawmillApp
from sawmill.tui.widgets.waive_modal import WaiveModal
from sawmill.utils.author import discover_author


@pytest.fixture
def severity_levels():
    """Standard Vivado-like severity levels for tests."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


def make_message(
    content: str,
    severity: str | None = None,
    message_id: str | None = None,
    line: int = 1,
) -> Message:
    """Create a test message."""
    return Message(
        start_line=line,
        end_line=line,
        raw_text=content,
        content=content,
        severity=severity,
        message_id=message_id,
    )


class TestDiscoverAuthor:
    """Tests for author discovery utility."""

    def test_env_var_takes_precedence(self):
        """SAWMILL_AUTHOR env var is used first."""
        with patch.dict("os.environ", {"SAWMILL_AUTHOR": "env_author@test.com"}):
            assert discover_author() == "env_author@test.com"

    def test_git_email_fallback(self):
        """Falls back to git config user.email."""
        with patch.dict("os.environ", {}, clear=True), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "git@email.com\n"
            result = discover_author()
            assert result == "git@email.com"

    def test_git_name_fallback(self):
        """Falls back to git config user.name when email is empty."""
        with patch.dict("os.environ", {}, clear=True), patch("subprocess.run") as mock_run:

            def side_effect(*args, **kwargs):
                cmd = args[0]
                result = type("Result", (), {"returncode": 0, "stdout": ""})()
                if "user.email" in cmd:
                    result.stdout = ""
                    result.returncode = 1
                elif "user.name" in cmd:
                    result.stdout = "Git User\n"
                return result

            mock_run.side_effect = side_effect
            result = discover_author()
            assert result == "Git User"

    def test_empty_when_nothing_found(self):
        """Returns empty string when no author can be discovered."""
        with patch.dict("os.environ", {}, clear=True), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            result = discover_author()
            assert result == ""

    def test_handles_git_not_found(self):
        """Handles FileNotFoundError when git is not installed."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            result = discover_author()
            assert result == ""


class TestWaiveModalInit:
    """Tests for WaiveModal initialization."""

    def test_init_basic(self):
        """WaiveModal can be initialized with basic parameters."""
        modal = WaiveModal(
            message_id="Synth 8-3332",
            severity="Warning",
            content="some warning content",
        )
        assert modal._message_id == "Synth 8-3332"
        assert modal._severity == "Warning"
        assert modal._content == "some warning content"

    def test_init_with_author(self):
        """WaiveModal accepts pre-filled author."""
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
            author="test@example.com",
        )
        assert modal._author == "test@example.com"

    def test_init_with_waiver_file_path(self):
        """WaiveModal accepts waiver file path."""
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
            waiver_file_path="/path/to/waivers.toml",
        )
        assert modal._waiver_file_path == "/path/to/waivers.toml"

    def test_import_from_widgets_package(self):
        """WaiveModal can be imported from widgets package."""
        from sawmill.tui.widgets import WaiveModal as WM

        assert WM is WaiveModal


class TestWaiveState:
    """Tests for waive state management in SawmillApp."""

    def test_initial_session_waivers_empty(self, severity_levels):
        """Session waivers list starts empty."""
        app = SawmillApp(severity_levels)
        assert app._session_waivers == []

    def test_initial_waived_ids_empty(self, severity_levels):
        """Waived IDs set starts empty."""
        app = SawmillApp(severity_levels)
        assert app.waived_ids == set()

    def test_initial_waivers_dirty_false(self, severity_levels):
        """Waivers dirty flag starts as False."""
        app = SawmillApp(severity_levels)
        assert app._waivers_dirty is False

    def test_default_waiver_file_path(self, severity_levels):
        """Default waiver file path is ./waivers.toml."""
        app = SawmillApp(severity_levels)
        assert app._waiver_file_path == Path("./waivers.toml")

    def test_custom_waiver_file_path(self, severity_levels):
        """Custom waiver file path from constructor."""
        app = SawmillApp(severity_levels, waiver_file_path=Path("/custom/waivers.toml"))
        assert app._waiver_file_path == Path("/custom/waivers.toml")


class TestWaiveKeybinding:
    """Tests for waive keybinding."""

    def test_waive_binding_is_w(self, severity_levels):
        """Waive is bound to 'w'."""
        app = SawmillApp(severity_levels)
        binding_keys = {b.key: b.action for b in app.BINDINGS}
        assert binding_keys.get("w") == "waive"


class TestActionWaive:
    """Tests for the waive action logic."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error in module A", severity="error", message_id="E-001", line=1),
            make_message("No ID message", severity="info", line=2),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_waive_message_without_id(self, app):
        """Cannot waive a message without message_id."""
        app._apply_filters()
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 1})()
        app.action_waive()
        # Should not have opened modal or changed state
        assert len(app._session_waivers) == 0

    def test_waive_no_filtered_messages(self, app):
        """Waive does nothing when there are no filtered messages."""
        app._filtered_messages = []
        app._log_viewer = type("FakeViewer", (), {"cursor_row": 0})()
        app.action_waive()
        assert len(app._session_waivers) == 0


class TestOnWaiveModalResult:
    """Tests for handling waive modal results."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error in module A", severity="error", message_id="E-001", line=1),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_result_none_does_nothing(self, app):
        """Cancelling the modal (None result) changes nothing."""
        app._on_waive_modal_result(None)
        assert len(app._session_waivers) == 0
        assert app._waivers_dirty is False

    def test_result_creates_waiver(self, app):
        """Valid modal result creates a waiver."""
        result = {
            "message_id": "E-001",
            "content_match": "raw",
            "content_pattern": "Error in module A",
            "reason": "Known issue",
            "author": "test@example.com",
        }
        app._on_waive_modal_result(result)

        assert len(app._session_waivers) == 1
        waiver = app._session_waivers[0]
        assert waiver.message_id == "E-001"
        assert waiver.content_match == "raw"
        assert waiver.content_pattern == "Error in module A"
        assert waiver.reason == "Known issue"
        assert waiver.author == "test@example.com"
        assert waiver.date == date.today().isoformat()

    def test_result_adds_to_waived_ids(self, app):
        """Modal result adds message ID to waived IDs set."""
        result = {
            "message_id": "E-001",
            "reason": "test",
            "author": "test",
        }
        app._on_waive_modal_result(result)
        assert "E-001" in app.waived_ids

    def test_result_sets_dirty_flag(self, app):
        """Modal result marks waivers as dirty."""
        result = {
            "message_id": "E-001",
            "reason": "test",
            "author": "test",
        }
        app._on_waive_modal_result(result)
        assert app._waivers_dirty is True

    def test_result_without_content_pattern(self, app):
        """Modal result without content pattern creates catch-all waiver."""
        result = {
            "message_id": "E-001",
            "reason": "Match all instances",
            "author": "test",
        }
        app._on_waive_modal_result(result)
        waiver = app._session_waivers[0]
        assert waiver.content_match is None
        assert waiver.content_pattern is None

    def test_multiple_waivers(self, app):
        """Can create multiple waivers in a session."""
        for i in range(3):
            result = {
                "message_id": f"E-{i:03d}",
                "reason": f"reason {i}",
                "author": "test",
            }
            app._on_waive_modal_result(result)
        assert len(app._session_waivers) == 3
        assert len(app.waived_ids) == 3


class TestMessageStatsWaived:
    """Tests for waived count in MessageStats widget."""

    def test_waived_count_default(self, severity_levels):
        """Waived count defaults to 0."""
        stats = MessageStats(severity_levels=severity_levels)
        assert stats.waived_count == 0

    def test_waived_count_in_render(self, severity_levels):
        """Waived count appears in render when > 0."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3}
        stats.waived_count = 3
        output = stats.render()
        assert "3 waived" in output

    def test_waived_count_hidden_when_zero(self, severity_levels):
        """Waived count not shown when 0."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.counts = {"error": 3}
        stats.waived_count = 0
        output = stats.render()
        assert "waived" not in output

    def test_both_waived_and_suppressed(self, severity_levels):
        """Both waived and suppressed counts shown when both > 0."""
        stats = MessageStats(severity_levels=severity_levels)
        stats.total = 10
        stats.waived_count = 3
        stats.suppressed_count = 5
        output = stats.render()
        assert "3 waived" in output
        assert "5 suppressed" in output


class TestWaivedDisplay:
    """Tests for waived message visual treatment."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_waived_messages_remain_visible(self, app):
        """Waived messages are not hidden from the filtered list."""
        app.waived_ids = {"E-001"}
        app._apply_filters()
        assert len(app.filtered_messages) == 2
        assert any(m.message_id == "E-001" for m in app.filtered_messages)
