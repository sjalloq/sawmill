"""Target runner for the manifest and rules design.

:func:`run_target` executes one manifest target end to end: it selects the
plugin, loads the applicable rule files, parses every matched log, tags each
message with its log, applies the rules and returns a :class:`TargetResult`.
The runner produces no output; callers format the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sawmill.core.discovery import TargetRef
from sawmill.core.plugin import (
    PluginManager,
    get_plugin_manager,
    load_messages,
    plugin_implements_configure,
)
from sawmill.core.rule_matcher import RuleMatcher
from sawmill.core.rules import RuleLoader
from sawmill.core.severity import get_severity_levels, resolve_fail_on_level
from sawmill.models.manifest import Manifest, Target, VariableError
from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.rule import Rule, RuleFile

_OTHER = "other"


class RunnerError(Exception):
    """Raised when a target cannot be run."""


@dataclass
class LogResult:
    """The outcome of running one log of a target."""

    path: Path
    rel_path: str
    messages: list[Message] = field(default_factory=list)
    waived: list[tuple[Message, Rule]] = field(default_factory=list)
    unwaived: list[Message] = field(default_factory=list)
    failures: list[Message] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """True when the log has no failures."""
        return not self.failures


@dataclass
class TargetResult:
    """The outcome of running one target."""

    manifest: Manifest
    target: Target
    plugin_name: str
    severity_levels: list[SeverityLevel]
    fail_on: str
    fail_on_level: int
    logs: list[LogResult]
    matcher: RuleMatcher
    warnings: list[str] = field(default_factory=list)
    overrides: dict[str, str] = field(default_factory=dict)
    vars: dict[str, str] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """Return ``manifest:target``."""
        return f"{self.manifest.name}:{self.target.name}"

    @property
    def no_logs(self) -> bool:
        """True when the target's globs matched no log."""
        return not self.logs

    @property
    def passed(self) -> bool:
        """True when at least one log matched and every log passed."""
        return bool(self.logs) and all(log.passed for log in self.logs)

    @property
    def counts(self) -> dict[str, int]:
        """Per-severity counts summed over all logs."""
        total: dict[str, int] = {s.id.lower(): 0 for s in self.severity_levels}
        total[_OTHER] = 0
        for log in self.logs:
            for key, n in log.counts.items():
                total[key] = total.get(key, 0) + n
        return total

    @property
    def waived_count(self) -> int:
        """Total waived messages over all logs."""
        return sum(len(log.waived) for log in self.logs)

    @property
    def unwaived_count(self) -> int:
        """Total unwaived messages over all logs."""
        return sum(len(log.unwaived) for log in self.logs)

    @property
    def failures(self) -> list[Message]:
        """Failing messages over all logs, in log order."""
        return [m for log in self.logs for m in log.failures]

    def unused_rules(self) -> list[Rule]:
        """Rules that matched nothing, or [] when the target ignores them."""
        if self.target.unused_rules == "ignore":
            return []
        return self.matcher.unused_rules()

    @property
    def all_messages(self) -> list[Message]:
        """Every message over all logs, in log order."""
        return [m for log in self.logs for m in log.messages]


def _load_rule_file(loader: RuleLoader, path: Path, owner: str) -> RuleFile:
    if not path.is_file():
        raise RunnerError(f"rule file {path} listed by {owner} not found")
    return loader.load(path)


def load_rule_files_for(ref: TargetRef) -> list[RuleFile]:
    """Load the rule files in scope for a target, in matching order.

    Plugin-wide manifest files whose plugin equals the target's come first,
    then the target's own files.

    Raises:
        RunnerError: If a rule file is missing, or a target rule file is for
            a different plugin.
        RuleValidationError: If a rule file is invalid.
    """
    manifest, target = ref.manifest, ref.target
    qualified = f"{manifest.name}:{target.name}"
    loader = RuleLoader()
    files: list[RuleFile] = []
    for path in manifest.rule_paths():
        rf = _load_rule_file(loader, path, f"manifest '{manifest.name}'")
        if rf.plugin == target.plugin:
            files.append(rf)
    for path in target.rule_paths(manifest.rules_dir):
        rf = _load_rule_file(loader, path, f"target '{qualified}'")
        if rf.plugin != target.plugin:
            raise RunnerError(
                f"rule file {path} listed by target '{qualified}' is for plugin "
                f"'{rf.plugin}', but the target uses plugin '{target.plugin}'"
            )
        files.append(rf)
    return files


def _rel_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def run_target(
    ref: TargetRef,
    manager: PluginManager | None = None,
    fail_on: str | None = None,
) -> TargetResult:
    """Run one target end to end and return its result.

    Args:
        ref: The target and the manifest that defines it.
        manager: Plugin manager; defaults to :func:`get_plugin_manager`.
        fail_on: Severity id overriding the target and manifest ``fail_on``.

    Raises:
        RunnerError: If the plugin is not installed, rejects the target's
            ``plugin_options``, a rule file is missing
            or for the wrong plugin, or ``fail_on`` is unknown.
        RuleValidationError: If a rule file is invalid.
    """
    return _run_ref(ref, manager, fail_on)


def run_single_log(
    log_path: Path,
    plugin_name: str,
    manager: PluginManager | None = None,
    fail_on: str | None = None,
) -> TargetResult:
    """Run a bare log file, with no manifest, as a synthetic one-log target.

    The synthetic manifest is rooted at the log's directory, so the rules
    file ``.sawmill/rules/<plugin>.toml`` beside the log is applied when it
    exists. The result's qualified name is ``<parent dir>:<log name>``.

    Args:
        log_path: The log file to run.
        plugin_name: Name of the plugin that parses the log.
        manager: Plugin manager; defaults to :func:`get_plugin_manager`.
        fail_on: Severity id overriding the plugin default ``fail_on``.

    Raises:
        RunnerError: If the log is not an existing file, or as for
            :func:`run_target`.
        RuleValidationError: If the rules file is invalid.
    """
    if not log_path.is_file():
        raise RunnerError(f"log file {log_path} not found")
    log_path = log_path.resolve()
    parent = log_path.parent
    manifest = Manifest(
        name=parent.name or "log",
        path=parent / ".sawmill" / "manifest.toml",
    )
    rules_name = f"{plugin_name}.toml"
    rules = [rules_name] if (manifest.rules_dir / rules_name).exists() else []
    target = Target(name=log_path.name, plugin=plugin_name, logs=[log_path.name], rules=rules)
    return _run_ref(TargetRef(manifest, target), manager, fail_on)


def _match_log(
    messages: list[Message],
    path: Path,
    rel: str,
    matcher: RuleMatcher,
    level_map: dict[str, int],
    fail_on_level: int,
) -> LogResult:
    """Apply rules to one log's parsed messages and compute counts and failures."""
    result = LogResult(path=path, rel_path=rel, messages=messages)
    waived = result.waived
    unwaived = result.unwaived
    failures = result.failures
    match = matcher.match
    lower_cache: dict[str, str] = {}
    for msg in messages:
        res = match(msg, path)
        if res is not None and res.waived:
            waived.append((msg, res.rule))
        else:
            unwaived.append(msg)

    counts: dict[str, int] = dict.fromkeys(level_map, 0)
    counts[_OTHER] = 0
    for msg in messages:
        sev = msg.severity
        if sev is None:
            counts[_OTHER] += 1
            continue
        key = lower_cache.get(sev)
        if key is None:
            key = lower_cache[sev] = sev.lower()
        if key in counts and key != _OTHER:
            counts[key] += 1
        else:
            counts[_OTHER] += 1
    for msg in unwaived:
        sev = msg.severity
        if sev is not None:
            level = level_map.get(lower_cache.get(sev) or sev.lower())
            if level is not None and level >= fail_on_level:
                failures.append(msg)
    result.counts = counts
    return result


def reapply_rules(
    result: TargetResult,
    manager: PluginManager | None = None,
    ref: TargetRef | None = None,
) -> TargetResult:
    """Re-read the rule files and re-apply them to already-parsed messages.

    No plugin is called and no log is read; the returned result shares the
    ``Message`` objects of ``result``.

    Args:
        result: A previous run's result.
        manager: Unused; accepted for symmetry with :func:`rerun_target`.
        ref: Manifest and target to use instead of ``result``'s, e.g. after
            the manifest is re-read.

    Raises:
        RunnerError: If a rule file is missing or for the wrong plugin.
        RuleValidationError: If a rule file is invalid.
    """
    if ref is None:
        ref = TargetRef(result.manifest, result.target, overrides=dict(result.overrides))
    root = ref.manifest.root.resolve()
    matcher = RuleMatcher(load_rule_files_for(ref), root, ref.target.name)
    level_map = {s.id.lower(): s.level for s in result.severity_levels}
    logs = [
        _match_log(log.messages, log.path, log.rel_path, matcher, level_map, result.fail_on_level)
        for log in result.logs
    ]
    return TargetResult(
        manifest=ref.manifest,
        target=ref.target,
        plugin_name=result.plugin_name,
        severity_levels=result.severity_levels,
        fail_on=result.fail_on,
        fail_on_level=result.fail_on_level,
        logs=logs,
        matcher=matcher,
        warnings=list(result.warnings),
        overrides=dict(ref.overrides),
        vars=ref.vars,
    )


def rerun_target(
    result: TargetResult,
    manager: PluginManager | None = None,
    ref: TargetRef | None = None,
) -> TargetResult:
    """Re-run a target from scratch, re-parsing its logs and re-reading rules.

    Works for :func:`run_single_log` results as well as manifest targets.

    Args:
        result: A previous run's result.
        manager: Plugin manager; defaults to :func:`get_plugin_manager`.
        ref: Manifest and target to use instead of ``result``'s, e.g. after
            the manifest is re-read.

    Raises:
        RunnerError, RuleValidationError: As for :func:`run_target`.
    """
    if ref is None:
        ref = TargetRef(result.manifest, result.target, overrides=dict(result.overrides))
    return _run_ref(ref, manager, result.fail_on)


def _run_ref(
    ref: TargetRef,
    manager: PluginManager | None,
    fail_on: str | None,
) -> TargetResult:
    manifest, target = ref.manifest, ref.target
    qualified = f"{manifest.name}:{target.name}"
    if manager is None:
        manager = get_plugin_manager()

    plugin = manager.get_plugin(target.plugin)
    if plugin is None:
        raise RunnerError(f"plugin '{target.plugin}' for target '{qualified}' is not installed")
    warnings: list[str] = []
    options = dict(target.plugin_options)
    if plugin_implements_configure(plugin):
        try:
            plugin.configure(options)
        except ValueError as e:
            raise RunnerError(
                f"plugin '{target.plugin}' rejected plugin_options for target '{qualified}': {e}"
            ) from e
    elif options:
        warnings.append(
            f"target '{qualified}': plugin '{target.plugin}' does not implement configure; "
            "plugin_options ignored"
        )

    severity_levels: list[SeverityLevel] = get_severity_levels(plugin)
    fail_on_id = fail_on if fail_on is not None else manifest.effective_fail_on(target)
    try:
        fail_on_level = resolve_fail_on_level(fail_on_id, severity_levels)
    except ValueError as e:
        valid = ", ".join(s.id for s in sorted(severity_levels, key=lambda s: -s.level))
        raise RunnerError(
            f"unknown fail_on '{fail_on_id}' for target '{qualified}'; valid: {valid}"
        ) from e
    if fail_on_id is None:
        fail_on_id = next(s.id for s in severity_levels if s.level == fail_on_level)

    root = manifest.root.resolve()
    matcher = RuleMatcher(load_rule_files_for(ref), root, target.name)
    level_map = {s.id.lower(): s.level for s in severity_levels}

    logs: list[LogResult] = []
    resolved_vars = ref.vars
    try:
        log_paths = target.resolve_logs(root, resolved_vars)
    except VariableError as e:
        raise RunnerError(f"target '{qualified}': {e}") from e
    for log_path in log_paths:
        path = log_path.resolve()
        rel = _rel_path(path, root)
        messages: list[Message] = []
        for msg in load_messages(plugin, path):
            msg.log_path = rel
            messages.append(msg)
        logs.append(_match_log(messages, path, rel, matcher, level_map, fail_on_level))

    return TargetResult(
        manifest=manifest,
        target=target,
        plugin_name=target.plugin,
        severity_levels=severity_levels,
        fail_on=fail_on_id,
        fail_on_level=fail_on_level,
        logs=logs,
        matcher=matcher,
        warnings=warnings,
        overrides=dict(ref.overrides),
        vars=resolved_vars,
    )
