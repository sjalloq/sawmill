"""Grouped message list widget for sawmill TUI.

This module provides a message list widget that supports grouping
messages by severity, ID, file, or category with expand/collapse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Tree, Label
from textual.widgets.tree import TreeNode

if TYPE_CHECKING:
    from sawmill.models.message import Message as LogMessage

from sawmill.core.aggregation import Aggregator


class MessageSelected(Message):
    """Message emitted when a log message is selected.

    Attributes:
        message: The selected log message.
    """

    def __init__(self, message: LogMessage) -> None:
        """Initialize the message."""
        super().__init__()
        self.message = message


class GroupSelected(Message):
    """Message emitted when a group is selected.

    Attributes:
        group_key: The key of the selected group.
        group_by: The field used for grouping.
    """

    def __init__(self, group_key: str, group_by: str) -> None:
        """Initialize the message."""
        super().__init__()
        self.group_key = group_key
        self.group_by = group_by


class MessageTree(Tree):
    """Tree widget for displaying grouped messages."""

    def __init__(self, *args, **kwargs):
        """Initialize the tree."""
        super().__init__("Messages", *args, **kwargs)
        self.show_root = False


class GroupedMessageList(Static):
    """Widget for displaying messages in groups with expand/collapse.

    Features:
    - Group messages by severity, ID, file, or category
    - Expand/collapse groups
    - Show sample messages with "N more" indicator
    - Click to select message
    """

    # Class-level attribute to avoid AttributeError during init
    _tree: MessageTree | None = None
    _messages: list = []

    DEFAULT_CSS = """
    GroupedMessageList {
        width: 100%;
        height: 100%;
        background: $surface;
    }

    MessageTree {
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
    group_by: reactive[str] = reactive("severity")
    max_per_group: reactive[int] = reactive(5)

    def __init__(
        self,
        messages: list[LogMessage] | None = None,
        group_by: str = "severity",
        max_per_group: int = 5,
        *args,
        **kwargs,
    ):
        """Initialize the widget.

        Args:
            messages: Initial list of messages to display.
            group_by: Field to group by (severity, id, file, category).
            max_per_group: Maximum messages to show per group.
        """
        # Initialize _tree before super().__init__ to avoid reactive watcher issues
        self._tree: MessageTree | None = None
        self._messages: list[LogMessage] = messages or []
        self._group_by = group_by
        self._max_per_group = max_per_group
        super().__init__(*args, **kwargs)
        # Set reactive properties after super().__init__
        self.group_by = group_by
        self.max_per_group = max_per_group

    @property
    def messages(self) -> list[LogMessage]:
        """Get the current messages."""
        return self._messages

    @messages.setter
    def messages(self, value: list[LogMessage]) -> None:
        """Set messages and refresh the display."""
        self._messages = value
        self.refresh_display()

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        yield MessageTree(id="message-tree")

    def on_mount(self) -> None:
        """Handle mount - set up the tree."""
        self._tree = self.query_one("#message-tree", MessageTree)
        self.refresh_display()

    def watch_group_by(self, value: str) -> None:
        """React to group_by changes."""
        self.refresh_display()

    def watch_max_per_group(self, value: int) -> None:
        """React to max_per_group changes."""
        self.refresh_display()

    def refresh_display(self) -> None:
        """Refresh the display with current messages and grouping."""
        if not self._tree:
            return

        self._tree.clear()

        if not self._messages:
            self._tree.root.add_leaf("[dim]No messages[/dim]")
            return

        # Group messages
        aggregator = Aggregator()
        groups = aggregator.group_by(self._messages, self.group_by)
        sorted_groups = aggregator.sorted_groups(groups, by_count=True)

        # Build tree
        for key, stats in sorted_groups:
            # Format group label
            group_label = self._format_group_label(key, stats)

            # Add group node
            group_node = self._tree.root.add(group_label, expand=False)
            group_node.data = {"type": "group", "key": key, "group_by": self.group_by}

            # Add messages under group
            messages_to_show = (
                stats.messages[:self.max_per_group]
                if self.max_per_group > 0
                else stats.messages
            )

            for msg in messages_to_show:
                msg_label = self._format_message_label(msg)
                msg_node = group_node.add_leaf(msg_label)
                msg_node.data = {"type": "message", "message": msg}

            # Add "and N more" if truncated
            remaining = len(stats.messages) - len(messages_to_show)
            if remaining > 0:
                more_node = group_node.add_leaf(f"[dim]... and {remaining} more[/dim]")
                more_node.data = None

    def _format_group_label(self, key: str, stats) -> str:
        """Format a group label.

        Args:
            key: The group key.
            stats: The MessageStats for this group.

        Returns:
            Formatted label string.
        """
        if self.group_by == "severity":
            sev_display = key.title().replace("_", " ")
            return f"{sev_display} ({stats.count})"
        elif self.group_by == "id":
            sev_tag = f" [{stats.severity.title()}]" if stats.severity else ""
            return f"{key}{sev_tag} ({stats.count})"
        elif self.group_by == "file":
            return f"{key} ({stats.count})"
        elif self.group_by == "category":
            return f"{key.title()} ({stats.count})"
        else:
            return f"{key} ({stats.count})"

    def _format_message_label(self, msg: LogMessage) -> str:
        """Format a message label for display.

        Args:
            msg: The message to format.

        Returns:
            Formatted label string.
        """
        # Build location string
        if msg.file_ref:
            loc = msg.file_ref.path
            if msg.file_ref.line:
                loc += f":{msg.file_ref.line}"
        else:
            loc = f"L{msg.start_line}"

        # Truncate content
        content = msg.content
        if len(content) > 60:
            content = content[:57] + "..."

        # Format with severity color
        sev = msg.severity.lower() if msg.severity else "other"
        sev_tag = sev.title()[:4]

        return f"[{sev_tag}] {loc}: {content}"

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node = event.node
        if node.data:
            if node.data["type"] == "message":
                self.post_message(MessageSelected(node.data["message"]))
            elif node.data["type"] == "group":
                self.post_message(GroupSelected(
                    node.data["key"],
                    node.data["group_by"],
                ))

    def set_grouping(self, group_by: str) -> None:
        """Set the grouping mode.

        Args:
            group_by: Field to group by (severity, id, file, category).
        """
        self.group_by = group_by

    def set_max_per_group(self, max_count: int) -> None:
        """Set the maximum messages shown per group.

        Args:
            max_count: Maximum messages per group (0 = no limit).
        """
        self.max_per_group = max_count
