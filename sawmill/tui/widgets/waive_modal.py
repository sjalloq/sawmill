"""Waive modal for sawmill TUI.

This module provides a modal dialog for creating waiver entries
for specific messages, with fields for content matching, reason,
and author information.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, RadioButton, RadioSet, Static


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
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #waive-modal-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
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

    #waive-content-match RadioSet {
        height: auto;
        width: 100%;
        background: transparent;
    }

    #waive-pattern-input {
        width: 100%;
    }

    #waive-reason-input {
        width: 100%;
    }

    #waive-author-input {
        width: 100%;
    }

    #waive-modal-footer {
        margin-top: 1;
        height: 1;
        width: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
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
        with Vertical(id="waive-modal-container"):
            yield Static("Waive Message", id="waive-modal-title")

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
            with RadioSet(id="waive-content-match"):
                yield RadioButton("raw string", value=True, id="radio-raw")
                yield RadioButton("regex", id="radio-regex")

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
                "Enter: Save    Escape: Cancel",
                id="waive-modal-footer",
            )

    def on_mount(self) -> None:
        """Focus the reason field on mount."""
        try:
            reason_input = self.query_one("#waive-reason-input", Input)
            reason_input.focus()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter on any input field as modal confirm."""
        event.stop()
        self.action_confirm()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Validate and confirm the waiver."""
        # Get field values
        reason_input = self.query_one("#waive-reason-input", Input)
        author_input = self.query_one("#waive-author-input", Input)
        pattern_input = self.query_one("#waive-pattern-input", Input)
        reason = reason_input.value.strip()
        author = author_input.value.strip()
        pattern = pattern_input.value

        # Determine content_match from radio selection
        raw_radio = self.query_one("#radio-raw", RadioButton)
        content_match = "raw" if raw_radio.value else "regex"

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
