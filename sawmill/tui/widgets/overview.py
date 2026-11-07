"""Overview table for the sawmill TUI.

Shows one row per target and one row per log beneath it, with counts per
severity, waived and hidden counts and the pass or fail result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.binding import Binding
from textual.message import Message as TextualMessage
from textual.widgets import DataTable

if TYPE_CHECKING:
    from sawmill.core.runner import LogResult
    from sawmill.models.plugin_api import SeverityLevel
    from sawmill.tui.state import TargetState

__all__ = ["OverviewTable", "counts_text"]

_PASS_STYLE = "green"
_FAIL_STYLE = "bold red"


def counts_text(counts: dict[str, int], levels: list[SeverityLevel]) -> str:
    """Format ``counts`` as ``<sev>=<n>`` most severe first.

    Zero counts are skipped, but at least one entry is always kept.
    ``other`` is appended when non-zero.
    """
    ordered = [lvl.id.lower() for lvl in sorted(levels, key=lambda s: s.level, reverse=True)]
    parts = [f"{sev}={counts.get(sev, 0)}" for sev in ordered if counts.get(sev, 0)]
    other = counts.get("other", 0)
    if other:
        parts.append(f"other={other}")
    if not parts and ordered:
        parts.append(f"{ordered[0]}=0")
    return " ".join(parts)


def _result(passed: bool) -> Text:
    return Text("PASS", style=_PASS_STYLE) if passed else Text("FAIL", style=_FAIL_STYLE)


def _hidden(log: LogResult, hidden_ids: set[str]) -> int:
    if not hidden_ids:
        return 0
    return sum(1 for m in log.messages if m.message_id in hidden_ids)


class OverviewTable(DataTable):
    """Summary table of every target and its logs."""

    BINDINGS = [Binding("enter", "open", "Open", show=False)]

    class Open(TextualMessage):
        """Posted when a target or log row is opened.

        Attributes:
            target_index: Index of the target.
            log_rel_path: Log path for a log row, else None.
        """

        def __init__(self, target_index: int, log_rel_path: str | None) -> None:
            super().__init__()
            self.target_index = target_index
            self.log_rel_path = log_rel_path

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self._row_targets: dict[str, tuple[int, str | None]] = {}

    def on_mount(self) -> None:
        """Set up the columns."""
        self.add_column("Target / Log", width=40, key="name")
        self.add_column("Counts", width=30, key="counts")
        self.add_column("Waived", width=8, key="waived")
        self.add_column("Hidden", width=8, key="hidden")
        self.add_column("Result", width=8, key="result")

    def on_resize(self) -> None:
        """Give the counts column the remaining width (minimum 30)."""
        self._fit_columns()

    def _fit_columns(self) -> None:
        """Size the counts column to fill the width left after the others."""
        col = self.columns.get("counts")  # type: ignore[call-overload]
        name = self.columns.get("name")  # type: ignore[call-overload]
        if col is None or name is None:
            return
        fixed = name.width + 8 + 8 + 8 + 2 * self.cell_padding * 5
        col.width = max(30, self.size.width - fixed - 2 * self.cell_padding)
        col.auto_width = False
        self.refresh()

    def populate(self, states: list[TargetState]) -> None:
        """Rebuild the rows from the target states."""
        self.clear()
        self._row_targets = {}
        for ti, state in enumerate(states):
            result = state.result
            levels = list(result.severity_levels)
            hidden_total = sum(_hidden(log, state.hidden_ids) for log in result.logs)
            key = f"t:{ti}"
            self._row_targets[key] = (ti, None)
            self.add_row(
                Text(result.qualified_name),
                counts_text(result.counts, levels),
                str(result.waived_count),
                str(hidden_total),
                _result(result.passed),
                key=key,
            )
            if result.no_logs:
                key = f"l:{ti}:none"
                self._row_targets[key] = (ti, None)
                self.add_row(Text("  (no logs matched)"), "", "", "", _result(False), key=key)
                continue
            for li, log in enumerate(result.logs):
                key = f"l:{ti}:{li}"
                self._row_targets[key] = (ti, log.rel_path)
                self.add_row(
                    Text(f"  {log.rel_path}"),
                    counts_text(log.counts, levels),
                    str(len(log.waived)),
                    str(_hidden(log, state.hidden_ids)),
                    _result(log.passed),
                    key=key,
                )
        self._fit_name_column()

    def _fit_name_column(self) -> None:
        """Widen the name column to the longest name plus 2 (minimum 40)."""
        name = self.columns.get("name")  # type: ignore[call-overload]
        if name is None:
            return
        longest = max((Text(str(c)).cell_len for c in self.get_column("name")), default=0)
        name.width = max(40, longest + 2)
        name.auto_width = False
        self._fit_columns()

    def action_open(self) -> None:
        """Post :class:`OverviewTable.Open` for the highlighted row."""
        if not self.row_count:
            return
        key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key.value
        if key is None or key not in self._row_targets:
            return
        ti, rel = self._row_targets[key]
        self.post_message(self.Open(ti, rel))
