"""The ``sawmill plugins`` command group: list and inspect plugins."""

from __future__ import annotations

from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table

from sawmill.core.plugin import get_plugin_manager, plugin_implements_configure
from sawmill.core.severity import get_severity_levels
from sawmill.models.plugin_api import DEFAULT_GROUPING_FIELDS, grouping_fields_from_dicts

_HOOK_NAMES = [
    "can_handle",
    "load_and_parse",
    "get_severity_levels",
    "get_filters",
    "get_grouping_fields",
    "extract_file_reference",
]


def _get_implemented_hooks(plugin: Any) -> list[str]:
    """Return the names of hooks implemented by a plugin."""
    hooks = []
    for hook_name in _HOOK_NAMES:
        method = getattr(plugin, hook_name, None)
        if method is not None and hasattr(method, "sawmill_impl"):
            hooks.append(hook_name)
    if plugin_implements_configure(plugin):
        hooks.append("configure")
    return hooks


@click.group()
def plugins() -> None:
    """List and inspect installed plugins."""


@plugins.command("list")
def list_plugins() -> None:
    """List installed plugins."""
    console = Console()
    manager = get_plugin_manager()
    names = manager.list_plugins()
    if not names:
        console.print("[yellow]No plugins found.[/yellow]")
        return

    table = Table(title="Available Plugins")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Description")
    for name in sorted(names):
        info = manager.get_plugin_info(name)
        if info:
            table.add_row(info["name"], info.get("version", "unknown"), info.get("description", ""))
    console.print(table)


@plugins.command("info")
@click.argument("name")
def plugin_info(name: str) -> None:
    """Show hooks, filters, severity levels and grouping fields for plugin NAME."""
    console = Console()
    manager = get_plugin_manager()
    plugin = manager.get_plugin(name)
    info = manager.get_plugin_info(name)
    if plugin is None or info is None:
        available = ", ".join(sorted(manager.list_plugins())) or "(none)"
        raise click.UsageError(f"Plugin '{name}' not found. Available: {available}")

    console.print(f"\n[bold cyan]Plugin: {info['name']}[/bold cyan]")
    console.print(f"Version: {info.get('version', 'unknown')}")
    console.print(f"Description: {info.get('description', 'No description')}")

    console.print("\n[bold]Implemented Hooks:[/bold]")
    hooks = _get_implemented_hooks(plugin)
    for hook in hooks:
        console.print(f"  - {hook}")
    if not hooks:
        console.print("  [dim]None detected[/dim]")

    filters = plugin.get_filters()
    console.print(f"\n[bold]Filters:[/bold] {len(filters)}")
    if filters:
        filter_table = Table(show_header=True, header_style="bold")
        filter_table.add_column("ID", style="cyan")
        filter_table.add_column("Name")
        filter_table.add_column("Description")
        for f in filters:
            filter_table.add_row(f.id, f.name, f.description or "")
        console.print(filter_table)

    severity_table = Table(title="Severity Levels")
    severity_table.add_column("ID", style="cyan", no_wrap=True)
    severity_table.add_column("Name", style="green")
    severity_table.add_column("Level", justify="right")
    severity_table.add_column("Style")
    for level in sorted(get_severity_levels(plugin), key=lambda x: -x.level):
        severity_table.add_row(level.id, level.name, str(level.level), level.style or "")
    console.print()
    console.print(severity_table)

    grouping_fields = DEFAULT_GROUPING_FIELDS
    if hasattr(plugin, "get_grouping_fields"):
        grouping_dicts = plugin.get_grouping_fields()
        if grouping_dicts:
            grouping_fields = grouping_fields_from_dicts(grouping_dicts)
    grouping_table = Table(title="Grouping Fields")
    grouping_table.add_column("ID", style="cyan", no_wrap=True)
    grouping_table.add_column("Name", style="green")
    grouping_table.add_column("Type")
    grouping_table.add_column("Description")
    for field in grouping_fields:
        grouping_table.add_row(field.id, field.name, field.field_type, field.description)
    console.print()
    console.print(grouping_table)
