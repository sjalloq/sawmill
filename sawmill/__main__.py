"""Entry point for sawmill CLI."""

from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table

from sawmill.core.filter import FilterEngine
from sawmill.core.plugin import NoPluginFoundError, PluginConflictError, PluginManager
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


def _process_log_file(
    ctx: click.Context,
    console: Console,
    logfile: str,
    plugin_name: str | None,
    severity: str | None,
    filter_pattern: str | None,
    suppress_patterns: tuple[str, ...],
    suppress_ids: tuple[str, ...],
) -> None:
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

    # Output the messages with colorization
    # Note: We use markup=False to prevent Rich from interpreting
    # log content like [/path/to/file:line] as markup tags.
    for msg in messages:
        style = _get_severity_style(msg.severity)
        if style:
            console.print(msg.raw_text, style=style, markup=False)
        else:
            console.print(msg.raw_text, markup=False)


@click.command()
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
@click.pass_context
def cli(
    ctx: click.Context,
    logfile: str | None,
    version: bool,
    list_plugins: bool,
    plugin: str | None,
    show_info: bool,
    severity: str | None,
    filter_pattern: str | None,
    suppress_patterns: tuple[str, ...],
    suppress_ids: tuple[str, ...],
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

    if logfile is None:
        click.echo(ctx.get_help())
        return

    # Process the log file
    _process_log_file(
        ctx,
        console,
        logfile,
        plugin,
        severity,
        filter_pattern,
        suppress_patterns,
        suppress_ids,
    )


if __name__ == "__main__":
    cli()
