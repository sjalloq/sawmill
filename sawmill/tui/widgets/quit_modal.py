"""Quit confirmation modal for sawmill TUI.

This module provides a modal dialog that prompts the user when
quitting with unsaved changes (suppressions or waivers).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class QuitConfirmModal(ModalScreen[str | None]):
    """Modal screen for confirming quit with unsaved changes.

    Shows what unsaved items exist and offers three options:
    - Enter: save and quit
    - q: quit without saving
    - Escape: cancel (return to TUI)

    Dismisses with "save_quit", "discard_quit", or None.
    """

    DEFAULT_CSS = """
    QuitConfirmModal {
        align: center middle;
    }

    #quit-modal-container {
        width: 55;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #quit-modal-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    .quit-item {
        padding: 0 2;
    }

    #quit-modal-options {
        margin-top: 1;
        padding: 0 2;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "save_quit", "Save and quit"),
        ("q", "discard_quit", "Quit without saving"),
    ]

    def __init__(
        self,
        suppression_count: int = 0,
        waiver_count: int = 0,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._suppression_count = suppression_count
        self._waiver_count = waiver_count

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-modal-container"):
            yield Static("Unsaved Changes", id="quit-modal-title")

            yield Static("You have unsaved changes:")
            if self._suppression_count > 0:
                yield Static(
                    f"  * {self._suppression_count} suppression rule"
                    + ("s" if self._suppression_count != 1 else ""),
                    classes="quit-item",
                )
            if self._waiver_count > 0:
                yield Static(
                    f"  * {self._waiver_count} waiver entr"
                    + ("ies" if self._waiver_count != 1 else "y"),
                    classes="quit-item",
                )

            yield Static("")
            yield Static(
                "Save and quit ............... Enter\n"
                "Quit without saving ......... q\n"
                "Cancel ...................... Escape",
                id="quit-modal-options",
            )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save_quit(self) -> None:
        self.dismiss("save_quit")

    def action_discard_quit(self) -> None:
        self.dismiss("discard_quit")
