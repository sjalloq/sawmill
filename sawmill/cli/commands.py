"""CLI command definition for sawmill.

Contains the main @click.command with all options and routing logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from sawmill.cli.processing import generate_waivers as _generate_waivers_cmd
from sawmill.cli.processing import process_log_file
from sawmill.cli.reporting import (
    apply_waivers,
    generate_check_report,
    get_fail_on_level,
    has_check_failures,
)
from sawmill.core.plugin import NoPluginFoundError, PluginConflictError, get_plugin_manager
from sawmill.core.severity import get_severity_levels, get_severity_style
from sawmill.core.waiver import WaiverLoader, WaiverMatcher, WaiverValidationError
from sawmill.models.waiver import Waiver

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True


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

    for hook_name in ["can_handle", "load_and_parse", "get_filters", "extract_file_reference"]:
        method = getattr(plugin, hook_name, None)
        if method is not None and hasattr(method, "sawmill_impl"):
            hooks.append(hook_name)
    return hooks


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("logfile", required=False, type=click.Path(exists=True))
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.option("--list-plugins", is_flag=True, help="List all available plugins and exit.")
@click.option("--plugin", type=str, help="Force a specific plugin (bypasses auto-detection).")
@click.option(
    "--show-info",
    is_flag=True,
    help="Show detailed information about a plugin (requires --plugin).",
)
@click.option(
    "--list-groupings",
    is_flag=True,
    help="List available grouping fields from the plugin and exit.",
)
@click.option(
    "--list-severity", is_flag=True, help="List available severity levels from the plugin and exit."
)
@click.option(
    "--severity", type=str, help="Filter to show only messages at or above this severity level."
)
@click.option(
    "--filter", "filter_pattern", type=str, help="Regex pattern to include matching messages."
)
@click.option(
    "--suppress",
    "suppress_patterns",
    type=str,
    multiple=True,
    help="Regex pattern to exclude matching messages (can be repeated).",
)
@click.option(
    "--suppress-id",
    "suppress_ids",
    type=str,
    multiple=True,
    help="Message ID to exclude (can be repeated).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "count"], case_sensitive=False),
    default="text",
    help="Output format: text (colored), json (JSONL), or count (summary).",
)
@click.option(
    "--id",
    "id_patterns",
    type=str,
    multiple=True,
    help="Message ID pattern to include (supports wildcards, e.g., 'Synth 8-*'). Can be repeated.",
)
@click.option(
    "--category",
    "categories",
    type=str,
    multiple=True,
    help="Category to include (e.g., 'synth', 'timing'). Can be repeated.",
)
@click.option(
    "--generate-waivers",
    is_flag=True,
    help="Generate waiver TOML from errors/warnings in the log. Output to stdout.",
)
@click.option(
    "--waiver-level",
    "waiver_level",
    type=int,
    default=1,
    help="Min severity level for waiver generation. Default: 1.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Check mode: exit 1 if unwaived messages above the lowest severity level are found.",
)
@click.option(
    "--fail-on",
    "fail_on",
    type=str,
    help="With --check, set min failure severity. Default: second-lowest.",
)
@click.option(
    "--waivers",
    type=click.Path(exists=False),
    help="Path to waiver TOML file. Waived messages don't count toward CI failure.",
)
@click.option(
    "--show-waived", is_flag=True, help="Display messages that were waived (with waiver reasons)."
)
@click.option(
    "--report-unused",
    is_flag=True,
    help="Report waivers that didn't match any messages (stale waivers).",
)
@click.option(
    "--report", "report_file", type=click.Path(), help="Write JSON summary report to this file."
)
@click.option(
    "--summary",
    is_flag=True,
    help="Show summary counts by severity and message ID (like hal_log_parser.py).",
)
@click.option(
    "--group-by",
    "group_by",
    type=click.Choice(["severity", "id", "file", "category"], case_sensitive=False),
    help="Group output by the specified field with sample messages.",
)
@click.option(
    "--top",
    "top_n",
    type=int,
    default=5,
    help="Limit messages shown per group when using --group-by (default: 5, 0 = no limit).",
)
@click.option(
    "--batch",
    is_flag=True,
    help="Run in batch mode (no TUI). Implied by any output/filter/check flags.",
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
    list_severity: bool,
    severity: str | None,
    filter_pattern: str | None,
    suppress_patterns: tuple[str, ...],
    suppress_ids: tuple[str, ...],
    output_format: str,
    id_patterns: tuple[str, ...],
    categories: tuple[str, ...],
    generate_waivers: bool,
    waiver_level: int,
    check: bool,
    fail_on: str | None,
    waivers: str | None,
    show_waived: bool,
    report_unused: bool,
    report_file: str | None,
    summary: bool,
    group_by: str | None,
    top_n: int,
    batch: bool,
) -> None:
    """Sawmill - A plugin-driven terminal log analyzer.

    Analyze and filter structured log files using tool-specific plugins.
    """
    console = Console()

    if version:
        from sawmill import __version__

        click.echo(f"sawmill {__version__}")
        return

    if list_plugins:
        manager = get_plugin_manager()
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

        manager = get_plugin_manager()
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
        if info is None:
            console.print(f"[red]Error:[/red] No info available for plugin '{plugin}'.")
            ctx.exit(1)
            return
        console.print(f"\n[bold cyan]Plugin: {info['name']}[/bold cyan]")
        console.print(f"Version: {info.get('version', 'unknown')}")
        console.print(f"Description: {info.get('description', 'No description')}")

        console.print("\n[bold]Implemented Hooks:[/bold]")
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
            filter_table.add_column("Description")

            for f in filters:
                filter_table.add_row(
                    f.id,
                    f.name,
                    f.description or "",
                )

            console.print(filter_table)

        console.print()
        return

    if list_groupings:
        # List available grouping fields from the plugin
        manager = get_plugin_manager()

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

    if list_severity:
        # List available severity levels from the plugin
        manager = get_plugin_manager()

        # Determine which plugin to query
        if plugin:
            plugin_instance = manager.get_plugin(plugin)
            if plugin_instance is None:
                console.print(f"[red]Error:[/red] Plugin '{plugin}' not found.")
                ctx.exit(1)
        else:
            plugin_instance = None

        # Get severity levels from plugin or use defaults
        if plugin_instance and hasattr(plugin_instance, "get_severity_levels"):
            try:
                severity_dicts = plugin_instance.get_severity_levels()
                from sawmill.models.plugin_api import severity_levels_from_dicts

                severity_levels = severity_levels_from_dicts(severity_dicts)
            except Exception:
                severity_levels = None
        else:
            severity_levels = None

        if severity_levels is None:
            console.print("[yellow]No severity levels available.[/yellow]")
            console.print(
                "Severity levels are provided by plugins. Use --plugin <name> to see "
                "plugin-specific severity levels."
            )
            return

        # Display the severity levels (sorted by level descending - most severe first)
        table = Table(title="Available Severity Levels")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Level", justify="right")
        table.add_column("Style")

        for level in sorted(severity_levels, key=lambda x: -x.level):
            table.add_row(
                level.id,
                level.name,
                str(level.level),
                level.style or "",
            )

        console.print(table)
        console.print("\nUse --severity <id> to filter messages at or above that level.")
        return

    if logfile is None:
        click.echo(ctx.get_help())
        return

    # Determine if batch mode is needed.
    # Explicit --batch flag, or any output/filter/check flag implies batch.
    is_batch = batch or any(
        [
            severity is not None,
            filter_pattern is not None,
            suppress_patterns,
            suppress_ids,
            id_patterns,
            categories,
            generate_waivers,
            check,
            fail_on is not None,
            waivers is not None,
            show_waived,
            report_unused,
            report_file is not None,
            summary,
            group_by is not None,
        ]
    )

    # --format explicitly provided also implies batch
    if not is_batch:
        source = ctx.get_parameter_source("output_format")
        if source is not None and source.name == "COMMANDLINE":
            is_batch = True

    # Non-interactive environment (piped, CliRunner, etc.) implies batch
    import sys

    if not is_batch and not sys.stdin.isatty():
        is_batch = True

    if not is_batch:
        # Launch TUI mode
        from sawmill.tui import run_tui

        log_path = Path(logfile)
        manager = get_plugin_manager()

        try:
            plugin_name = plugin or manager.auto_detect(log_path)

            plugin_instance = manager.get_plugin(plugin_name)
            severity_levels = get_severity_levels(plugin_instance)
        except (NoPluginFoundError, PluginConflictError) as e:
            console.print(f"[red]Error:[/red] {e}")
            ctx.exit(1)
            return

        # Resolve waiver file path for TUI
        waiver_file_path = Path(waivers) if waivers else None

        run_tui(
            log_file=log_path,
            plugin_name=plugin_name,
            severity_levels=severity_levels,
            waiver_file_path=waiver_file_path,
        )
        return

    # Handle waiver generation mode
    if generate_waivers:
        _generate_waivers_cmd(ctx, console, logfile, plugin, waiver_level)
        return

    # Load waivers — from explicit path or auto-discovered .sawmill/waivers.toml
    waiver_matcher: WaiverMatcher | None = None
    all_waivers: list[Waiver] = []
    waiver_path: Path | None = None
    if waivers:
        waiver_path = Path(waivers)
        if not waiver_path.exists():
            console.print(f"[red]Error:[/red] Waiver file not found: {waivers}")
            ctx.exit(1)
    else:
        from sawmill.utils.dirs import resolve_sawmill_dir

        sawmill_dir = resolve_sawmill_dir()
        if sawmill_dir is not None:
            candidate = sawmill_dir / "waivers.toml"
            if candidate.exists():
                waiver_path = candidate

    if waiver_path is not None and waiver_path.exists():
        try:
            loader = WaiverLoader()
            waiver_file = loader.load(waiver_path)
            all_waivers = waiver_file.waivers
            waiver_matcher = WaiverMatcher(all_waivers)
        except WaiverValidationError as e:
            console.print(f"[red]Error:[/red] Invalid waiver file: {e}")
            ctx.exit(1)

    # Warn if suppress + check are combined (suppressions don't affect CI)
    if check and (suppress_patterns or suppress_ids):
        import sys

        err_console = Console(file=sys.stderr)
        err_console.print(
            "[yellow]Warning:[/yellow] --suppress/--suppress-id affects display only, "
            "not CI pass/fail. Use --waivers for CI acceptance.",
        )

    # Process the log file
    messages, ci_messages, severity_style_map = process_log_file(
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

    # Compute suppressed messages (in CI set but removed from display by suppress filters)
    display_id_set = {id(m) for m in messages}
    suppressed_messages = [m for m in ci_messages if id(m) not in display_id_set]

    # Apply waivers to CI message set (for CI evaluation)
    ci_waived_messages: list = []
    ci_used_waivers: list[Waiver] = []
    if waiver_matcher:
        ci_messages, ci_waived_messages, ci_used_waivers = apply_waivers(
            ci_messages, waiver_matcher
        )

    # Apply waivers to display message set (for --show-waived output)
    display_waived: list = []
    if waiver_matcher:
        messages, display_waived, _display_used_waivers = apply_waivers(messages, waiver_matcher)

    # Show waived messages if requested (from display set)
    if show_waived and display_waived:
        console.print("\n[bold cyan]Waived Messages:[/bold cyan]")
        for msg, waiver in display_waived:
            style = get_severity_style(msg.severity, severity_style_map)
            console.print(f"  [dim]Waived by:[/dim] {waiver.message_id}")
            console.print(f"  [dim]Reason:[/dim] {waiver.reason}")
            if style:
                console.print(f"  {msg.raw_text}", style=style, markup=False)
            else:
                console.print(f"  {msg.raw_text}", markup=False)
            console.print()

    # Report unused waivers if requested (from CI set — most complete)
    if report_unused and all_waivers:
        unused_waivers = [w for w in all_waivers if w not in ci_used_waivers]
        if unused_waivers:
            console.print("\n[bold yellow]Unused Waivers:[/bold yellow]")
            for waiver in unused_waivers:
                console.print(f"  - {waiver.message_id}: {waiver.reason}")

    # Get plugin for report and check mode
    report_plugin = None
    used_plugin_name = plugin if plugin else "unknown"
    if report_file or check:
        manager = get_plugin_manager()
        if plugin:
            report_plugin = manager.get_plugin(plugin)
            used_plugin_name = plugin
        else:
            try:
                detected_name = manager.auto_detect(Path(logfile))
                report_plugin = manager.get_plugin(detected_name)
                used_plugin_name = detected_name
            except (NoPluginFoundError, PluginConflictError):
                pass

    # Get fail-on level (default: second-lowest severity from plugin)
    min_level = 1
    if report_plugin:
        min_level = get_fail_on_level(fail_on, report_plugin)

    # Generate check report if requested (uses CI message set)
    if report_file:
        if report_plugin:
            report = generate_check_report(
                messages=ci_messages,
                waived_messages=ci_waived_messages,
                used_waivers=ci_used_waivers,
                all_waivers=all_waivers,
                plugin=report_plugin,
                min_level=min_level,
                log_file=logfile,
                plugin_name=used_plugin_name,
                suppressed_messages=suppressed_messages,
            )

            # Write the report to file
            report_path = Path(report_file)
            # Create parent directories if they don't exist
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))
        else:
            console.print(
                "[yellow]Warning:[/yellow] Cannot generate report without a valid plugin."
            )

    # Check exit codes (on unwaived CI messages — suppressions do NOT affect this)
    if check:
        if report_plugin:
            if has_check_failures(ci_messages, report_plugin, min_level):
                ctx.exit(1)
        else:
            console.print("[yellow]Warning:[/yellow] Cannot check failures without a valid plugin.")
            ctx.exit(1)
