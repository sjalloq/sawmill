"""Main TUI application for sawmill.

This module provides the Textual-based terminal user interface for
interactive log analysis. Layout follows the hpc-runner style:
header / severity bar / search / messages / detail / footer.
"""

from __future__ import annotations

import re
from datetime import date
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

from sawmill.core.filter import FilterEngine, filter_by_severity_toggles, match_message_id
from sawmill.core.waiver import WaiverMatcher
from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.filter_parser import parse_filter
from sawmill.tui.theme import register_nord_theme
from sawmill.tui.widgets.footer import SawmillFooter

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
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "clear_filter", "Clear Filter", show=False),
        Binding("/", "focus_filter", "Filter", show=False),
        Binding("tab", "toggle_focus", "Toggle Focus", show=False),
        Binding("o", "cycle_sort", "Sort", show=False),
        Binding("s", "suppress", "Suppress", show=False),
        Binding("w", "waive", "Waive", show=False),
        Binding("left", "prev_tab", "Prev Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
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
    suppressed_ids: reactive[set[str]] = reactive(set, always_update=True, init=False)
    # TODO: _waiver_version is a workaround to trigger re-filtering when
    # _waiver_matcher changes. Investigate making _waiver_matcher itself
    # reactive, or using Textual's message system instead.
    _waiver_version: reactive[int] = reactive(0, init=False)
    active_tab: reactive[str] = reactive("messages", init=False)

    def __init__(
        self,
        severity_levels: list[SeverityLevel],
        log_file: Path | None = None,
        messages: list[Message] | None = None,
        plugin_name: str | None = None,
        waiver_file_path: Path | None = None,
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
            level.id.lower(): level.level for level in self._severity_levels
        }
        # Map numeric keys to severity IDs (sorted ascending by level: 1=lowest)
        self._key_to_severity: dict[int, str] = {}
        for i, level in enumerate(sorted(self._severity_levels, key=lambda s: s.level), start=1):
            self._key_to_severity[i] = level.id

        # Widget refs (set in on_mount)
        self._stats_widget: MessageStats | None = None
        self._log_viewer: LogViewer | None = None
        self._filter_input: FilterInput | None = None
        self._detail_content: Static | None = None

        # Suppress state
        self._suppressions_dirty: bool = False
        self._suppress_patterns: list[str] = []

        # Waive state
        from sawmill.models.waiver import Waiver

        self._file_waivers: list[Waiver] = []
        self._session_waivers: list[Waiver] = []
        self._waivers_dirty: bool = False
        self._waiver_file_path: Path | None = waiver_file_path
        self._waiver_matcher = WaiverMatcher([])

        # ID count cache for count sort mode
        self._id_counts: dict[str, int] = {}

        # Tab message lists (managed in _apply_filters, not reactive)
        self._main_messages: list[Message] = []
        self._waived_messages: list[Message] = []
        self._suppressed_messages: list[Message] = []

    def _rebuild_waiver_matcher(self) -> None:
        """Rebuild the WaiverMatcher from file + session waivers and trigger re-filter."""
        self._waiver_matcher = WaiverMatcher(self._file_waivers + self._session_waivers)
        self._waiver_version += 1

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
        filename = self.log_file.name if self.log_file else ""
        with Horizontal(id="header"):
            yield Static("sawmill", id="header-brand")
            yield Static("Messages", id="tab-messages", classes="header-tab active-tab")
            yield Static("Waived", id="tab-waived", classes="header-tab")
            yield Static("Suppressed", id="tab-suppressed", classes="header-tab")
            yield Static(filename, id="header-right")
        with Vertical(id="severity-panel", classes="panel"):
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
                ("o", "Sort"),
                ("\u2190\u2192", "Tab"),
                ("s", "Suppress"),
                ("w", "Waive"),
                ("?", "Help"),
            ],
        )

    def on_mount(self) -> None:
        """Handle app mount — apply theme, set up widgets, load saved state."""
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

        # Load config (may set default_plugin before loading messages)
        self._load_config()

        # Load messages if we have a log file
        if self.log_file and not self._messages:
            self._load_messages()

        # Load saved suppressions and waivers (does not mark dirty)
        self._load_saved_suppressions()
        self._load_saved_waivers()

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

        from sawmill.core.plugin import PluginError, get_plugin_manager, select_plugin
        from sawmill.models.plugin_api import severity_levels_from_dicts

        manager = get_plugin_manager()

        try:
            plugin = select_plugin(manager, self._plugin_name, self.log_file)
            self._messages = plugin.load_and_parse(self.log_file)

            if hasattr(plugin, "get_severity_levels"):
                try:
                    severity_dicts = plugin.get_severity_levels()
                    self._severity_levels = severity_levels_from_dicts(severity_dicts)
                    self._severity_level_map = {
                        level.id.lower(): level.level for level in self._severity_levels
                    }
                except Exception:
                    pass
        except PluginError as e:
            self.notify(f"Error loading log: {e}", severity="error")

    def _load_config(self) -> None:
        """Load config on startup and apply defaults (e.g. default_plugin)."""
        try:
            from sawmill.core.config import ConfigLoader

            config = ConfigLoader().load_resolved()
            if config.general.default_plugin and not self._plugin_name:
                self._plugin_name = config.general.default_plugin
        except Exception:
            pass  # Config errors are non-fatal at startup

    def _load_saved_suppressions(self) -> None:
        """Load saved suppression IDs from .sawmill/suppress.toml."""
        try:
            from sawmill.tui.session import load_suppressions

            config = load_suppressions()
            if config.message_ids:
                self.suppressed_ids = set(config.message_ids)
            if config.patterns:
                self._suppress_patterns = list(config.patterns)
        except Exception:
            pass  # Suppression load errors are non-fatal

    def _load_saved_waivers(self) -> None:
        """Load saved waivers from waiver file."""
        try:
            from sawmill.tui.session import load_waivers
            from sawmill.utils.dirs import resolve_sawmill_dir

            waiver_path = self._waiver_file_path
            if waiver_path is None:
                sawmill_dir = resolve_sawmill_dir()
                if sawmill_dir is not None:
                    candidate = sawmill_dir / "waivers.toml"
                    if candidate.exists():
                        waiver_path = candidate

            if waiver_path and waiver_path.exists():
                waivers = load_waivers(waiver_path)
                if waivers:
                    self._file_waivers = waivers
                    self._rebuild_waiver_matcher()
        except Exception:
            pass  # Waiver load errors are non-fatal

    # -- Filtering & Sorting -------------------------------------------------

    def _apply_filters(self) -> None:
        """Apply current filters, sort, and update the display.

        This is the single rendering path. All state changes that affect the
        display go through reactive watchers which call this method.
        """
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
            filtered = filter_by_severity_toggles(filtered, effective_sev)

        # Apply id: prefix filter (fnmatch)
        if parsed.message_id:
            filtered = [m for m in filtered if match_message_id(m.message_id, parsed.message_id)]

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

        # Bucket into three lists: suppressed, waived, main
        engine = FilterEngine()
        non_suppressed, self._suppressed_messages = engine.apply_suppress_ids(
            self.suppressed_ids, filtered
        )

        # Apply regex suppression patterns (from saved config)
        if self._suppress_patterns:
            non_suppressed = engine.apply_suppressions(self._suppress_patterns, non_suppressed)

        self._waived_messages = [
            m for m in non_suppressed if self._waiver_matcher.is_waived(m) is not None
        ]
        self._main_messages = [
            m for m in non_suppressed if self._waiver_matcher.is_waived(m) is None
        ]

        # Select active list
        self._filtered_messages = self._active_message_list()

        # Compute ID counts for count sort mode (on active list)
        self._id_counts = {}
        for m in self._filtered_messages:
            mid = m.message_id or ""
            self._id_counts[mid] = self._id_counts.get(mid, 0) + 1

        # Sort
        self._filtered_messages = self._sort_messages(self._filtered_messages)

        self._update_stats()
        self._update_tab_labels()
        self._populate_table()

    def _active_message_list(self) -> list[Message]:
        """Return the message list for the currently active tab."""
        if self.active_tab == "waived":
            return self._waived_messages.copy()
        elif self.active_tab == "suppressed":
            return self._suppressed_messages.copy()
        return self._main_messages.copy()

    def _update_tab_labels(self) -> None:
        """Update tab label counts from the bucketed message lists."""
        pass  # Tab labels are now static text without counts

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

                sev_display = sev.title()

                self._log_viewer.add_row(
                    str(msg.start_line),
                    sev_display,
                    escape(msg_id),
                    escape(content),
                    key=str(i),
                )

            # Restore cursor position (clamped to valid range)
            if self._filtered_messages:
                restored_row = min(prev_row, len(self._filtered_messages) - 1)
                self._log_viewer.move_cursor(row=restored_row)
                self._update_detail_for_row(restored_row)
            else:
                self._update_detail_for_row(0)

        # Update panel border title and sort subtitle
        try:
            panel = self.query_one("#messages-panel")
            titles = {
                "messages": "Messages",
                "waived": "Waived",
                "suppressed": "Suppressed",
            }
            panel.border_title = titles.get(self.active_tab, "Messages")
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

    def watch_suppressed_ids(self, value: set[str]) -> None:
        self._apply_filters()

    def watch__waiver_version(self, value: int) -> None:
        self._apply_filters()

    def watch_active_tab(self, tab: str) -> None:
        """Handle tab switch: swap displayed messages, update header styling."""
        for tab_id in ("tab-messages", "tab-waived", "tab-suppressed"):
            try:
                widget = self.query_one(f"#{tab_id}", Static)
                if tab_id == f"tab-{tab}":
                    widget.add_class("active-tab")
                else:
                    widget.remove_class("active-tab")
            except Exception:
                pass

        # Swap the displayed message list and repopulate
        self._filtered_messages = self._active_message_list()

        # Recompute ID counts for the new list
        self._id_counts = {}
        for m in self._filtered_messages:
            mid = m.message_id or ""
            self._id_counts[mid] = self._id_counts.get(mid, 0) + 1

        self._filtered_messages = self._sort_messages(self._filtered_messages)
        self._update_stats()
        self._populate_table()
        self._update_footer_hints()

    def _update_footer_hints(self) -> None:
        """Update footer keybinding hints based on the active tab."""
        try:
            footer = self.query_one(SawmillFooter)
        except Exception:
            return
        base: list[tuple[str, str]] = [
            ("q", "Quit"),
            ("/", "Search"),
            ("Tab", "Focus"),
            ("1-4", "Severity"),
            ("o", "Sort"),
            ("\u2190\u2192", "Tab"),
        ]
        if self.active_tab == "messages":
            base.extend([("s", "Suppress"), ("w", "Waive")])
        elif self.active_tab == "waived":
            base.extend([("s", "Suppress"), ("w", "Un-waive")])
        elif self.active_tab == "suppressed":
            base.append(("s", "Un-suppress"))
        base.append(("?", "Help"))
        footer.update_bindings(base)

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
                    str(i),
                    "message",
                    content,
                    update_width=False,
                )

    # -- Actions -------------------------------------------------------------

    async def action_quit(self) -> None:
        """Quit with dirty-state check."""
        if self._suppressions_dirty or self._waivers_dirty:
            from sawmill.tui.widgets.quit_modal import QuitConfirmModal

            suppression_count = len(self.suppressed_ids)
            waiver_count = len(self._session_waivers)
            self.push_screen(
                QuitConfirmModal(
                    suppression_count=suppression_count,
                    waiver_count=waiver_count,
                ),
                callback=self._on_quit_result,
            )
        else:
            self.exit()

    def _on_quit_result(self, result: str | None) -> None:
        """Handle quit confirmation modal result."""
        if result == "save_quit":
            self._save_all()
            self.exit()
        elif result == "discard_quit":
            self.exit()
        # else: None (cancelled) — stay in app

    def action_save(self) -> None:
        """Save session state (Ctrl+S)."""
        self._save_all()

    def _notify_safe(self, message: str, **kwargs) -> None:
        """Notify if the app is mounted, otherwise silently ignore."""
        import contextlib

        with contextlib.suppress(Exception):
            self.notify(message, **kwargs)

    def _save_all(self) -> None:
        """Save both suppressions and waivers to their respective files."""
        saved_parts = []

        # Save suppressions to sawmill.toml
        if self._suppressions_dirty:
            try:
                self._save_suppressions()
                saved_parts.append(f"{len(self.suppressed_ids)} suppressions to suppress.toml")
                self._suppressions_dirty = False
            except Exception as e:
                self._notify_safe(f"Failed to save suppressions: {e}", severity="error")

        # Save waivers to waiver file
        if self._waivers_dirty and self._session_waivers:
            try:
                self._save_waivers()
                saved_parts.append(
                    f"{len(self._session_waivers)} waivers to {self._resolve_waiver_path().name}"
                )
                self._waivers_dirty = False
                self._session_waivers = []
            except Exception as e:
                self._notify_safe(f"Failed to save waivers: {e}", severity="error")

        if saved_parts:
            self._notify_safe(f"Saved: {', '.join(saved_parts)}")
        elif not self._suppressions_dirty and not self._waivers_dirty:
            self._notify_safe("Nothing to save")

    def _save_suppressions(self) -> None:
        """Save suppression IDs to .sawmill/suppress.toml."""
        from sawmill.tui.session import save_suppressions

        save_suppressions(self.suppressed_ids)

    def _resolve_waiver_path(self) -> Path:
        """Resolve the waiver file path, defaulting to .sawmill/waivers.toml."""
        if self._waiver_file_path is None:
            from sawmill.tui.session import resolve_waiver_path

            self._waiver_file_path = resolve_waiver_path()
        return self._waiver_file_path

    def _save_waivers(self) -> None:
        """Append session waivers to the waiver file."""
        from sawmill.tui.session import save_session_waivers

        save_session_waivers(
            self._session_waivers,
            self._resolve_waiver_path(),
            plugin_name=self._plugin_name,
        )

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

    def action_prev_tab(self) -> None:
        """Switch to the previous tab (left arrow)."""
        if self._filter_input and self._filter_input.has_focus:
            return
        tabs = ["messages", "waived", "suppressed"]
        idx = tabs.index(self.active_tab)
        self.active_tab = tabs[(idx - 1) % len(tabs)]

    def action_next_tab(self) -> None:
        """Switch to the next tab (right arrow)."""
        if self._filter_input and self._filter_input.has_focus:
            return
        tabs = ["messages", "waived", "suppressed"]
        idx = tabs.index(self.active_tab)
        self.active_tab = tabs[(idx + 1) % len(tabs)]

    def action_cycle_sort(self) -> None:
        """Cycle through sort modes."""
        idx = SORT_MODES.index(self.sort_mode)
        self.sort_mode = SORT_MODES[(idx + 1) % len(SORT_MODES)]

    def action_suppress(self) -> None:
        """Context-sensitive suppress: un-suppress on Suppressed tab, suppress elsewhere."""
        if self.active_tab == "suppressed":
            self._unsuppress_current()
        else:
            self._suppress_current()

    def _suppress_current(self) -> None:
        """Suppress the highlighted message (from Messages or Waived tab)."""
        if not self._log_viewer or not self._filtered_messages:
            return
        row = self._log_viewer.cursor_row
        if row < 0 or row >= len(self._filtered_messages):
            return
        msg = self._filtered_messages[row]
        if msg.message_id is None:
            self.notify("Cannot suppress: message has no ID")
            return
        current = set(self.suppressed_ids)
        current.add(msg.message_id)
        self._suppressions_dirty = True
        self.notify(f"Suppressed: {msg.message_id}")
        self.suppressed_ids = current

    def _unsuppress_current(self) -> None:
        """Un-suppress the highlighted message (from Suppressed tab)."""
        if not self._log_viewer or not self._filtered_messages:
            return
        row = self._log_viewer.cursor_row
        if row < 0 or row >= len(self._filtered_messages):
            return
        msg = self._filtered_messages[row]
        if msg.message_id is None:
            return
        current = set(self.suppressed_ids)
        current.discard(msg.message_id)
        self._suppressions_dirty = True
        self.notify(f"Un-suppressed: {msg.message_id}")
        self.suppressed_ids = current

    def action_waive(self) -> None:
        """Context-sensitive waive: un-waive on Waived tab, no-op on Suppressed, waive elsewhere."""
        if self.active_tab == "waived":
            self._unwaive_current()
        elif self.active_tab == "suppressed":
            self.notify("Un-suppress first before waiving", severity="warning")
        else:
            self._waive_current()

    def _waive_current(self) -> None:
        """Open waive modal for the highlighted message."""
        if not self._log_viewer or not self._filtered_messages:
            return

        row = self._log_viewer.cursor_row
        if row < 0 or row >= len(self._filtered_messages):
            return

        msg = self._filtered_messages[row]
        if msg.message_id is None:
            self.notify("Cannot waive: message has no ID")
            return

        from sawmill.tui.widgets.waive_modal import WaiveModal
        from sawmill.utils.author import discover_author

        self.push_screen(
            WaiveModal(
                message_id=msg.message_id,
                severity=(msg.severity or "").title(),
                content=msg.content,
                author=discover_author(),
                waiver_file_path=str(self._resolve_waiver_path()),
            ),
            callback=self._on_waive_modal_result,
        )

    def _unwaive_current(self) -> None:
        """Un-waive the highlighted message (from Waived tab)."""
        if not self._log_viewer or not self._filtered_messages:
            return
        row = self._log_viewer.cursor_row
        if row < 0 or row >= len(self._filtered_messages):
            return
        msg = self._filtered_messages[row]
        if msg.message_id is None:
            return

        matching_waiver = self._waiver_matcher.is_waived(msg)
        if matching_waiver is None:
            return

        was_session = any(w is matching_waiver for w in self._session_waivers)
        was_file = any(w is matching_waiver for w in self._file_waivers)
        self._session_waivers = [w for w in self._session_waivers if w is not matching_waiver]
        self._file_waivers = [w for w in self._file_waivers if w is not matching_waiver]
        self._waivers_dirty = True
        self._rebuild_waiver_matcher()

        if was_session:
            self.notify(f"Un-waived: {msg.message_id}")
        elif was_file:
            self.notify(
                f"Un-waived: {msg.message_id} (for this session only \u2014 "
                f"edit waivers.toml to remove permanently)",
                severity="warning",
            )
        else:
            self.notify(f"Un-waived: {msg.message_id}")

    def _on_waive_modal_result(self, result: dict | None) -> None:
        """Handle the result from the waive modal."""
        if result is None:
            return

        from sawmill.models.waiver import Waiver

        waiver = Waiver(
            message_id=result["message_id"],
            content_match=result.get("content_match"),
            content_pattern=result.get("content_pattern"),
            reason=result["reason"],
            author=result["author"],
            date=date.today().isoformat(),
        )
        self._session_waivers.append(waiver)
        self._waivers_dirty = True
        self.notify(f"Waived: {waiver.message_id}")
        self._rebuild_waiver_matcher()

    def _toggle_severity(self, key_num: int) -> None:
        """Toggle visibility of a severity level by number key."""
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


def run_tui(
    log_file: Path | None = None,
    plugin_name: str | None = None,
    severity_levels: list[SeverityLevel] | None = None,
    waiver_file_path: Path | None = None,
) -> None:
    """Run the TUI application.

    Args:
        log_file: Path to the log file to analyze.
        plugin_name: Name of plugin to use.
        severity_levels: Severity level definitions from plugin.
        waiver_file_path: Path to the waiver file for saving waivers.
    """
    app = SawmillApp(
        log_file=log_file,
        plugin_name=plugin_name,
        severity_levels=severity_levels or [],
        waiver_file_path=waiver_file_path,
    )
    app.run()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_tui(Path(sys.argv[1]))
    else:
        run_tui()
