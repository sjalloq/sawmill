"""JSON report builder for manifest target runs.

:func:`build_report` turns a sequence of :class:`TargetResult` into a plain,
JSON-serialisable dictionary. It performs no I/O; callers write the result.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sawmill import __version__
from sawmill.core.rule_matcher import RuleMatcher
from sawmill.core.runner import LogResult, TargetResult
from sawmill.models.rule import Rule

_OTHER = "other"


def rule_ref(rule: Rule, matcher: RuleMatcher) -> dict[str, Any]:
    """Return the JSON description of ``rule`` with its match count."""
    return {
        "file": str(rule.source) if rule.source is not None else None,
        "index": rule.index,
        "name": rule.name,
        "display": rule.display,
        "id": rule.id,
        "regex": rule.regex,
        "file_glob": rule.file,
        "logs": list(rule.logs) if rule.logs is not None else None,
        "severity": rule.severity,
        "max_count": rule.max_count,
        "per": rule.per,
        "comment": rule.comment,
        "matches": matcher.match_count(rule),
    }


def _ordered_counts(result: TargetResult, counts: dict[str, int]) -> dict[str, int]:
    ordered = sorted(result.severity_levels, key=lambda s: -s.level)
    out = {s.id.lower(): counts.get(s.id.lower(), 0) for s in ordered}
    out[_OTHER] = counts.get(_OTHER, 0)
    return out


def _log_entry(result: TargetResult, log: LogResult) -> dict[str, Any]:
    return {
        "path": log.rel_path,
        "passed": log.passed,
        "counts": _ordered_counts(result, log.counts),
        "waived": len(log.waived),
        "unwaived": len(log.unwaived),
        "failures": [
            {
                "message_id": m.message_id,
                "severity": m.severity,
                "line": m.start_line,
                "content": m.content,
            }
            for m in log.failures
        ],
        "waived_messages": [
            {
                "message_id": m.message_id,
                "severity": m.severity,
                "line": m.start_line,
                "rule": rule.display,
            }
            for m, rule in log.waived
        ],
    }


def _target_entry(result: TargetResult) -> dict[str, Any]:
    matcher = result.matcher
    return {
        "manifest": result.manifest.name,
        "name": result.target.name,
        "plugin": result.plugin_name,
        "fail_on": result.fail_on,
        "fail_on_level": result.fail_on_level,
        "vars": dict(result.vars),
        "passed": result.passed,
        "no_logs": result.no_logs,
        "counts": _ordered_counts(result, result.counts),
        "waived": result.waived_count,
        "unwaived": result.unwaived_count,
        "logs": [_log_entry(result, log) for log in result.logs],
        "rules_used": [rule_ref(r, matcher) for r in matcher.used_rules()],
        "rules_unused": [rule_ref(r, matcher) for r in result.unused_rules()],
        "overflows": [
            {
                "rule": rule_ref(o.rule, matcher),
                "scope": o.scope,
                "count": o.count,
                "max_count": o.max_count,
            }
            for o in matcher.overflows()
        ],
    }


def _run_unused(results: Sequence[TargetResult]) -> list[dict[str, Any]]:
    used = {(rule.source, rule.index) for r in results for rule in r.matcher.used_rules()}
    seen: set[tuple[Path | None, int]] = set()
    unused: list[dict[str, Any]] = []
    for r in results:
        for rule in r.unused_rules():
            key = (rule.source, rule.index)
            if key in used or key in seen:
                continue
            seen.add(key)
            unused.append(rule_ref(rule, r.matcher))
    return unused


def build_report(results: Sequence[TargetResult]) -> dict[str, Any]:
    """Build the JSON report document covering every result.

    Args:
        results: One result per selected target, in run order.

    Returns:
        A JSON-serialisable dictionary.
    """
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "sawmill_version": __version__,
        "passed": all(r.passed for r in results),
        "targets": [_target_entry(r) for r in results],
        "rules_unused": _run_unused(results),
    }
