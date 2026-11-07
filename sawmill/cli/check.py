"""The ``sawmill check`` command: run manifest targets and gate on failures."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import rich_click as click
from rich.console import Console

from sawmill.cli.common import emit_warnings, manifest_options, run_selected, write_report_file
from sawmill.core.plugin import get_plugin_manager
from sawmill.core.report import build_report
from sawmill.core.runner import LogResult, TargetResult
from sawmill.models.message import Message
from sawmill.models.rule import Rule

MAX_FAILURES_SHOWN = 20
_INDENT = "    "


def target_header(result: TargetResult) -> str:
    """Return the ``== name (plugin, fail_on=id)`` header line."""
    return f"== {result.qualified_name} ({result.plugin_name}, fail_on={result.fail_on})"


def severity_columns(result: TargetResult, counts: dict[str, int]) -> str:
    """Format ``sev=n`` columns most-severe first, with ``other`` only when non-zero."""
    ordered = sorted(result.severity_levels, key=lambda s: -s.level)
    parts = [f"{s.id}={counts.get(s.id.lower(), 0)}" for s in ordered]
    other = counts.get("other", 0)
    if other:
        parts.append(f"other={other}")
    return " ".join(parts)


def log_line(result: TargetResult, log: LogResult) -> str:
    """Return the per-log summary line."""
    status = "PASS" if log.passed else "FAIL"
    cols = severity_columns(result, log.counts)
    return f"{log.rel_path}  {cols}  waived={len(log.waived)}  {status}"


def no_logs_line(result: TargetResult) -> str:
    """Return the line printed when a target matched no logs."""
    return f"no logs matched: {', '.join(result.target.logs)}  FAIL"


def message_line(message: Message) -> str:
    """Return the first line of a message's raw text, marking truncation."""
    lines = message.raw_text.splitlines() or [""]
    return lines[0] + (" …" if len(lines) > 1 else "")


def failure_lines(log: LogResult, limit: int = MAX_FAILURES_SHOWN) -> list[str]:
    """Return the failing message lines of a log, capped at ``limit``."""
    lines = [message_line(m) for m in log.failures[:limit]]
    extra = len(log.failures) - limit
    if extra > 0:
        lines.append(f"... and {extra} more")
    return lines


def target_lines(result: TargetResult) -> list[str]:
    """Return the full text block for one target."""
    lines = [target_header(result)]
    if result.no_logs:
        lines.append(no_logs_line(result))
        return lines
    for log in result.logs:
        lines.append(log_line(result, log))
        lines.extend(_INDENT + line for line in failure_lines(log))
    return lines


def overflow_lines(results: Sequence[TargetResult]) -> list[str]:
    """Return one line per ``max_count`` overflow over all results."""
    return [
        f"{o.rule.display}  {o.scope}  {o.count}/{o.max_count}"
        for r in results
        for o in r.matcher.overflows()
    ]


def unused_rules(results: Sequence[TargetResult]) -> list[Rule]:
    """Rules unused across the whole run, respecting per-target ``ignore``."""
    used = {(rule.source, rule.index) for r in results for rule in r.matcher.used_rules()}
    seen: set[tuple[Path | None, int]] = set()
    unused: list[Rule] = []
    for r in results:
        for rule in r.unused_rules():
            key = (rule.source, rule.index)
            if key in used or key in seen:
                continue
            seen.add(key)
            unused.append(rule)
    return unused


def summary_line(results: Sequence[TargetResult], unused: Sequence[Rule]) -> str:
    """Return the final ``check: passed/total targets passed`` line."""
    passed = sum(1 for r in results if r.passed)
    line = f"check: {passed}/{len(results)} targets passed"
    if unused:
        line += f", {len(unused)} unused rules"
    return line


def report_text_lines(results: Sequence[TargetResult]) -> list[str]:
    """Return the full ``check`` text output for ``results``."""
    lines: list[str] = []
    for result in results:
        lines.extend(target_lines(result))
    overflows = overflow_lines(results)
    if overflows:
        lines.append("Overflows:")
        lines.extend(_INDENT + line for line in overflows)
    unused = unused_rules(results)
    if unused:
        lines.append("Unused rules:")
        lines.extend(f"{_INDENT}{rule.display}  {rule.comment}" for rule in unused)
    lines.append(summary_line(results, unused))
    return lines


@click.command()
@click.argument("names", metavar="[TARGET...]", nargs=-1)
@click.option("--all", "all_targets", is_flag=True, help="Run every target of every manifest.")
@click.option(
    "--fail-on",
    "fail_on",
    metavar="SEV",
    help="Severity at or above which unwaived messages fail, for every target.",
)
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path),
    metavar="PATH",
    help="Also write the JSON report to PATH.",
)
@manifest_options
@click.pass_context
def check(
    ctx: click.Context,
    names: tuple[str, ...],
    all_targets: bool,
    fail_on: str | None,
    report_path: Path | None,
    manifest_path: Path | None,
    roots: tuple[Path, ...],
) -> None:
    """Run manifest targets and exit non-zero on unwaived failures."""
    results = run_selected(
        manifest_path, roots, names, all_targets, fail_on, manager=get_plugin_manager()
    )
    emit_warnings(results)
    console = Console(highlight=False, soft_wrap=True)
    for line in report_text_lines(results):
        console.print(line, markup=False)
    if report_path is not None:
        write_report_file(report_path, json.dumps(build_report(results), indent=2) + "\n")
    if not all(r.passed for r in results):
        ctx.exit(1)
