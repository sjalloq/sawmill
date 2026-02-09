"""Log file processing and waiver generation for sawmill CLI.

Provides the main orchestration functions that load, parse, filter,
and display log file content.
"""

from __future__ import annotations

from pathlib import Path

import rich_click as click
from rich.console import Console

from sawmill.cli.formatting import output_messages, print_grouped, print_summary
from sawmill.core.filter import FilterEngine, match_message_id
from sawmill.core.plugin import NoPluginFoundError, PluginConflictError, get_plugin_manager
from sawmill.core.severity import (
    get_severity_level_map,
    get_severity_levels,
    get_severity_style_map,
    severity_at_or_above,
)
from sawmill.core.waiver import WaiverGenerator


def process_log_file(
    ctx: click.Context,
    console: Console,
    logfile: str,
    plugin_name: str | None,
    severity: str | None,
    filter_pattern: str | None,
    suppress_patterns: tuple[str, ...],
    suppress_ids: tuple[str, ...],
    id_patterns: tuple[str, ...],
    categories: tuple[str, ...],
    output_format: str,
    summary: bool = False,
    group_by: str | None = None,
    top_n: int = 5,
) -> tuple[list, list, dict[str, str]]:
    """Process a log file with the specified filters.

    Args:
        ctx: Click context.
        console: Rich console for output.
        logfile: Path to the log file.
        plugin_name: Specific plugin to use (or None for auto-detect).
        severity: Minimum severity level to show.
        filter_pattern: Regex pattern to include.
        suppress_patterns: Regex patterns to exclude.
        suppress_ids: Message IDs to exclude.
        id_patterns: Message ID patterns to include (supports wildcards).
        categories: Categories to include.
        output_format: Output format (text, json, count).
        summary: If True, show summary view instead of messages.
        group_by: Group output by this field (severity, id, file, category).
        top_n: Limit messages per group when using group_by.

    Returns:
        Tuple of (display_messages, ci_messages, severity_style_map).
        display_messages: Messages after all filters including suppressions (for display).
        ci_messages: Messages after scope filters only, before suppressions (for CI evaluation).
    """
    manager = get_plugin_manager()
    path = Path(logfile)

    # Select plugin
    if plugin_name:
        plugin = manager.get_plugin(plugin_name)
        if plugin is None:
            console.print(f"[red]Error:[/red] Plugin '{plugin_name}' not found.")
            console.print("\nAvailable plugins:")
            for name in manager.list_plugins():
                console.print(f"  - {name}")
            ctx.exit(1)
    else:
        # Auto-detect plugin
        try:
            detected_name = manager.auto_detect(path)
            plugin = manager.get_plugin(detected_name)
        except NoPluginFoundError as e:
            console.print("[red]Error:[/red] No plugin can handle this file.")
            console.print(f"  {e}")
            console.print("\nInstalled plugins:")
            for name in manager.list_plugins():
                console.print(f"  - {name}")
            console.print("\nUse --plugin to specify a plugin manually.")
            ctx.exit(1)
        except PluginConflictError as e:
            console.print(f"[red]Error:[/red] {e}")
            ctx.exit(1)

    if plugin is None:
        console.print("[red]Error:[/red] Plugin not found.")
        ctx.exit(1)

    # Get severity level and style maps from plugin
    severity_level_map = get_severity_level_map(plugin)
    severity_style_map = get_severity_style_map(plugin)

    # Handle numeric severity input (map level number to ID)
    if severity:
        try:
            level_num = int(severity)
            # Find the severity ID with this level number
            level_to_id = {v: k for k, v in severity_level_map.items()}
            if level_num in level_to_id:
                severity = level_to_id[level_num]
            else:
                valid_nums = sorted(level_to_id.keys())
                console.print(f"[red]Error:[/red] Unknown severity level '{level_num}'.")
                console.print(f"\nValid severity levels: {valid_nums}")
                console.print("Use --list-severity to see all available levels.")
                ctx.exit(1)
        except ValueError:
            # Not a number, validate as ID
            if severity.lower() not in severity_level_map:
                valid_levels = sorted(
                    severity_level_map.keys(), key=lambda x: -severity_level_map[x]
                )
                console.print(f"[red]Error:[/red] Unknown severity level '{severity}'.")
                console.print("\nValid severity levels for this plugin:")
                for level_id in valid_levels:
                    level_num = severity_level_map[level_id]
                    console.print(f"  - {level_id} ({level_num})")
                console.print("\nUse --list-severity to see all available levels.")
                ctx.exit(1)

    # Load and parse the file using the plugin
    messages = plugin.load_and_parse(path)

    # Apply severity filter
    if severity:
        messages = [
            msg
            for msg in messages
            if severity_at_or_above(msg.severity, severity, severity_level_map)
        ]

    # Apply regex filter if specified (scope filter — affects CI)
    if filter_pattern:
        engine = FilterEngine()
        messages = engine.apply_filter(filter_pattern, messages)

    # Apply message ID pattern filters (scope filter — affects CI)
    if id_patterns:
        filtered = []
        for msg in messages:
            for pattern in id_patterns:
                if match_message_id(msg.message_id, pattern):
                    filtered.append(msg)
                    break
        messages = filtered

    # Apply category filters (scope filter — affects CI)
    if categories:
        category_set = {c.lower() for c in categories}
        messages = [
            msg for msg in messages if msg.category and msg.category.lower() in category_set
        ]

    # Snapshot for CI: all scope filters applied, before display-only suppressions
    ci_messages = list(messages)

    # Apply suppression patterns (display only — does NOT affect CI)
    if suppress_patterns:
        engine = FilterEngine()
        messages = engine.apply_suppressions(list(suppress_patterns), messages)

    # Apply suppress-id filters (display only — does NOT affect CI)
    if suppress_ids:
        suppress_id_set = set(suppress_ids)
        messages = [
            msg
            for msg in messages
            if msg.message_id is None or msg.message_id not in suppress_id_set
        ]

    # Get severity levels from plugin for aggregation and count format
    severity_levels = get_severity_levels(plugin)
    severity_ids = [level.id for level in severity_levels]

    # Output based on mode
    if summary:
        print_summary(console, messages, severity_style_map, severity_levels)
    elif group_by:
        print_grouped(console, messages, group_by, top_n, severity_style_map, severity_levels)
    else:
        output_messages(console, messages, output_format, severity_style_map, severity_ids)

    return messages, ci_messages, severity_style_map


def generate_waivers(
    ctx: click.Context,
    console: Console,
    logfile: str,
    plugin_name: str | None,
    min_waiver_level: int = 1,
) -> None:
    """Generate waiver TOML from a log file's errors/warnings.

    Args:
        ctx: Click context.
        console: Rich console for error output.
        logfile: Path to the log file.
        plugin_name: Specific plugin to use (or None for auto-detect).
        min_waiver_level: Minimum severity level to include in waivers.
            Messages with severity.level >= min_waiver_level are included.
            Level 0 is informational; level 1+ are actionable. Default: 1.
    """
    import sys

    # Use stderr console for error messages to keep stdout clean for TOML
    stderr_console = Console(file=sys.stderr)

    manager = get_plugin_manager()
    path = Path(logfile)

    # Select plugin (same logic as process_log_file)
    if plugin_name:
        plugin = manager.get_plugin(plugin_name)
        if plugin is None:
            stderr_console.print(f"[red]Error:[/red] Plugin '{plugin_name}' not found.")
            stderr_console.print("\nAvailable plugins:")
            for name in manager.list_plugins():
                stderr_console.print(f"  - {name}")
            ctx.exit(1)
    else:
        try:
            detected_name = manager.auto_detect(path)
            plugin = manager.get_plugin(detected_name)
        except NoPluginFoundError as e:
            stderr_console.print("[red]Error:[/red] No plugin can handle this file.")
            stderr_console.print(f"  {e}")
            stderr_console.print("\nInstalled plugins:")
            for name in manager.list_plugins():
                stderr_console.print(f"  - {name}")
            stderr_console.print("\nUse --plugin to specify a plugin manually.")
            ctx.exit(1)
        except PluginConflictError as e:
            stderr_console.print(f"[red]Error:[/red] {e}")
            ctx.exit(1)

    if plugin is None:
        stderr_console.print("[red]Error:[/red] Plugin not found.")
        ctx.exit(1)

    # Load and parse the file using the plugin
    messages = plugin.load_and_parse(path)

    # Get severity levels from plugin
    severity_levels = get_severity_levels(plugin)

    # Generate waiver TOML
    # Get tool name from plugin if available
    tool_name = getattr(plugin, "name", None)
    generator = WaiverGenerator(
        severity_levels=severity_levels,
        min_waiver_level=min_waiver_level,
    )
    toml_content = generator.generate(messages, tool=tool_name)

    # Output to stdout (raw print to allow redirection)
    print(toml_content)
