"""The ``sawmill report`` command: write a report of manifest target runs."""

from __future__ import annotations

import json
from pathlib import Path

import rich_click as click
from rich.console import Console

from sawmill.cli.check import report_text_lines
from sawmill.cli.common import (
    SawmillCliError,
    emit_warnings,
    manifest_options,
    parse_vars,
    run_selected,
    var_options,
    write_report_file,
)
from sawmill.core.junit import report_to_junit
from sawmill.core.plugin import get_plugin_manager
from sawmill.core.report import build_report
from sawmill.models.manifest import VariableError


@click.command()
@click.argument("names", metavar="[TARGET...]", nargs=-1)
@click.option("--all", "all_targets", is_flag=True, help="Report every target of every manifest.")
@click.option(
    "--fail-on",
    "fail_on",
    metavar="SEV",
    help="Severity at or above which unwaived messages fail, for every target.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "text", "junit"]),
    default="json",
    show_default=True,
    help="Report format.",
)
@click.option(
    "--output",
    "-o",
    "output",
    is_flag=False,
    flag_value="",
    metavar="PATH",
    help="Write to PATH. With no PATH, use the manifest's `report` setting.",
)
@manifest_options
@var_options
def report(
    names: tuple[str, ...],
    all_targets: bool,
    fail_on: str | None,
    fmt: str,
    output: str | None,
    manifest_path: Path | None,
    roots: tuple[Path, ...],
    var_args: tuple[str, ...],
) -> None:
    """Report on manifest targets; always exits 0 unless the configuration is invalid."""
    overrides = parse_vars(var_args)
    results = run_selected(
        manifest_path,
        roots,
        names,
        all_targets,
        fail_on,
        manager=get_plugin_manager(),
        overrides=overrides,
    )
    out_path: Path | None = None
    if output == "":
        manifest = results[0].manifest if results else None
        try:
            out_path = manifest.report_path(results[0].vars) if manifest is not None else None
        except VariableError as e:
            raise SawmillCliError(f"manifest '{results[0].manifest.name}': {e}") from e
        if out_path is None:
            name = manifest.name if manifest is not None else "?"
            raise SawmillCliError(
                f"--output given without PATH but manifest '{name}' has no report setting"
            )
    elif output is not None:
        out_path = Path(output)

    if fmt in ("json", "junit"):
        data = build_report(results)
        text = json.dumps(data, indent=2) + "\n" if fmt == "json" else report_to_junit(data)
        if out_path is None:
            click.echo(text, nl=False)
        else:
            write_report_file(out_path, text)
        return

    emit_warnings(results)
    lines = report_text_lines(results)
    if out_path is None:
        console = Console(highlight=False, soft_wrap=True)
        for line in lines:
            console.print(line, markup=False)
    else:
        write_report_file(out_path, "\n".join(lines) + "\n")
