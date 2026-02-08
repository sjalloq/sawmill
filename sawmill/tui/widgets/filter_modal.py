"""Filter modal for sawmill TUI.

This module provides a modal dialog for configuring severity filters
and regex patterns, driven dynamically by the plugin's severity levels.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from sawmill.models.plugin_api import SeverityLevel


class FilterModal(ModalScreen[dict | None]):
    """Modal screen for configuring message filters.

    Displays a checkbox for each severity level (dynamically from plugin)
    and a regex pattern input field.

    On Apply: dismisses with {"severity_filter": {id: bool, ...}, "pattern": str}
    On Cancel/Escape: dismisses with None.
    """

    DEFAULT_CSS = """
    FilterModal {
        align: center middle;
    }

    #filter-modal-container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #filter-modal-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    .section-label {
        margin-top: 1;
        color: $text-muted;
        text-style: bold;
    }

    #filter-pattern-input {
        width: 100%;
        margin-top: 1;
    }

    #filter-modal-buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    #filter-modal-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        severity_levels: list[SeverityLevel],
        current_filter: dict | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the filter modal.

        Args:
            severity_levels: Severity level definitions from plugin.
            current_filter: Current filter state to pre-populate.
                Expected format: {"severity_filter": {id: bool}, "pattern": str}
        """
        super().__init__(*args, **kwargs)
        self._severity_levels = list(severity_levels)
        self._current_filter = current_filter or {}

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        current_severity = self._current_filter.get("severity_filter", {})
        current_pattern = self._current_filter.get("pattern", "")

        with Vertical(id="filter-modal-container"):
            yield Static("Filter Settings", id="filter-modal-title")

            yield Label("Severity Levels", classes="section-label")
            for level in sorted(self._severity_levels, key=lambda s: -s.level):
                checked = current_severity.get(level.id, True)
                yield Checkbox(
                    level.name,
                    value=checked,
                    id=f"sev-{level.id.replace('_', '-')}",
                )

            yield Label("Pattern (regex)", classes="section-label")
            yield Input(
                value=current_pattern,
                placeholder="Regex pattern to match...",
                id="filter-pattern-input",
            )

            with Horizontal(id="filter-modal-buttons"):
                yield Button("Apply", variant="primary", id="btn-apply")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-apply":
            self._apply()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)

    def _apply(self) -> None:
        """Collect filter state and dismiss with result."""
        severity_filter: dict[str, bool] = {}
        for level in self._severity_levels:
            checkbox_id = f"sev-{level.id.replace('_', '-')}"
            try:
                checkbox = self.query_one(f"#{checkbox_id}", Checkbox)
                severity_filter[level.id] = checkbox.value
            except Exception:
                severity_filter[level.id] = True

        pattern_input = self.query_one("#filter-pattern-input", Input)
        pattern = pattern_input.value

        self.dismiss({
            "severity_filter": severity_filter,
            "pattern": pattern,
        })
