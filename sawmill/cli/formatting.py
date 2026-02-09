"""Output formatting for sawmill CLI.

Provides functions to format and display messages in various output modes.
"""

from __future__ import annotations

import json
import textwrap

from rich.console import Console

from sawmill.core.aggregation import Aggregator
from sawmill.core.severity import get_severity_style


def output_messages(
    console: Console,
    messages: list,
    output_format: str,
    style_map: dict[str, str],
    severity_ids: list[str] | None = None,
) -> None:
    """Output messages in the specified format.

    Args:
        console: Rich console for output.
        messages: List of messages to output.
        output_format: Output format (text, json, count).
        style_map: Dictionary mapping severity ID to Rich style string.
        severity_ids: List of severity IDs from plugin (for count format).
    """
    if output_format.lower() == "json":
        # JSONL format: one JSON object per line
        for msg in messages:
            obj = {
                "start_line": msg.start_line,
                "end_line": msg.end_line,
                "raw_text": msg.raw_text,
                "content": msg.content,
                "severity": msg.severity,
                "message_id": msg.message_id,
                "category": msg.category,
            }
            # Add file_ref if present
            if msg.file_ref:
                obj["file_ref"] = {
                    "path": msg.file_ref.path,
                    "line": msg.file_ref.line,
                }
            print(json.dumps(obj))

    elif output_format.lower() == "count":
        # Count format: summary statistics by severity
        # Build counts dynamically from plugin's severity IDs
        if severity_ids:
            counts: dict[str, int] = {sev_id: 0 for sev_id in severity_ids}
        else:
            counts = {}
        counts["other"] = 0

        for msg in messages:
            if msg.severity:
                sev = msg.severity.lower()
                if sev in counts:
                    counts[sev] += 1
                else:
                    counts["other"] += 1
            else:
                counts["other"] += 1

        # Output the summary with dynamic severity names
        total = len(messages)
        parts = [f"total={total}"]
        for sev_id in severity_ids or []:
            parts.append(f"{sev_id}={counts.get(sev_id, 0)}")
        if counts["other"] > 0:
            parts.append(f"other={counts['other']}")
        console.print(" ".join(parts))

    else:
        # Text format (default): human-readable with colors
        # Note: We use markup=False to prevent Rich from interpreting
        # log content like [/path/to/file:line] as markup tags.
        for msg in messages:
            style = get_severity_style(msg.severity, style_map)
            if style:
                console.print(msg.raw_text, style=style, markup=False)
            else:
                console.print(msg.raw_text, markup=False)


def print_summary(
    console: Console,
    messages: list,
    style_map: dict[str, str],
    severity_levels: list,
) -> None:
    """Print summary statistics grouped by severity with ID breakdown.

    Similar to hal_log_parser.py's print_summary() function.

    Args:
        console: Rich console for output.
        messages: List of messages to summarize.
        style_map: Dictionary mapping severity ID to Rich style string.
        severity_levels: List of SeverityLevel objects from plugin.
    """
    aggregator = Aggregator(severity_levels=severity_levels)
    summary = aggregator.get_summary(messages)

    if not summary:
        console.print("[dim]No messages to summarize.[/dim]")
        return

    # Sort summary by severity order
    sorted_summary = aggregator.sorted_summary(summary)

    console.print()
    console.print("=" * 70)
    console.print("Log Analysis Summary")
    console.print("=" * 70)

    for sev, stats in sorted_summary:
        sev_display = sev.title().replace("_", " ")
        console.print(f"\n {sev_display:16s} : ({stats.total})")

        # Sort IDs by count descending
        sorted_ids = sorted(stats.by_id.items(), key=lambda x: (-x[1], x[0]))

        # Print IDs in columns (4 per row like HAL)
        for i in range(0, len(sorted_ids), 4):
            row = sorted_ids[i : i + 4]
            formatted = [f"  {msg_id} ({count})" for msg_id, count in row]
            # Right-pad each item to 16 chars for columnar display
            line = "".join(f"{item:18s}" for item in formatted)
            console.print(line)

    console.print()
    console.print("=" * 70)
    console.print(f"Total: {len(messages)} messages")
    console.print("=" * 70)


def print_grouped(
    console: Console,
    messages: list,
    group_by: str,
    top_n: int,
    style_map: dict[str, str],
    severity_levels: list,
) -> None:
    """Print messages grouped by the specified field.

    Similar to hal_log_parser.py's print_details() and print_by_file().

    Args:
        console: Rich console for output.
        messages: List of messages to group.
        group_by: Field to group by ("severity", "id", "file", "category").
        top_n: Maximum number of messages to show per group (0 = no limit).
        style_map: Dictionary mapping severity ID to Rich style string.
        severity_levels: List of SeverityLevel objects from plugin.
    """
    aggregator = Aggregator(severity_levels=severity_levels)
    groups = aggregator.group_by(messages, group_by)

    if not groups:
        console.print("[dim]No messages to display.[/dim]")
        return

    # Sort groups by count descending
    sorted_groups = aggregator.sorted_groups(groups, by_count=True)

    console.print()
    console.print("=" * 70)
    console.print(f"Log Analysis - Grouped by {group_by.title()}")
    console.print("=" * 70)

    for key, stats in sorted_groups:
        console.print()
        console.print("-" * 70)

        # Show group header with severity info
        if group_by == "severity":
            header = f" {key.title().replace('_', ' ')} ({stats.count} messages)"
        elif group_by == "id":
            sev_display = stats.severity.title() if stats.severity else "Unknown"
            header = f" {key} [{sev_display}] ({stats.count} messages)"
        elif group_by == "file":
            header = f" {key} ({stats.count} messages)"
            # Count by severity for file groups
            sev_counts: dict[str, int] = {}
            for msg in stats.messages:
                sev = msg.severity.lower() if msg.severity else "other"
                sev_counts[sev] = sev_counts.get(sev, 0) + 1
            sev_parts = [f"{s.title()}: {c}" for s, c in sorted(sev_counts.items())]
            if sev_parts:
                console.print(f" File: {key}")
                console.print(f" Total: {stats.count} ({', '.join(sev_parts)})")
                header = None  # Already printed
        else:  # category
            header = f" {key.title()} ({stats.count} messages)"

        if header:
            console.print(header)

        if stats.files_affected and group_by != "file":
            console.print(f" Files affected: {len(stats.files_affected)}")

        console.print("-" * 70)

        # Show sample messages
        msgs_to_show = stats.messages[:top_n] if top_n > 0 else stats.messages

        for msg in msgs_to_show:
            # Format location
            if msg.file_ref:
                loc = f"{msg.file_ref.path}"
                if msg.file_ref.line:
                    loc += f":{msg.file_ref.line}"
            else:
                loc = "(no location)"

            # Format severity tag
            sev_tag = msg.severity.title() if msg.severity else "?"
            msg_id = msg.message_id or ""

            style = get_severity_style(msg.severity, style_map)
            line = f"  {sev_tag:8s} {msg_id:20s} @ {loc}"
            if style:
                console.print(line, style=style)
            else:
                console.print(line)

            # Wrap content with 2-space indent (align with severity)
            indent = "  "
            width = (console.width or 80) - len(indent)
            wrapped = textwrap.fill(msg.content, width=width)
            for wrapped_line in wrapped.split("\n"):
                console.print(f"{indent}{wrapped_line}", markup=False)
            console.print()

        # Show "and N more" if truncated
        if top_n > 0 and len(stats.messages) > top_n:
            remaining = len(stats.messages) - top_n
            console.print(f"  ... and {remaining} more")

    console.print()
    console.print("=" * 70)
