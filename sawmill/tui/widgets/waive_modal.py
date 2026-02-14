"""Waive modal for sawmill TUI.

This module provides a modal dialog for creating waiver entries
for specific messages, with fields for content matching, reason,
and author information.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class WaiveModal(ModalScreen[dict | None]):
    """Modal screen for creating a waiver entry.

    Displays fields for message ID (read-only), content match type,
    content pattern, reason, and author.

    On confirm: dismisses with dict containing waiver field values.
    On cancel/Escape: dismisses with None.
    """

    DEFAULT_CSS = """
    WaiveModal {
        align: center middle;
    }

    #waive-modal-container {
        width: 70;
        height: auto;
        max-height: 80%;
    }

    .waive-field-label {
        margin-top: 1;
        color: $text-muted;
        text-style: bold;
    }

    .waive-field-value {
        padding: 0 1;
    }

    .waive-hint {
        color: $text-muted;
        text-style: italic;
        padding: 0 1;
    }

    .waive-error {
        color: $error;
        padding: 0 1;
    }

    #waive-content-match {
        height: auto;
        width: auto;
    }

    #waive-pattern-input { width: 100%; }
    #waive-reason-input  { width: 100%; }
    #waive-author-input  { width: 100%; }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
        ("f12", "screenshot", "Screenshot"),
    ]

    def __init__(
        self,
        message_id: str,
        severity: str,
        content: str,
        author: str = "",
        waiver_file_path: str = "",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._message_id = message_id
        self._severity = severity
        self._content = content
        self._author = author
        self._waiver_file_path = waiver_file_path

    def compose(self) -> ComposeResult:
        with Vertical(id="waive-modal-container", classes="modal-container"):
            yield Static("Waive Message", id="waive-modal-title", classes="modal-title")

            yield Label("Message ID:", classes="waive-field-label")
            yield Static(f"  {self._message_id}", classes="waive-field-value")

            yield Label("Severity:", classes="waive-field-label")
            yield Static(f"  {self._severity}", classes="waive-field-value")

            yield Label("Reason:", classes="waive-field-label")
            yield Input(
                value="",
                placeholder="Why is this waived?",
                id="waive-reason-input",
            )
            yield Static("", id="waive-reason-error", classes="waive-error")

            yield Label("Pattern:", classes="waive-field-label")
            yield Input(
                value=self._content,
                placeholder="(empty = match all with this ID)",
                id="waive-pattern-input",
            )
            yield Static("", id="waive-pattern-hint", classes="waive-hint")

            yield Label("Content match:", classes="waive-field-label")
            with Horizontal(id="waive-content-match"):
                yield Button(
                    "raw string", id="btn-raw", classes="content-match-btn content-match-selected"
                )
                yield Button("regex", id="btn-regex", classes="content-match-btn")

            yield Label("Author:", classes="waive-field-label")
            yield Input(
                value=self._author,
                placeholder="Your name or email",
                id="waive-author-input",
            )
            yield Static("", id="waive-author-error", classes="waive-error")

            if self._waiver_file_path:
                yield Label("File:", classes="waive-field-label")
                yield Static(f"  {self._waiver_file_path}", classes="waive-field-value")

            yield Static(
                "[bold $primary]Enter[/]  Save    [bold $primary]Escape[/]  Cancel",
                id="waive-modal-footer",
                classes="modal-footer",
            )

    def on_mount(self) -> None:
        """Focus the reason field on mount; only selected toggle is tab-focusable."""
        try:
            self.query_one("#btn-regex", Button).can_focus = False
            reason_input = self.query_one("#waive-reason-input", Input)
            reason_input.focus()
        except Exception:
            pass

    def _select_content_match(self, button: Button) -> None:
        """Select a content-match button and deselect the other."""
        for btn in self.query(".content-match-btn"):
            btn.remove_class("content-match-selected")
            btn.can_focus = False
        button.add_class("content-match-selected")
        button.can_focus = True
        button.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Toggle content-match button selection on click."""
        if "content-match-btn" in event.button.classes:
            event.stop()
            self._select_content_match(event.button)

    def on_key(self, event) -> None:
        """Arrow keys switch content-match selection when a toggle button is focused."""
        focused = self.focused
        if focused is None or "content-match-btn" not in focused.classes:
            return
        if event.key in ("left", "right"):
            event.stop()
            event.prevent_default()
            other_id = "btn-regex" if focused.id == "btn-raw" else "btn-raw"
            self._select_content_match(self.query_one(f"#{other_id}", Button))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter on any input field as modal confirm."""
        event.stop()
        self.action_confirm()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_screenshot(self) -> None:
        """Save a screenshot as SVG (delegates to the app)."""
        saved = self.app.save_screenshot()
        self.app.notify(f"Screenshot saved: {saved}")

    def action_confirm(self) -> None:
        """Validate and confirm the waiver."""
        # Get field values
        reason_input = self.query_one("#waive-reason-input", Input)
        author_input = self.query_one("#waive-author-input", Input)
        pattern_input = self.query_one("#waive-pattern-input", Input)
        reason = reason_input.value.strip()
        author = author_input.value.strip()
        pattern = pattern_input.value

        # Determine content_match from button selection
        raw_btn = self.query_one("#btn-raw", Button)
        content_match = "raw" if raw_btn.has_class("content-match-selected") else "regex"

        # Clear previous errors
        self.query_one("#waive-reason-error", Static).update("")
        self.query_one("#waive-author-error", Static).update("")
        self.query_one("#waive-pattern-hint", Static).update("")

        # Validate
        if not reason:
            self.query_one("#waive-reason-error", Static).update("Reason is required")
            reason_input.focus()
            return

        if not author:
            self.query_one("#waive-author-error", Static).update("Author is required")
            author_input.focus()
            return

        if content_match == "regex" and pattern:
            try:
                re.compile(pattern)
            except re.error:
                self.query_one("#waive-pattern-hint", Static).update("Invalid regex")
                pattern_input.focus()
                return

        # Build result
        result: dict = {
            "message_id": self._message_id,
            "reason": reason,
            "author": author,
        }

        # Only include content_match/content_pattern if pattern is non-empty
        if pattern:
            result["content_match"] = content_match
            result["content_pattern"] = pattern

        self.dismiss(result)
