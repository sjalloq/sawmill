"""Rule matching for the manifest and rules design.

A :class:`RuleMatcher` is built per target from the ordered rule files that
apply to it. For each message the first rule whose present keys all match
claims it; ``max_count`` limits how many claimed messages are waived.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sawmill.models.message import Message
from sawmill.models.rule import Rule, RuleFile
from sawmill.utils.globs import glob_to_regex


@dataclass(frozen=True)
class MatchResult:
    """The rule that claimed a message and whether it was waived."""

    rule: Rule
    waived: bool


@dataclass(frozen=True)
class Overflow:
    """A rule whose ``max_count`` was exceeded within a scope."""

    rule: Rule
    scope: str
    count: int
    max_count: int


@dataclass
class _Compiled:
    rule: Rule
    order: int
    id: str | None
    regex: re.Pattern[str] | None
    file: re.Pattern[str] | None
    logs: list[re.Pattern[str]] | None
    severity: str | None


class RuleMatcher:
    """Match messages against an ordered list of rules for one target."""

    def __init__(
        self, rule_files: Sequence[RuleFile], project_root: Path, target_name: str
    ) -> None:
        """Build the matcher from ordered rule files."""
        self._root = project_root.resolve()
        self._target = target_name
        self._rules: list[Rule] = [r for f in rule_files for r in f.rules]
        self._compiled: list[_Compiled] = [
            _Compiled(
                rule=r,
                order=i,
                id=r.id,
                regex=re.compile(r.regex, re.DOTALL) if r.regex is not None else None,
                file=glob_to_regex(r.file) if r.file is not None else None,
                logs=[glob_to_regex(g) for g in r.logs] if r.logs is not None else None,
                severity=r.severity.lower() if r.severity is not None else None,
            )
            for i, r in enumerate(self._rules)
        ]
        self._log_cache: dict[Path, str] = {}
        self._file_cache: dict[str, str | None] = {}
        self._counts: dict[tuple[int, str], int] = {}
        self._totals: dict[int, int] = {}

    @property
    def rules(self) -> list[Rule]:
        """All rules, concatenated in file then rule order."""
        return list(self._rules)

    def _log_rel(self, log_path: Path) -> str:
        rel = self._log_cache.get(log_path)
        if rel is None:
            resolved = log_path.resolve()
            try:
                rel = resolved.relative_to(self._root).as_posix()
            except ValueError:
                rel = resolved.as_posix()
            self._log_cache[log_path] = rel
        return rel

    def _resolved_file(self, path: str) -> str | None:
        if path in self._file_cache:
            return self._file_cache[path]
        p = Path(path)
        result = None if p.is_absolute() else (self._root / p).resolve().as_posix()
        self._file_cache[path] = result
        return result

    def _file_matches(self, pat: re.Pattern[str], message: Message) -> bool:
        if message.file_ref is None:
            return False
        path = message.file_ref.path
        if pat.match(path):
            return True
        resolved = self._resolved_file(path)
        return resolved is not None and pat.match(resolved) is not None

    def match(self, message: Message, log_path: Path) -> MatchResult | None:
        """Return the claiming rule for ``message`` in ``log_path``, or None."""
        log_rel: str | None = None
        sev = message.severity.lower() if message.severity is not None else None
        for c in self._compiled:
            if c.id is not None and message.message_id != c.id:
                continue
            if c.severity is not None and sev != c.severity:
                continue
            if c.logs is not None:
                if log_rel is None:
                    log_rel = self._log_rel(log_path)
                if not any(g.match(log_rel) for g in c.logs):
                    continue
            if c.regex is not None and not c.regex.search(message.raw_text):
                continue
            if c.file is not None and not self._file_matches(c.file, message):
                continue
            key = id(c.rule)
            self._totals[key] = self._totals.get(key, 0) + 1
            rule = c.rule
            if rule.max_count is None:
                return MatchResult(rule=rule, waived=True)
            if rule.per == "target":
                scope = self._target
            else:
                scope = log_rel if log_rel is not None else self._log_rel(log_path)
            ckey = (key, scope)
            count = self._counts.get(ckey, 0) + 1
            self._counts[ckey] = count
            return MatchResult(rule=rule, waived=count <= rule.max_count)
        return None

    def used_rules(self) -> list[Rule]:
        """Rules that matched at least one message, in rule order."""
        return [r for r in self._rules if self._totals.get(id(r), 0) > 0]

    def unused_rules(self) -> list[Rule]:
        """Rules that matched no message, in rule order."""
        return [r for r in self._rules if self._totals.get(id(r), 0) == 0]

    def match_count(self, rule: Rule) -> int:
        """Total matches for ``rule`` across the target (waived and overflow)."""
        return self._totals.get(id(rule), 0)

    def overflows(self) -> list[Overflow]:
        """Scopes where a rule matched more than ``max_count`` times."""
        order = {id(c.rule): c.order for c in self._compiled}
        by_id = {id(r): r for r in self._rules}
        result: list[tuple[int, str, Overflow]] = []
        for (key, scope), count in self._counts.items():
            rule = by_id[key]
            assert rule.max_count is not None
            if count > rule.max_count:
                result.append(
                    (
                        order[key],
                        scope,
                        Overflow(rule=rule, scope=scope, count=count, max_count=rule.max_count),
                    )
                )
        result.sort(key=lambda t: (t[0], t[1]))
        return [t[2] for t in result]

    def reset_counts(self) -> None:
        """Clear all counters and usage tracking."""
        self._counts.clear()
        self._totals.clear()
