"""Tests for the JUnit XML view of the report."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from sawmill.core.junit import report_to_junit

_GEN = "2026-11-06T12:00:00+00:00"


def _rule(display: str) -> dict[str, Any]:
    return {"display": display, "file": "vivado.toml", "index": 1, "name": None}


def _log(path: str, failures: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "path": path,
        "passed": not failures,
        "counts": {"error": len(failures), "other": 0},
        "waived": 0,
        "unwaived": len(failures),
        "failures": failures,
        "waived_messages": [],
    }


def _target(name: str, logs: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    t: dict[str, Any] = {
        "manifest": "proj",
        "name": name,
        "plugin": "vivado",
        "fail_on": "error",
        "fail_on_level": 2,
        "passed": all(lg["passed"] for lg in logs),
        "no_logs": False,
        "counts": {"error": 0, "warning": 0, "other": 0},
        "waived": 0,
        "unwaived": 0,
        "logs": logs,
        "rules_used": [],
        "rules_unused": [],
        "overflows": [],
    }
    t.update(kw)
    return t


def _report() -> dict[str, Any]:
    fails = [
        {"message_id": "E-1", "severity": "error", "line": 3, "content": "bad"},
        {"message_id": None, "severity": "error", "line": 5, "content": 'worse <&"> x'},
    ]
    return {
        "generated": _GEN,
        "sawmill_version": "0",
        "passed": False,
        "targets": [
            _target(
                "ok",
                [_log("a.log", []), _log("b.log", [])],
                counts={"error": 0, "warning": 3, "other": 1},
                waived=4,
                unwaived=3,
                rules_unused=[_rule("vivado.toml#1"), _rule("vivado.toml:name")],
            ),
            _target("bad", [_log("c.log", fails)], counts={"error": 2, "other": 0}, unwaived=2),
            _target("empty", [], no_logs=True, passed=False),
        ],
        "rules_unused": [],
    }


def _root() -> ET.Element:
    return ET.fromstring(report_to_junit(_report()).encode())


def _suite(name: str) -> ET.Element:
    s = _root().find(f"testsuite[@name='proj:{name}']")
    assert s is not None
    return s


def test_root_is_testsuites_with_totals() -> None:
    root = _root()
    assert root.tag == "testsuites"
    assert root.get("name") == "sawmill"
    assert root.get("tests") == "4"
    assert root.get("failures") == "2"
    assert root.get("errors") == "0"
    assert root.get("time") == "0"


def test_one_testsuite_per_target_named_manifest_colon_target() -> None:
    suites = _root().findall("testsuite")
    assert [s.get("name") for s in suites] == ["proj:ok", "proj:bad", "proj:empty"]
    assert [s.get("tests") for s in suites] == ["2", "1", "1"]
    assert [s.get("failures") for s in suites] == ["0", "1", "1"]
    assert all(s.get("errors") == "0" for s in suites)


def test_one_testcase_per_log_with_classname_and_name() -> None:
    cases = _suite("ok").findall("testcase")
    assert [(c.get("classname"), c.get("name")) for c in cases] == [
        ("proj:ok", "a.log"),
        ("proj:ok", "b.log"),
    ]


def test_failure_element_message_and_body_lists_failures() -> None:
    case = _suite("bad").find("testcase")
    assert case is not None
    failure = case.find("failure")
    assert failure is not None
    assert failure.get("message") == "2 unwaived messages at or above error"
    assert failure.get("type") == "failure"
    lines = (failure.text or "").strip().splitlines()
    assert lines == ["error [E-1] bad", 'error worse <&"> x']


def test_passing_log_has_no_failure_child() -> None:
    for case in _suite("ok").findall("testcase"):
        assert case.find("failure") is None


def test_no_logs_target_single_failing_case() -> None:
    cases = _suite("empty").findall("testcase")
    assert len(cases) == 1
    assert cases[0].get("name") == "(no logs)"
    failure = cases[0].find("failure")
    assert failure is not None
    assert failure.get("message") == "no logs matched"
    assert failure.get("type") == "failure"


def test_properties_counts_waived_unwaived_fail_on_plugin_rules_unused() -> None:
    props = {p.get("name"): p.get("value") for p in _suite("ok").findall("properties/property")}
    assert props == {
        "counts.error": "0",
        "counts.warning": "3",
        "counts.other": "1",
        "waived": "4",
        "unwaived": "3",
        "fail_on": "error",
        "plugin": "vivado",
        "rules_unused": "vivado.toml#1, vivado.toml:name",
    }
    bad = {p.get("name") for p in _suite("bad").findall("properties/property")}
    assert "rules_unused" not in bad


def test_special_characters_escaped() -> None:
    text = report_to_junit(_report())
    assert 'worse <&"> x' not in text
    failure = _suite("bad").find("testcase/failure")
    assert failure is not None
    assert 'worse <&"> x' in (failure.text or "")


def test_output_has_xml_declaration_and_trailing_newline() -> None:
    text = report_to_junit(_report())
    assert text.startswith("<?xml version='1.0' encoding='UTF-8'?>") or text.startswith(
        '<?xml version="1.0" encoding="UTF-8"?>'
    )
    assert text.endswith("\n")
    assert "\n  <testsuite" in text


def test_timestamp_from_report_generated() -> None:
    assert all(s.get("timestamp") == _GEN for s in _root().findall("testsuite"))
