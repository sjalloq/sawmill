"""Main TUI application for sawmill.

This module provides the Textual-based terminal user interface for
interactive log analysis. Layout follows the hpc-runner style:
header / severity bar / search / messages / detail / footer.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.message import Message as TextualMessage
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static
from textual.widgets._data_table import ColumnKey

from sawmill.core.discovery import TargetRef
from sawmill.core.filter import FilterEngine, filter_by_severity_toggles, match_message_id
from sawmill.core.manifest import ManifestError, ManifestLoader
from sawmill.core.rules import RuleLoader, RuleValidationError, append_rule, ensure_rule_file
from sawmill.core.runner import RunnerError, reapply_rules, rerun_target
from sawmill.core.scaffold import add_target, write_manifest_template
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.filter_parser import parse_filter
from sawmill.tui.state import (
    SORT_COUNT,
    SORT_ID,
    SORT_LINE,
    SORT_MODES,
    SORT_SEVERITY,
    TargetState,
)
from sawmill.tui.theme import register_nord_theme
from sawmill.tui.widgets.footer import SawmillFooter
from sawmill.tui.widgets.overview import OverviewTable
from sawmill.tui.widgets.rules_prompt import RulesFilePrompt
from sawmill.tui.widgets.waive_modal import WaiveModal
from sawmill.utils.author import discover_author

if TYPE_CHECKING:
    from sawmill.core.runner import TargetResult
    from sawmill.models.message import Message

__all__ = [
    "SORT_COUNT",
    "SORT_ID",
    "SORT_LINE",
    "SORT_MODES",
    "SORT_SEVERITY",
    "FilterInput",
    "LogViewer",
    "MessageStats",
    "SawmillApp",
    "run_tui",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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

    def set_levels(self, severity_levels: list[SeverityLevel]) -> None:
        """Replace the severity levels shown and clear counts and toggles."""
        self._severity_levels = list(severity_levels)
        self._counts = {}
        self._active = {}
        self.refresh()

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
        for i, level in enumerate(sorted(self._severity_levels, key=lambda s: s.level), start=1):
            count = self._counts.get(level.id, 0)
            is_active = self._active.get(level.id, True)
            hint = f"\\[{i}] "
            if level.style and is_active:
                parts.append(f"[{level.style}]{hint}{level.name}: {count}[/{level.style}]")
            elif not is_active:
                parts.append(f"[dim]{hint}{level.name}: {count}[/dim]")
            else:
                parts.append(f"{hint}{level.name}: {count}")
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
        Binding("home", "scroll_top", "Top", show=False),
        Binding("end", "scroll_bottom", "Bottom", show=False),
    ]

    class FlexWidthChanged(TextualMessage):
        """Posted when the flexible column width changes."""

    # Fixed columns: (key, label, width)
    FIXED_COLUMNS = [
        ("status", "St", 4),
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
        # Windowing: the table holds rows [window_start, window_start + row_count)
        # of a longer list of total_rows. ``navigate`` moves the cursor to an
        # absolute index over the full list; the owner re-windows as needed.
        self.window_start: int = 0
        self.total_rows: int = 0
        self.navigate: Callable[[int], None] | None = None
        self.on_scroll_edge: Callable[[int], None] | None = None

    @property
    def page_rows(self) -> int:
        """Number of data rows visible at once."""
        height = self.scrollable_content_region.height - (
            self.header_height if self.show_header else 0
        )
        return max(1, height)

    def _absolute_cursor(self) -> int:
        return self.window_start + self.cursor_row

    def _go(self, target: int) -> None:
        if self.navigate is None or self.total_rows <= 0:
            return
        self._set_hover_cursor(False)
        self.navigate(max(0, min(target, self.total_rows - 1)))

    def action_cursor_up(self) -> None:
        if self.navigate is None:
            return super().action_cursor_up()
        self._go(self._absolute_cursor() - 1)

    def action_cursor_down(self) -> None:
        if self.navigate is None:
            return super().action_cursor_down()
        self._go(self._absolute_cursor() + 1)

    def action_page_up(self) -> None:
        if self.navigate is None:
            return super().action_page_up()
        self._go(self._absolute_cursor() - self.page_rows)

    def action_page_down(self) -> None:
        if self.navigate is None:
            return super().action_page_down()
        self._go(self._absolute_cursor() + self.page_rows)

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        """Re-window when mouse-wheel scrolling hits the edge of the window."""
        super().watch_scroll_y(old_value, new_value)
        if self.on_scroll_edge is None or self.row_count == 0:
            return
        if new_value > old_value and new_value >= self.max_scroll_y:
            if self.window_start + self.row_count < self.total_rows:
                self.on_scroll_edge(1)
        elif new_value < old_value and new_value <= 0 and self.window_start > 0:
            self.on_scroll_edge(-1)

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
        flex_column = self.columns.get(ColumnKey(self.FLEX_COL_KEY))
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
        if self.navigate is not None:
            self._go(0)
        else:
            self.move_cursor(row=0)

    def action_scroll_bottom(self) -> None:
        if self.navigate is not None:
            self._go(self.total_rows - 1)
        elif self.row_count > 0:
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

    Shows one tab per target. The table is merged across the active
    target's logs with a log column.

    Attributes:
        filtered_messages: Active target's messages after filtering.
    """

    CSS_PATH = ["base.tcss"]

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "clear_filter", "Clear Filter", show=False),
        Binding("/", "focus_filter", "Filter", show=False),
        Binding("tab", "toggle_focus", "Toggle Focus", show=False),
        Binding("o", "cycle_sort", "Sort", show=False),
        Binding("left", "prev_tab", "Previous Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("v", "toggle_show_all", "Show All", show=False),
        Binding("w", "waive", "Waive", show=False),
        Binding("h", "hide_id", "Hide", show=False),
        Binding("r", "refresh_rules", "Refresh", show=False),
        Binding("R", "refresh_all", "Refresh All", show=False),
        Binding("1", "toggle_sev_1", "Sev 1", show=False),
        Binding("2", "toggle_sev_2", "Sev 2", show=False),
        Binding("3", "toggle_sev_3", "Sev 3", show=False),
        Binding("4", "toggle_sev_4", "Sev 4", show=False),
        Binding("f12", "screenshot", "Screenshot", show=False),
        Binding("question_mark", "help", "Help", show=False),
    ]

    # Reactive properties — all use init=False to prevent watcher calls during
    # lazy initialisation (which would cause re-entrant _apply_filters calls).
    filter_pattern: reactive[str] = reactive("", init=False)
    severity_filter: reactive[dict[str, bool]] = reactive({}, always_update=True, init=False)
    sort_mode: reactive[str] = reactive(SORT_LINE, init=False)

    def __init__(
        self,
        targets: list[TargetResult],
        *args,
        single_log: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if not targets:
            raise ValueError("targets is required and cannot be empty")
        self._states: list[TargetState] = [TargetState(t) for t in targets]
        self._active: int = 0
        self._single_log = single_log
        # Rules file chosen through the single-log prompt (asked once per session)
        self._single_log_rules_path: Path | None = None
        self._filtered_messages: list[Message] = []
        # Windowing state: the table shows _filtered_messages[_window_start:...]
        self._window_start: int = 0
        self._cursor_index: int = 0
        self._shown_window_size: int = 0
        self._severity_levels: list[SeverityLevel] = []
        self._severity_level_map: dict[str, int] = {}
        # Map numeric keys to severity IDs (sorted ascending by level: 1=lowest)
        self._key_to_severity: dict[int, str] = {}

        # Widget refs (set in on_mount)
        self._stats_widget: MessageStats | None = None
        self._log_viewer: LogViewer | None = None
        self._filter_input: FilterInput | None = None
        self._detail_content: Static | None = None

        # ID count cache for count sort mode
        self._id_counts: dict[str, int] = {}

        self._load_active_target()

    OVERVIEW = -1

    def _active_state(self) -> TargetState:
        """Return the state of the active target (never call on the overview)."""
        return self._states[self._active]

    def _load_active_target(self) -> None:
        """Load the active tab: severity scheme and saved view state.

        Restores the target's filter text, severity toggles, sort mode,
        cursor and window without triggering watchers, then re-applies the
        filters once when mounted. On the overview only the table is cleared.
        """
        if self._active == self.OVERVIEW:
            if self._stats_widget is not None:
                self._stats_widget.set_levels([])
            if self._log_viewer is not None:
                self._apply_filters()
            return
        state = self._active_state()
        levels = list(state.result.severity_levels)
        self._severity_levels = levels
        self._severity_level_map = {level.id.lower(): level.level for level in levels}
        self._key_to_severity = {
            i: level.id for i, level in enumerate(sorted(levels, key=lambda s: s.level), start=1)
        }
        self.set_reactive(SawmillApp.filter_pattern, state.filter_text)
        self.set_reactive(SawmillApp.severity_filter, dict(state.severity_filter))
        self.set_reactive(SawmillApp.sort_mode, state.sort_mode)
        self._window_start = state.window_start
        self._cursor_index = state.cursor_index
        if self._filter_input is not None:
            with self.prevent(Input.Changed):
                self._filter_input.value = state.filter_text
        if self._stats_widget is not None:
            self._stats_widget.set_levels(levels)
        if self._log_viewer is not None:
            self._apply_filters()

    def _save_active_target(self) -> None:
        """Store the app's view state into the active target's state."""
        if self._active == self.OVERVIEW:
            return
        state = self._active_state()
        state.filter_text = self.filter_pattern
        state.severity_filter = dict(self.severity_filter)
        state.sort_mode = self.sort_mode
        state.cursor_index = self._cursor_index
        state.window_start = self._window_start

    def _tab_order(self) -> list[int]:
        """Return the tab indices in display order."""
        order = list(range(len(self._states)))
        return order if self._single_log else [self.OVERVIEW, *order]

    def _switch_tab(self, step: int) -> None:
        """Move ``step`` tabs along the tab order, wrapping."""
        order = self._tab_order()
        if len(order) < 2:
            return
        new = order[(order.index(self._active) + step) % len(order)]
        self._save_active_target()
        self._active = new
        self._update_header()
        self._load_active_target()

    def _update_header(self) -> None:
        """Mark the active tab and show its fail_on in the header."""
        try:
            tabs = list(self.query(".header-tab"))
            right = self.query_one("#header-right", Static)
        except Exception:
            return
        active_id = (
            "tab-overview" if self._active == self.OVERVIEW else f"tab-target-{self._active}"
        )
        for tab in tabs:
            tab.set_class(tab.id == active_id, "active-tab")
        if self._active == self.OVERVIEW:
            right.update("")
        else:
            right.update(f"fail_on: {self._active_state().result.fail_on}")

    # -- Properties ----------------------------------------------------------

    @property
    def filtered_messages(self) -> list[Message]:
        return self._filtered_messages

    # -- Compose & Mount -----------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Static("sawmill", id="header-brand")
            if not self._single_log:
                yield Static("Overview", id="tab-overview", classes="header-tab")
            for i, state in enumerate(self._states):
                classes = "header-tab active-tab" if i == self._active else "header-tab"
                yield Static(
                    state.result.qualified_name,
                    id=f"tab-target-{i}",
                    classes=classes,
                    markup=False,
                )
            yield Static(
                f"fail_on: {self._active_state().result.fail_on}",
                id="header-right",
                markup=False,
            )
        with Vertical(id="severity-panel", classes="panel"):
            yield MessageStats(severity_levels=self._severity_levels, id="severity-bar")
        with Vertical(id="search-panel", classes="panel"):
            yield FilterInput(id="filter-input")
        with Vertical(id="messages-panel", classes="panel"):
            yield LogViewer(id="log-viewer")
            overview = OverviewTable(id="overview-table")
            overview.display = False
            yield overview
        with Vertical(id="detail-panel", classes="panel"):
            yield Static(
                "Select a message to view details",
                id="detail-content",
                markup=False,
            )
        yield SawmillFooter(bindings=list(self.TARGET_HINTS))

    def on_mount(self) -> None:
        """Handle app mount: apply theme and set up widgets."""
        register_nord_theme(self)

        # Widget refs
        self._stats_widget = self.query_one("#severity-bar", MessageStats)
        self._log_viewer = self.query_one("#log-viewer", LogViewer)
        self._filter_input = self.query_one("#filter-input", FilterInput)
        self._detail_content = self.query_one("#detail-content", Static)

        # Border titles
        self.query_one("#severity-panel").border_title = "Severity"
        self.query_one("#search-panel").border_title = "Search"
        self.query_one("#messages-panel").border_title = "Messages"
        self.query_one("#detail-panel").border_title = "Message Detail"

        # Columns are set up by LogViewer.on_mount via _setup_columns()

        # Defer initial display until after layout so LogViewer knows its width
        self.call_after_refresh(self._apply_filters)

        # Focus the log viewer by default
        if self._log_viewer:
            self._log_viewer.focus()

    # -- Filtering & Sorting -------------------------------------------------

    def _apply_filters(self) -> None:
        """Apply current filters, sort, and update the display.

        This is the single rendering path. All state changes that affect the
        display go through reactive watchers which call this method.
        """
        self._show_overview(self._active == self.OVERVIEW)
        if self._active == self.OVERVIEW:
            self._filtered_messages = []
            self._id_counts = {}
            if self._stats_widget:
                self._stats_widget.total = 0
                self._stats_widget.counts = {}
            if self._log_viewer:
                self._log_viewer.clear()
                self._log_viewer.window_start = 0
                self._log_viewer.total_rows = 0
            if self._detail_content:
                self._detail_content.update(self.OVERVIEW_DETAIL)
            self._set_detail_subtitle("")
            self._update_panel_titles()
            return
        filtered = self._active_state().base_messages()

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
            filtered = filter_by_severity_toggles(filtered, effective_sev)

        # Apply id: prefix filter (fnmatch)
        if parsed.message_id:
            filtered = [m for m in filtered if match_message_id(m.message_id, parsed.message_id)]

        # Apply log: prefix filter (case-sensitive fnmatch on log_path)
        if parsed.log:
            log_pat = parsed.log
            filtered = [
                m
                for m in filtered
                if (fnmatch.fnmatchcase(m.log_path, log_pat) if m.log_path else log_pat == "*")
            ]

        # Apply cat: prefix filter
        if parsed.category:
            filtered = [m for m in filtered if m.category and m.category.lower() == parsed.category]

        # Apply regex pattern (remaining text)
        if parsed.pattern:
            try:
                re.compile(parsed.pattern)
            except re.error:
                pass  # Invalid regex — skip filter, keep current results
            else:
                filtered = FilterEngine().apply_filter(
                    parsed.pattern, filtered, case_sensitive=False
                )

        self._filtered_messages = filtered

        # Compute ID counts for count sort mode (on active list)
        self._id_counts = {}
        for m in self._filtered_messages:
            mid = m.message_id or ""
            self._id_counts[mid] = self._id_counts.get(mid, 0) + 1

        # Sort
        self._filtered_messages = self._sort_messages(self._filtered_messages)

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
            level.id: self.severity_filter.get(level.id, True) if self.severity_filter else True
            for level in self._severity_levels
        }

    WINDOW_MIN = 200

    def _window_size(self) -> int:
        """Rows held in the table: three screens, at least WINDOW_MIN."""
        visible = self._log_viewer.page_rows if self._log_viewer else 0
        return max(3 * visible, self.WINDOW_MIN)

    def _window_margin(self) -> int:
        """Distance from a window edge at which the window slides."""
        return self._log_viewer.page_rows if self._log_viewer else 1

    def _current_index(self) -> int:
        """Absolute index into _filtered_messages of the highlighted row."""
        if not self._log_viewer:
            return self._cursor_index
        return self._window_start + self._log_viewer.cursor_row

    def _current_message(self) -> Message | None:
        idx = self._current_index()
        if 0 <= idx < len(self._filtered_messages):
            return self._filtered_messages[idx]
        return None

    def _centred_start(self, index: int) -> int:
        size = self._window_size()
        return max(0, min(index - size // 2, len(self._filtered_messages) - size))

    def _navigate_to(self, index: int) -> None:
        """Move the cursor to an absolute index, sliding the window if needed."""
        total = len(self._filtered_messages)
        if not self._log_viewer or total == 0:
            return
        index = max(0, min(index, total - 1))
        self._cursor_index = index
        start = self._window_start
        end = start + self._log_viewer.row_count
        margin = self._window_margin()
        near_top = index < start + margin and start > 0
        near_bottom = index >= end - margin and end < total
        if start <= index < end and not (near_top or near_bottom):
            self._log_viewer.move_cursor(row=index - start)
            return
        # Keep the cursor at the same screen offset across the re-window
        screen_offset = self._log_viewer.cursor_row - round(self._log_viewer.scroll_y)
        screen_offset = max(0, min(screen_offset, self._log_viewer.page_rows - 1))
        self._window_start = self._centred_start(index)
        self._populate_table(screen_offset=screen_offset)

    def on_resize(self, event: Resize) -> None:
        """Grow the window if the table can now show more rows than it holds."""
        del event
        self.call_after_refresh(self._rewindow_if_too_small)

    def _rewindow_if_too_small(self) -> None:
        if not self._log_viewer:
            return
        if self._window_size() > self._shown_window_size and self._log_viewer.row_count < len(
            self._filtered_messages
        ):
            self._populate_table()

    def _on_scroll_edge(self, direction: int) -> None:
        """Mouse wheel reached a window edge: slide the window by half its size."""
        if not self._log_viewer:
            return
        total = len(self._filtered_messages)
        size = self._window_size()
        top = round(self._log_viewer.scroll_y)
        first_visible = self._window_start + top
        new_start = self._window_start + direction * (size // 2)
        new_start = max(0, min(new_start, total - size))
        if new_start == self._window_start:
            return
        self._window_start = new_start
        # Keep the cursor if it is still inside the new window, else drag it
        # to the first visible row.
        if not (new_start <= self._cursor_index < new_start + size):
            self._cursor_index = max(new_start, min(first_visible, new_start + size - 1))
        self._populate_table(scroll_top_index=first_visible)

    def _populate_table(
        self,
        screen_offset: int | None = None,
        scroll_top_index: int | None = None,
    ) -> None:
        """Fill the table with the window of _filtered_messages around the cursor."""
        if not self._log_viewer:
            return
        viewer = self._log_viewer
        viewer.navigate = self._navigate_to
        viewer.on_scroll_edge = self._on_scroll_edge

        total = len(self._filtered_messages)
        size = self._window_size()
        self._cursor_index = max(0, min(self._cursor_index, total - 1)) if total else 0
        start = max(0, min(self._window_start, total - size))
        if not (start <= self._cursor_index < start + size):
            start = self._centred_start(self._cursor_index)
        self._window_start = start
        self._shown_window_size = size
        viewer.window_start = start
        viewer.total_rows = total

        state = self._active_state()
        waived = state.waived_ids if state.show_all else frozenset()
        hidden = state.hidden_ids if state.show_all else set()

        with self.batch_update():
            viewer.clear()

            window = self._filtered_messages[start : start + size]
            for i, msg in enumerate(window, start):
                sev = msg.severity or ""
                msg_id = msg.message_id or ""
                content = viewer.truncate_text(msg.content)
                status = ("W" if id(msg) in waived else "") + (
                    "H" if msg.message_id and msg.message_id in hidden else ""
                )
                viewer.add_row(
                    status,
                    str(msg.start_line),
                    sev.title(),
                    escape(msg_id),
                    escape(content),
                    key=str(i),
                )

            if window:
                row = self._cursor_index - start
                keep_scroll = screen_offset is not None or scroll_top_index is not None
                viewer.move_cursor(row=row, scroll=not keep_scroll)
                if scroll_top_index is not None:
                    top = scroll_top_index - start
                    viewer.call_after_refresh(viewer.scroll_to, y=top, animate=False)
                elif screen_offset is not None:
                    top = max(0, row - screen_offset)
                    viewer.call_after_refresh(viewer.scroll_to, y=top, animate=False)
            self._update_detail_for_row(self._cursor_index)

        self._update_panel_titles()

    TARGET_HINTS: list[tuple[str, str]] = [
        ("q", "Quit"),
        ("/", "Search"),
        ("Tab", "Focus"),
        ("1-4", "Severity"),
        ("o", "Sort"),
        ("\u2190\u2192", "Tab"),
        ("v", "All"),
        ("w", "Waive"),
        ("h", "Hide"),
        ("r/R", "Refresh"),
        ("?", "Help"),
    ]
    OVERVIEW_HINTS: list[tuple[str, str]] = [
        ("q", "Quit"),
        ("\u2190\u2192", "Tab"),
        ("Enter", "Open"),
        ("?", "Help"),
    ]
    OVERVIEW_DETAIL = "Select a target or log and press Enter"

    def _show_overview(self, show: bool) -> None:
        """Swap the log viewer and footer for the overview table, or back."""
        try:
            overview = self.query_one("#overview-table", OverviewTable)
        except Exception:
            return
        if self._log_viewer is None:
            return
        had_focus = overview.has_focus or self._log_viewer.has_focus
        if show:
            overview.populate(self._states)
        overview.display = show
        self._log_viewer.display = not show
        footer = self.query_one(SawmillFooter)
        hints = self.OVERVIEW_HINTS if show else self.TARGET_HINTS
        if footer._footer_bindings != hints:
            footer.update_bindings(list(hints))
        if had_focus:
            (overview if show else self._log_viewer).focus()

    def on_overview_table_open(self, event: OverviewTable.Open) -> None:
        """Open a target's tab, filtered to the log when one is given."""
        if self._active != self.OVERVIEW:
            return
        self._save_active_target()
        self._active = event.target_index
        if event.log_rel_path is not None:
            self._active_state().filter_text = f"log:{event.log_rel_path}"
        self._update_header()
        self._load_active_target()

    def _update_panel_titles(self) -> None:
        """Update panel border title, position and sort subtitle."""
        try:
            panel = self.query_one("#messages-panel")
        except Exception:
            return
        if self._active == self.OVERVIEW:
            panel.border_title = "Overview"
            panel.border_subtitle = ""
            return
        state = self._active_state()
        panel.border_title = state.result.qualified_name
        total = len(self._filtered_messages)
        position = f"row {self._cursor_index + 1} of {total} \u00b7 " if total else ""
        show_all = " \u00b7 all" if state.show_all else ""
        panel.border_subtitle = f"{position}sorted by: {self.sort_mode}{show_all}"

    def _update_detail_for_row(self, row_index: int) -> None:
        """Update the detail panel for a given row index."""
        if not self._detail_content:
            return
        if 0 <= row_index < len(self._filtered_messages):
            msg = self._filtered_messages[row_index]
            self._detail_content.update(msg.raw_text)
            self._set_detail_subtitle(msg.log_path or "")
        else:
            self._detail_content.update("Select a message to view details")
            self._set_detail_subtitle("")

    def _set_detail_subtitle(self, text: str) -> None:
        """Show ``text`` (the selected message's log path) on the detail border."""
        try:
            self.query_one("#detail-panel").border_subtitle = text
        except Exception:
            return

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
        if event.cursor_row is None or event.data_table is not self._log_viewer:
            return
        # Read the live cursor, not event.cursor_row: re-windowing clears and
        # refills the table, so queued events can carry stale relative rows.
        index = self._current_index()
        self._cursor_index = index
        self._update_detail_for_row(index)
        self._update_panel_titles()
        # Mouse clicks can land near a window edge; slide if so.
        total = len(self._filtered_messages)
        end = self._window_start + self._log_viewer.row_count
        margin = self._window_margin()
        if (index < self._window_start + margin and self._window_start > 0) or (
            index >= end - margin and end < total
        ):
            self.call_after_refresh(self._navigate_to, index)

    def on_log_viewer_flex_width_changed(self, event: LogViewer.FlexWidthChanged) -> None:
        """Re-truncate message cells when the flex column width changes."""
        self._retruncate_message_cells()

    def _retruncate_message_cells(self) -> None:
        """Update message column text to reflect new flex width without clearing."""
        if not self._log_viewer or not self._filtered_messages:
            return
        with self.batch_update():
            start = self._window_start
            window = self._filtered_messages[start : start + self._log_viewer.row_count]
            for i, msg in enumerate(window, start):
                content = self._log_viewer.truncate_text(msg.content)
                self._log_viewer.update_cell(
                    str(i),
                    "message",
                    content,
                    update_width=False,
                )

    # -- Actions -------------------------------------------------------------

    async def action_quit(self) -> None:
        """Quit the application."""
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
        if self._active == self.OVERVIEW:
            return
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
        if self._active == self.OVERVIEW:
            return
        idx = SORT_MODES.index(self.sort_mode)
        self.sort_mode = SORT_MODES[(idx + 1) % len(SORT_MODES)]

    def action_prev_tab(self) -> None:
        """Switch to the previous tab, wrapping."""
        self._switch_tab(-1)

    def action_next_tab(self) -> None:
        """Switch to the next tab, wrapping."""
        self._switch_tab(1)

    def action_toggle_show_all(self) -> None:
        """Toggle showing waived and hidden messages on the active target."""
        if self._active == self.OVERVIEW:
            return
        state = self._active_state()
        state.show_all = not state.show_all
        self._apply_filters()

    def action_waive(self) -> None:
        """Open the waive modal on the highlighted message of a target tab."""
        if self._active == self.OVERVIEW:
            return
        msg = self._current_message()
        if msg is None:
            return
        if not msg.message_id:
            self.notify("Cannot waive: message has no ID", severity="warning")
            return
        result = self._active_state().result
        manifest = result.manifest
        target_files = result.target.rule_paths(manifest.rules_dir)
        loader = RuleLoader()
        plugin_files: list[Path] = []
        for path in manifest.rule_paths():
            try:
                if loader.load(path).plugin == result.plugin_name:
                    plugin_files.append(path)
            except (RuleValidationError, OSError):
                continue
        if not target_files and not plugin_files:
            no_manifest = manifest.path is None or not manifest.path.exists()
            if self._single_log and no_manifest:
                if self._single_log_rules_path is None:
                    self.push_screen(
                        RulesFilePrompt(
                            rules_dir=manifest.rules_dir,
                            default_name=f"{result.plugin_name}.toml",
                            log_name=result.target.name,
                        ),
                        callback=lambda value: self._on_rules_prompt_result(value, msg),
                    )
                    return
                target_files = [self._single_log_rules_path]
            else:
                self.notify(
                    "No rule file listed for this target; add one to the manifest",
                    severity="warning",
                )
                return
        self._open_waive_modal(msg, target_files, plugin_files)

    def _open_waive_modal(
        self, msg: Message, target_files: list[Path], plugin_files: list[Path]
    ) -> None:
        """Push the waive modal for ``msg`` with the given destination files."""
        self.push_screen(
            WaiveModal(
                message_id=msg.message_id or "",
                severity=msg.severity or "",
                content=msg.content,
                log_rel_path=msg.log_path or "",
                target_files=target_files,
                plugin_files=plugin_files,
                author=discover_author(),
            ),
            callback=self._on_waive_result,
        )

    def _on_rules_prompt_result(self, value: dict | None, msg: Message) -> None:
        """Set up the chosen rules file (and manifest), then open the waive modal."""
        if not value or self._active == self.OVERVIEW:
            return
        path: Path = value["path"]
        state = self._active_state()
        result = state.result
        manifest = result.manifest
        plugin_name = result.plugin_name
        self._single_log_rules_path = path
        try:
            if value["create_manifest"]:
                mpath = manifest.path
                if mpath is None:
                    raise ValueError("log has no manifest location")
                if not mpath.exists():
                    write_manifest_template(mpath, name=manifest.root.name)
                log_path = result.logs[0].path if result.logs else manifest.root
                name = re.sub(r"[^A-Za-z0-9]", "_", log_path.stem)
                glob = log_path.relative_to(manifest.root).as_posix()
                add_target(mpath, name, plugin_name, glob, rules_file=path.name)
                new_manifest = ManifestLoader().load(mpath)
                new_target = new_manifest.get_target(name)
                if new_target is None:
                    raise ValueError(f"target '{name}' missing from {mpath}")
                state.set_result(
                    reapply_rules(
                        result,
                        ref=TargetRef(new_manifest, new_target, overrides=result.overrides),
                    )
                )
                self.notify(f"Created {mpath} with target '{name}'")
            else:
                ensure_rule_file(path, plugin_name)
                target = result.target.model_copy(update={"rules": [path.name]})
                state.set_result(
                    reapply_rules(
                        result, ref=TargetRef(manifest, target, overrides=result.overrides)
                    )
                )
        except (
            OSError,
            ManifestError,
            RuleValidationError,
            RunnerError,
            ValueError,
        ) as e:
            self._single_log_rules_path = None
            self.notify(f"Cannot set up rules file: {e}", severity="error")
            return
        self._open_waive_modal(msg, [path], [])

    def _on_waive_result(self, value: dict | None) -> None:
        """Append the modal's rule to its file and re-apply rules live."""
        if not value or self._active == self.OVERVIEW:
            return
        rule = value["rule"]
        path: Path = value["path"]
        active = self._active_state()
        plugin_name = active.result.plugin_name
        try:
            append_rule(path, rule, plugin_name)
        except (RuleValidationError, OSError) as e:
            self.notify(f"Cannot waive: {e}", severity="error")
            return
        if value["scope"] == "plugin":
            states = [s for s in self._states if s.result.plugin_name == plugin_name]
        else:
            states = [active]
        for state in states:
            try:
                state.set_result(reapply_rules(state.result))
            except (RunnerError, RuleValidationError) as e:
                self.notify(
                    f"Cannot re-apply rules for {state.result.qualified_name}: {e}",
                    severity="error",
                )
        self._cursor_index = self._current_index()
        self._apply_filters()
        self.notify(f"Waived {rule.id} in {path.name}")

    def action_hide_id(self) -> None:
        """Toggle session hiding of the highlighted message's ID."""
        if self._active == self.OVERVIEW:
            return
        msg = self._current_message()
        if msg is None:
            return
        if not msg.message_id:
            self.notify("Cannot hide: message has no ID", severity="warning")
            return
        hidden = self._active_state().hidden_ids
        if msg.message_id in hidden:
            hidden.discard(msg.message_id)
            verb = "Unhidden"
        else:
            hidden.add(msg.message_id)
            verb = "Hidden"
        self._cursor_index = self._current_index()
        self._apply_filters()
        self.notify(f"{verb} {msg.message_id}")

    def _refresh_ref(self, state: TargetState) -> TargetRef | None:
        """Re-read a target's manifest and return the ref to re-run it with.

        Returns None, after notifying, when the manifest is invalid or no
        longer defines the target. For a single log (no manifest on disk)
        the plugin rules file beside the log is re-checked.
        """
        manifest = state.result.manifest
        target = state.result.target
        path = manifest.path
        if path is None or not path.exists():
            rules_name = f"{target.plugin}.toml"
            rules = [rules_name] if (manifest.rules_dir / rules_name).exists() else []
            return TargetRef(
                manifest,
                target.model_copy(update={"rules": rules}),
                overrides=state.result.overrides,
            )
        try:
            new_manifest = ManifestLoader().load(path)
        except ManifestError as e:
            self.notify(f"Cannot re-read manifest: {e}", severity="error")
            return None
        new_target = new_manifest.get_target(target.name)
        if new_target is None:
            self.notify(f"target '{target.name}' no longer in manifest", severity="error")
            return None
        return TargetRef(new_manifest, new_target, overrides=state.result.overrides)

    def _refresh(self, reparse: bool) -> int:
        """Re-run every target from the re-read manifest; return the count refreshed."""
        self._cursor_index = self._current_index()
        refreshed = 0
        for state in self._states:
            ref = self._refresh_ref(state)
            if ref is None:
                continue
            try:
                if reparse:
                    new = rerun_target(state.result, ref=ref)
                else:
                    new = reapply_rules(state.result, ref=ref)
            except (RunnerError, RuleValidationError) as e:
                self.notify(
                    f"Cannot refresh {state.result.qualified_name}: {e}",
                    severity="error",
                )
                continue
            state.set_result(new)
            refreshed += 1
        if self._active == self.OVERVIEW:
            self._apply_filters()
        else:
            self._save_active_target()
            self._update_header()
            self._load_active_target()
        return refreshed

    def action_refresh_rules(self) -> None:
        """Re-read the manifest and rule files and re-apply them to all targets."""
        n = self._refresh(reparse=False)
        self.notify(f"Rules re-applied ({n} targets)")

    def action_refresh_all(self) -> None:
        """Re-read the manifest, rule files and logs of all targets."""
        n = self._refresh(reparse=True)
        self.notify(f"Logs re-read ({n} targets)")

    def _toggle_severity(self, key_num: int) -> None:
        """Toggle visibility of a severity level by number key."""
        if self._active == self.OVERVIEW:
            return
        sev_id = self._key_to_severity.get(key_num)
        if not sev_id:
            return

        current = (
            dict(self.severity_filter)
            if self.severity_filter
            else {level.id: True for level in self._severity_levels}
        )
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

    def action_help(self) -> None:
        """Show keybinding help modal."""
        from sawmill.tui.widgets.help_modal import HelpModal

        self.push_screen(HelpModal())

    def action_screenshot(self, filename: str | None = None, path: str | None = None) -> None:
        """Save a screenshot as SVG (Textual built-in)."""
        saved = self.save_screenshot(filename=filename, path=path)
        self.notify(f"Screenshot saved: {saved}")


# ---------------------------------------------------------------------------
# Entry point helper
# ---------------------------------------------------------------------------


def run_tui(targets: list[TargetResult], single_log: bool = False) -> None:
    """Run the TUI application.

    Args:
        targets: Runner results, one tab per target.
        single_log: True when the one target is a bare log file (no overview).
    """
    app = SawmillApp(targets, single_log=single_log)
    app.run()
