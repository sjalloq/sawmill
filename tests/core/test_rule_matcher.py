"""Tests for RuleMatcher."""

from __future__ import annotations

import dataclasses
import pathlib
from pathlib import Path
from typing import Any

import pytest

from sawmill.core.rule_matcher import MatchResult, Overflow, RuleMatcher
from sawmill.models.message import FileRef, Message
from sawmill.models.rule import Rule, RuleFile

_counter = 0


def _rule(**kw: Any) -> Rule:
    global _counter
    kw.setdefault("comment", "c")
    kw.setdefault("source", Path("/p/.sawmill/rules/r.toml"))
    if "index" not in kw:
        _counter += 1
        kw["index"] = _counter
    return Rule(**kw)


def _file(plugin: str, rules: list[Rule]) -> RuleFile:
    return RuleFile(plugin=plugin, rules=rules)


def _msg(
    raw: str = "text",
    mid: str | None = None,
    sev: str | None = None,
    path: str | None = None,
) -> Message:
    return Message(
        start_line=1,
        end_line=1,
        raw_text=raw,
        content=raw,
        severity=sev,
        message_id=mid,
        file_ref=FileRef(path=path) if path is not None else None,
    )


def _m(tmp_path: Path, *rules: Rule) -> RuleMatcher:
    return RuleMatcher([_file("vivado", list(rules))], tmp_path, "tgt")


def _log(tmp_path: Path, rel: str = "a.log") -> Path:
    return tmp_path / rel


def test_id_exact_match(tmp_path: Path) -> None:
    r = _rule(id="V 1-2")
    res = _m(tmp_path, r).match(_msg(mid="V 1-2"), _log(tmp_path))
    assert res == MatchResult(rule=r, waived=True)


def test_id_no_match_different_id(tmp_path: Path) -> None:
    assert _m(tmp_path, _rule(id="V 1-2")).match(_msg(mid="V 1-23"), _log(tmp_path)) is None


def test_message_without_id_never_matches_id_rule(tmp_path: Path) -> None:
    assert _m(tmp_path, _rule(id="V 1-2")).match(_msg(), _log(tmp_path)) is None


def test_regex_searches_raw_text_dotall(tmp_path: Path) -> None:
    r = _rule(regex="first.*third")
    res = _m(tmp_path, r).match(_msg(raw="first\nsecond\nthird"), _log(tmp_path))
    assert res is not None and res.rule is r


def test_regex_no_match(tmp_path: Path) -> None:
    assert _m(tmp_path, _rule(regex="zzz")).match(_msg(raw="abc"), _log(tmp_path)) is None


def test_file_glob_matches_path_as_written(tmp_path: Path) -> None:
    r = _rule(file="**/ip/**/*.v")
    assert _m(tmp_path, r).match(_msg(path="src/ip/x/a.v"), _log(tmp_path)) is not None


def test_file_glob_matches_resolved_path(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    r = _rule(file=f"{root.as_posix()}/ip/*.v")
    assert _m(root, r).match(_msg(path="ip/a.v"), _log(root)) is not None


def test_file_rule_skips_message_without_file_ref(tmp_path: Path) -> None:
    assert _m(tmp_path, _rule(file="**")).match(_msg(), _log(tmp_path)) is None


def test_severity_case_insensitive(tmp_path: Path) -> None:
    r = _rule(id="X", severity="WARNING")
    assert _m(tmp_path, r).match(_msg(mid="X", sev="warning"), _log(tmp_path)) is not None


def test_severity_mismatch(tmp_path: Path) -> None:
    r = _rule(id="X", severity="error")
    assert _m(tmp_path, r).match(_msg(mid="X", sev="warning"), _log(tmp_path)) is None


def test_message_without_severity_never_matches_severity_rule(tmp_path: Path) -> None:
    r = _rule(id="X", severity="error")
    assert _m(tmp_path, r).match(_msg(mid="X"), _log(tmp_path)) is None


def test_all_present_keys_must_match(tmp_path: Path) -> None:
    r = _rule(id="X", regex="nope")
    assert _m(tmp_path, r).match(_msg(mid="X", raw="yes"), _log(tmp_path)) is None


def test_logs_scoping_relative_to_root(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    m = _m(root, _rule(id="X", logs=["build/pnr/job_3/vivado.log"]))
    assert m.match(_msg(mid="X"), root / "build/pnr/job_3/vivado.log") is not None
    assert m.match(_msg(mid="X"), root / "build/pnr/job_4/vivado.log") is None


def test_logs_scoping_glob(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    m = _m(root, _rule(id="X", logs=["build/pnr/job_*/vivado.log"]))
    assert m.match(_msg(mid="X"), root / "build/pnr/job_4/vivado.log") is not None
    assert m.match(_msg(mid="X"), root / "build/syn/job_4/vivado.log") is None


def test_log_outside_root_uses_absolute_path(tmp_path: Path) -> None:
    root = (tmp_path / "proj").resolve()
    outside = (tmp_path / "other" / "v.log").resolve()
    m = _m(root, _rule(id="X", logs=[outside.as_posix()]))
    assert m.match(_msg(mid="X"), outside) is not None
    m2 = _m(root, _rule(id="X", logs=["other/v.log"]))
    assert m2.match(_msg(mid="X"), outside) is None


def test_order_plugin_wide_before_target_then_rule_order(tmp_path: Path) -> None:
    a1 = _rule(id="Y")
    a2 = _rule(id="X")
    b1 = _rule(id="X")
    m = RuleMatcher([_file("v", [a1, a2]), _file("v", [b1])], tmp_path, "t")
    res = m.match(_msg(mid="X"), _log(tmp_path))
    assert res is not None and res.rule is a2


def test_first_match_wins_even_if_later_more_specific(tmp_path: Path) -> None:
    broad = _rule(regex=".")
    specific = _rule(id="X", regex="abc", severity="warning")
    res = _m(tmp_path, broad, specific).match(
        _msg(mid="X", raw="abc", sev="warning"), _log(tmp_path)
    )
    assert res is not None and res.rule is broad


def test_max_count_per_log(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    r = _rule(id="X", max_count=2)
    m = _m(root, r)
    a = root / "A.log"
    b = root / "B.log"
    results = [m.match(_msg(mid="X"), a) for _ in range(3)]
    assert [x.waived for x in results if x] == [True, True, False]
    assert all(x is not None and x.rule is r for x in results)
    res_b = m.match(_msg(mid="X"), b)
    assert res_b is not None and res_b.waived
    assert m.overflows() == [Overflow(rule=r, scope="A.log", count=3, max_count=2)]


def test_max_count_per_target(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    r = _rule(id="X", max_count=2, per="target")
    m = _m(root, r)
    out = [m.match(_msg(mid="X"), root / p) for p in ("A.log", "A.log", "B.log")]
    assert [x.waived for x in out if x] == [True, True, False]
    assert m.overflows() == [Overflow(rule=r, scope="tgt", count=3, max_count=2)]


def test_overflow_does_not_fall_through(tmp_path: Path) -> None:
    r = _rule(id="X", max_count=1)
    catch = _rule(regex=".")
    m = _m(tmp_path, r, catch)
    m.match(_msg(mid="X", raw="a"), _log(tmp_path))
    res = m.match(_msg(mid="X", raw="a"), _log(tmp_path))
    assert res is not None and res.rule is r and not res.waived
    assert m.used_rules() == [r]
    assert m.unused_rules() == [catch]


def test_used_and_unused_rules(tmp_path: Path) -> None:
    r1, r2, r3 = _rule(id="A"), _rule(id="B"), _rule(id="C")
    m = _m(tmp_path, r1, r2, r3)
    m.match(_msg(mid="B"), _log(tmp_path))
    m.match(_msg(mid="B"), _log(tmp_path))
    assert m.used_rules() == [r2]
    assert m.unused_rules() == [r1, r3]
    assert m.match_count(r2) == 2
    assert m.match_count(r1) == 0


def test_rule_used_after_overflow(tmp_path: Path) -> None:
    r = _rule(id="X", max_count=1)
    m = _m(tmp_path, r)
    m.match(_msg(mid="X"), _log(tmp_path))
    m.match(_msg(mid="X"), _log(tmp_path))
    assert m.used_rules() == [r]
    assert m.match_count(r) == 2


def test_reset_counts_clears_everything(tmp_path: Path) -> None:
    r = _rule(id="X", max_count=1)
    m = _m(tmp_path, r)
    m.match(_msg(mid="X"), _log(tmp_path))
    m.match(_msg(mid="X"), _log(tmp_path))
    m.reset_counts()
    assert m.used_rules() == []
    assert m.unused_rules() == [r]
    assert m.match_count(r) == 0
    assert m.overflows() == []
    res = m.match(_msg(mid="X"), _log(tmp_path))
    assert res is not None and res.waived


def test_no_rules_returns_none(tmp_path: Path) -> None:
    m = RuleMatcher([], tmp_path, "t")
    assert m.match(_msg(mid="X"), _log(tmp_path)) is None
    assert m.rules == []


def test_rules_property_concatenates_files_in_order(tmp_path: Path) -> None:
    a, b, c = _rule(id="A"), _rule(id="B"), _rule(id="C")
    m = RuleMatcher([_file("v", [a, b]), _file("v", [c])], tmp_path, "t")
    assert m.rules == [a, b, c]


def test_match_result_and_overflow_are_frozen() -> None:
    r = _rule(id="X")
    with pytest.raises(dataclasses.FrozenInstanceError):
        MatchResult(rule=r, waived=True).waived = False  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Overflow(rule=r, scope="s", count=1, max_count=1).count = 2  # type: ignore[misc]


def test_no_resolve_after_warm_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path.resolve()
    m = _m(root, _rule(id="X", logs=["a.log"]), _rule(file="ip/*.v"))
    log = root / "a.log"
    m.match(_msg(mid="X"), log)
    m.match(_msg(path="ip/a.v"), log)

    def _boom(self: Path, strict: bool = False) -> Path:
        raise AssertionError("resolve called")

    monkeypatch.setattr(pathlib.Path, "resolve", _boom)
    assert m.match(_msg(mid="X"), log) is not None
    assert m.match(_msg(path="ip/a.v"), log) is not None
