"""Tests for the ``sawmill report`` command."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
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
    monkeypatch.setattr("sawmill.cli.report.get_plugin_manager", lambda: manager)

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


def _report(tmp_path: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["report", "--root", str(tmp_path), *args])


def _check(tmp_path: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["check", "--root", str(tmp_path), *args])


_TWO_TARGETS = (
    '[manifest]\nname = "proj"\n\n'
    '[[target]]\nname = "a"\nplugin = "fake"\nlogs = ["a/*.log"]\n\n'
    '[[target]]\nname = "b"\nplugin = "fake"\nlogs = ["b/*.log"]\n'
)


def test_report_json_to_stdout_default(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    result = _report(tmp_path)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["targets"][0]["name"] == "t"
    assert data["passed"] is True


def test_report_output_file_written_and_parent_created(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    out = tmp_path / "deep" / "dir" / "r.json"
    result = _report(tmp_path, "--output", str(out))
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert text.endswith("\n")
    assert json.loads(text)["targets"][0]["manifest"] == "proj"


def _block(output: str) -> list[str]:
    lines = output.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("== "))
    end = next(i for i, line in enumerate(lines) if line.startswith("check: "))
    return lines[start : end + 1]


def test_report_text_format_matches_check_output(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='rules = ["r.toml"]'),
        rules={"r.toml": _rules('id = "NEVER"', 'id = "E-2"\nmax_count = 1')},
        logs={"build/a.log": "ERROR [E-1] bad\nERROR [E-2] x\nERROR [E-2] y\nNOTE n\n"},
    )
    checked = _check(tmp_path)
    reported = _report(tmp_path, "--format", "text")
    assert checked.exit_code == 1
    assert reported.exit_code == 0, reported.output
    assert _block(reported.output) == _block(checked.output)
    assert "Overflows:" in reported.output
    assert "Unused rules:" in reported.output


def test_report_text_to_file(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    out = tmp_path / "out" / "r.txt"
    result = _report(tmp_path, "--format", "text", "--output", str(out))
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "== proj:t (fake, fail_on=" in text
    assert "check: 1/1 targets passed" in text
    assert "== proj:t" not in result.output


def test_report_exit_0_even_when_targets_fail(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "ERROR [E-1] bad\n"})
    result = _report(tmp_path)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["passed"] is False


def test_report_bare_output_flag_uses_manifest_report_key(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(manifest_extra='report = "build/out/sawmill-report.json"'),
        logs={"build/a.log": "INFO ok\n"},
    )
    result = _report(tmp_path, "--output")
    assert result.exit_code == 0, result.output
    out = tmp_path / "build" / "out" / "sawmill-report.json"
    assert json.loads(out.read_text())["targets"][0]["name"] == "t"


def test_report_bare_output_flag_without_manifest_key_exit_2(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    result = _report(tmp_path, "--output")
    assert result.exit_code == 2
    assert "report" in result.output


def test_report_fail_on_override_reflected_in_json(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(target_extra='fail_on = "error"'),
        logs={"build/a.log": "WARNING [W-1] meh\n"},
    )
    data = json.loads(_report(tmp_path).output)
    assert data["targets"][0]["fail_on"] == "error"
    assert data["passed"] is True
    result = _report(tmp_path, "--fail-on", "warning")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["targets"][0]["fail_on"] == "warning"
    assert data["targets"][0]["fail_on_level"] == 1
    assert data["passed"] is False


def test_report_invalid_format_exit_2(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    result = _report(tmp_path, "--format", "xml")
    assert result.exit_code == 2


def test_report_selects_targets_and_all(tmp_path: Path) -> None:
    _project(tmp_path, _TWO_TARGETS, logs={"a/x.log": "INFO ok\n", "b/x.log": "INFO ok\n"})
    result = _report(tmp_path, "b")
    assert result.exit_code == 0, result.output
    assert [t["name"] for t in json.loads(result.output)["targets"]] == ["b"]

    multi = tmp_path / "multi"
    _project(multi / "one", _manifest(name="one"), logs={"build/a.log": "INFO ok\n"})
    _project(multi / "two", _manifest(name="two"), logs={"build/a.log": "INFO ok\n"})
    assert _report(multi).exit_code == 2
    result = _report(multi, "--all")
    assert result.exit_code == 0, result.output
    names = [t["manifest"] for t in json.loads(result.output)["targets"]]
    assert names == ["one", "two"]


def test_report_in_help() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "report" in result.output
    result = CliRunner().invoke(cli, ["report", "--help"])
    assert result.exit_code == 0
    for opt in ("TARGET", "--all", "--fail-on", "--format", "--output", "--manifest", "--root"):
        assert opt in result.output


def test_report_junit_to_stdout_parses(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "ERROR [E-1] bad <x>\n"})
    result = _report(tmp_path, "--format", "junit")
    assert result.exit_code == 0, result.output
    root = ET.fromstring(result.output.encode())
    assert root.tag == "testsuites"
    suites = root.findall("testsuite")
    assert len(suites) == 1
    assert suites[0].get("name") == "proj:t"


def test_report_junit_to_file(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "INFO ok\n"})
    out = tmp_path / "out" / "r.xml"
    result = _report(tmp_path, "--format", "junit", "--output", str(out))
    assert result.exit_code == 0, result.output
    assert result.output == ""
    text = out.read_text()
    assert text.endswith("\n")
    root = ET.fromstring(text.encode())
    assert root.find("testsuite/testcase").get("name") == "build/a.log"


def _vars_project(tmp_path: Path, manifest_extra: str) -> None:
    _project(
        tmp_path,
        _manifest(manifest_extra=manifest_extra, logs='["run.${build}/*.log"]'),
        logs={"run.top/a.log": "INFO top\n", "run.sub/a.log": "INFO sub\n"},
    )


def test_report_var_recorded_in_json(tmp_path: Path) -> None:
    _vars_project(tmp_path, '\n[vars]\nbuild = "top"')
    result = _report(tmp_path, "--var", "build=sub")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["targets"][0]["vars"] == {"build": "sub"}


def test_report_bare_output_expands_vars(tmp_path: Path) -> None:
    _vars_project(tmp_path, 'report = "run.${build}/r.json"\n\n[vars]\nbuild = "top"')
    result = _report(tmp_path, "--var", "build=sub", "--output")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "run.sub" / "r.json").is_file()
    assert not (tmp_path / "run.top" / "r.json").exists()


def test_report_bare_output_undefined_var_exit_2(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(manifest_extra='report = "run.${nope}/r.json"'),
        logs={"build/a.log": "INFO ok\n"},
    )
    result = _report(tmp_path, "--output")
    assert result.exit_code == 2
    assert "nope" in result.output
