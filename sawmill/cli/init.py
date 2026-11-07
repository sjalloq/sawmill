"""``sawmill init``: scaffold a manifest, and append targets to it."""

from __future__ import annotations

from pathlib import Path

import rich_click as click
import tomlkit

from sawmill.cli.common import SawmillCliError
from sawmill.core.plugin import NoPluginFoundError, PluginConflictError, get_plugin_manager
from sawmill.core.scaffold import add_target, write_manifest_template


def _write_template(manifest: Path, name: str) -> None:
    """Create the template manifest and the rules directory."""
    write_manifest_template(manifest, name)
    click.echo(f"created {manifest}")


def _detect_plugin(glob: str, plugin: str | None) -> str:
    """Return the plugin for a target, verifying or auto-detecting it."""
    manager = get_plugin_manager()
    if plugin is not None:
        if manager.get_plugin(plugin) is None:
            installed = ", ".join(manager.list_plugins()) or "none"
            raise SawmillCliError(f"plugin '{plugin}' is not installed; installed: {installed}")
        return plugin
    matches = [p for p in sorted(Path.cwd().glob(glob)) if p.is_file()]
    if not matches:
        raise SawmillCliError(f"no log matches {glob}; pass --plugin")
    try:
        return manager.auto_detect(matches[0])
    except (NoPluginFoundError, PluginConflictError) as e:
        raise SawmillCliError(str(e)) from e


@click.command()
@click.option("--name", default=None, help="Manifest name (default: current directory name).")
@click.option(
    "--target",
    "target",
    nargs=2,
    default=None,
    metavar="NAME GLOB",
    help="Append a target NAME whose logs match GLOB.",
)
@click.option("--plugin", default=None, help="Plugin for --target (default: auto-detect).")
def init(name: str | None, target: tuple[str, str] | None, plugin: str | None) -> None:
    """Create .sawmill/manifest.toml, or append a target to it."""
    root = Path.cwd()
    manifest = root / ".sawmill" / "manifest.toml"
    if target is None:
        if plugin is not None:
            raise click.UsageError("--plugin requires --target")
        if manifest.exists():
            raise SawmillCliError(f"{manifest} already exists")
        _write_template(manifest, name or root.name)
        return

    target_name, glob = target
    if Path(glob).is_absolute():
        raise SawmillCliError(f"log glob must be relative to {root}: {glob}")

    doc = None
    if manifest.exists():
        try:
            doc = tomlkit.parse(manifest.read_text(encoding="utf-8"))
        except tomlkit.exceptions.TOMLKitError as e:
            raise SawmillCliError(f"{manifest}: invalid TOML: {e}") from e
        existing = doc.get("target", [])
        if any(t.get("name") == target_name for t in existing):
            raise SawmillCliError(f"target '{target_name}' already exists in {manifest}")

    plugin_name = _detect_plugin(glob, plugin)

    if doc is None:
        _write_template(manifest, name or root.name)

    rules_file = manifest.parent / "rules" / f"{target_name}.toml"
    rules_existed = rules_file.exists()
    add_target(manifest, target_name, plugin_name, glob)
    click.echo(f"appended target '{target_name}' (plugin {plugin_name}) to {manifest}")
    if not rules_existed:
        click.echo(f"created {rules_file}")


__all__ = ["init"]
