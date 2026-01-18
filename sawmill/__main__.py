"""Entry point for sawmill CLI."""

import rich_click as click
from rich.console import Console
from rich.table import Table

from sawmill.core.plugin import PluginManager
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
@click.pass_context
def cli(
    ctx: click.Context,
    logfile: str | None,
    version: bool,
    list_plugins: bool,
    plugin: str | None,
    show_info: bool,
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

    click.echo(f"Processing: {logfile}")


if __name__ == "__main__":
    cli()
