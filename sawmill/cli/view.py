"""The ``sawmill view`` command: open targets or a log in the TUI."""

from __future__ import annotations

from pathlib import Path

import rich_click as click

from sawmill.cli.common import (
    SawmillCliError,
    emit_warnings,
    manifest_options,
    parse_vars,
    run_selected,
    var_options,
)
from sawmill.core.plugin import PluginError, get_plugin_manager
from sawmill.core.rules import RuleValidationError
from sawmill.core.runner import RunnerError, run_single_log


@click.command()
@click.argument("target", required=False)
@manifest_options
@var_options
@click.option("--plugin", "plugin_name", metavar="NAME", help="Plugin to parse a log file with.")
@click.option(
    "--fail-on",
    "fail_on",
    metavar="SEV",
    help="Severity id overriding every target's fail_on.",
)
def view(
    target: str | None,
    manifest_path: Path | None,
    roots: tuple[Path, ...],
    var_args: tuple[str, ...],
    plugin_name: str | None,
    fail_on: str | None,
) -> None:
    """Open TARGET, every target of the manifest, or a LOGFILE in the TUI."""
    from sawmill import tui

    overrides = parse_vars(var_args)
    manager = get_plugin_manager()
    if target is not None and Path(target).is_file():
        log_path = Path(target)
        if plugin_name is not None:
            if manager.get_plugin(plugin_name) is None:
                available = ", ".join(sorted(manager.list_plugins())) or "(none)"
                raise SawmillCliError(f"Plugin '{plugin_name}' not found. Available: {available}")
        else:
            try:
                plugin_name = manager.auto_detect(log_path)
            except PluginError as e:
                raise SawmillCliError(str(e)) from e
        try:
            result = run_single_log(log_path, plugin_name, manager, fail_on)
        except (RunnerError, RuleValidationError) as e:
            raise SawmillCliError(str(e)) from e
        emit_warnings([result])
        tui.run_tui([result], single_log=True)
        return

    names = [target] if target else []
    results = run_selected(
        manifest_path, roots, names, False, fail_on, manager=manager, overrides=overrides
    )
    emit_warnings(results)
    if not results:
        raise SawmillCliError("no targets to view")
    tui.run_tui(results)
