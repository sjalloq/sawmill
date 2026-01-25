"""Summary panel widget for sawmill TUI.

This module provides a summary panel showing severity breakdown
with expandable ID counts, similar to hal_log_parser.py's summary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Tree, Label
from textual.widgets.tree import TreeNode

if TYPE_CHECKING:
    from sawmill.models.message import Message as LogMessage

from sawmill.core.aggregation import Aggregator, SEVERITY_ORDER


class SeveritySelected(Message):
    """Message emitted when a severity is selected.

    Attributes:
        severity: The selected severity level.
    """

    def __init__(self, severity: str) -> None:
        """Initialize the message."""
        super().__init__()
        self.severity = severity


class IdSelected(Message):
    """Message emitted when a message ID is selected.

    Attributes:
        message_id: The selected message ID.
    """

    def __init__(self, message_id: str) -> None:
        """Initialize the message."""
        super().__init__()
        self.message_id = message_id


class SummaryTree(Tree):
    """Tree widget for displaying message summary with severity/ID breakdown."""

    def __init__(self, *args, **kwargs):
        """Initialize the tree."""
        super().__init__("Summary", *args, **kwargs)
        self.show_root = False


class SummaryPanel(Static):
    """Panel widget displaying message summary by severity and ID.

    Features:
    - Expandable severity levels
    - Message ID breakdown within each severity
    - Counts for each level
    - Click to filter
    """

    DEFAULT_CSS = """
    SummaryPanel {
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 1;
    }

    SummaryPanel > Label {
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }

    SummaryPanel > .total-label {
        margin-top: 1;
        color: $text-muted;
    }

    SummaryTree {
        height: 100%;
    }

    .severity-critical {
        color: red;
        text-style: bold;
    }

    .severity-error {
        color: red;
    }

    .severity-warning {
        color: yellow;
    }

    .severity-info {
        color: cyan;
    }
    """

    # Reactive properties
    total_count: reactive[int] = reactive(0)

    def __init__(self, messages: list[LogMessage] | None = None, *args, **kwargs):
        """Initialize the panel.

        Args:
            messages: Initial list of messages to summarize.
        """
        super().__init__(*args, **kwargs)
        self._messages: list[LogMessage] = messages or []
        self._tree: SummaryTree | None = None

    @property
    def messages(self) -> list[LogMessage]:
        """Get the current messages."""
        return self._messages

    @messages.setter
    def messages(self, value: list[LogMessage]) -> None:
        """Set messages and update the summary."""
        self._messages = value
        self.refresh_summary()

    def compose(self) -> ComposeResult:
        """Create the panel layout."""
        yield Label("Message Summary")
        yield SummaryTree(id="summary-tree")
        yield Label(f"Total: {self.total_count}", id="total-label", classes="total-label")

    def on_mount(self) -> None:
        """Handle mount - set up the tree."""
        self._tree = self.query_one("#summary-tree", SummaryTree)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """Refresh the summary display with current messages."""
        if not self._tree:
            return

        # Clear existing tree
        self._tree.clear()

        if not self._messages:
            self._tree.root.add_leaf("[dim]No messages[/dim]")
            self.total_count = 0
            return

        # Get summary using Aggregator
        aggregator = Aggregator()
        summary = aggregator.get_summary(self._messages)
        sorted_summary = aggregator.sorted_summary(summary)

        # Update total
        self.total_count = len(self._messages)

        # Build tree
        for severity, stats in sorted_summary:
            # Format severity label with count
            sev_display = severity.title().replace("_", " ")
            sev_label = f"{sev_display} ({stats.total})"

            # Add severity color class
            severity_class = f"severity-{severity.replace('_', '-')}"

            # Add severity node
            sev_node = self._tree.root.add(sev_label, expand=False)
            sev_node.data = {"type": "severity", "value": severity}

            # Sort IDs by count descending
            sorted_ids = sorted(stats.by_id.items(), key=lambda x: (-x[1], x[0]))

            # Add ID nodes under severity
            for msg_id, count in sorted_ids:
                id_label = f"{msg_id} ({count})"
                id_node = sev_node.add_leaf(id_label)
                id_node.data = {"type": "id", "value": msg_id}

        # Update the total label
        total_label = self.query_one("#total-label", Label)
        total_label.update(f"Total: {self.total_count}")

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node = event.node
        if node.data:
            if node.data["type"] == "severity":
                self.post_message(SeveritySelected(node.data["value"]))
            elif node.data["type"] == "id":
                self.post_message(IdSelected(node.data["value"]))

    def get_severity_counts(self) -> dict[str, int]:
        """Get counts by severity level.

        Returns:
            Dictionary mapping severity to count.
        """
        aggregator = Aggregator()
        summary = aggregator.get_summary(self._messages)
        return {sev: stats.total for sev, stats in summary.items()}

    def get_id_counts(self, severity: str | None = None) -> dict[str, int]:
        """Get counts by message ID.

        Args:
            severity: Optional severity to filter by.

        Returns:
            Dictionary mapping message ID to count.
        """
        aggregator = Aggregator()
        summary = aggregator.get_summary(self._messages)

        if severity:
            if severity in summary:
                return dict(summary[severity].by_id)
            return {}

        # Combine all severities
        all_ids: dict[str, int] = {}
        for stats in summary.values():
            for msg_id, count in stats.by_id.items():
                all_ids[msg_id] = all_ids.get(msg_id, 0) + count
        return all_ids
