"""Help modal for sawmill TUI.

Displays keybinding reference when the user presses '?'.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = (
    "[bold $primary]q[/]          Quit\n"
    "[bold $primary]/[/]          Search / filter messages\n"
    "[bold $primary]Escape[/]     Clear filter\n"
    "[bold $primary]Tab[/]        Toggle focus\n"
    "[bold $primary]1-4[/]        Toggle severity levels\n"
    "[bold $primary]o[/]          Cycle sort mode\n"
    "[bold $primary]\u2190 \u2192[/]        Switch tab\n"
    "[bold $primary]s[/]          Suppress / Un-suppress\n"
    "[bold $primary]w[/]          Waive / Un-waive\n"
    "[bold $primary]Ctrl+S[/]     Save suppressions & waivers\n"
    "[bold $primary]F12[/]        Screenshot (SVG)\n"
    "[bold $primary]?[/]          This help"
)


class HelpModal(ModalScreen[None]):
    """Modal screen showing keybinding reference."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    #help-modal-container {
        width: 50;
        height: auto;
        max-height: 80%;
    }

    #help-modal-bindings {
        padding: 0 2;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
        ("f12", "screenshot", "Screenshot"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-modal-container", classes="modal-container"):
            yield Static("Keybindings", id="help-modal-title", classes="modal-title")
            yield Static(HELP_TEXT, id="help-modal-bindings")
            yield Static(
                "Press [bold $primary]?[/] or [bold $primary]Escape[/] to close",
                classes="modal-footer",
            )

    def action_close(self) -> None:
        self.dismiss(None)

    def action_screenshot(self) -> None:
        saved = self.app.save_screenshot()
        self.app.notify(f"Screenshot saved: {saved}")
