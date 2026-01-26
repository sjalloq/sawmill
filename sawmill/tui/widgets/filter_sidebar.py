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

from sawmill.models.plugin_api import SeverityLevel


class FilterChanged(Message):
    """Message emitted when filter settings change.

    Attributes:
        severity_filter: Dictionary mapping severity ID to show/hide state.
        pattern: The regex filter pattern.
    """

    def __init__(
        self,
        severity_filter: dict[str, bool],
        pattern: str,
    ) -> None:
        """Initialize the message."""
        super().__init__()
        self.severity_filter = severity_filter
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
    - Severity toggles (checkboxes from plugin severity levels)
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
    """

    # Reactive properties for filter state
    pattern: reactive[str] = reactive("")

    def __init__(
        self,
        severity_levels: list[SeverityLevel],
        *args,
        **kwargs,
    ):
        """Initialize the sidebar.

        Args:
            severity_levels: Severity level definitions from plugin (required).
        """
        super().__init__(*args, **kwargs)
        if not severity_levels:
            raise ValueError("severity_levels is required and cannot be empty")
        self._severity_levels = list(severity_levels)
        # Initialize filter state: all severities shown by default
        self._severity_filter: dict[str, bool] = {
            level.id: True for level in self._severity_levels
        }

    def _apply_severity_style(self, widget: Checkbox, style: str) -> None:
        """Apply a Rich-format style string to a widget.

        Parses Rich style format (e.g., "red bold") and applies to Textual widget styles.

        Args:
            widget: The widget to style.
            style: Rich-format style string (e.g., "red", "red bold", "yellow").
        """
        if not style:
            return

        parts = style.lower().split()
        for part in parts:
            if part == "bold":
                widget.styles.text_style = "bold"
            elif part == "italic":
                widget.styles.text_style = "italic"
            elif part == "underline":
                widget.styles.text_style = "underline"
            else:
                # Assume it's a color
                widget.styles.color = part

    def compose(self) -> ComposeResult:
        """Create the sidebar layout with dynamic severity checkboxes."""
        yield Label("Filters")

        yield Label("Severity", classes="section-label")

        # Create checkboxes dynamically from severity levels (sorted by level descending)
        for level in sorted(self._severity_levels, key=lambda x: -x.level):
            checkbox_id = f"chk-{level.id.replace('_', '-')}"
            checkbox = SeverityCheckbox(
                level.name,
                severity=level.id,
                value=True,
                id=checkbox_id,
            )
            # Apply style from plugin's SeverityLevel.style (Rich format like "red bold")
            self._apply_severity_style(checkbox, level.style)
            yield checkbox

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
            self._severity_filter[severity] = event.value
            self._emit_filter_changed()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle pattern input changes."""
        if event.input.id == "pattern-input":
            self.pattern = event.value
            self._emit_filter_changed()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle quick filter button presses."""
        if event.button.id == "btn-errors-only":
            # Show only severities with level >= 2 (error, critical_warning)
            self._set_severity_by_level(min_level=2)
        elif event.button.id == "btn-warnings-plus":
            # Show severities with level >= 1 (warning and above)
            self._set_severity_by_level(min_level=1)
        elif event.button.id == "btn-show-all":
            self._set_all_severities(show=True)
        elif event.button.id == "btn-clear":
            self._set_all_severities(show=True)
            self.pattern = ""
            pattern_input = self.query_one("#pattern-input", Input)
            pattern_input.value = ""

    def _set_severity_by_level(self, min_level: int) -> None:
        """Set severity filters based on minimum level threshold.

        Args:
            min_level: Minimum severity level to show.
        """
        for level in self._severity_levels:
            show = level.level >= min_level
            self._severity_filter[level.id] = show

            # Update checkbox
            checkbox_id = f"#chk-{level.id.replace('_', '-')}"
            try:
                self.query_one(checkbox_id, Checkbox).value = show
            except Exception:
                pass  # Checkbox may not exist

        self._emit_filter_changed()

    def _set_all_severities(self, show: bool) -> None:
        """Set all severity filters to the same value.

        Args:
            show: Whether to show all severities.
        """
        for level in self._severity_levels:
            self._severity_filter[level.id] = show

            # Update checkbox
            checkbox_id = f"#chk-{level.id.replace('_', '-')}"
            try:
                self.query_one(checkbox_id, Checkbox).value = show
            except Exception:
                pass  # Checkbox may not exist

        self._emit_filter_changed()

    def _emit_filter_changed(self) -> None:
        """Emit a FilterChanged message with current settings."""
        self.post_message(FilterChanged(
            severity_filter=self._severity_filter.copy(),
            pattern=self.pattern,
        ))

    def get_filter_state(self) -> dict:
        """Get the current filter state as a dictionary.

        Returns:
            Dictionary with current filter settings including:
            - severity_filter: dict mapping severity ID to show/hide state
            - pattern: the regex filter pattern
        """
        return {
            "severity_filter": self._severity_filter.copy(),
            "pattern": self.pattern,
        }
