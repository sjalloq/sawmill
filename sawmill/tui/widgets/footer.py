"""Custom footer widget for sawmill TUI.

Textual's built-in Footer ignores ANSI transparency, so we build
our own from HorizontalGroup + Static widgets per STYLE_SPEC.md §4.4.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import HorizontalGroup
from textual.widget import Widget
from textual.widgets import Static


class SawmillFooter(Widget):
    """Custom footer displaying keybinding hints.

    Args:
        bindings: List of (key, label) tuples to display.
    """

    DEFAULT_CSS = """
    SawmillFooter {
        dock: bottom;
        height: 1;
        background: transparent;
    }

    SawmillFooter > HorizontalGroup {
        background: transparent;
        height: 1;
    }

    SawmillFooter .footer-key {
        color: $primary;
        text-style: bold;
        width: auto;
    }

    SawmillFooter .footer-label {
        color: $text;
        width: auto;
        padding: 0 1 0 0;
    }
    """

    def __init__(
        self,
        bindings: list[tuple[str, str]] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._bindings = bindings or []

    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            for key, label in self._bindings:
                yield Static(f" {key} ", classes="footer-key")
                yield Static(label, classes="footer-label")

    def update_bindings(self, bindings: list[tuple[str, str]]) -> None:
        """Replace the displayed bindings and re-render."""
        self._bindings = bindings
        self.query("HorizontalGroup").remove()
        self.mount(HorizontalGroup())
        group = self.query_one(HorizontalGroup)
        for key, label in self._bindings:
            group.mount(Static(f" {key} ", classes="footer-key"))
            group.mount(Static(label, classes="footer-label"))
