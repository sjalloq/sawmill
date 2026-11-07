"""Per-target view state for the sawmill TUI."""

from __future__ import annotations

from dataclasses import dataclass, field

from sawmill.core.runner import TargetResult
from sawmill.models.message import Message

# ---------------------------------------------------------------------------
# Sort mode constants
# ---------------------------------------------------------------------------
SORT_LINE = "line"
SORT_SEVERITY = "severity"
SORT_ID = "id"
SORT_COUNT = "count"
SORT_MODES = [SORT_LINE, SORT_SEVERITY, SORT_ID, SORT_COUNT]


@dataclass
class TargetState:
    """View state of one target tab.

    Attributes:
        result: The runner result shown by the tab.
        filter_text: Search bar text.
        severity_filter: Per-severity visibility toggles; empty means all on.
        sort_mode: One of :data:`SORT_MODES`.
        hidden_ids: Message ids hidden until the app exits.
        show_all: Include waived and hidden messages.
        cursor_index: Absolute index of the highlighted row.
        window_start: First row of the table window.
        waived_ids: ``id()`` of every waived message, computed from ``result``.
    """

    result: TargetResult
    filter_text: str = ""
    severity_filter: dict[str, bool] = field(default_factory=dict)
    sort_mode: str = SORT_LINE
    hidden_ids: set[str] = field(default_factory=set)
    show_all: bool = False
    cursor_index: int = 0
    window_start: int = 0
    waived_ids: frozenset[int] = field(init=False, default=frozenset())

    def __post_init__(self) -> None:
        """Compute the waived message identities once."""
        self.waived_ids = frozenset(id(m) for log in self.result.logs for m, _ in log.waived)

    def set_result(self, result: TargetResult) -> None:
        """Replace the result and recompute :attr:`waived_ids`."""
        self.result = result
        self.__post_init__()

    def base_messages(self) -> list[Message]:
        """Return the target's messages before search, severity and sort.

        Waived messages and messages with a hidden id are excluded unless
        ``show_all`` is set. Order is log order, then parse order.
        """
        messages = self.result.all_messages
        if self.show_all:
            return messages
        waived = self.waived_ids
        hidden = self.hidden_ids
        return [
            m for m in messages if id(m) not in waived and not (hidden and m.message_id in hidden)
        ]
