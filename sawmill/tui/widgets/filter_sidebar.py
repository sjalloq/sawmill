"""Filter sidebar widget for sawmill TUI.

This module provides the filter sidebar with severity toggles,
pattern input, and quick-filter presets.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Checkbox, Input, Button, Label


class FilterChanged(Message):
    """Message emitted when filter settings change.

    Attributes:
        show_info: Whether to show info messages.
        show_warning: Whether to show warning messages.
        show_error: Whether to show error messages.
        show_critical: Whether to show critical messages.
        pattern: The regex filter pattern.
    """

    def __init__(
        self,
        show_info: bool,
        show_warning: bool,
        show_error: bool,
        show_critical: bool,
        pattern: str,
    ) -> None:
        """Initialize the message."""
        super().__init__()
        self.show_info = show_info
        self.show_warning = show_warning
        self.show_error = show_error
        self.show_critical = show_critical
        self.pattern = pattern


class SeverityCheckbox(Checkbox):
    """Checkbox for severity level filtering."""

    def __init__(self, label: str, severity: str, value: bool = True, **kwargs):
        """Initialize the checkbox.

        Args:
            label: Display label for the checkbox.
            severity: The severity level this checkbox controls.
            value: Initial checked state.
        """
        super().__init__(label, value=value, **kwargs)
        self.severity = severity


class FilterSidebar(Static):
    """Sidebar widget for interactive filter controls.

    Features:
    - Severity toggles (checkboxes for error/warning/info/critical)
    - Pattern input for regex filtering
    - Quick-filter presets
    """

    DEFAULT_CSS = """
    FilterSidebar {
        width: 30;
        height: 100%;
        background: $surface;
        border-right: solid $primary;
        padding: 1;
    }

    FilterSidebar > Label {
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }

    FilterSidebar > .section-label {
        margin-top: 1;
        color: $text-muted;
    }

    FilterSidebar > Input {
        width: 100%;
        margin-bottom: 1;
    }

    FilterSidebar > Button {
        width: 100%;
        margin-top: 1;
    }

    .severity-critical {
        color: red;
        text-style: bold;
    }

    .severity-error {
        color: red;
    }

    .severity-warning {
        color: yellow;
    }

    .severity-info {
        color: cyan;
    }
    """

    # Reactive properties for filter state
    show_info: reactive[bool] = reactive(True)
    show_warning: reactive[bool] = reactive(True)
    show_error: reactive[bool] = reactive(True)
    show_critical: reactive[bool] = reactive(True)
    pattern: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        """Create the sidebar layout."""
        yield Label("Filters")

        yield Label("Severity", classes="section-label")
        yield SeverityCheckbox(
            "Critical",
            severity="critical",
            value=True,
            id="chk-critical",
            classes="severity-critical",
        )
        yield SeverityCheckbox(
            "Error",
            severity="error",
            value=True,
            id="chk-error",
            classes="severity-error",
        )
        yield SeverityCheckbox(
            "Warning",
            severity="warning",
            value=True,
            id="chk-warning",
            classes="severity-warning",
        )
        yield SeverityCheckbox(
            "Info",
            severity="info",
            value=True,
            id="chk-info",
            classes="severity-info",
        )

        yield Label("Pattern", classes="section-label")
        yield Input(placeholder="Regex pattern...", id="pattern-input")

        yield Label("Quick Filters", classes="section-label")
        yield Button("Errors Only", id="btn-errors-only", variant="error")
        yield Button("Warnings+", id="btn-warnings-plus", variant="warning")
        yield Button("Show All", id="btn-show-all", variant="default")
        yield Button("Clear", id="btn-clear", variant="default")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle severity checkbox changes."""
        if isinstance(event.checkbox, SeverityCheckbox):
            severity = event.checkbox.severity
            if severity == "info":
                self.show_info = event.value
            elif severity == "warning":
                self.show_warning = event.value
            elif severity == "error":
                self.show_error = event.value
            elif severity == "critical":
                self.show_critical = event.value

            self._emit_filter_changed()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle pattern input changes."""
        if event.input.id == "pattern-input":
            self.pattern = event.value
            self._emit_filter_changed()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle quick filter button presses."""
        if event.button.id == "btn-errors-only":
            self._set_severity_filters(info=False, warning=False, error=True, critical=True)
        elif event.button.id == "btn-warnings-plus":
            self._set_severity_filters(info=False, warning=True, error=True, critical=True)
        elif event.button.id == "btn-show-all":
            self._set_severity_filters(info=True, warning=True, error=True, critical=True)
        elif event.button.id == "btn-clear":
            self._set_severity_filters(info=True, warning=True, error=True, critical=True)
            self.pattern = ""
            pattern_input = self.query_one("#pattern-input", Input)
            pattern_input.value = ""

    def _set_severity_filters(
        self,
        info: bool,
        warning: bool,
        error: bool,
        critical: bool,
    ) -> None:
        """Set all severity filters at once."""
        self.show_info = info
        self.show_warning = warning
        self.show_error = error
        self.show_critical = critical

        # Update checkboxes to match
        self.query_one("#chk-info", Checkbox).value = info
        self.query_one("#chk-warning", Checkbox).value = warning
        self.query_one("#chk-error", Checkbox).value = error
        self.query_one("#chk-critical", Checkbox).value = critical

        self._emit_filter_changed()

    def _emit_filter_changed(self) -> None:
        """Emit a FilterChanged message with current settings."""
        self.post_message(FilterChanged(
            show_info=self.show_info,
            show_warning=self.show_warning,
            show_error=self.show_error,
            show_critical=self.show_critical,
            pattern=self.pattern,
        ))

    def get_filter_state(self) -> dict:
        """Get the current filter state as a dictionary.

        Returns:
            Dictionary with current filter settings.
        """
        return {
            "show_info": self.show_info,
            "show_warning": self.show_warning,
            "show_error": self.show_error,
            "show_critical": self.show_critical,
            "pattern": self.pattern,
        }
