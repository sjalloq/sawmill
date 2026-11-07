"""Tests for the target runner."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from sawmill.core.discovery import TargetRef
from sawmill.core.manifest import ManifestLoader
from sawmill.core.plugin import PluginManager
from sawmill.core.rules import RuleValidationError
from sawmill.core.runner import (
    RunnerError,
    reapply_rules,
    rerun_target,
    run_single_log,
    run_target,
)
from sawmill.models.message import FileRef, Message
from sawmill.plugin import SawmillPlugin, hookimpl

_LINE_RE = re.compile(r"^(ERROR|WARNING|INFO|NOTE)(?: \[([^\]]+)\])? (.*)$")


class FakePlugin(SawmillPlugin):
    """Minimal line-per-message plugin."""

    name = "fake"
    version = "1.0.0"

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

    parse_calls = 0

    @hookimpl
    def load_and_parse(self, path: Path) -> Iterator[Message]:
        self.parse_calls += 1
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
            fref = None
            if "@ " in text:
                fref = FileRef(text.split("@ ", 1)[1].strip())
            yield Message(n, n, line, text, sev, mid, None, fref)


def _manager() -> PluginManager:
    manager = PluginManager()
    manager.register(FakePlugin())
    return manager


def _project(
    tmp_path: Path,
    manifest_toml: str,
    rules: dict[str, str] | None = None,
    logs: dict[str, str] | None = None,
    target: str | None = None,
) -> TargetRef:
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
    t = manifest.targets[0] if target is None else manifest.get_target(target)
    assert t is not None
    return TargetRef(manifest, t)


def _manifest(
    target_extra: str = "",
    manifest_extra: str = "",
    logs: str = '["build/*.log"]',
) -> str:
    return (
        f'[manifest]\nname = "proj"\n{manifest_extra}\n\n'
        f'[[target]]\nname = "t"\nplugin = "fake"\nlogs = {logs}\n{target_extra}\n'
    )


def _rules(plugin: str, *bodies: str) -> str:
    out = f'[rules]\nplugin = "{plugin}"\n'
    for b in bodies:
        out += f'\n[[rule]]\n{b}\ncomment = "c"\n'
    return out


LOG_A = "ERROR [X-1] bad thing\nWARNING [Y-2] meh\nINFO hello\n"
LOG_B = "WARNING [Y-2] other\nNOTE plain\n"


def test_run_target_loads_all_logs_in_order(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/b.log": LOG_B, "build/a.log": LOG_A})
    result = run_target(ref, _manager())
    assert len(result.logs) == 2
    assert [log.rel_path for log in result.logs] == ["build/a.log", "build/b.log"]
    assert [m.message_id for m in result.logs[0].messages] == ["X-1", "Y-2", None]
    assert [m.content for m in result.logs[1].messages] == ["other", "plain"]
    assert result.logs[0].path == (tmp_path / "build/a.log").resolve()
    for log in result.logs:
        assert all(m.log_path == log.rel_path for m in log.messages)
        assert all(m.log_path is log.rel_path for m in log.messages)


def test_counts_per_severity_and_other(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A + LOG_B})
    result = run_target(ref, _manager())
    assert result.logs[0].counts == {"error": 1, "warning": 2, "info": 1, "other": 1}


def test_plugin_wide_rules_apply_when_plugin_matches(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(manifest_extra='rules = ["other.toml", "fake.toml"]'),
        rules={
            "other.toml": _rules("other", 'id = "X-1"'),
            "fake.toml": _rules("fake", 'id = "Y-2"'),
        },
        logs={"build/a.log": LOG_A},
    )
    result = run_target(ref, _manager())
    assert [r.id for r in result.matcher.rules] == ["Y-2"]
    log = result.logs[0]
    assert [(m.message_id, r.id) for m, r in log.waived] == [("Y-2", "Y-2")]
    assert [m.message_id for m in log.unwaived] == ["X-1", None]


def test_target_rules_apply_after_plugin_wide(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(manifest_extra='rules = ["wide.toml"]', target_extra='rules = ["mine.toml"]'),
        rules={
            "wide.toml": _rules("fake", 'regex = "bad"'),
            "mine.toml": _rules("fake", 'id = "X-1"', 'id = "Y-2"'),
        },
        logs={"build/a.log": LOG_A},
    )
    result = run_target(ref, _manager())
    assert [r.regex or r.id for r in result.matcher.rules] == ["bad", "X-1", "Y-2"]
    waived = {m.message_id: r for m, r in result.logs[0].waived}
    assert waived["X-1"].regex == "bad"
    assert waived["Y-2"].id == "Y-2"


def test_target_rule_file_with_wrong_plugin_raises(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["mine.toml"]'),
        rules={"mine.toml": _rules("other", 'id = "X-1"')},
        logs={"build/a.log": LOG_A},
    )
    with pytest.raises(RunnerError, match=r"mine\.toml.*other"):
        run_target(ref, _manager())


def test_missing_rule_file_raises_names_path(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["nope.toml"]'),
        logs={"build/a.log": LOG_A},
    )
    with pytest.raises(RunnerError, match=r"nope\.toml") as exc:
        run_target(ref, _manager())
    assert "proj:t" in str(exc.value)

    ref = _project(
        tmp_path,
        _manifest(manifest_extra='rules = ["gone.toml"]'),
        logs={"build/a.log": LOG_A},
    )
    with pytest.raises(RunnerError, match=r"gone\.toml") as exc:
        run_target(ref, _manager())
    assert "proj" in str(exc.value)


def test_rule_validation_error_propagates(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["bad.toml"]'),
        rules={"bad.toml": '[rules]\nplugin = "fake"\n\n[[rule]]\nid = "X"\n'},
        logs={"build/a.log": LOG_A},
    )
    with pytest.raises(RuleValidationError):
        run_target(ref, _manager())


def test_missing_plugin_raises(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A})
    with pytest.raises(RunnerError, match=r"plugin 'fake' for target 'proj:t' is not installed"):
        run_target(ref, PluginManager())


@pytest.mark.parametrize(
    ("target_extra", "manifest_extra", "expected", "level"),
    [
        ('fail_on = "info"', 'fail_on = "error"', "info", 0),
        ("", 'fail_on = "error"', "error", 2),
        ("", "", "warning", 1),
    ],
)
def test_fail_on_from_target_then_manifest_then_default(
    tmp_path: Path, target_extra: str, manifest_extra: str, expected: str, level: int
) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra=target_extra, manifest_extra=manifest_extra),
        logs={"build/a.log": LOG_A},
    )
    result = run_target(ref, _manager())
    assert result.fail_on == expected
    assert result.fail_on_level == level


def test_fail_on_override_argument_wins(tmp_path: Path) -> None:
    ref = _project(
        tmp_path, _manifest(target_extra='fail_on = "info"'), logs={"build/a.log": LOG_A}
    )
    result = run_target(ref, _manager(), fail_on="error")
    assert result.fail_on == "error"
    assert result.fail_on_level == 2


def test_fail_on_unknown_raises_lists_valid(tmp_path: Path) -> None:
    ref = _project(
        tmp_path, _manifest(target_extra='fail_on = "fatal"'), logs={"build/a.log": LOG_A}
    )
    with pytest.raises(RunnerError, match="proj:t") as exc:
        run_target(ref, _manager())
    for sev in ("error", "warning", "info"):
        assert sev in str(exc.value)


def test_failures_only_at_or_above_fail_on(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": LOG_A, "build/b.log": LOG_B},
    )
    result = run_target(ref, _manager())
    a, b = result.logs
    assert [m.message_id for m in a.failures] == ["X-1"]
    assert not a.passed
    assert [m.severity for m in b.unwaived] == ["warning", None]
    assert b.failures == []
    assert b.passed


def test_waived_messages_not_failures(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules("fake", 'id = "X-1"', 'id = "Y-2"')},
        logs={"build/a.log": LOG_A},
    )
    result = run_target(ref, _manager())
    log = result.logs[0]
    assert log.failures == []
    assert log.passed
    assert result.passed


def test_overflow_counts_as_unwaived(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules("fake", 'id = "X-1"\nmax_count = 1')},
        logs={"build/a.log": "ERROR [X-1] one\nERROR [X-1] two\n"},
    )
    result = run_target(ref, _manager())
    log = result.logs[0]
    assert [m.content for m, _ in log.waived] == ["one"]
    assert [m.content for m in log.unwaived] == ["two"]
    assert [m.content for m in log.failures] == ["two"]
    assert result.matcher.overflows()


def test_no_logs_target_fails(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(logs='["nothing/*.log"]'))
    result = run_target(ref, _manager())
    assert result.no_logs
    assert result.logs == []
    assert not result.passed


def test_passed_requires_all_logs_pass(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": LOG_A, "build/b.log": LOG_B},
    )
    result = run_target(ref, _manager())
    assert [log.passed for log in result.logs] == [False, True]
    assert not result.passed

    ref2 = _project(
        tmp_path / "p2",
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/b.log": LOG_B, "build/c.log": "INFO ok\n"},
    )
    result2 = run_target(ref2, _manager())
    assert result2.passed


def test_unused_rules_respects_ignore(tmp_path: Path) -> None:
    manifest = (
        '[manifest]\nname = "proj"\n\n'
        '[[target]]\nname = "warn"\nplugin = "fake"\nlogs = ["build/*.log"]\n'
        'rules = ["r.toml"]\n\n'
        '[[target]]\nname = "quiet"\nplugin = "fake"\nlogs = ["build/*.log"]\n'
        'rules = ["r.toml"]\nunused_rules = "ignore"\n'
    )
    files = {"r.toml": _rules("fake", 'id = "NEVER"')}
    ref = _project(tmp_path, manifest, rules=files, logs={"build/a.log": LOG_A}, target="warn")
    unused = run_target(ref, _manager()).unused_rules()
    assert [r.id for r in unused] == ["NEVER"]
    ref_q = TargetRef(ref.manifest, ref.manifest.get_target("quiet"))  # type: ignore[arg-type]
    assert run_target(ref_q, _manager()).unused_rules() == []


def test_qualified_name(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A})
    assert run_target(ref, _manager()).qualified_name == "proj:t"


def test_aggregate_properties(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules("fake", 'id = "Y-2"')},
        logs={"build/a.log": LOG_A, "build/b.log": LOG_B},
    )
    result = run_target(ref, _manager())
    assert result.counts == {"error": 1, "warning": 2, "info": 1, "other": 1}
    assert result.waived_count == 2
    assert result.unwaived_count == 3
    assert [m.content for m in result.all_messages] == [
        "bad thing",
        "meh",
        "hello",
        "other",
        "plain",
    ]
    assert [m.message_id for m in result.failures] == ["X-1"]


def test_runner_uses_default_manager_when_none(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A})
    with patch("sawmill.core.runner.get_plugin_manager", return_value=_manager()) as gpm:
        result = run_target(ref)
    gpm.assert_called_once_with()
    assert result.plugin_name == "fake"


def test_export() -> None:
    from sawmill.core import LogResult, RunnerError, TargetResult, run_target

    assert all(x is not None for x in (LogResult, RunnerError, TargetResult, run_target))


def test_load_rule_files_for_filters_and_orders(tmp_path: Path) -> None:
    from sawmill.core.runner import load_rule_files_for

    ref = _project(
        tmp_path,
        _manifest(
            manifest_extra='rules = ["other.toml", "wide.toml"]',
            target_extra='rules = ["mine.toml"]',
        ),
        rules={
            "other.toml": _rules("other", 'id = "O-1"'),
            "wide.toml": _rules("fake", 'id = "W-1"'),
            "mine.toml": _rules("fake", 'id = "M-1"'),
        },
    )
    files = load_rule_files_for(ref)
    assert [f.path.name for f in files if f.path] == ["wide.toml", "mine.toml"]
    assert [r.id for f in files for r in f.rules] == ["W-1", "M-1"]


def test_load_rule_files_for_missing_file_raises(tmp_path: Path) -> None:
    from sawmill.core.runner import load_rule_files_for

    ref = _project(tmp_path, _manifest(target_extra='rules = ["nope.toml"]'))
    with pytest.raises(RunnerError, match=r"nope\.toml"):
        load_rule_files_for(ref)


class ConfigurablePlugin(FakePlugin):
    """Fake plugin that implements configure and records its options."""

    def __init__(self, reject: bool = False) -> None:
        self.options: dict | None = None
        self.parsed_before_configure = False
        self.reject = reject

    @hookimpl
    def configure(self, options: dict) -> None:
        if self.reject:
            raise ValueError("bad option 'x'")
        self.options = options

    @hookimpl
    def load_and_parse(self, path: Path) -> Iterator[Message]:
        if self.options is None:
            self.parsed_before_configure = True
        yield from super().load_and_parse(path)


def _conf_manager(plugin: SawmillPlugin) -> PluginManager:
    manager = PluginManager()
    manager.register(plugin)
    return manager


def test_configure_called_with_plugin_options_before_parsing(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='[target.plugin_options]\nmode = "strict"\nlevel = 2'),
        logs={"build/a.log": LOG_A},
    )
    plugin = ConfigurablePlugin()
    result = run_target(ref, _conf_manager(plugin))
    assert plugin.options == {"mode": "strict", "level": 2}
    assert plugin.parsed_before_configure is False
    assert result.warnings == []


def test_configure_called_with_empty_dict_when_no_options(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A})
    plugin = ConfigurablePlugin()
    result = run_target(ref, _conf_manager(plugin))
    assert plugin.options == {}
    assert result.warnings == []


def test_configure_value_error_becomes_runner_error(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra="[target.plugin_options]\nx = 1"),
        logs={"build/a.log": LOG_A},
    )
    with pytest.raises(
        RunnerError, match=r"plugin 'fake' rejected plugin_options for target 'proj:t': bad option"
    ):
        run_target(ref, _conf_manager(ConfigurablePlugin(reject=True)))


def test_options_without_configure_hook_adds_warning(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra="[target.plugin_options]\nx = 1"),
        logs={"build/a.log": LOG_A},
    )
    result = run_target(ref, _manager())
    assert result.warnings == [
        "target 'proj:t': plugin 'fake' does not implement configure; plugin_options ignored"
    ]
    assert len(result.logs) == 1


def test_no_options_without_hook_no_warning(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A})
    result = run_target(ref, _manager())
    assert result.warnings == []


def test_run_single_log_builds_synthetic_target(tmp_path: Path) -> None:
    d = tmp_path / "work"
    d.mkdir()
    log = d / "run.log"
    log.write_text(LOG_A)
    result = run_single_log(log, "fake", _manager())
    assert result.qualified_name == "work:run.log"
    assert result.manifest.root == d.resolve()
    assert len(result.logs) == 1
    assert result.logs[0].rel_path == "run.log"
    assert result.logs[0].path == log.resolve()
    assert result.logs[0].messages
    assert all(m.log_path == "run.log" for m in result.logs[0].messages)
    assert result.fail_on == "warning"


def test_run_single_log_applies_rules_file_beside_log(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG_A)
    rules_dir = tmp_path / ".sawmill" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "fake.toml").write_text(_rules("fake", 'id = "X-1"'))
    result = run_single_log(log, "fake", _manager())
    assert result.matcher.rules
    assert [m.message_id for m, _ in result.logs[0].waived] == ["X-1"]


def test_run_single_log_without_rules_dir(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG_A)
    result = run_single_log(log, "fake", _manager())
    assert result.matcher.rules == []
    assert result.waived_count == 0


def test_run_single_log_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RunnerError):
        run_single_log(tmp_path / "nope.log", "fake", _manager())


def test_run_single_log_missing_plugin_raises(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG_A)
    with pytest.raises(RunnerError, match="not installed"):
        run_single_log(log, "absent", _manager())


def test_run_single_log_fail_on_override(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG_A)
    result = run_single_log(log, "fake", _manager(), fail_on="error")
    assert result.fail_on == "error"
    assert [m.message_id for m in result.failures] == ["X-1"]


# --- reapply_rules / rerun_target -------------------------------------------


def _counted() -> tuple[PluginManager, FakePlugin]:
    plugin = FakePlugin()
    manager = PluginManager()
    manager.register(plugin)
    return manager, plugin


def test_reapply_rules_uses_existing_messages(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["t.toml"]'),
        rules={"t.toml": _rules("fake", 'id = "NOPE"')},
        logs={"build/a.log": LOG_A},
    )
    manager, plugin = _counted()
    first = run_target(ref, manager)
    assert first.waived_count == 0
    calls = plugin.parse_calls
    (tmp_path / ".sawmill/rules/t.toml").write_text(_rules("fake", 'id = "X-1"'))
    new = reapply_rules(first, manager)
    assert plugin.parse_calls == calls
    assert new is not first
    assert [m.message_id for m, _ in new.logs[0].waived] == ["X-1"]
    for a, b in zip(first.logs[0].messages, new.logs[0].messages, strict=True):
        assert a is b
    assert new.logs[0].counts == first.logs[0].counts
    assert new.manifest is first.manifest and new.target is first.target
    assert new.fail_on == first.fail_on
    assert new.severity_levels == first.severity_levels
    assert [r.id for r in new.matcher.rules] == ["X-1"]


def test_reapply_rules_recomputes_failures_and_passed(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["t.toml"]\nfail_on = "error"'),
        rules={"t.toml": _rules("fake", 'id = "NOPE"')},
        logs={"build/a.log": LOG_A},
    )
    first = run_target(ref, _manager())
    assert not first.passed
    assert [m.message_id for m in first.failures] == ["X-1"]
    (tmp_path / ".sawmill/rules/t.toml").write_text(_rules("fake", 'id = "X-1"'))
    new = reapply_rules(first, _manager())
    assert new.failures == []
    assert new.passed
    assert not first.passed


def test_reapply_rules_rule_file_error_propagates(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["t.toml"]'),
        rules={"t.toml": _rules("fake", 'id = "NOPE"')},
        logs={"build/a.log": LOG_A},
    )
    first = run_target(ref, _manager())
    (tmp_path / ".sawmill/rules/t.toml").write_text(
        '[rules]\nplugin = "fake"\n[[rule]]\nid = "X"\n'
    )
    with pytest.raises(RuleValidationError):
        reapply_rules(first, _manager())


def test_rerun_target_reparses(tmp_path: Path) -> None:
    ref = _project(tmp_path, _manifest(), logs={"build/a.log": LOG_A})
    manager, plugin = _counted()
    first = run_target(ref, manager)
    calls = plugin.parse_calls
    (tmp_path / "build/a.log").write_text(LOG_A + "ERROR [Z-9] new\n")
    new = rerun_target(first, manager)
    assert plugin.parse_calls > calls
    assert [m.message_id for m in new.logs[0].messages] == ["X-1", "Y-2", None, "Z-9"]
    assert all(
        a is not b for a, b in zip(first.logs[0].messages, new.logs[0].messages, strict=False)
    )
    assert new.fail_on == first.fail_on


def test_rerun_target_works_for_single_log_result(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG_A)
    manager, plugin = _counted()
    first = run_single_log(log, "fake", manager, fail_on="error")
    log.write_text(LOG_B)
    new = rerun_target(first, manager)
    assert plugin.parse_calls == 2
    assert new.qualified_name == first.qualified_name
    assert [m.content for m in new.logs[0].messages] == ["other", "plain"]
    assert new.fail_on == "error"


def test_reapply_rules_works_for_single_log_result(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(LOG_A)
    rules_dir = tmp_path / ".sawmill" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "fake.toml").write_text(_rules("fake", 'id = "NOPE"'))
    manager, plugin = _counted()
    first = run_single_log(log, "fake", manager)
    assert first.waived_count == 0
    (rules_dir / "fake.toml").write_text(_rules("fake", 'id = "X-1"'))
    new = reapply_rules(first, manager)
    assert plugin.parse_calls == 1
    assert [m.message_id for m, _ in new.logs[0].waived] == ["X-1"]


def test_export_reapply_and_rerun() -> None:
    from sawmill.core import append_rule
    from sawmill.core import reapply_rules as core_reapply
    from sawmill.core import rerun_target as core_rerun

    assert core_reapply is reapply_rules
    assert core_rerun is rerun_target
    assert append_rule is not None


def test_reapply_rules_with_ref_uses_new_target_rules(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["t.toml"]'),
        rules={"t.toml": _rules("fake", 'id = "NOPE"'), "u.toml": _rules("fake", 'id = "X-1"')},
        logs={"build/a.log": LOG_A},
    )
    manager, plugin = _counted()
    first = run_target(ref, manager)
    calls = plugin.parse_calls
    new_target = first.target.model_copy(update={"rules": ["u.toml"]})
    new = reapply_rules(first, ref=TargetRef(first.manifest, new_target))
    assert plugin.parse_calls == calls
    assert [m.message_id for m, _ in new.logs[0].waived] == ["X-1"]
    assert new.target is new_target
    assert reapply_rules(first).waived_count == 0


def test_rerun_target_with_ref(tmp_path: Path) -> None:
    ref = _project(
        tmp_path,
        _manifest(target_extra='rules = ["t.toml"]'),
        rules={"t.toml": _rules("fake", 'id = "NOPE"'), "u.toml": _rules("fake", 'id = "Y-2"')},
        logs={"build/a.log": LOG_A},
    )
    manager, plugin = _counted()
    first = run_target(ref, manager)
    calls = plugin.parse_calls
    new_target = first.target.model_copy(update={"rules": ["u.toml"]})
    new = rerun_target(first, manager, ref=TargetRef(first.manifest, new_target))
    assert plugin.parse_calls > calls
    assert new.target is new_target
    assert [m.message_id for m, _ in new.logs[0].waived] == ["Y-2"]
