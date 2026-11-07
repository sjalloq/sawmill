"""Tests for the ``sawmill check`` command."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner, Result

from sawmill.cli import cli
from sawmill.core.plugin import PluginManager
from sawmill.models.message import Message
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


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = PluginManager()
    manager.register(FakePlugin())
    monkeypatch.setattr("sawmill.cli.check.get_plugin_manager", lambda: manager)

    class FakeLoader:
        def load_resolved(self) -> SimpleNamespace:
            return SimpleNamespace(general=SimpleNamespace(roots=[]))

    monkeypatch.setattr("sawmill.cli.common.ConfigLoader", FakeLoader)


def _project(
    tmp_path: Path,
    manifest_toml: str,
    rules: dict[str, str] | None = None,
    logs: dict[str, str] | None = None,
) -> None:
    sawmill_dir = tmp_path / ".sawmill"
    (sawmill_dir / "rules").mkdir(parents=True, exist_ok=True)
    (sawmill_dir / "manifest.toml").write_text(manifest_toml)
    for name, content in (rules or {}).items():
        (sawmill_dir / "rules" / name).write_text(content)
    for name, content in (logs or {}).items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def _manifest(
    target_extra: str = "",
    manifest_extra: str = "",
    logs: str = '["build/*.log"]',
    name: str = "proj",
    plugin: str = "fake",
) -> str:
    return (
        f'[manifest]\nname = "{name}"\n{manifest_extra}\n\n'
        f'[[target]]\nname = "t"\nplugin = "{plugin}"\nlogs = {logs}\n{target_extra}\n'
    )


def _rules(*bodies: str, comment: str = "c") -> str:
    out = '[rules]\nplugin = "fake"\n'
    for b in bodies:
        out += f'\n[[rule]]\n{b}\ncomment = "{comment}"\n'
    return out


def _check(tmp_path: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["check", "--root", str(tmp_path), *args])


def test_check_passes_exit_0_and_summary_line(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": "WARNING [W-1] meh\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "== proj:t (fake, fail_on=error)" in result.output
    assert "PASS" in result.output
    assert "check: 1/1 targets passed" in result.output


def test_check_failure_exit_1_lists_messages(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "ERROR [E-1] broken thing\n"})
    result = _check(tmp_path)
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output
    assert "ERROR [E-1] broken thing" in result.output
    assert "check: 0/1 targets passed" in result.output


def test_check_waived_message_passes(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('id = "E-1"')},
        logs={"build/a.log": "ERROR [E-1] broken\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "waived=1" in result.output


def test_check_no_logs_is_failure(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(logs='["nothing/*.log"]'))
    result = _check(tmp_path)
    assert result.exit_code == 1, result.output
    assert "no logs matched: nothing/*.log  FAIL" in result.output


def test_check_fail_on_option_overrides(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": "WARNING [W-1] meh\n"},
    )
    assert _check(tmp_path).exit_code == 0
    result = _check(tmp_path, "--fail-on", "warning")
    assert result.exit_code == 1, result.output
    assert "fail_on=warning" in result.output


def test_check_unused_rules_listed_but_pass(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('id = "NEVER"', comment="obsolete waiver")},
        logs={"build/a.log": "INFO ok\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "Unused rules:" in result.output
    assert "r.toml#1" in result.output
    assert "obsolete waiver" in result.output
    assert "check: 1/1 targets passed, 1 unused rules" in result.output


def test_check_unused_rules_ignore_target_not_listed(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]\nunused_rules = "ignore"'),
        rules={"r.toml": _rules('id = "NEVER"')},
        logs={"build/a.log": "INFO ok\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "Unused rules:" not in result.output
    assert "unused" not in result.output


_TWO_TARGETS = (
    '[manifest]\nname = "proj"\nrules = ["wide.toml"]\n\n'
    '[[target]]\nname = "a"\nplugin = "fake"\nlogs = ["a/*.log"]\n\n'
    '[[target]]\nname = "b"\nplugin = "fake"\nlogs = ["b/*.log"]\n'
)


def test_check_unused_rule_used_by_other_target_not_listed(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _TWO_TARGETS,
        rules={"wide.toml": _rules('id = "E-1"')},
        logs={"a/x.log": "ERROR [E-1] bad\n", "b/x.log": "INFO ok\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert "== proj:a" in result.output
    assert "== proj:b" in result.output
    assert "Unused rules:" not in result.output


def test_check_overflow_listed_and_fails(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('id = "E-1"\nmax_count = 1')},
        logs={"build/a.log": "ERROR [E-1] one\nERROR [E-1] two\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 1, result.output
    assert "Overflows:" in result.output
    assert re.search(r"r\.toml#1\s+\S+\s+2/1", result.output), result.output


def test_check_selects_named_targets_only(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _TWO_TARGETS,
        rules={"wide.toml": _rules('id = "E-1"')},
        logs={"a/x.log": "INFO ok\n", "b/x.log": "INFO ok\n"},
    )
    result = _check(tmp_path, "b")
    assert result.exit_code == 0, result.output
    assert "== proj:b" in result.output
    assert "== proj:a" not in result.output


def test_check_qualified_target_name(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _TWO_TARGETS,
        rules={"wide.toml": _rules('id = "E-1"')},
        logs={"a/x.log": "ERROR [E-1] x\n"},
    )
    result = _check(tmp_path, "proj:a")
    assert result.exit_code == 0, result.output
    assert "== proj:a" in result.output
    assert "== proj:b" not in result.output


def test_check_all_flag_spans_two_manifests(tmp_path: Path) -> None:
    _project(tmp_path / "one", _manifest(name="one"), logs={"build/a.log": "INFO ok\n"})
    _project(tmp_path / "two", _manifest(name="two"), logs={"build/a.log": "INFO ok\n"})
    result = _check(tmp_path)
    assert result.exit_code == 2
    assert "--all" in result.output
    result = _check(tmp_path, "--all")
    assert result.exit_code == 0, result.output
    assert "== one:t" in result.output
    assert "== two:t" in result.output
    assert "check: 2/2 targets passed" in result.output


def test_check_unknown_target_exit_2(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    result = _check(tmp_path, "nosuch")
    assert result.exit_code == 2
    assert "nosuch" in result.output


def test_check_missing_plugin_exit_2(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(plugin="nope"), logs={"build/a.log": "INFO ok\n"})
    result = _check(tmp_path)
    assert result.exit_code == 2
    assert "nope" in result.output


def test_check_rule_validation_error_exit_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='rules = ["bad.toml"]'),
        rules={"bad.toml": '[rules]\nplugin = "fake"\n\n[[rule]]\nid = "X"\n'},
        logs={"build/a.log": "INFO ok\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 2
    assert "bad.toml" in result.output
    assert re.search(r"line \d+|:\d+", result.output), result.output


def test_check_severity_columns_most_severe_first(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": "INFO i\nWARNING w\nINFO j\nNOTE n\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert re.search(
        r"build/a\.log\s+error=0 warning=1 info=2 other=1\s+waived=0\s+PASS", result.output
    ), result.output
    _project(
        tmp_path / "q",
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": "INFO i\n"},
    )
    result = _check(tmp_path / "q")
    assert "other=" not in result.output


def test_check_failure_list_capped_at_20(tmp_path: Path) -> None:
    log = "".join(f"ERROR [E-{i}] boom {i}\n" for i in range(25))
    _project(tmp_path, _manifest(), logs={"build/a.log": log})
    result = _check(tmp_path)
    assert result.exit_code == 1
    assert "boom 19" in result.output
    assert "boom 20" not in result.output
    assert "... and 5 more" in result.output


def test_check_message_text_not_interpreted_as_markup(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "ERROR [E-1] [bold]x[/bold]\n"})
    result = _check(tmp_path)
    assert result.exit_code == 1
    assert "ERROR [E-1] [bold]x[/bold]" in result.output


def test_check_in_help() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.output
    result = CliRunner().invoke(cli, ["check", "--help"])
    for opt in ("TARGET", "--all", "--fail-on", "--manifest", "--root"):
        assert opt in result.output
    assert "--report" in result.output


def test_check_report_written_on_failure_and_exit_1(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "ERROR [E-1] bad\n"})
    out = tmp_path / "out" / "r.json"
    result = _check(tmp_path, "--report", str(out))
    assert result.exit_code == 1, result.output
    data = json.loads(out.read_text())
    assert data["passed"] is False
    assert data["targets"][0]["name"] == "t"


def test_check_report_written_on_pass(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    out = tmp_path / "r.json"
    result = _check(tmp_path, "--report", str(out))
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text())["passed"] is True


def test_check_report_requires_path(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    result = _check(tmp_path, "--report")
    assert result.exit_code == 2


def test_check_prints_configure_warning_to_stderr(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"\n[target.plugin_options]\nx = 1'),
        logs={"build/a.log": "WARNING [W-1] meh\n"},
    )
    result = _check(tmp_path)
    assert result.exit_code == 0, result.output
    assert (
        "warning: target 'proj:t': plugin 'fake' does not implement configure; "
        "plugin_options ignored" in result.stderr
    )
    assert "warning:" not in result.stdout
