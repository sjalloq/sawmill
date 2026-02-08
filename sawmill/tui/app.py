"""Main TUI application for sawmill.

This module provides the Textual-based terminal user interface for
interactive log analysis. Layout follows the hpc-runner style:
header / severity bar / search / messages / detail / footer.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Resize
from textual.message import Message as TextualMessage
from textual.widgets import Static, DataTable, Input
from textual.reactive import reactive

from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.theme import register_nord_theme
from sawmill.tui.widgets.footer import SawmillFooter
from sawmill.tui.filter_parser import parse_filter

if TYPE_CHECKING:
    from sawmill.models.message import Message


# ---------------------------------------------------------------------------
# Sort mode constants
# ---------------------------------------------------------------------------
SORT_LINE = "line"
SORT_SEVERITY = "severity"
SORT_ID = "id"
SORT_COUNT = "count"
SORT_MODES = [SORT_LINE, SORT_SEVERITY, SORT_ID, SORT_COUNT]


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class MessageStats(Static):
    """Widget displaying message statistics.

    Dynamically displays counts for each severity level defined by the plugin.
    Visually dims severity levels that are toggled off.
    """

    total: reactive[int] = reactive(0)

    def __init__(
        self,
        severity_levels: list[SeverityLevel] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._severity_levels = list(severity_levels) if severity_levels else []
        self._counts: dict[str, int] = {}
        self._active: dict[str, bool] = {}

    @property
    def counts(self) -> dict[str, int]:
        return self._counts.copy()

    @counts.setter
    def counts(self, value: dict[str, int]) -> None:
        self._counts = value
        self.refresh()

    @property
    def active(self) -> dict[str, bool]:
        return self._active.copy()

    @active.setter
    def active(self, value: dict[str, bool]) -> None:
        self._active = value
        self.refresh()

    def render(self) -> str:
        """Render the stats display with plugin-driven severity counts."""
        parts = [f"Total: {self.total}"]
        for level in sorted(self._severity_levels, key=lambda s: -s.level):
            count = self._counts.get(level.id, 0)
            is_active = self._active.get(level.id, True)
            if level.style and is_active:
                parts.append(f"[{level.style}]{level.name}: {count}[/{level.style}]")
            elif not is_active:
                parts.append(f"[dim]{level.name}: {count}[/dim]")
            else:
                parts.append(f"{level.name}: {count}")
        return " | ".join(parts)


class LogViewer(DataTable):
    """Widget for displaying log messages in a scrollable table.

    Implements dynamic column width management to prevent horizontal
    scrollbars. The Message column is flexible and absorbs remaining
    space, while Line/Severity/ID columns have fixed widths.
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    class FlexWidthChanged(TextualMessage):
        """Posted when the flexible column width changes."""

    # Fixed columns: (key, label, width)
    FIXED_COLUMNS = [
        ("line", "Line", 8),
        ("severity", "Severity", 14),
        ("msg_id", "ID", 20),
    ]
    FLEX_COL_KEY = "message"
    FLEX_COL_LABEL = "Message"
    FLEX_COL_MIN = 20
    FLEX_WIDTH_THRESHOLD = 3  # Ignore width changes smaller than this

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._flex_col_width: int = 40

    def on_mount(self) -> None:
        self._setup_columns()
        self.call_after_refresh(self._sync_columns_to_current_width)

    def on_resize(self, event: Resize) -> None:
        del event
        self.call_after_refresh(self._sync_columns_to_current_width)

    def _setup_columns(self) -> None:
        for key, label, width in self.FIXED_COLUMNS:
            self.add_column(label, key=key, width=width)
        self.add_column(
            self.FLEX_COL_LABEL,
            key=self.FLEX_COL_KEY,
            width=self._flex_col_width,
        )

    def _get_table_width(self) -> int:
        content_size = getattr(self, "content_size", None)
        if content_size is not None:
            return int(content_size.width)
        return self.size.width or self.app.console.size.width

    def _calculate_flex_width(self, table_width: int) -> int:
        fixed_total = sum(w for _, _, w in self.FIXED_COLUMNS)
        # 2 chars spacing per column boundary
        column_spacing = (len(self.FIXED_COLUMNS) + 1) * 2
        flex_width = table_width - fixed_total - column_spacing
        return max(self.FLEX_COL_MIN, flex_width)

    def _sync_columns_to_current_width(self) -> None:
        table_width = self._get_table_width()
        if table_width <= 0:
            return
        desired_width = self._calculate_flex_width(table_width)
        if desired_width != self._flex_col_width:
            self._set_flex_column_width(desired_width)
        self.call_after_refresh(self._post_layout_adjust, table_width)

    def _post_layout_adjust(self, table_width: int) -> None:
        if table_width <= 0:
            return
        scrollbar_width = 1 if self.show_vertical_scrollbar else 0
        effective_width = table_width - scrollbar_width
        overflow = self.virtual_size.width - effective_width
        if overflow <= 0 or self._flex_col_width <= self.FLEX_COL_MIN:
            return
        adjusted_width = max(self.FLEX_COL_MIN, self._flex_col_width - overflow)
        if adjusted_width != self._flex_col_width:
            self._set_flex_column_width(adjusted_width)

    def _set_flex_column_width(self, width: int) -> None:
        old_width = self._flex_col_width
        self._flex_col_width = width
        flex_column = self.columns.get(self.FLEX_COL_KEY)
        if flex_column is not None:
            flex_column.width = width
        # Only notify if the change is large enough to matter for truncation
        if abs(width - old_width) >= self.FLEX_WIDTH_THRESHOLD:
            self.post_message(self.FlexWidthChanged())

    def truncate_text(self, text: str) -> str:
        """Truncate text to fit in the flexible column."""
        if len(text) <= self._flex_col_width:
            return text
        return text[: self._flex_col_width - 1] + "\u2026"

    def action_scroll_top(self) -> None:
        self.move_cursor(row=0)

    def action_scroll_bottom(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)


class FilterInput(Input):
    """Input widget for filter patterns."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("placeholder", "Type to filter (sev:X  id:X  regex)...")
        super().__init__(*args, **kwargs)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class SawmillApp(App):
    """Main Textual application for sawmill log analysis.

    Attributes:
        log_file: Path to the log file being analyzed.
        messages: List of parsed messages.
        filtered_messages: List of messages after filtering.
    """

    CSS_PATH = ["base.tcss"]

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "clear_filter", "Clear Filter", show=False),
        Binding("/", "focus_filter", "Filter", show=False),
        Binding("tab", "toggle_focus", "Toggle Focus", show=False),
        Binding("s", "cycle_sort", "Sort", show=False),
        Binding("1", "toggle_sev_1", "Sev 1", show=False),
        Binding("2", "toggle_sev_2", "Sev 2", show=False),
        Binding("3", "toggle_sev_3", "Sev 3", show=False),
        Binding("4", "toggle_sev_4", "Sev 4", show=False),
        Binding("f", "open_filter", "Filter", show=False),
        Binding("f12", "screenshot", "Screenshot", show=False),
    ]

    # Reactive properties
    filter_pattern: reactive[str] = reactive("")
    severity_filter: reactive[dict[str, bool]] = reactive({}, always_update=True)
    sort_mode: reactive[str] = reactive(SORT_LINE)

    def __init__(
        self,
        severity_levels: list[SeverityLevel],
        log_file: Path | None = None,
        messages: list[Message] | None = None,
        plugin_name: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if not severity_levels:
            raise ValueError("severity_levels is required and cannot be empty")
        self.log_file = log_file
        self._messages: list[Message] = messages or []
        self._filtered_messages: list[Message] = []
        self._plugin_name = plugin_name
        self._severity_levels = list(severity_levels)
        self._severity_level_map: dict[str, int] = {
            level.id: level.level for level in self._severity_levels
        }
        # Map numeric keys to severity IDs (sorted ascending by level: 1=lowest)
        self._key_to_severity: dict[int, str] = {}
        for i, level in enumerate(
            sorted(self._severity_levels, key=lambda s: s.level), start=1
        ):
            self._key_to_severity[i] = level.id

        # Widget refs (set in on_mount)
        self._stats_widget: MessageStats | None = None
        self._log_viewer: LogViewer | None = None
        self._filter_input: FilterInput | None = None
        self._detail_content: Static | None = None

        # ID count cache for count sort mode
        self._id_counts: dict[str, int] = {}

    # -- Properties ----------------------------------------------------------

    @property
    def messages(self) -> list[Message]:
        return self._messages

    @messages.setter
    def messages(self, value: list[Message]) -> None:
        self._messages = value
        self._apply_filters()

    @property
    def filtered_messages(self) -> list[Message]:
        return self._filtered_messages

    # -- Compose & Mount -----------------------------------------------------

    def compose(self) -> ComposeResult:
        filename = self.log_file.name if self.log_file else "sawmill"
        yield Static(f"sawmill \u2014 {filename}", id="header")
        yield MessageStats(severity_levels=self._severity_levels, id="severity-bar")
        with Vertical(id="search-panel", classes="panel"):
            yield FilterInput(id="filter-input")
        with Vertical(id="messages-panel", classes="panel"):
            yield LogViewer(id="log-viewer")
        with Vertical(id="detail-panel", classes="panel"):
            yield Static(
                "Select a message to view details",
                id="detail-content",
                markup=False,
            )
        yield SawmillFooter(
            bindings=[
                ("q", "Quit"),
                ("/", "Search"),
                ("Tab", "Focus"),
                ("1-4", "Severity"),
                ("s", "Sort"),
                ("?", "Help"),
            ],
        )

    def on_mount(self) -> None:
        """Handle app mount — apply theme, set up widgets."""
        register_nord_theme(self)

        # Widget refs
        self._stats_widget = self.query_one("#severity-bar", MessageStats)
        self._log_viewer = self.query_one("#log-viewer", LogViewer)
        self._filter_input = self.query_one("#filter-input", FilterInput)
        self._detail_content = self.query_one("#detail-content", Static)

        # Border titles
        self.query_one("#search-panel").border_title = "Search"
        self.query_one("#messages-panel").border_title = "Messages"
        self.query_one("#detail-panel").border_title = "Message Detail"

        # Columns are set up by LogViewer.on_mount via _setup_columns()

        # Load messages if we have a log file
        if self.log_file and not self._messages:
            self._load_messages()

        # Defer initial display until after layout so LogViewer knows its width
        self.call_after_refresh(self._apply_filters)

        # Focus the log viewer by default
        if self._log_viewer:
            self._log_viewer.focus()

    # -- Data loading --------------------------------------------------------

    def _load_messages(self) -> None:
        """Load messages from the log file using a plugin."""
        if not self.log_file:
            return

        from sawmill.core.plugin import PluginManager, NoPluginFoundError, PluginConflictError
        from sawmill.models.plugin_api import severity_levels_from_dicts

        manager = PluginManager()
        manager.discover()

        try:
            if self._plugin_name:
                plugin = manager.get_plugin(self._plugin_name)
            else:
                detected = manager.auto_detect(self.log_file)
                plugin = manager.get_plugin(detected)

            if plugin:
                self._messages = plugin.load_and_parse(self.log_file)

                if hasattr(plugin, "get_severity_levels"):
                    try:
                        severity_dicts = plugin.get_severity_levels()
                        self._severity_levels = severity_levels_from_dicts(severity_dicts)
                        self._severity_level_map = {
                            level.id: level.level for level in self._severity_levels
                        }
                    except Exception:
                        pass
        except (NoPluginFoundError, PluginConflictError) as e:
            self.notify(f"Error loading log: {e}", severity="error")

    # -- Filtering & Sorting -------------------------------------------------

    def _apply_filters(self) -> None:
        """Apply current filters, sort, and update the display."""
        filtered = self._messages.copy()

        # Parse the search bar for prefix filters
        parsed = parse_filter(self.filter_pattern)

        # Build effective severity toggle state from number keys + sev: prefix
        effective_sev = dict(self.severity_filter) if self.severity_filter else {}

        # If sev: prefix is present in search, hide all except those
        if parsed.severities:
            for level in self._severity_levels:
                effective_sev[level.id] = level.id in parsed.severities

        # Apply per-severity toggle filter
        if effective_sev:
            filtered = [
                m for m in filtered
                if m.severity is None or effective_sev.get(m.severity.lower(), True)
            ]

        # Apply id: prefix filter (fnmatch)
        if parsed.message_id:
            id_pattern = parsed.message_id
            filtered = [
                m for m in filtered
                if m.message_id is not None and fnmatch.fnmatch(m.message_id, id_pattern)
            ]

        # Apply regex pattern (remaining text)
        regex_pattern = parsed.pattern
        if regex_pattern:
            try:
                compiled = re.compile(regex_pattern, re.IGNORECASE)
                filtered = [m for m in filtered if compiled.search(m.raw_text)]
            except re.error:
                pass

        # Compute ID counts for count sort mode (before sorting)
        self._id_counts = {}
        for m in filtered:
            mid = m.message_id or ""
            self._id_counts[mid] = self._id_counts.get(mid, 0) + 1

        # Sort
        filtered = self._sort_messages(filtered)

        self._filtered_messages = filtered
        self._update_stats()
        self._populate_table()

    def _sort_messages(self, messages: list[Message]) -> list[Message]:
        """Sort messages according to current sort mode."""
        if self.sort_mode == SORT_LINE:
            return sorted(messages, key=lambda m: m.start_line)
        elif self.sort_mode == SORT_SEVERITY:
            return sorted(
                messages,
                key=lambda m: (
                    -(self._severity_level_map.get(m.severity.lower(), -1) if m.severity else -1),
                    m.start_line,
                ),
            )
        elif self.sort_mode == SORT_ID:
            return sorted(messages, key=lambda m: (m.message_id or "", m.start_line))
        elif self.sort_mode == SORT_COUNT:
            return sorted(
                messages,
                key=lambda m: (-self._id_counts.get(m.message_id or "", 0), m.start_line),
            )
        return messages

    def _update_stats(self) -> None:
        """Update the severity stats bar."""
        if not self._stats_widget:
            return

        self._stats_widget.total = len(self._filtered_messages)

        counts: dict[str, int] = {level.id: 0 for level in self._severity_levels}
        for msg in self._filtered_messages:
            if msg.severity:
                sev = msg.severity.lower()
                if sev in counts:
                    counts[sev] += 1

        self._stats_widget.counts = counts
        self._stats_widget.active = {
            level.id: self.severity_filter.get(level.id, True)
            if self.severity_filter else True
            for level in self._severity_levels
        }

    def _populate_table(self) -> None:
        """Populate the log viewer table with filtered messages."""
        if not self._log_viewer:
            return

        # Preserve cursor position across repopulation
        prev_row = self._log_viewer.cursor_row

        with self.batch_update():
            self._log_viewer.clear()

            for i, msg in enumerate(self._filtered_messages):
                sev = msg.severity or ""
                msg_id = msg.message_id or ""
                content = self._log_viewer.truncate_text(msg.content)

                self._log_viewer.add_row(
                    str(msg.start_line),
                    sev.title(),
                    msg_id,
                    content,
                    key=str(i),
                )

            # Restore cursor position (clamped to valid range)
            if self._filtered_messages:
                restored_row = min(prev_row, len(self._filtered_messages) - 1)
                self._log_viewer.move_cursor(row=restored_row)
                self._update_detail_for_row(restored_row)
            else:
                self._update_detail_for_row(0)

        # Update sort subtitle
        try:
            panel = self.query_one("#messages-panel")
            panel.border_subtitle = f"sorted by: {self.sort_mode}"
        except Exception:
            pass

    def _update_detail_for_row(self, row_index: int) -> None:
        """Update the detail panel for a given row index."""
        if not self._detail_content:
            return
        if 0 <= row_index < len(self._filtered_messages):
            self._detail_content.update(self._filtered_messages[row_index].raw_text)
        else:
            self._detail_content.update("Select a message to view details")

    # -- Watchers ------------------------------------------------------------

    def watch_filter_pattern(self, pattern: str) -> None:
        self._apply_filters()

    def watch_severity_filter(self, value: dict[str, bool]) -> None:
        self._apply_filters()

    def watch_sort_mode(self, mode: str) -> None:
        self._apply_filters()

    # -- Event handlers ------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_pattern = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input" and self._log_viewer:
            self._log_viewer.focus()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel when a row is highlighted."""
        if event.cursor_row is not None:
            self._update_detail_for_row(event.cursor_row)

    def on_log_viewer_flex_width_changed(self, event: LogViewer.FlexWidthChanged) -> None:
        """Re-truncate message cells when the flex column width changes."""
        self._retruncate_message_cells()

    def _retruncate_message_cells(self) -> None:
        """Update message column text to reflect new flex width without clearing."""
        if not self._log_viewer or not self._filtered_messages:
            return
        with self.batch_update():
            for i, msg in enumerate(self._filtered_messages):
                content = self._log_viewer.truncate_text(msg.content)
                self._log_viewer.update_cell(
                    str(i), "message", content, update_width=False,
                )

    # -- Actions -------------------------------------------------------------

    def action_quit(self) -> None:
        self.exit()

    def action_clear_filter(self) -> None:
        """Clear the search bar and severity filter, return focus to table."""
        if self._filter_input:
            self._filter_input.value = ""
        self.filter_pattern = ""
        self.severity_filter = {}
        if self._log_viewer:
            self._log_viewer.focus()

    def action_focus_filter(self) -> None:
        if self._filter_input:
            self._filter_input.focus()

    def action_toggle_focus(self) -> None:
        """Toggle focus between search bar and message table."""
        if self._filter_input and self._log_viewer:
            if self._filter_input.has_focus:
                self._log_viewer.focus()
            else:
                self._filter_input.focus()

    def action_cycle_sort(self) -> None:
        """Cycle through sort modes."""
        idx = SORT_MODES.index(self.sort_mode)
        self.sort_mode = SORT_MODES[(idx + 1) % len(SORT_MODES)]

    def _toggle_severity(self, key_num: int) -> None:
        """Toggle visibility of a severity level by number key."""
        sev_id = self._key_to_severity.get(key_num)
        if not sev_id:
            return

        current = dict(self.severity_filter) if self.severity_filter else {
            level.id: True for level in self._severity_levels
        }
        current[sev_id] = not current.get(sev_id, True)
        self.severity_filter = current

    def action_toggle_sev_1(self) -> None:
        self._toggle_severity(1)

    def action_toggle_sev_2(self) -> None:
        self._toggle_severity(2)

    def action_toggle_sev_3(self) -> None:
        self._toggle_severity(3)

    def action_toggle_sev_4(self) -> None:
        self._toggle_severity(4)

    def action_screenshot(self) -> None:
        """Save a screenshot as SVG (Textual built-in)."""
        path = self.save_screenshot()
        self.notify(f"Screenshot saved: {path}")

    def action_open_filter(self) -> None:
        """Open the filter modal dialog."""
        from sawmill.tui.widgets.filter_modal import FilterModal

        current_filter = {
            "severity_filter": self.severity_filter.copy() if self.severity_filter else {
                level.id: True for level in self._severity_levels
            },
            "pattern": self.filter_pattern,
        }
        self.push_screen(
            FilterModal(self._severity_levels, current_filter),
            callback=self._on_filter_modal_result,
        )

    def _on_filter_modal_result(self, result: dict | None) -> None:
        if result is None:
            return
        self.severity_filter = result.get("severity_filter", {})
        pattern = result.get("pattern", "")
        if self._filter_input:
            self._filter_input.value = pattern
        self.filter_pattern = pattern


# ---------------------------------------------------------------------------
# Entry point helper
# ---------------------------------------------------------------------------

def run_tui(
    log_file: Path | None = None,
    plugin_name: str | None = None,
    severity_levels: list[SeverityLevel] | None = None,
) -> None:
    """Run the TUI application.

    Args:
        log_file: Path to the log file to analyze.
        plugin_name: Name of plugin to use.
        severity_levels: Severity level definitions from plugin.
    """
    app = SawmillApp(
        log_file=log_file,
        plugin_name=plugin_name,
        severity_levels=severity_levels,
    )
    app.run()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_tui(Path(sys.argv[1]))
    else:
        run_tui()
