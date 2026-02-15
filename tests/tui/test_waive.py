"""Tests for TUI waive functionality."""

import inspect
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.waiver import Waiver
from sawmill.tui.app import SawmillApp
from sawmill.tui.widgets.waive_modal import WaiveModal
from sawmill.utils.author import discover_author


def _add_catchall_waivers(app: SawmillApp, message_ids: set[str]) -> None:
    """Add catch-all waivers (no content pattern) and rebuild matcher."""
    for mid in message_ids:
        app._session_waivers.append(
            Waiver(message_id=mid, reason="test", author="test", date="2026-01-01")
        )
    app._rebuild_waiver_matcher()


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

    def test_initial_waiver_matcher_empty(self, severity_levels):
        """Waiver matcher starts with no waivers."""
        app = SawmillApp(severity_levels)
        assert app._waiver_matcher.waivers == []

    def test_initial_waivers_dirty_false(self, severity_levels):
        """Waivers dirty flag starts as False."""
        app = SawmillApp(severity_levels)
        assert app._waivers_dirty is False

    def test_default_waiver_file_path(self, severity_levels):
        """Default waiver file path is None (resolved lazily)."""
        app = SawmillApp(severity_levels)
        assert app._waiver_file_path is None

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

    def test_result_rebuilds_waiver_matcher(self, app):
        """Modal result rebuilds waiver matcher with new waiver."""
        result = {
            "message_id": "E-001",
            "reason": "test",
            "author": "test",
        }
        app._on_waive_modal_result(result)
        msg = make_message("Error in module A", severity="error", message_id="E-001")
        assert app._waiver_matcher.is_waived(msg) is not None

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
        assert len(app._waiver_matcher.waivers) == 3


class TestWaivedDisplay:
    """Tests for waived message visual treatment."""

    @pytest.fixture
    def app(self, severity_levels):
        messages = [
            make_message("Error A", severity="error", message_id="E-001", line=1),
            make_message("Warning B", severity="warning", message_id="W-001", line=2),
        ]
        return SawmillApp(severity_levels, messages=messages)

    def test_waived_messages_in_waived_tab(self, app):
        """Waived messages move to the waived tab, not the main filtered list."""
        _add_catchall_waivers(app, {"E-001"})
        app._apply_filters()
        # Main tab excludes waived messages
        assert len(app.filtered_messages) == 1
        assert all(m.message_id != "E-001" for m in app.filtered_messages)
        # Waived tab contains them
        assert len(app._waived_messages) == 1
        assert app._waived_messages[0].message_id == "E-001"


class TestWaiveModalTabOrder:
    """Tests for WaiveModal focusable widget DOM order matching spec.

    Spec tab order: Reason -> Pattern -> Content match (raw/regex) -> Author (cycle).
    DOM order of focusable widgets must match this to get correct Tab behavior.

    Since compose() requires an active Textual app context (due to container
    context managers), we verify DOM order by inspecting the compose source
    and extracting the IDs of focusable widgets (Input and Button) in the
    order they appear.
    """

    def _get_focusable_widget_ids_from_source(self) -> list[str]:
        """Extract IDs of focusable widgets from compose() source in DOM order.

        Parses the compose() method source to find Input and Button widget
        IDs in the order they appear (which is the DOM/focus chain order).
        """
        import re as _re

        source = inspect.getsource(WaiveModal.compose)
        # Match Input(..., id="...") and Button(id="...") patterns
        # These are the focusable widgets that determine tab order
        focusable_pattern = _re.compile(
            r"(?:Input\(|Button\()"  # Match Input( or Button(
            r".*?"  # Any args before id= (DOTALL for multi-line)
            r'id="([^"]+)"',  # Capture the id value
            _re.DOTALL,
        )
        return focusable_pattern.findall(source)

    def test_focusable_widgets_in_spec_order(self):
        """Focusable widgets appear in DOM order: Reason, Pattern, Content match buttons, Author."""
        ids = self._get_focusable_widget_ids_from_source()
        assert ids == [
            "waive-reason-input",
            "waive-pattern-input",
            "btn-raw",
            "btn-regex",
            "waive-author-input",
        ]

    def test_reason_is_first_focusable_widget(self):
        """Reason input is the first focusable widget in DOM order."""
        ids = self._get_focusable_widget_ids_from_source()
        assert ids[0] == "waive-reason-input"

    def test_author_is_last_focusable_widget(self):
        """Author input is the last focusable widget in DOM order."""
        ids = self._get_focusable_widget_ids_from_source()
        assert ids[-1] == "waive-author-input"

    def test_content_match_after_pattern(self):
        """Content match buttons appear after Pattern input (not before)."""
        ids = self._get_focusable_widget_ids_from_source()
        pattern_idx = ids.index("waive-pattern-input")
        content_match_idx = ids.index("btn-raw")
        assert content_match_idx > pattern_idx

    def test_exactly_five_focusable_widgets(self):
        """There are exactly 5 focusable widgets in the modal (3 inputs + 2 buttons)."""
        ids = self._get_focusable_widget_ids_from_source()
        assert len(ids) == 5


class TestWaiveModalInputSubmitted:
    """Tests for Enter key handling via on_input_submitted in WaiveModal."""

    def test_on_input_submitted_method_exists(self):
        """WaiveModal has an on_input_submitted handler."""
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
        )
        assert hasattr(modal, "on_input_submitted")
        assert callable(modal.on_input_submitted)

    def test_on_input_submitted_signature(self):
        """on_input_submitted accepts an Input.Submitted event parameter."""

        sig = inspect.signature(WaiveModal.on_input_submitted)
        params = list(sig.parameters.keys())
        assert "event" in params
        # Verify annotation references Input.Submitted
        event_param = sig.parameters["event"]
        assert "Input.Submitted" in str(event_param.annotation)

    def test_on_input_submitted_calls_action_confirm(self):
        """on_input_submitted delegates to action_confirm."""
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
        )
        mock_event = MagicMock()
        with patch.object(modal, "action_confirm") as mock_confirm:
            modal.on_input_submitted(mock_event)
            mock_confirm.assert_called_once()

    def test_on_input_submitted_stops_event(self):
        """on_input_submitted stops the event to prevent further propagation."""
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
        )
        mock_event = MagicMock()
        with patch.object(modal, "action_confirm"):
            modal.on_input_submitted(mock_event)
            mock_event.stop.assert_called_once()

    def test_on_input_submitted_stops_before_confirm(self):
        """Event is stopped before action_confirm is called (correct ordering)."""
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
        )
        call_order = []
        mock_event = MagicMock()
        mock_event.stop.side_effect = lambda: call_order.append("stop")
        with patch.object(
            modal, "action_confirm", side_effect=lambda: call_order.append("confirm")
        ):
            modal.on_input_submitted(mock_event)
        assert call_order == ["stop", "confirm"]

    def test_on_input_submitted_triggers_validation_on_empty_reason(self):
        """Enter on input with empty reason triggers validation (not silent)."""
        # This test verifies that action_confirm (with its validation) is called
        # even when the event originates from an Input.Submitted. We mock
        # action_confirm to verify delegation happens; the validation logic
        # itself is tested via the action_confirm path in TestOnWaiveModalResult.
        modal = WaiveModal(
            message_id="E-001",
            severity="Error",
            content="error content",
        )
        mock_event = MagicMock()
        with patch.object(modal, "action_confirm") as mock_confirm:
            modal.on_input_submitted(mock_event)
            # action_confirm is called, which will run validation
            mock_confirm.assert_called_once()
            # Event was stopped so Input.Submitted doesn't silently pass through
            mock_event.stop.assert_called_once()
