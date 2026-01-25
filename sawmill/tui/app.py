"""Main TUI application for sawmill.

This module provides the Textual-based terminal user interface for
interactive log analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static, DataTable, Input, Label
from textual.reactive import reactive

if TYPE_CHECKING:
    from sawmill.models.message import Message


class MessageStats(Static):
    """Widget displaying message statistics."""

    total: reactive[int] = reactive(0)
    errors: reactive[int] = reactive(0)
    warnings: reactive[int] = reactive(0)
    info: reactive[int] = reactive(0)

    def render(self) -> str:
        """Render the stats display."""
        return (
            f"Total: {self.total} | "
            f"[red]Errors: {self.errors}[/red] | "
            f"[yellow]Warnings: {self.warnings}[/yellow] | "
            f"[cyan]Info: {self.info}[/cyan]"
        )


class LogViewer(DataTable):
    """Widget for displaying log messages in a scrollable table."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    def __init__(self, *args, **kwargs):
        """Initialize the log viewer."""
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True

    def action_scroll_top(self) -> None:
        """Scroll to the top of the table."""
        self.move_cursor(row=0)

    def action_scroll_bottom(self) -> None:
        """Scroll to the bottom of the table."""
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)


class FilterInput(Input):
    """Input widget for filter patterns."""

    def __init__(self, *args, **kwargs):
        """Initialize the filter input."""
        kwargs.setdefault("placeholder", "Type to filter (regex)...")
        super().__init__(*args, **kwargs)


class SawmillApp(App):
    """Main Textual application for sawmill log analysis.

    Attributes:
        log_file: Path to the log file being analyzed.
        messages: List of parsed messages.
        filtered_messages: List of messages after filtering.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto auto;
    }

    #stats-bar {
        dock: top;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    #log-viewer {
        height: 100%;
    }

    #filter-bar {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }

    FilterInput {
        width: 100%;
    }

    .severity-error {
        color: red;
    }

    .severity-warning {
        color: yellow;
    }

    .severity-critical {
        color: red;
        text-style: bold;
    }

    .severity-info {
        color: cyan;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "clear_filter", "Clear Filter"),
        Binding("/", "focus_filter", "Filter"),
        Binding("s", "toggle_summary", "Summary"),
        Binding("1", "filter_all", "All"),
        Binding("2", "filter_warning", "Warning+"),
        Binding("3", "filter_error", "Error+"),
    ]

    # Reactive properties
    filter_pattern: reactive[str] = reactive("")
    min_severity: reactive[str | None] = reactive(None)

    def __init__(
        self,
        log_file: Path | None = None,
        messages: list[Message] | None = None,
        plugin_name: str | None = None,
        *args,
        **kwargs,
    ):
        """Initialize the application.

        Args:
            log_file: Path to the log file to analyze.
            messages: Pre-loaded list of messages (optional).
            plugin_name: Name of plugin to use (optional).
        """
        super().__init__(*args, **kwargs)
        self.log_file = log_file
        self._messages: list[Message] = messages or []
        self._filtered_messages: list[Message] = []
        self._plugin_name = plugin_name
        self._stats_widget: MessageStats | None = None
        self._log_viewer: LogViewer | None = None
        self._filter_input: FilterInput | None = None

    @property
    def messages(self) -> list[Message]:
        """Get all messages."""
        return self._messages

    @messages.setter
    def messages(self, value: list[Message]) -> None:
        """Set messages and update display."""
        self._messages = value
        self._apply_filters()

    @property
    def filtered_messages(self) -> list[Message]:
        """Get filtered messages."""
        return self._filtered_messages

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        yield MessageStats(id="stats-bar")
        yield LogViewer(id="log-viewer")
        yield Container(
            FilterInput(id="filter-input"),
            id="filter-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount - load data and set up table."""
        # Get references to widgets
        self._stats_widget = self.query_one("#stats-bar", MessageStats)
        self._log_viewer = self.query_one("#log-viewer", LogViewer)
        self._filter_input = self.query_one("#filter-input", FilterInput)

        # Set up the log viewer table
        self._log_viewer.add_column("Line", width=6)
        self._log_viewer.add_column("Sev", width=8)
        self._log_viewer.add_column("ID", width=20)
        self._log_viewer.add_column("Message", width=100)

        # Load messages if we have a log file
        if self.log_file and not self._messages:
            self._load_messages()

        # Apply initial filters and populate table
        self._apply_filters()

    def _load_messages(self) -> None:
        """Load messages from the log file using a plugin."""
        if not self.log_file:
            return

        from sawmill.core.plugin import PluginManager, NoPluginFoundError, PluginConflictError
        from sawmill.plugins.vivado import VivadoPlugin

        manager = PluginManager()
        manager.register(VivadoPlugin())
        manager.discover()

        try:
            if self._plugin_name:
                plugin = manager.get_plugin(self._plugin_name)
            else:
                detected = manager.auto_detect(self.log_file)
                plugin = manager.get_plugin(detected)

            if plugin:
                self._messages = plugin.load_and_parse(self.log_file)
        except (NoPluginFoundError, PluginConflictError) as e:
            self.notify(f"Error loading log: {e}", severity="error")

    def _apply_filters(self) -> None:
        """Apply current filters and update the display."""
        import re

        filtered = self._messages.copy()

        # Apply severity filter
        if self.min_severity:
            severity_levels = {"info": 0, "warning": 1, "error": 2, "critical": 3}
            min_level = severity_levels.get(self.min_severity.lower(), 0)
            filtered = [
                m for m in filtered
                if m.severity and severity_levels.get(m.severity.lower(), -1) >= min_level
            ]

        # Apply regex filter
        if self.filter_pattern:
            try:
                pattern = re.compile(self.filter_pattern, re.IGNORECASE)
                filtered = [m for m in filtered if pattern.search(m.raw_text)]
            except re.error:
                pass  # Invalid regex - ignore

        self._filtered_messages = filtered
        self._update_stats()
        self._populate_table()

    def _update_stats(self) -> None:
        """Update the stats widget."""
        if not self._stats_widget:
            return

        self._stats_widget.total = len(self._filtered_messages)

        errors = warnings = info = 0
        for msg in self._filtered_messages:
            if msg.severity:
                sev = msg.severity.lower()
                if sev in ("error", "critical", "critical_warning"):
                    errors += 1
                elif sev == "warning":
                    warnings += 1
                elif sev == "info":
                    info += 1

        self._stats_widget.errors = errors
        self._stats_widget.warnings = warnings
        self._stats_widget.info = info

    def _populate_table(self) -> None:
        """Populate the log viewer table with filtered messages."""
        if not self._log_viewer:
            return

        self._log_viewer.clear()

        for msg in self._filtered_messages:
            sev = msg.severity or ""
            msg_id = msg.message_id or ""
            content = msg.content[:100] if len(msg.content) > 100 else msg.content

            # Add row with styling based on severity
            self._log_viewer.add_row(
                str(msg.start_line),
                sev.title(),
                msg_id,
                content,
            )

    def watch_filter_pattern(self, pattern: str) -> None:
        """React to filter pattern changes."""
        self._apply_filters()

    def watch_min_severity(self, severity: str | None) -> None:
        """React to severity filter changes."""
        self._apply_filters()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "filter-input":
            self.filter_pattern = event.value

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_clear_filter(self) -> None:
        """Clear the filter."""
        if self._filter_input:
            self._filter_input.value = ""
        self.filter_pattern = ""
        self.min_severity = None

    def action_focus_filter(self) -> None:
        """Focus the filter input."""
        if self._filter_input:
            self._filter_input.focus()

    def action_toggle_summary(self) -> None:
        """Toggle summary view (placeholder for future implementation)."""
        self.notify("Summary view: coming soon!", severity="information")

    def action_filter_all(self) -> None:
        """Show all messages."""
        self.min_severity = None
        self.notify("Showing all messages")

    def action_filter_warning(self) -> None:
        """Filter to warnings and above."""
        self.min_severity = "warning"
        self.notify("Showing warnings and above")

    def action_filter_error(self) -> None:
        """Filter to errors and above."""
        self.min_severity = "error"
        self.notify("Showing errors only")


def run_tui(log_file: Path | None = None, plugin_name: str | None = None) -> None:
    """Run the TUI application.

    Args:
        log_file: Path to the log file to analyze.
        plugin_name: Name of plugin to use.
    """
    app = SawmillApp(log_file=log_file, plugin_name=plugin_name)
    app.run()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_tui(Path(sys.argv[1]))
    else:
        run_tui()
