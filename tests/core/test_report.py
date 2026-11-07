"""Tests for the JSON report builder."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sawmill import __version__
from sawmill.core.discovery import TargetRef
from sawmill.core.manifest import ManifestLoader
from sawmill.core.plugin import PluginManager
from sawmill.core.report import build_report, rule_ref
from sawmill.core.runner import TargetResult, run_target
from sawmill.models.message import Message
from sawmill.plugin import SawmillPlugin, hookimpl

_LINE_RE = re.compile(r"^(ERROR|WARNING|INFO|NOTE)(?: \[([^\]]+)\])? (.*)$")


class FakePlugin(SawmillPlugin):
    """Minimal line-per-message plugin; severities declared least severe first."""

    name = "fake"
    version = "1.0.0"

    @hookimpl
    def can_handle(self, path: Path) -> float:
        return 0.0

    @hookimpl
    def get_severity_levels(self) -> list[dict]:
        return [
            {"id": "info", "name": "Info", "level": 0},
            {"id": "error", "name": "Error", "level": 2},
            {"id": "warning", "name": "Warning", "level": 1},
        ]

    @hookimpl
    def load_and_parse(self, path: Path) -> Iterator[Message]:
        for n, line in enumerate(Path(path).read_text().splitlines(), start=1):
            if not line.strip():
                continue
            m = _LINE_RE.match(line)
            if m is None:
                sev, mid, text = None, None, line
            elif m.group(1) == "NOTE":
                sev, mid, text = None, m.group(2), m.group(3)
            else:
                sev, mid, text = m.group(1).lower(), m.group(2), m.group(3)
            yield Message(n, n, line, text, sev, mid, None, None)


def _manager() -> PluginManager:
    manager = PluginManager()
    manager.register(FakePlugin())
    return manager


def _project(
    tmp_path: Path,
    manifest_toml: str,
    rules: dict[str, str] | None = None,
    logs: dict[str, str] | None = None,
) -> list[TargetRef]:
    sawmill_dir = tmp_path / ".sawmill"
    (sawmill_dir / "rules").mkdir(parents=True, exist_ok=True)
    (sawmill_dir / "manifest.toml").write_text(manifest_toml)
    for name, content in (rules or {}).items():
        (sawmill_dir / "rules" / name).write_text(content)
    for name, content in (logs or {}).items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    manifest = ManifestLoader().load(sawmill_dir / "manifest.toml")
    return [TargetRef(manifest, t) for t in manifest.targets]


def _manifest(target_extra: str = "", logs: str = '["build/*.log"]') -> str:
    return (
        '[manifest]\nname = "proj"\n\n'
        f'[[target]]\nname = "t"\nplugin = "fake"\nlogs = {logs}\n{target_extra}\n'
    )


def _rules(*bodies: str) -> str:
    out = '[rules]\nplugin = "fake"\n'
    for b in bodies:
        out += f'\n[[rule]]\n{b}\ncomment = "c"\n'
    return out


def _run(refs: list[TargetRef]) -> list[TargetResult]:
    manager = _manager()
    return [run_target(ref, manager) for ref in refs]


LOG = "ERROR [E-1] bad\nWARNING [W-1] meh\nINFO hi\nNOTE n\n"


def _simple(tmp_path: Path) -> list[TargetResult]:
    refs = _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('id = "W-1"', 'id = "NEVER"')},
        logs={"build/a.log": LOG},
    )
    return _run(refs)


def test_report_top_level_keys_and_passed(tmp_path: Path) -> None:
    report = build_report(_simple(tmp_path))
    assert set(report) == {"generated", "sawmill_version", "passed", "targets", "rules_unused"}
    assert report["sawmill_version"] == __version__
    assert report["passed"] is False
    assert len(report["targets"]) == 1


def test_report_target_fields_and_counts_order(tmp_path: Path) -> None:
    t = build_report(_simple(tmp_path))["targets"][0]
    assert t["manifest"] == "proj"
    assert t["name"] == "t"
    assert t["plugin"] == "fake"
    assert t["fail_on"] == "warning"
    assert t["fail_on_level"] == 1
    keys = list(t)
    assert keys.index("vars") == keys.index("fail_on_level") + 1
    assert t["vars"] == {}
    assert t["passed"] is False
    assert t["no_logs"] is False
    assert list(t["counts"]) == ["error", "warning", "info", "other"]
    assert t["counts"] == {"error": 1, "warning": 1, "info": 1, "other": 1}
    assert list(t["logs"][0]["counts"]) == ["error", "warning", "info", "other"]
    assert t["waived"] == 1
    assert t["unwaived"] == 3


def test_report_log_entries_failures_and_waived_messages(tmp_path: Path) -> None:
    log = build_report(_simple(tmp_path))["targets"][0]["logs"][0]
    assert log["path"] == "build/a.log"
    assert log["passed"] is False
    assert log["waived"] == 1
    assert log["unwaived"] == 3
    assert log["failures"] == [
        {"message_id": "E-1", "severity": "error", "line": 1, "content": "bad"}
    ]
    assert log["waived_messages"] == [
        {"message_id": "W-1", "severity": "warning", "line": 2, "rule": "r.toml#1"}
    ]


def test_report_rule_ref_shape(tmp_path: Path) -> None:
    refs = _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('file = "*.v"\nseverity = "warning"\nmax_count = 3')},
        logs={"build/a.log": LOG},
    )
    result = _run(refs)[0]
    rule = result.matcher.rules[0]
    ref = rule_ref(rule, result.matcher)
    assert set(ref) == {
        "file", "index", "name", "display", "id", "regex", "file_glob",
        "logs", "severity", "max_count", "per", "comment", "matches",
    }  # fmt: skip
    assert ref["file"] == str(rule.source)
    assert Path(ref["file"]).is_absolute()
    assert ref["index"] == 0
    assert ref["display"] == "r.toml#1"
    assert ref["file_glob"] == "*.v"
    assert ref["severity"] == "warning"
    assert ref["max_count"] == 3
    assert ref["per"] == "log"
    assert ref["comment"] == "c"
    assert ref["id"] is None
    assert ref["matches"] == result.matcher.match_count(rule)


_TWO = (
    '[manifest]\nname = "proj"\nrules = ["wide.toml"]\n\n'
    '[[target]]\nname = "a"\nplugin = "fake"\nlogs = ["a/*.log"]\n\n'
    '[[target]]\nname = "b"\nplugin = "fake"\nlogs = ["b/*.log"]\n'
)


def test_report_rules_used_unused_per_target_and_run_wide(tmp_path: Path) -> None:
    refs = _project(
        tmp_path,
        _TWO,
        rules={"wide.toml": _rules('id = "E-1"')},
        logs={"a/x.log": "ERROR [E-1] bad\n", "b/x.log": "INFO ok\n"},
    )
    report = build_report(_run(refs))
    a, b = report["targets"]
    assert [r["display"] for r in a["rules_used"]] == ["wide.toml#1"]
    assert a["rules_used"][0]["matches"] == 1
    assert a["rules_unused"] == []
    assert [r["display"] for r in b["rules_unused"]] == ["wide.toml#1"]
    assert b["rules_used"] == []
    assert report["rules_unused"] == []


def test_report_overflows(tmp_path: Path) -> None:
    refs = _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('id = "E-1"\nmax_count = 1')},
        logs={"build/a.log": "ERROR [E-1] one\nERROR [E-1] two\n"},
    )
    t = build_report(_run(refs))["targets"][0]
    assert len(t["overflows"]) == 1
    o = t["overflows"][0]
    assert o["rule"]["display"] == "r.toml#1"
    assert o["scope"] == "build/a.log"
    assert o["count"] == 2
    assert o["max_count"] == 1


def test_report_no_logs_target(tmp_path: Path) -> None:
    refs = _project(tmp_path, _manifest(logs='["none/*.log"]'))
    t = build_report(_run(refs))["targets"][0]
    assert t["no_logs"] is True
    assert t["logs"] == []
    assert t["passed"] is False


def _walk(obj: object) -> Iterator[object]:
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_report_is_json_serialisable(tmp_path: Path) -> None:
    report = build_report(_simple(tmp_path))
    json.dumps(report)
    assert not any(isinstance(v, Path) for v in _walk(report))


def test_report_generated_is_utc_iso(tmp_path: Path) -> None:
    generated = datetime.fromisoformat(build_report(_simple(tmp_path))["generated"])
    assert generated.tzinfo is not None
    assert generated.utcoffset() is not None
    assert generated.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_report_vars_resolved_mapping(tmp_path: Path) -> None:
    sawmill_dir = tmp_path / ".sawmill"
    refs = _project(
        tmp_path,
        _manifest(logs='["run.${build}/*.log"]').replace(
            '[manifest]\nname = "proj"\n', '[manifest]\nname = "proj"\n\n[vars]\nbuild = "top"\n'
        ),
        logs={"run.top/a.log": LOG},
    )
    assert sawmill_dir.exists()
    ref = TargetRef(refs[0].manifest, refs[0].target, overrides={"build": "top", "x": "1"})
    t = build_report(_run([ref]))["targets"][0]
    assert t["vars"] == {"build": "top", "x": "1"}
