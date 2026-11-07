"""Options and helpers shared by manifest-driven commands."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar

import rich_click as click
from rich.console import Console

from sawmill.core.config import ConfigError, ConfigLoader
from sawmill.core.discovery import (
    DiscoveryError,
    TargetRef,
    discover_manifests,
    load_single_manifest,
    resolve_roots,
    resolve_targets,
)
from sawmill.core.manifest import ManifestError
from sawmill.core.plugin import PluginManager, get_plugin_manager
from sawmill.core.rules import RuleValidationError
from sawmill.core.runner import RunnerError, TargetResult, run_target

F = TypeVar("F", bound=Callable[..., Any])

_VAR_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class SawmillCliError(click.ClickException):
    """A configuration, manifest or rule error; exits with status 2."""

    exit_code = 2


def manifest_options(func: F) -> F:
    """Add ``--manifest PATH`` and repeatable ``--root DIR`` options."""
    func = click.option(
        "--root",
        "roots",
        multiple=True,
        type=click.Path(path_type=Path),
        metavar="DIR",
        help="Directory to search for manifests (repeatable).",
    )(func)
    func = click.option(
        "--manifest",
        "manifest_path",
        type=click.Path(path_type=Path),
        metavar="PATH",
        help="Use exactly this manifest; no directory walk.",
    )(func)
    return func


def var_options(func: F) -> F:
    """Add the repeatable ``--var NAME=VALUE`` option (dest ``var_args``)."""
    return click.option(
        "--var",
        "var_args",
        multiple=True,
        metavar="NAME=VALUE",
        help="Set a manifest variable (repeatable).",
    )(func)


def parse_vars(var_args: Sequence[str]) -> dict[str, str]:
    """Parse ``NAME=VALUE`` arguments; later values override earlier ones.

    Raises:
        click.UsageError: If an argument has no ``=`` or an invalid name.
    """
    out: dict[str, str] = {}
    for arg in var_args:
        name, sep, value = arg.partition("=")
        if not sep or not _VAR_NAME_RE.fullmatch(name):
            raise click.UsageError(f"invalid --var '{arg}': expected NAME=VALUE")
        out[name] = value
    return out


def select_targets(
    manifest_path: Path | None,
    roots: Sequence[Path],
    names: Sequence[str],
    all_targets: bool,
    overrides: Mapping[str, str] | None = None,
) -> list[TargetRef]:
    """Discover manifests by root precedence and resolve target names.

    Raises:
        click.UsageError: If ``--manifest`` and ``--root`` are both given.
        SawmillCliError: On discovery, manifest or config errors.
    """
    if manifest_path is not None and roots:
        raise click.UsageError("--manifest cannot be combined with --root")
    try:
        if manifest_path is not None:
            manifests = load_single_manifest(manifest_path)
        else:
            config_roots: list[str] = []
            if not roots:
                config_roots = ConfigLoader().load_resolved().general.roots
            manifests = discover_manifests(resolve_roots(roots, config_roots))
        return resolve_targets(manifests, names, all_targets, overrides)
    except (DiscoveryError, ManifestError, ConfigError) as e:
        raise SawmillCliError(str(e)) from e


def run_selected(
    manifest_path: Path | None,
    roots: Sequence[Path],
    names: Sequence[str],
    all_targets: bool,
    fail_on: str | None,
    manager: PluginManager | None = None,
    overrides: Mapping[str, str] | None = None,
) -> list[TargetResult]:
    """Select targets and run each one, returning results in selection order.

    Args:
        manifest_path: Explicit manifest, or None to walk the roots.
        roots: Directories to search for manifests.
        names: Target names to select.
        all_targets: Select every target of every manifest.
        fail_on: Severity id overriding every target's ``fail_on``.
        manager: Plugin manager; defaults to :func:`get_plugin_manager`.
        overrides: Command-line variable values (``--var``).

    Raises:
        SawmillCliError: On selection, runner or rule errors.
    """
    refs = select_targets(manifest_path, roots, names, all_targets, overrides)
    if manager is None:
        manager = get_plugin_manager()
    try:
        return [run_target(ref, manager, fail_on=fail_on) for ref in refs]
    except (RunnerError, RuleValidationError) as e:
        raise SawmillCliError(str(e)) from e


def write_report_file(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def emit_warnings(results: Sequence[TargetResult]) -> None:
    """Print each result's runner warnings to stderr as ``warning: <text>``."""
    console = Console(stderr=True, highlight=False, soft_wrap=True)
    for result in results:
        for text in result.warnings:
            console.print(f"warning: {text}", markup=False)
