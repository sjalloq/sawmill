"""Nord transparent theme for sawmill TUI.

Standalone Nord theme registration following STYLE_SPEC.md §6.
No external dependency on textual-tui-kit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App


def register_nord_theme(app: App, transparent: bool = True) -> None:
    """Register and activate the Nord theme.

    Args:
        app: The Textual application to register the theme on.
        transparent: If True, enable ANSI transparency so the
            terminal background shows through.
    """
    from textual.theme import Theme

    theme = Theme(
        name="nord-transparent",
        primary="#88C0D0",
        secondary="#81A1C1",
        accent="#B48EAD",
        foreground="#D8DEE9",
        success="#A3BE8C",
        warning="#EBCB8B",
        error="#BF616A",
        surface="#3B4252",
        panel="#434C5E",
        dark=True,
    )
    app.register_theme(theme)
    app.theme = "nord-transparent"
    if transparent:
        app.ansi_color = True
