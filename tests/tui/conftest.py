"""Shared fixtures and helpers for TUI tests."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from sawmill.core.rule_matcher import RuleMatcher
from sawmill.core.runner import LogResult, TargetResult
from sawmill.models.manifest import Manifest, Target
from sawmill.models.message import Message
from sawmill.models.plugin_api import SeverityLevel
from sawmill.models.rule import Rule, RuleFile
from sawmill.plugin import SawmillPlugin, hookimpl

_ROOT = Path("/nonexistent/sawmill-tui-tests")


def make_message(
    content: str,
    severity: str | None = None,
    message_id: str | None = None,
    line: int = 1,
) -> Message:
    """Create a test message."""
    return Message(
        start_line=line,
        end_line=line,
        raw_text=content,
        content=content,
        severity=severity,
        message_id=message_id,
    )


def make_target_result(
    messages_by_log: dict[str, list[Message]],
    severity_levels: list[SeverityLevel],
    name: str = "t",
    manifest: str = "m",
    rules: list[Rule] | None = None,
    fail_on: str | None = None,
) -> TargetResult:
    """Build a synthetic TargetResult with rules applied through a RuleMatcher."""
    man = Manifest(name=manifest, path=_ROOT / ".sawmill" / "manifest.toml")
    target = Target(name=name, plugin="test", logs=list(messages_by_log) or ["*.log"])
    matcher = RuleMatcher([RuleFile(plugin="test", rules=list(rules or []))], _ROOT, name)
    level_map = {s.id.lower(): s.level for s in severity_levels}
    if fail_on is None:
        fail_on = max(severity_levels, key=lambda s: s.level).id
    fail_level = level_map[fail_on.lower()]
    logs: list[LogResult] = []
    for rel, messages in messages_by_log.items():
        path = _ROOT / rel
        log = LogResult(path=path, rel_path=rel)
        for msg in messages:
            msg.log_path = rel
            log.messages.append(msg)
            res = matcher.match(msg, path)
            if res is not None and res.waived:
                log.waived.append((msg, res.rule))
            else:
                log.unwaived.append(msg)
                sev = (msg.severity or "").lower()
                if level_map.get(sev, -1) >= fail_level:
                    log.failures.append(msg)
        counts = dict.fromkeys(level_map, 0)
        counts["other"] = 0
        for msg in messages:
            sev = (msg.severity or "").lower()
            counts[sev if sev in level_map else "other"] += 1
        log.counts = counts
        logs.append(log)
    return TargetResult(
        manifest=man,
        target=target,
        plugin_name="test",
        severity_levels=list(severity_levels),
        fail_on=fail_on,
        fail_on_level=fail_level,
        logs=logs,
        matcher=matcher,
    )


@pytest.fixture
def severity_levels() -> list[SeverityLevel]:
    """Standard Vivado-like severity levels for tests."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


_LINE_RE = re.compile(r"^(ERROR|WARNING|INFO)(?: \[([^\]]+)\])? (.*)$")


class FakePlugin(SawmillPlugin):
    """Minimal line-per-message plugin (copied from tests/core/test_runner.py)."""

    name = "test"
    version = "1.0.0"

    def __init__(self, name: str = "test") -> None:
        super().__init__()
        self.name = name
        self.parse_calls = 0

    @hookimpl
    def can_handle(self, path: Path) -> float:
        return 0.0

    @hookimpl
    def get_severity_levels(self) -> list[dict]:
        return [
            {"id": "error", "name": "Error", "level": 2},
            {"id": "warning", "name": "Warning", "level": 1},
            {"id": "info", "name": "Info", "level": 0},
        ]

    @hookimpl
    def load_and_parse(self, path: Path) -> Iterator[Message]:
        self.parse_calls += 1
        for n, line in enumerate(Path(path).read_text().splitlines(), start=1):
            m = _LINE_RE.match(line)
            if m is None:
                yield Message(n, n, line, line, None, None)
            else:
                yield Message(n, n, line, m.group(3), m.group(1).lower(), m.group(2))


LOG = "ERROR [X-1] bad thing\nWARNING [Y-2] meh\nINFO hello\n"


class Recorder:
    """Records notify calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, message: str, **kwargs) -> None:
        self.calls.append((message, kwargs))
