"""Rules file prompt for sawmill TUI.

Shown once per session in single-log mode when the log has no rules file:
asks for a rules file name and whether to create a manifest as well.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

_YES = "btn-manifest-yes"
_NO = "btn-manifest-no"


class RulesFilePrompt(ModalScreen[dict | None]):
    """Modal screen that asks where to store rules for a bare log.

    On confirm: dismisses with ``{"path": Path, "create_manifest": bool}``.
    On cancel/Escape: dismisses with None.
    """

    DEFAULT_CSS = """
    RulesFilePrompt {
        align: center middle;
    }

    #rules-prompt-container {
        width: 80;
        height: auto;
        max-height: 90%;
        overflow-y: auto;
    }

    .waive-field-label {
        margin-top: 1;
        color: $text-muted;
        text-style: bold;
    }

    .waive-field-value {
        padding: 0 1;
    }

    .waive-error {
        color: $error;
        padding: 0 1;
    }

    .waive-group {
        height: auto;
        width: auto;
    }

    .waive-selected {
        text-style: bold reverse;
    }

    #rules-name-input { width: 100%; }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
        ("f12", "screenshot", "Screenshot"),
    ]

    def __init__(
        self,
        rules_dir: Path,
        default_name: str,
        log_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._rules_dir = rules_dir
        self._default_name = default_name
        self._log_name = log_name
        self._create_manifest = False

    def compose(self) -> ComposeResult:
        with Vertical(id="rules-prompt-container", classes="modal-container"):
            yield Static("Rules File", id="rules-prompt-title", classes="modal-title")
            yield Label("Log:", classes="waive-field-label")
            yield Static(f"  {self._log_name}", classes="waive-field-value", markup=False)
            yield Label("Directory:", classes="waive-field-label")
            yield Static(f"  {self._rules_dir}", classes="waive-field-value", markup=False)
            yield Label("Rules file:", classes="waive-field-label")
            yield Input(value=self._default_name, id="rules-name-input")
            yield Label("Manifest:", classes="waive-field-label")
            with Horizontal(id="rules-prompt-manifest", classes="waive-group"):
                yield self._group_button(
                    "Create manifest (.sawmill/manifest.toml) with this log as a target", _YES
                )
                yield self._group_button("Rules file only", _NO, selected=True)
            yield Static("", id="rules-prompt-error", classes="waive-error")
            yield Static(
                "[bold $primary]Enter[/]  Confirm    [bold $primary]Escape[/]  Cancel",
                id="rules-prompt-footer",
                classes="modal-footer",
            )

    @staticmethod
    def _group_button(label: str, button_id: str, selected: bool = False) -> Button:
        classes = "waive-btn manifest-btn" + (" waive-selected" if selected else "")
        button = Button(label, id=button_id, classes=classes)
        button.can_focus = selected
        return button

    def on_mount(self) -> None:
        """Focus the name field."""
        self.query_one("#rules-name-input", Input).focus()

    def _select(self, button: Button) -> None:
        for other in self.query(".manifest-btn").results(Button):
            other.remove_class("waive-selected")
            other.can_focus = False
        button.add_class("waive-selected")
        button.can_focus = True
        button.focus()
        self._create_manifest = button.id == _YES

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Select a manifest choice on click."""
        if event.button.has_class("manifest-btn"):
            event.stop()
            self._select(event.button)

    def on_key(self, event: events.Key) -> None:
        """Left/Right switch the manifest choice; Enter on a choice confirms."""
        focused = self.focused
        if not isinstance(focused, Button) or not focused.has_class("manifest-btn"):
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.action_confirm()
            return
        if event.key not in ("left", "right"):
            return
        event.stop()
        event.prevent_default()
        target = _NO if focused.id == _YES else _YES
        self._select(self.query_one(f"#{target}", Button))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter in the name field as confirm."""
        event.stop()
        self.action_confirm()

    def action_cancel(self) -> None:
        """Dismiss without a choice."""
        self.dismiss(None)

    def action_screenshot(self) -> None:
        """Save a screenshot as SVG (delegates to the app)."""
        saved = self.app.save_screenshot()
        self.app.notify(f"Screenshot saved: {saved}")

    def action_confirm(self) -> None:
        """Validate the name and dismiss with the path and manifest choice."""
        error = self.query_one("#rules-prompt-error", Static)
        name = self.query_one("#rules-name-input", Input).value.strip()
        if not name.endswith(".toml") or name == ".toml":
            error.update("File name must end in .toml")
            return
        if "/" in name or "\\" in name:
            error.update("File name must not contain a path separator")
            return
        error.update("")
        self.dismiss({"path": self._rules_dir / name, "create_manifest": self._create_manifest})
