"""Waive modal for sawmill TUI.

This module provides a modal dialog that builds one rule for a message:
scope, match, count limit, comment, destination file and author. The app
appends the rule to the chosen file and re-applies rules.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from sawmill.models.rule import Rule

_SCOPES = {"btn-scope-log": "log", "btn-scope-target": "target", "btn-scope-plugin": "plugin"}
_MATCHES = {"btn-match-id": "id", "btn-match-substring": "substring", "btn-match-regex": "regex"}
_PERS = {"btn-per-log": "log", "btn-per-target": "target"}
_GROUPS = ("scope-btn", "match-btn", "per-btn")


class WaiveModal(ModalScreen[dict | None]):
    """Modal screen that builds a rule for one message.

    On confirm: dismisses with ``{"rule": Rule, "path": Path, "scope": str}``
    where scope is ``"log"``, ``"target"`` or ``"plugin"``.
    On cancel/Escape: dismisses with None.

    Attributes:
        target_files: Candidate destination files for log and target scope.
        plugin_files: Candidate destination files for plugin scope.
    """

    DEFAULT_CSS = """
    WaiveModal {
        align: center middle;
    }

    #waive-modal-container {
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

    .waive-hint {
        color: $text-muted;
        text-style: italic;
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

    #waive-pattern-input { width: 100%; }
    #waive-count-input   { width: 12; }
    #waive-comment-input { width: 100%; }
    #waive-author-input  { width: 100%; }
    #waive-dest-select   { width: 100%; }
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
        log_rel_path: str,
        target_files: list[Path],
        plugin_files: list[Path],
        author: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._message_id = message_id
        self._severity = severity
        lines = content.strip().splitlines()
        self._pattern = lines[0].strip() if lines else ""
        self._log_rel_path = log_rel_path
        self.target_files = list(target_files)
        self.plugin_files = list(plugin_files)
        self._author = author
        self._date = date.today().isoformat()
        self._scope = "target" if self.target_files else "plugin"

    # -- Compose -------------------------------------------------------------

    def _files_for(self, scope: str) -> list[Path]:
        return self.plugin_files if scope == "plugin" else self.target_files

    def _dest_options(self) -> list[tuple[str, Path]]:
        return [(p.name, p) for p in self._files_for(self._scope)]

    def compose(self) -> ComposeResult:
        with Vertical(id="waive-modal-container", classes="modal-container"):
            yield Static("Waive Message", id="waive-modal-title", classes="modal-title")

            yield Label("Message:", classes="waive-field-label")
            yield Static(
                f"  {self._message_id}  ({self._severity})  {self._log_rel_path}",
                classes="waive-field-value",
                markup=False,
            )

            yield Label("Scope:", classes="waive-field-label")
            with Horizontal(id="waive-scope", classes="waive-group"):
                yield self._button("this log", "btn-scope-log", "scope-btn", "log")
                yield self._button("this target", "btn-scope-target", "scope-btn", "target")
                yield self._button(
                    "all targets using this plugin", "btn-scope-plugin", "scope-btn", "plugin"
                )

            yield Label("Match:", classes="waive-field-label")
            with Horizontal(id="waive-match", classes="waive-group"):
                yield self._group_button("id only", "btn-match-id", "match-btn", True)
                yield self._group_button("id + substring", "btn-match-substring", "match-btn")
                yield self._group_button("id + regex", "btn-match-regex", "match-btn")
            yield Input(
                value=self._pattern,
                placeholder="Substring or regex",
                id="waive-pattern-input",
                disabled=True,
            )

            yield Label("Max count:", classes="waive-field-label")
            with Horizontal(id="waive-count", classes="waive-group"):
                yield Input(value="", placeholder="none", id="waive-count-input")
                yield self._group_button("per log", "btn-per-log", "per-btn", True)
                yield self._group_button("per target", "btn-per-target", "per-btn")

            yield Label("Comment:", classes="waive-field-label")
            yield Input(value="", placeholder="Why is this waived?", id="waive-comment-input")

            yield Label("Destination:", classes="waive-field-label")
            options = self._dest_options()
            if options:
                yield Select(
                    options, allow_blank=False, value=options[-1][1], id="waive-dest-select"
                )
            else:
                yield Select([], id="waive-dest-select", disabled=True)

            yield Label("Author:", classes="waive-field-label")
            yield Input(value=self._author, placeholder="(optional)", id="waive-author-input")
            yield Label("Date:", classes="waive-field-label")
            yield Static(f"  {self._date}", classes="waive-field-value")

            no_files = not self.target_files and not self.plugin_files
            yield Static(
                "No rule file is listed for this target" if no_files else "",
                id="waive-error",
                classes="waive-error",
            )
            yield Static(
                "[bold $primary]Enter[/]  Save    [bold $primary]Escape[/]  Cancel",
                id="waive-modal-footer",
                classes="modal-footer",
            )

    def _button(self, label: str, button_id: str, group: str, scope: str) -> Button:
        button = self._group_button(label, button_id, group, scope == self._scope)
        button.disabled = not self._files_for(scope)
        return button

    @staticmethod
    def _group_button(label: str, button_id: str, group: str, selected: bool = False) -> Button:
        classes = f"waive-btn {group}" + (" waive-selected" if selected else "")
        button = Button(label, id=button_id, classes=classes)
        button.can_focus = selected
        return button

    def on_mount(self) -> None:
        """Focus the comment field and sync the count-dependent widgets."""
        self._sync_count()
        self.query_one("#waive-comment-input", Input).focus()

    # -- Button groups -------------------------------------------------------

    def _selected(self, group: str) -> Button:
        return next(
            b for b in self.query(f".{group}").results(Button) if b.has_class("waive-selected")
        )

    def _select(self, button: Button, focus: bool = True) -> None:
        """Select ``button`` within its group and apply the side effects."""
        group = next(g for g in _GROUPS if button.has_class(g))
        for other in self.query(f".{group}").results(Button):
            other.remove_class("waive-selected")
            other.can_focus = False
        button.add_class("waive-selected")
        button.can_focus = True
        if focus:
            button.focus()
        if group == "scope-btn":
            self._scope = _SCOPES[button.id or ""]
            select: Select[Path] = self.query_one("#waive-dest-select", Select)
            options = self._dest_options()
            select.set_options(options)
            if options:
                select.value = options[-1][1]
        elif group == "match-btn":
            self.query_one("#waive-pattern-input", Input).disabled = button.id == "btn-match-id"

    def _sync_count(self) -> None:
        has_count = bool(self.query_one("#waive-count-input", Input).value.strip())
        for button in self.query(".per-btn").results(Button):
            button.disabled = not has_count

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Select a group button on click."""
        if event.button.has_class("waive-btn"):
            event.stop()
            self._select(event.button)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Enable the per buttons only when a count is entered."""
        if event.input.id == "waive-count-input":
            self._sync_count()

    def on_key(self, event: events.Key) -> None:
        """Left/Right switch the selection when a group button is focused."""
        focused = self.focused
        if not isinstance(focused, Button) or not focused.has_class("waive-btn"):
            return
        if event.key not in ("left", "right"):
            return
        event.stop()
        event.prevent_default()
        group = next(g for g in _GROUPS if focused.has_class(g))
        buttons = [b for b in self.query(f".{group}").results(Button) if not b.disabled]
        if focused not in buttons or len(buttons) < 2:
            return
        step = 1 if event.key == "right" else -1
        self._select(buttons[(buttons.index(focused) + step) % len(buttons)])

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter on any input field as modal confirm."""
        event.stop()
        self.action_confirm()

    # -- Actions -------------------------------------------------------------

    def action_cancel(self) -> None:
        """Dismiss without a rule."""
        self.dismiss(None)

    def action_screenshot(self) -> None:
        """Save a screenshot as SVG (delegates to the app)."""
        saved = self.app.save_screenshot()
        self.app.notify(f"Screenshot saved: {saved}")

    def _error(self, text: str, focus: str | None = None) -> None:
        self.query_one("#waive-error", Static).update(text)
        if focus is not None:
            self.query_one(focus, Input).focus()

    def action_confirm(self) -> None:
        """Validate the fields and dismiss with the rule, path and scope."""
        self._error("")
        select: Select[Path] = self.query_one("#waive-dest-select", Select)
        path = select.value
        if not isinstance(path, Path):
            self._error("No rule file is listed for this target")
            return

        comment = self.query_one("#waive-comment-input", Input).value.strip()
        if not comment:
            self._error("Comment is required", "#waive-comment-input")
            return

        match = _MATCHES[self._selected("match-btn").id or ""]
        regex: str | None = None
        if match != "id":
            pattern = self.query_one("#waive-pattern-input", Input).value
            if not pattern:
                self._error("Pattern is required for this match", "#waive-pattern-input")
                return
            if match == "substring":
                regex = re.escape(pattern)
            else:
                try:
                    re.compile(pattern)
                except re.error as e:
                    self._error(f"Invalid regex: {e}", "#waive-pattern-input")
                    return
                regex = pattern

        fields: dict[str, Any] = {}
        count_text = self.query_one("#waive-count-input", Input).value.strip()
        if count_text:
            try:
                count = int(count_text)
            except ValueError:
                count = 0
            if count < 1:
                self._error("Max count must be an integer >= 1", "#waive-count-input")
                return
            fields["max_count"] = count
            fields["per"] = _PERS[self._selected("per-btn").id or ""]

        author = self.query_one("#waive-author-input", Input).value.strip()
        if author:
            fields["author"] = author
        if self._scope == "log":
            fields["logs"] = [self._log_rel_path]
        try:
            rule = Rule(
                id=self._message_id,
                regex=regex,
                comment=comment,
                date=self._date,
                **fields,
            )
        except ValidationError as e:
            self._error(f"Invalid rule: {e.errors()[0]['msg']}")
            return
        self.dismiss({"rule": rule, "path": path, "scope": self._scope})
