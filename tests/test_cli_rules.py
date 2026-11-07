"""Tests for the ``sawmill rules`` command group."""

from __future__ import annotations

import datetime
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner, Result

from sawmill.cli import cli
from sawmill.core.plugin import PluginManager
from sawmill.core.rules import RuleLoader
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
    monkeypatch.setattr("sawmill.cli.rules.get_plugin_manager", lambda: manager)
    monkeypatch.setattr("sawmill.cli.rules.discover_author", lambda: "")

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


def _manifest(manifest_extra: str = "", *targets: str) -> str:
    out = f'[manifest]\nname = "proj"\n{manifest_extra}\n'
    for t in targets or (_target(),):
        out += t
    return out


def _target(
    name: str = "t", extra: str = "", logs: str = '["build/*.log"]', plugin: str = "fake"
) -> str:
    return f'\n[[target]]\nname = "{name}"\nplugin = "{plugin}"\nlogs = {logs}\n{extra}\n'


def _rules(*bodies: str, comment: str = "c", plugin: str = "fake") -> str:
    out = f'[rules]\nplugin = "{plugin}"\n'
    for b in bodies:
        out += f'\n[[rule]]\n{b}\ncomment = "{comment}"\n'
    return out


def _run(tmp_path: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["rules", *args, "--root", str(tmp_path)])


# -- list ---------------------------------------------------------------------


def test_rules_list_shows_rules_in_matching_order_with_keys(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest('rules = ["wide.toml"]', _target(extra='rules = ["mine.toml"]')),
        rules={
            "wide.toml": _rules('id = "W-1"', comment="wide one"),
            "mine.toml": _rules(
                'id = "E-1"\nregex = "bad"\nlogs = ["a.log", "b.log"]\nmax_count = 2',
                comment="mine one",
            ),
        },
    )
    result = _run(tmp_path, "list")
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == "== proj:t"
    assert lines[1] == "wide.toml#1  id=W-1  # wide one"
    assert lines[2] == (
        "mine.toml#1  id=E-1 regex=bad logs=[a.log,b.log]  max_count=2/log  # mine one"
    )


def test_rules_list_filters_plugin_wide_files_by_plugin(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest('rules = ["other.toml", "wide.toml"]'),
        rules={
            "other.toml": _rules('id = "O-1"', plugin="other"),
            "wide.toml": _rules('id = "W-1"'),
        },
    )
    result = _run(tmp_path, "list")
    assert result.exit_code == 0, result.output
    assert "W-1" in result.output
    assert "O-1" not in result.output


def test_rules_list_does_not_read_logs(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest("", _target(extra='rules = ["r.toml"]', logs='["none/*.log"]')),
        rules={"r.toml": _rules('id = "X-1"')},
    )
    result = _run(tmp_path, "list")
    assert result.exit_code == 0, result.output
    assert "r.toml#1  id=X-1  # c" in result.output


def test_rules_list_missing_rule_file_exit_2(tmp_path: Path) -> None:
    _project(tmp_path, _manifest("", _target(extra='rules = ["nope.toml"]')))
    result = _run(tmp_path, "list")
    assert result.exit_code == 2
    assert "nope.toml" in result.output


def test_rules_list_invalid_rule_file_exit_2_names_line(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest("", _target(extra='rules = ["bad.toml"]')),
        rules={"bad.toml": '[rules]\nplugin = "fake"\n\n[[rule]]\nid = "X"\n'},
    )
    result = _run(tmp_path, "list")
    assert result.exit_code == 2
    assert "bad.toml" in result.output
    assert re.search(r"line \d+", result.output), result.output


def test_rules_list_two_targets_headers(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest("", _target("a", 'rules = ["a.toml"]'), _target("b", 'rules = ["b.toml"]')),
        rules={"a.toml": _rules('id = "A-1"'), "b.toml": _rules('id = "B-1"')},
    )
    result = _run(tmp_path, "list", "--all")
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines.index("== proj:a") < lines.index("a.toml#1  id=A-1  # c")
    assert lines.index("a.toml#1  id=A-1  # c") < lines.index("== proj:b")
    assert lines.index("== proj:b") < lines.index("b.toml#1  id=B-1  # c")


# -- unused -------------------------------------------------------------------


def test_rules_unused_lists_run_wide(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(
            'rules = ["wide.toml"]',
            _target("a", logs='["a/*.log"]'),
            _target("b", logs='["b/*.log"]'),
        ),
        rules={"wide.toml": _rules('id = "A-1"', 'id = "Z-9"', comment="why")},
        logs={"a/x.log": "WARNING [A-1] used\n", "b/x.log": "WARNING [B-1] other\n"},
    )
    result = _run(tmp_path, "unused", "--all")
    assert result.exit_code == 0, result.output
    path = (tmp_path / ".sawmill" / "rules" / "wide.toml").resolve()
    lines = result.output.splitlines()
    assert not any("wide.toml#1" in line for line in lines)
    unused = [line for line in lines if "wide.toml#2" in line]
    assert len(unused) == 1
    assert re.fullmatch(rf"wide\.toml#2  {re.escape(str(path))}:\d+  # why", unused[0])


def test_rules_unused_none_message(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest("", _target(extra='rules = ["r.toml"]')),
        rules={"r.toml": _rules('id = "E-1"')},
        logs={"build/a.log": "ERROR [E-1] x\n"},
    )
    result = _run(tmp_path, "unused")
    assert result.exit_code == 0, result.output
    assert "No unused rules." in result.output


def test_rules_unused_exit_0_even_with_failures(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest("", _target(extra='rules = ["r.toml"]')),
        rules={"r.toml": _rules('id = "Q-1"')},
        logs={"build/a.log": "ERROR [E-1] x\n"},
    )
    result = _run(tmp_path, "unused")
    assert result.exit_code == 0, result.output
    assert "r.toml#1" in result.output


# -- generate -----------------------------------------------------------------


def _generate(tmp_path: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["rules", "generate", *args, "--root", str(tmp_path)])


GEN_LOG = (
    "ERROR [E-1] first error\n"
    "ERROR [E-1] second error\n"
    "WARNING [W-1] warn one\n"
    "WARNING [W-2] warn two\n"
    "WARNING [W-2] warn two again\n"
    "WARNING [W-2] warn two more\n"
    "INFO [I-1] info\n"
    "NOTE [N-1] no severity\n"
    "ERROR no id\n"
)


def test_rules_generate_outputs_loadable_rule_file(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": GEN_LOG})
    result = _generate(tmp_path, "t")
    assert result.exit_code == 0, result.output
    rf = RuleLoader().load_from_string(result.output)
    assert rf.plugin == "fake"
    ids = [r.id for r in rf.rules]
    assert sorted(ids) == ["E-1", "W-1", "W-2"]
    today = datetime.date.today().isoformat()
    for r in rf.rules:
        assert r.comment == "TODO: explain why this is acceptable"
        assert r.date == today
    assert f"for proj:t on {today}" in result.output.splitlines()[0]


def test_rules_generate_skips_waived_and_below_min_level(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest("", _target(extra='rules = ["r.toml"]')),
        rules={"r.toml": _rules('id = "E-1"')},
        logs={"build/a.log": GEN_LOG},
    )
    result = _generate(tmp_path, "t")
    assert result.exit_code == 0, result.output
    ids = [r.id for r in RuleLoader().load_from_string(result.output).rules]
    assert "E-1" not in ids
    assert "I-1" not in ids
    result = _generate(tmp_path, "t", "--min-level", "0")
    assert result.exit_code == 0, result.output
    ids = [r.id for r in RuleLoader().load_from_string(result.output).rules]
    assert "I-1" in ids
    assert "N-1" not in ids


def test_rules_generate_sorted_by_severity_then_count(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": GEN_LOG})
    result = _generate(tmp_path, "t", "--min-level", "0")
    ids = [r.id for r in RuleLoader().load_from_string(result.output).rules]
    assert ids == ["E-1", "W-2", "W-1", "I-1"]


def test_rules_generate_count_and_first_content_in_comment_line(tmp_path: Path) -> None:
    long = "x" * 100
    _project(
        tmp_path,
        _manifest(),
        logs={"build/a.log": GEN_LOG + f"WARNING [L-1] {long}\n"},
    )
    result = _generate(tmp_path, "t")
    lines = [ln for ln in result.output.splitlines() if ln.startswith("[[rule]]")]
    assert any(ln.endswith("# 3 matches, first: warn two") for ln in lines), lines
    assert any(ln.endswith("# 2 matches, first: first error") for ln in lines), lines
    assert any(ln.endswith(f"# 1 matches, first: {'x' * 80}") for ln in lines), lines


def test_rules_generate_escapes_quotes_in_id(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": 'ERROR [Q"1] quoted\n'})
    result = _generate(tmp_path, "t")
    assert result.exit_code == 0, result.output
    rf = RuleLoader().load_from_string(result.output)
    assert [r.id for r in rf.rules] == ['Q"1']


def test_rules_generate_author_from_discover_author(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": "ERROR [E-1] x\n"})
    monkeypatch.setattr("sawmill.cli.rules.discover_author", lambda: "me@x")
    result = _generate(tmp_path, "t")
    assert RuleLoader().load_from_string(result.output).rules[0].author == "me@x"
    monkeypatch.setattr("sawmill.cli.rules.discover_author", lambda: "")
    result = _generate(tmp_path, "t")
    assert "author" not in result.output
    assert RuleLoader().load_from_string(result.output).rules[0].author is None


def test_rules_generate_requires_exactly_one_target(tmp_path: Path) -> None:
    _project(tmp_path, _manifest("", _target("a"), _target("b")))
    assert _generate(tmp_path).exit_code == 2
    assert _generate(tmp_path, "a", "b").exit_code == 2


def test_rules_generate_min_level_out_of_range_exit_2(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": GEN_LOG})
    for bad in ("3", "-1"):
        result = _generate(tmp_path, "t", "--min-level", bad)
        assert result.exit_code == 2, result.output
        assert "error" in result.output and "info" in result.output


def test_rules_generate_only_toml_on_stdout(tmp_path: Path) -> None:
    _project(tmp_path, _manifest(), logs={"build/a.log": GEN_LOG})
    result = _generate(tmp_path, "t")
    assert result.exit_code == 0
    head = result.output.split("[rules]", 1)[0]
    assert all(ln.startswith("#") or not ln.strip() for ln in head.splitlines())


def test_rules_in_help() -> None:
    out = CliRunner().invoke(cli, ["--help"]).output
    assert "rules" in out
    out = CliRunner().invoke(cli, ["rules", "--help"]).output
    for cmd in ("list", "unused", "generate"):
        assert cmd in out


# -- --var --------------------------------------------------------------------


def _vars_project(tmp_path: Path) -> None:
    _project(
        tmp_path,
        _manifest(
            '\n[vars]\nbuild = "top"\n',
            _target(logs='["run.${build}/*.log"]', extra='rules = ["r.toml"]'),
        ),
        rules={"r.toml": _rules('id = "S-1"')},
        logs={
            "run.top/a.log": "INFO top\n",
            "run.sub/a.log": "ERROR [S-1] sub\nWARNING [S-2] sub2\n",
        },
    )


def test_rules_unused_accepts_var(tmp_path: Path) -> None:
    _vars_project(tmp_path)
    assert "r.toml#1" in _run(tmp_path, "unused").output
    result = _run(tmp_path, "unused", "--var", "build=sub")
    assert result.exit_code == 0, result.output
    assert "No unused rules." in result.output


def test_rules_generate_accepts_var(tmp_path: Path) -> None:
    _vars_project(tmp_path)
    result = _run(tmp_path, "generate", "t", "--var", "build=sub")
    assert result.exit_code == 0, result.output
    assert "S-2" in result.output


def test_rules_list_rejects_var(tmp_path: Path) -> None:
    _vars_project(tmp_path)
    result = _run(tmp_path, "list", "--var", "x=y")
    assert result.exit_code == 2
    assert "No such option" in result.output
