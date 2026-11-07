"""Tests for rule file loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from sawmill.core.rules import RuleLoader, RuleValidationError, append_rule, ensure_rule_file
from sawmill.models.rule import Rule

SPEC = """[rules]
plugin = "vivado"

[[rule]]
id = "Vivado 12-3523"
comment = "Attempt to change param, harmless. BER-123"

[[rule]]
id = "Synth 8-7080"
regex = "u_dbg_.*"
logs = ["build/pnr/job_3/vivado.log"]
max_count = 2
comment = "Debug core only present in job 3; remove after 2027-01"

[[rule]]
id = "Synth 8-3331"
file = "**/ip/snps_pcie/**/*.v"
comment = "Vendor IP, not ours to fix"
"""

MINIMAL = """[rules]
plugin = "vivado"

[[rule]]
id = "X"
comment = "c"
"""

HEADER = '[rules]\nplugin = "vivado"\n\n[[rule]]\n'


def _err(content: str, path: Path | None = None) -> RuleValidationError:
    with pytest.raises(RuleValidationError) as exc:
        RuleLoader().load_from_string(content, path)
    return exc.value


def test_load_minimal_file() -> None:
    path = Path("/p/vivado.toml")
    rf = RuleLoader().load_from_string(MINIMAL, path)
    assert rf.plugin == "vivado"
    assert len(rf.rules) == 1
    rule = rf.rules[0]
    assert rule.index == 0
    assert rule.line == 4
    assert rule.source == path


def test_load_all_keys() -> None:
    rf = RuleLoader().load_from_string(SPEC)
    assert len(rf.rules) == 3
    r2 = rf.rules[1]
    assert r2.id == "Synth 8-7080"
    assert r2.regex == "u_dbg_.*"
    assert r2.logs == ["build/pnr/job_3/vivado.log"]
    assert r2.max_count == 2
    assert r2.per == "log"
    assert r2.comment.startswith("Debug core")
    assert r2.index == 1
    assert r2.line == 8
    r3 = rf.rules[2]
    assert r3.file == "**/ip/snps_pcie/**/*.v"
    assert r3.id == "Synth 8-3331"
    assert r3.line == 15


def test_load_from_file(tmp_path: Path) -> None:
    path = tmp_path / "vivado.toml"
    path.write_text(MINIMAL)
    rf = RuleLoader().load(path)
    assert rf.path == path
    assert rf.rules[0].source == path
    assert rf.rules[0].line == 4


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RuleLoader().load(tmp_path / "nope.toml")


def test_header_only_is_valid() -> None:
    rf = RuleLoader().load_from_string('[rules]\nplugin = "x"')
    assert rf.plugin == "x"
    assert rf.rules == []


def test_missing_rules_table() -> None:
    err = _err('[[rule]]\nid = "X"\ncomment = "c"\n')
    assert "[rules]" in str(err)
    assert err.line is None


def test_missing_plugin() -> None:
    err = _err('\n[rules]\n\n[[rule]]\nid = "X"\ncomment = "c"\n')
    assert "plugin" in str(err)
    assert err.line == 2


def test_rule_without_match_key() -> None:
    err = _err(HEADER + 'comment = "c"\n')
    msg = str(err)
    assert "id" in msg and "regex" in msg and "file" in msg
    assert err.rule_index == 0
    assert err.line == 4


def test_rule_missing_comment() -> None:
    err = _err(HEADER + 'id = "X"\n')
    assert "comment" in str(err)
    assert err.rule_index == 0


def test_rule_empty_comment() -> None:
    err = _err(HEADER + 'id = "X"\ncomment = ""\n')
    assert "comment" in str(err)


def test_invalid_regex() -> None:
    err = _err(HEADER + 'regex = "("\ncomment = "c"\n')
    assert "regex" in str(err)
    assert err.line == 4


@pytest.mark.parametrize("value", ["0", "-1", '"2"'])
def test_max_count_must_be_positive_int(value: str) -> None:
    err = _err(HEADER + f'id = "X"\nmax_count = {value}\ncomment = "c"\n')
    assert "max_count" in str(err)


def test_per_invalid_value() -> None:
    err = _err(HEADER + 'id = "X"\nmax_count = 1\nper = "file"\ncomment = "c"\n')
    assert "per" in str(err)


def test_per_without_max_count_raises() -> None:
    err = _err(HEADER + 'id = "X"\nper = "target"\ncomment = "c"\n')
    assert "max_count" in str(err)


@pytest.mark.parametrize("value", ['"a.log"', "[1]", '[""]'])
def test_logs_must_be_list_of_strings(value: str) -> None:
    err = _err(HEADER + f'id = "X"\nlogs = {value}\ncomment = "c"\n')
    assert "logs" in str(err)


def test_unknown_key_in_rule() -> None:
    err = _err(HEADER + 'id = "X"\nticket = "X"\ncomment = "c"\n')
    assert "ticket" in str(err)
    assert err.rule_index == 0


def test_unknown_key_in_header() -> None:
    err = _err('[rules]\nplugin = "x"\nfoo = "y"\n')
    assert "foo" in str(err)
    assert err.line == 1


def test_second_rule_error_reports_its_line_and_index() -> None:
    content = MINIMAL + '\n[[rule]]\ncomment = "c"\n'
    err = _err(content)
    assert err.rule_index == 1
    assert err.line == 8


def test_toml_syntax_error_reports_line() -> None:
    err = _err('[rules]\nplugin = "x"\nthis is broken\n')
    assert err.line == 3


def test_error_str_format() -> None:
    path = Path("/p/vivado.toml")
    err = _err(MINIMAL + '\n[[rule]]\ncomment = "c"\n', path)
    s = str(err)
    assert str(path) in s
    assert "rule 2" in s
    assert "line 8" in s


def test_rules_not_a_table() -> None:
    err = _err("rules = 1\n")
    assert "[rules]" in str(err)


def test_rule_not_array_of_tables() -> None:
    err = _err('[rules]\nplugin = "x"\nrule = 1\n')
    assert "rule" in str(err)


def test_exports() -> None:
    from sawmill.core import RuleLoader as CoreLoader
    from sawmill.core import RuleValidationError as CoreError
    from sawmill.models import Rule, RuleFile

    assert CoreLoader is RuleLoader
    assert CoreError is RuleValidationError
    assert Rule is not None and RuleFile is not None


# --- append_rule --------------------------------------------------------------


def test_append_rule_creates_file_with_header(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "fake.toml"
    append_rule(path, Rule(id="X-1", comment="ok"), "fake")
    rf = RuleLoader().load(path)
    assert rf.plugin == "fake"
    assert [r.id for r in rf.rules] == ["X-1"]
    assert rf.rules[0].comment == "ok"


_EXISTING = """# leading comment
[rules]
plugin = "fake" # note

[[rule]]
id = "OLD-1"
comment = "old"
"""


def test_append_rule_preserves_comments_and_existing_rules(tmp_path: Path) -> None:
    path = tmp_path / "fake.toml"
    path.write_text(_EXISTING)
    append_rule(path, Rule(id="NEW-1", comment="new"), "fake")
    text = path.read_text()
    assert text.startswith(_EXISTING)
    assert "# leading comment" in text
    assert 'plugin = "fake" # note' in text
    rf = RuleLoader().load(path)
    assert [r.id for r in rf.rules] == ["OLD-1", "NEW-1"]


def _new_block(text: str) -> list[str]:
    block = text.split("[[rule]]")[-1]
    return [ln.split("=")[0].strip() for ln in block.strip().splitlines() if "=" in ln]


def test_append_rule_key_order_and_omits_none(tmp_path: Path) -> None:
    path = tmp_path / "fake.toml"
    rule = Rule(
        id="X",
        regex="a.*b",
        file="src/*.sv",
        logs=["x.log"],
        severity="warning",
        max_count=3,
        comment="c",
        author="me",
        date="2026-11-07",
        name="n",
    )
    append_rule(path, rule, "fake")
    keys = _new_block(path.read_text())
    assert keys == [
        "id",
        "regex",
        "file",
        "logs",
        "severity",
        "max_count",
        "per",
        "comment",
        "author",
        "date",
        "name",
    ]
    assert 'per = "log"' in path.read_text()

    path2 = tmp_path / "other.toml"
    append_rule(path2, Rule(id="Y", comment="c"), "fake")
    text2 = path2.read_text()
    assert "regex =" not in text2
    assert "per =" not in text2
    assert _new_block(text2) == ["id", "comment"]


def test_append_rule_logs_array_and_escaping(tmp_path: Path) -> None:
    path = tmp_path / "fake.toml"
    append_rule(path, Rule(id='a"b\\c', logs=["x.log", "y/*.log"], comment="c"), "fake")
    rf = RuleLoader().load(path)
    assert rf.rules[0].id == 'a"b\\c'
    assert rf.rules[0].logs == ["x.log", "y/*.log"]
    assert 'logs = ["x.log", "y/*.log"]' in path.read_text()


def test_append_rule_wrong_plugin_raises(tmp_path: Path) -> None:
    path = tmp_path / "fake.toml"
    original = '[rules]\nplugin = "other"\n'
    path.write_text(original)
    with pytest.raises(RuleValidationError) as exc:
        append_rule(path, Rule(id="X", comment="c"), "fake")
    assert exc.value.path == path
    assert "other" in str(exc.value)
    assert path.read_text() == original


def test_append_rule_twice_appends_in_order(tmp_path: Path) -> None:
    path = tmp_path / "fake.toml"
    append_rule(path, Rule(id="A", comment="c"), "fake")
    append_rule(path, Rule(id="B", comment="c"), "fake")
    rf = RuleLoader().load(path)
    assert [r.id for r in rf.rules] == ["A", "B"]
    assert [r.index for r in rf.rules] == [0, 1]


def test_append_rule_atomic_no_temp_left(tmp_path: Path) -> None:
    path = tmp_path / "fake.toml"
    append_rule(path, Rule(id="A", comment="c"), "fake")
    append_rule(path, Rule(id="B", comment="c"), "fake")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fake.toml"]
    assert not list(tmp_path.glob("*.tmp"))


def test_ensure_rule_file_creates_header_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "rules" / "x.toml"
    ensure_rule_file(path, "vivado")
    assert path.read_text() == '[rules]\nplugin = "vivado"\n'
    assert RuleLoader().load(path).plugin == "vivado"


def test_ensure_rule_file_leaves_existing_untouched(tmp_path: Path) -> None:
    path = tmp_path / "x.toml"
    path.write_text(MINIMAL)
    ensure_rule_file(path, "other")
    assert path.read_text() == MINIMAL
