"""Entry point for sawmill CLI."""

import fnmatch
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from sawmill.core.aggregation import Aggregator, SEVERITY_ORDER
from sawmill.core.filter import FilterEngine
from sawmill.core.plugin import NoPluginFoundError, PluginConflictError, PluginManager
from sawmill.core.waiver import WaiverGenerator, WaiverLoader, WaiverMatcher, WaiverValidationError
from sawmill.models.waiver import Waiver
from sawmill.plugins.vivado import VivadoPlugin

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True


def _get_plugin_manager() -> PluginManager:
    """Create and configure the plugin manager with built-in plugins.

    Returns:
        Configured PluginManager instance.
    """
    manager = PluginManager()
    # Register built-in plugins
    manager.register(VivadoPlugin())
    # Discover external plugins via entry points
    manager.discover()
    return manager


def _get_implemented_hooks(plugin) -> list[str]:
    """Get list of hooks implemented by a plugin.

    Args:
        plugin: The plugin instance to check.

    Returns:
        List of hook names that are implemented.
    """
    hooks = []

    # Check each hook by seeing if the plugin has a non-default implementation
    # We do this by checking if the method exists and is decorated with hookimpl
    from sawmill.plugin import hookimpl

    for hook_name in ["can_handle", "load_and_parse", "get_filters", "extract_file_reference"]:
        method = getattr(plugin, hook_name, None)
        if method is not None:
            # Check if it's marked as a hookimpl
            if hasattr(method, "sawmill_impl"):
                hooks.append(hook_name)
    return hooks


def _get_severity_style(severity: str | None) -> str:
    """Get the Rich style for a given severity level.

    Args:
        severity: The severity level (info, warning, error, critical).

    Returns:
        Rich style string for the severity.
    """
    styles = {
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
        "critical": "red bold",
    }
    if severity:
        return styles.get(severity.lower(), "")
    return ""


def _severity_at_or_above(message_severity: str | None, min_severity: str) -> bool:
    """Check if message severity is at or above the minimum level.

    Args:
        message_severity: The message's severity (may be None).
        min_severity: The minimum severity level to show.

    Returns:
        True if the message should be shown.
    """
    if message_severity is None:
        return False

    levels = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    msg_level = levels.get(message_severity.lower(), -1)
    min_level = levels.get(min_severity.lower(), 0)
    return msg_level >= min_level


def _has_ci_failures(messages: list, strict: bool) -> bool:
    """Check if messages contain CI-failing severities.

    In normal CI mode, errors and critical warnings cause failure.
    In strict mode, regular warnings also cause failure.

    Args:
        messages: List of messages to check.
        strict: If True, also fail on regular warnings.

    Returns:
        True if there are CI-failing messages.
    """
    failing_severities = {"error", "critical_warning"}
    if strict:
        failing_severities.add("warning")

    for msg in messages:
        if msg.severity:
            sev = msg.severity.lower()
            if sev in failing_severities:
                return True
    return False


def _apply_waivers(
    messages: list,
    matcher: WaiverMatcher,
) -> tuple[list, list, list[Waiver]]:
    """Separate messages into waived and unwaived lists.

    Args:
        messages: All messages to process.
        matcher: WaiverMatcher to use for checking waivers.

    Returns:
        A tuple of (unwaived_messages, waived_messages, used_waivers).
    """
    unwaived: list = []
    waived: list = []
    used_waivers: list[Waiver] = []

    for msg in messages:
        waiver = matcher.is_waived(msg)
        if waiver:
            waived.append((msg, waiver))
            # Track used waivers (by identity, not by hash)
            if waiver not in used_waivers:
                used_waivers.append(waiver)
        else:
            unwaived.append(msg)

    return unwaived, waived, used_waivers


def _generate_ci_report(
    messages: list,
    waived_messages: list,
    used_waivers: list[Waiver],
    all_waivers: list[Waiver],
    strict: bool,
    log_file: str,
    plugin_name: str,
) -> dict:
    """Generate a CI summary report as a dictionary.

    Args:
        messages: List of unwaived messages.
        waived_messages: List of (message, waiver) tuples for waived messages.
        used_waivers: List of waivers that matched messages.
        all_waivers: All waivers that were loaded.
        strict: If True, warnings also cause CI failure.
        log_file: Path to the log file being analyzed.
        plugin_name: Name of the plugin used.

    Returns:
        Dictionary containing the CI report.
    """
    # Count messages by severity
    counts: dict[str, int] = {
        "error": 0,
        "critical_warning": 0,
        "warning": 0,
        "info": 0,
        "other": 0,
    }
    for msg in messages:
        if msg.severity:
            sev = msg.severity.lower()
            if sev in counts:
                counts[sev] += 1
            else:
                counts["other"] += 1
        else:
            counts["other"] += 1

    # Count waived messages by severity
    waived_counts: dict[str, int] = {
        "error": 0,
        "critical_warning": 0,
        "warning": 0,
        "info": 0,
        "other": 0,
    }
    for msg, waiver in waived_messages:
        if msg.severity:
            sev = msg.severity.lower()
            if sev in waived_counts:
                waived_counts[sev] += 1
            else:
                waived_counts["other"] += 1
        else:
            waived_counts["other"] += 1

    # Calculate exit code based on unwaived messages
    exit_code = 0
    failing_severities = {"error", "critical_warning"}
    if strict:
        failing_severities.add("warning")

    for msg in messages:
        if msg.severity:
            sev = msg.severity.lower()
            if sev in failing_severities:
                exit_code = 1
                break

    # Build issues list (unwaived messages with CI-relevant severities)
    issues = []
    for msg in messages:
        issues.append({
            "message_id": msg.message_id,
            "severity": msg.severity,
            "content": msg.content,
            "line": msg.start_line,
            "raw_text": msg.raw_text,
        })

    # Build waived list
    waived_list = []
    for msg, waiver in waived_messages:
        waived_list.append({
            "message_id": msg.message_id,
            "severity": msg.severity,
            "content": msg.content,
            "line": msg.start_line,
            "waiver_pattern": waiver.pattern,
            "waiver_type": waiver.type,
            "waiver_reason": waiver.reason,
        })

    # Find unused waivers
    unused_waivers = []
    for waiver in all_waivers:
        if waiver not in used_waivers:
            unused_waivers.append({
                "pattern": waiver.pattern,
                "type": waiver.type,
                "reason": waiver.reason,
            })

    # Build the report
    report = {
        "metadata": {
            "log_file": log_file,
            "plugin": plugin_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "exit_code": exit_code,
        "summary": {
            "total": len(messages) + len(waived_messages),
            "errors": counts["error"],
            "critical_warnings": counts["critical_warning"],
            "warnings": counts["warning"],
            "info": counts["info"],
            "waived": len(waived_messages),
            "unwaived_errors": counts["error"],
            "unwaived_critical_warnings": counts["critical_warning"],
            "unwaived_warnings": counts["warning"],
        },
        "issues": issues,
        "waived": waived_list,
        "unused_waivers": unused_waivers,
    }

    return report


def _match_message_id(message_id: str | None, pattern: str) -> bool:
    """Check if a message ID matches a pattern (supports wildcards).

    Uses fnmatch for glob-style pattern matching:
    - '*' matches any sequence of characters
    - '?' matches any single character

    Args:
        message_id: The message ID to check (may be None).
        pattern: The pattern to match against (e.g., "Synth 8-*").

    Returns:
        True if the message ID matches the pattern.
    """
    if message_id is None:
        return False

    return fnmatch.fnmatch(message_id, pattern)


def _process_log_file(
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
) -> list:
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
        List of filtered messages.
    """
    manager = _get_plugin_manager()
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
            console.print(f"[red]Error:[/red] No plugin can handle this file.")
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

    # Load and parse the file using the plugin
    messages = plugin.load_and_parse(path)

    # Apply severity filter
    if severity:
        messages = [
            msg for msg in messages
            if _severity_at_or_above(msg.severity, severity)
        ]

    # Apply regex filter if specified
    if filter_pattern:
        engine = FilterEngine()
        messages = engine.apply_filter(filter_pattern, messages)

    # Apply suppression patterns
    if suppress_patterns:
        engine = FilterEngine()
        messages = engine.apply_suppressions(list(suppress_patterns), messages)

    # Apply suppress-id filters
    if suppress_ids:
        suppress_id_set = set(suppress_ids)
        messages = [
            msg for msg in messages
            if msg.message_id is None or msg.message_id not in suppress_id_set
        ]

    # Apply message ID pattern filters (include only matching)
    if id_patterns:
        filtered = []
        for msg in messages:
            for pattern in id_patterns:
                if _match_message_id(msg.message_id, pattern):
                    filtered.append(msg)
                    break
        messages = filtered

    # Apply category filters (include only matching)
    if categories:
        category_set = {c.lower() for c in categories}
        messages = [
            msg for msg in messages
            if msg.category and msg.category.lower() in category_set
        ]

    # Output based on mode
    if summary:
        _print_summary(console, messages)
    elif group_by:
        _print_grouped(console, messages, group_by, top_n)
    else:
        _output_messages(console, messages, output_format)

    return messages


def _output_messages(
    console: Console,
    messages: list,
    output_format: str,
) -> None:
    """Output messages in the specified format.

    Args:
        console: Rich console for output.
        messages: List of messages to output.
        output_format: Output format (text, json, count).
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
        counts: dict[str, int] = {
            "error": 0,
            "critical_warning": 0,
            "warning": 0,
            "info": 0,
            "other": 0,
        }
        for msg in messages:
            if msg.severity:
                sev = msg.severity.lower()
                if sev in counts:
                    counts[sev] += 1
                else:
                    counts["other"] += 1
            else:
                counts["other"] += 1

        # Output the summary
        total = len(messages)
        console.print(f"total={total} errors={counts['error']} critical_warnings={counts['critical_warning']} warnings={counts['warning']} info={counts['info']}")

    else:
        # Text format (default): human-readable with colors
        # Note: We use markup=False to prevent Rich from interpreting
        # log content like [/path/to/file:line] as markup tags.
        for msg in messages:
            style = _get_severity_style(msg.severity)
            if style:
                console.print(msg.raw_text, style=style, markup=False)
            else:
                console.print(msg.raw_text, markup=False)


def _print_summary(
    console: Console,
    messages: list,
) -> None:
    """Print summary statistics grouped by severity with ID breakdown.

    Similar to hal_log_parser.py's print_summary() function.

    Args:
        console: Rich console for output.
        messages: List of messages to summarize.
    """
    aggregator = Aggregator()
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
            row = sorted_ids[i:i+4]
            formatted = [f"  {msg_id} ({count})" for msg_id, count in row]
            # Right-pad each item to 16 chars for columnar display
            line = "".join(f"{item:18s}" for item in formatted)
            console.print(line)

    console.print()
    console.print("=" * 70)
    console.print(f"Total: {len(messages)} messages")
    console.print("=" * 70)


def _print_grouped(
    console: Console,
    messages: list,
    group_by: str,
    top_n: int = 0,
) -> None:
    """Print messages grouped by the specified field.

    Similar to hal_log_parser.py's print_details() and print_by_file().

    Args:
        console: Rich console for output.
        messages: List of messages to group.
        group_by: Field to group by ("severity", "id", "file", "category").
        top_n: Maximum number of messages to show per group (0 = no limit).
    """
    aggregator = Aggregator()
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

            style = _get_severity_style(msg.severity)
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


def _generate_waivers(
    ctx: click.Context,
    console: Console,
    logfile: str,
    plugin_name: str | None,
) -> None:
    """Generate waiver TOML from a log file's errors/warnings.

    Args:
        ctx: Click context.
        console: Rich console for error output.
        logfile: Path to the log file.
        plugin_name: Specific plugin to use (or None for auto-detect).
    """
    import sys

    # Use stderr console for error messages to keep stdout clean for TOML
    stderr_console = Console(file=sys.stderr)

    manager = _get_plugin_manager()
    path = Path(logfile)

    # Select plugin (same logic as _process_log_file)
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
            stderr_console.print(f"[red]Error:[/red] No plugin can handle this file.")
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

    # Generate waiver TOML
    # Get tool name from plugin if available
    tool_name = getattr(plugin, "name", None)
    generator = WaiverGenerator()
    toml_content = generator.generate(messages, tool=tool_name)

    # Output to stdout (raw print to allow redirection)
    print(toml_content)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("logfile", required=False, type=click.Path(exists=True))
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.option(
    "--list-plugins",
    is_flag=True,
    help="List all available plugins and exit."
)
@click.option(
    "--plugin",
    type=str,
    help="Force a specific plugin (bypasses auto-detection)."
)
@click.option(
    "--show-info",
    is_flag=True,
    help="Show detailed information about a plugin (requires --plugin)."
)
@click.option(
    "--list-groupings",
    is_flag=True,
    help="List available grouping fields from the plugin and exit."
)
@click.option(
    "--severity",
    type=click.Choice(["info", "warning", "error", "critical"], case_sensitive=False),
    help="Filter to show only messages at or above this severity level."
)
@click.option(
    "--filter",
    "filter_pattern",
    type=str,
    help="Regex pattern to include matching messages."
)
@click.option(
    "--suppress",
    "suppress_patterns",
    type=str,
    multiple=True,
    help="Regex pattern to exclude matching messages (can be repeated)."
)
@click.option(
    "--suppress-id",
    "suppress_ids",
    type=str,
    multiple=True,
    help="Message ID to exclude (can be repeated)."
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "count"], case_sensitive=False),
    default="text",
    help="Output format: text (colored), json (JSONL), or count (summary)."
)
@click.option(
    "--id",
    "id_patterns",
    type=str,
    multiple=True,
    help="Message ID pattern to include (supports wildcards, e.g., 'Synth 8-*'). Can be repeated."
)
@click.option(
    "--category",
    "categories",
    type=str,
    multiple=True,
    help="Category to include (e.g., 'synth', 'timing'). Can be repeated."
)
@click.option(
    "--generate-waivers",
    is_flag=True,
    help="Generate waiver TOML from errors/warnings in the log. Output to stdout."
)
@click.option(
    "--ci",
    is_flag=True,
    help="CI mode: exit 1 if errors or critical warnings are found."
)
@click.option(
    "--strict",
    is_flag=True,
    help="With --ci, also fail on regular warnings."
)
@click.option(
    "--waivers",
    type=click.Path(exists=False),
    help="Path to waiver TOML file. Waived messages don't count toward CI failure."
)
@click.option(
    "--show-waived",
    is_flag=True,
    help="Display messages that were waived (with waiver reasons)."
)
@click.option(
    "--report-unused",
    is_flag=True,
    help="Report waivers that didn't match any messages (stale waivers)."
)
@click.option(
    "--report",
    "report_file",
    type=click.Path(),
    help="Write JSON summary report to this file."
)
@click.option(
    "--summary",
    is_flag=True,
    help="Show summary counts by severity and message ID (like hal_log_parser.py)."
)
@click.option(
    "--group-by",
    "group_by",
    type=click.Choice(["severity", "id", "file", "category"], case_sensitive=False),
    help="Group output by the specified field with sample messages."
)
@click.option(
    "--top",
    "top_n",
    type=int,
    default=5,
    help="Limit messages shown per group when using --group-by (default: 5, 0 = no limit)."
)
@click.pass_context
def cli(
    ctx: click.Context,
    logfile: str | None,
    version: bool,
    list_plugins: bool,
    plugin: str | None,
    show_info: bool,
    list_groupings: bool,
    severity: str | None,
    filter_pattern: str | None,
    suppress_patterns: tuple[str, ...],
    suppress_ids: tuple[str, ...],
    output_format: str,
    id_patterns: tuple[str, ...],
    categories: tuple[str, ...],
    generate_waivers: bool,
    ci: bool,
    strict: bool,
    waivers: str | None,
    show_waived: bool,
    report_unused: bool,
    report_file: str | None,
    summary: bool,
    group_by: str | None,
    top_n: int,
) -> None:
    """Sawmill - A terminal-based log analysis tool for EDA engineers.

    Analyze and filter log files from EDA tools like Vivado.
    """
    console = Console()

    if version:
        from sawmill import __version__
        click.echo(f"sawmill {__version__}")
        return

    if list_plugins:
        manager = _get_plugin_manager()
        plugins = manager.list_plugins()

        if not plugins:
            console.print("[yellow]No plugins found.[/yellow]")
            return

        table = Table(title="Available Plugins")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", style="green")
        table.add_column("Description")

        for name in sorted(plugins):
            info = manager.get_plugin_info(name)
            if info:
                table.add_row(
                    info["name"],
                    info.get("version", "unknown"),
                    info.get("description", ""),
                )

        console.print(table)
        return

    if show_info:
        if not plugin:
            console.print(
                "[red]Error:[/red] --show-info requires --plugin to specify which plugin.",
                style="bold",
            )
            ctx.exit(1)

        manager = _get_plugin_manager()
        plugin_instance = manager.get_plugin(plugin)

        if plugin_instance is None:
            console.print(f"[red]Error:[/red] Plugin '{plugin}' not found.")
            console.print("\nAvailable plugins:")
            for name in manager.list_plugins():
                console.print(f"  - {name}")
            ctx.exit(1)

        # Get plugin information
        info = manager.get_plugin_info(plugin)
        filters = plugin_instance.get_filters()
        hooks = _get_implemented_hooks(plugin_instance)

        # Display plugin info
        console.print(f"\n[bold cyan]Plugin: {info['name']}[/bold cyan]")
        console.print(f"Version: {info.get('version', 'unknown')}")
        console.print(f"Description: {info.get('description', 'No description')}")

        console.print(f"\n[bold]Implemented Hooks:[/bold]")
        if hooks:
            for hook in hooks:
                console.print(f"  - {hook}")
        else:
            console.print("  [dim]None detected[/dim]")

        console.print(f"\n[bold]Filters Provided:[/bold] {len(filters)}")
        if filters:
            filter_table = Table(show_header=True, header_style="bold")
            filter_table.add_column("ID", style="cyan")
            filter_table.add_column("Name")
            filter_table.add_column("Enabled", justify="center")
            filter_table.add_column("Description")

            for f in filters:
                enabled = "[green]✓[/green]" if f.enabled else "[dim]✗[/dim]"
                filter_table.add_row(
                    f.id,
                    f.name,
                    enabled,
                    f.description or "",
                )

            console.print(filter_table)

        console.print()
        return

    if list_groupings:
        # List available grouping fields from the plugin
        manager = _get_plugin_manager()

        # Determine which plugin to query
        if plugin:
            plugin_instance = manager.get_plugin(plugin)
            if plugin_instance is None:
                console.print(f"[red]Error:[/red] Plugin '{plugin}' not found.")
                ctx.exit(1)
        else:
            console.print("[yellow]Note:[/yellow] No plugin specified. Showing default groupings.")
            console.print("Use --plugin <name> to see plugin-specific groupings.\n")
            plugin_instance = None

        # Get grouping fields from plugin or use defaults
        if plugin_instance and hasattr(plugin_instance, "get_grouping_fields"):
            try:
                grouping_dicts = plugin_instance.get_grouping_fields()
                from sawmill.models.plugin_api import grouping_fields_from_dicts
                grouping_fields = grouping_fields_from_dicts(grouping_dicts)
            except Exception:
                grouping_fields = None
        else:
            grouping_fields = None

        if grouping_fields is None:
            from sawmill.models.plugin_api import DEFAULT_GROUPING_FIELDS
            grouping_fields = DEFAULT_GROUPING_FIELDS

        # Display the grouping fields
        table = Table(title="Available Grouping Fields")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Type")
        table.add_column("Description")

        for field in grouping_fields:
            table.add_row(
                field.id,
                field.name,
                field.field_type,
                field.description,
            )

        console.print(table)
        console.print("\nUse --group-by <id> to group messages by a field.")
        return

    if logfile is None:
        click.echo(ctx.get_help())
        return

    # Handle waiver generation mode
    if generate_waivers:
        _generate_waivers(ctx, console, logfile, plugin)
        return

    # Load waivers if specified
    waiver_matcher: WaiverMatcher | None = None
    all_waivers: list[Waiver] = []
    if waivers:
        waiver_path = Path(waivers)
        if not waiver_path.exists():
            console.print(f"[red]Error:[/red] Waiver file not found: {waivers}")
            ctx.exit(1)
        try:
            loader = WaiverLoader()
            waiver_file = loader.load(waiver_path)
            all_waivers = waiver_file.waivers
            waiver_matcher = WaiverMatcher(all_waivers)
        except WaiverValidationError as e:
            console.print(f"[red]Error:[/red] Invalid waiver file: {e}")
            ctx.exit(1)

    # Process the log file
    messages = _process_log_file(
        ctx,
        console,
        logfile,
        plugin,
        severity,
        filter_pattern,
        suppress_patterns,
        suppress_ids,
        id_patterns,
        categories,
        output_format,
        summary,
        group_by,
        top_n,
    )

    # Apply waivers if loaded
    waived_messages: list = []
    used_waivers: list[Waiver] = []
    if waiver_matcher:
        messages, waived_messages, used_waivers = _apply_waivers(messages, waiver_matcher)

    # Show waived messages if requested
    if show_waived and waived_messages:
        console.print("\n[bold cyan]Waived Messages:[/bold cyan]")
        for msg, waiver in waived_messages:
            style = _get_severity_style(msg.severity)
            console.print(f"  [dim]Waived by:[/dim] {waiver.pattern} ({waiver.type})")
            console.print(f"  [dim]Reason:[/dim] {waiver.reason}")
            if style:
                console.print(f"  {msg.raw_text}", style=style, markup=False)
            else:
                console.print(f"  {msg.raw_text}", markup=False)
            console.print()

    # Report unused waivers if requested
    if report_unused and all_waivers:
        unused_waivers = [w for w in all_waivers if w not in used_waivers]
        if unused_waivers:
            console.print("\n[bold yellow]Unused Waivers:[/bold yellow]")
            for waiver in unused_waivers:
                console.print(f"  - {waiver.pattern} ({waiver.type}): {waiver.reason}")

    # Determine the plugin name used (for report metadata)
    used_plugin_name = plugin if plugin else "vivado"  # Default to vivado for auto-detect
    if not plugin:
        try:
            manager = _get_plugin_manager()
            used_plugin_name = manager.auto_detect(Path(logfile))
        except (NoPluginFoundError, PluginConflictError):
            pass  # Keep default

    # Generate CI report if requested
    if report_file:
        report = _generate_ci_report(
            messages=messages,
            waived_messages=waived_messages,
            used_waivers=used_waivers,
            all_waivers=all_waivers,
            strict=strict,
            log_file=logfile,
            plugin_name=used_plugin_name,
        )

        # Write the report to file
        report_path = Path(report_file)
        # Create parent directories if they don't exist
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))

    # Check CI exit codes (only on unwaived messages)
    if ci and _has_ci_failures(messages, strict):
        ctx.exit(1)


if __name__ == "__main__":
    cli()
