"""JUnit XML view of the report built by :func:`sawmill.core.report.build_report`.

One testsuite per target and one testcase per log, for CI systems that render
JUnit results. Performs no I/O.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def _failure_line(failure: dict[str, Any]) -> str:
    mid = failure.get("message_id")
    tag = f" [{mid}]" if mid is not None else ""
    return f"{failure['severity']}{tag} {failure['content']}"


def _add_properties(suite: ET.Element, target: dict[str, Any]) -> None:
    props = ET.SubElement(suite, "properties")

    def add(name: str, value: object) -> None:
        ET.SubElement(props, "property", name=name, value=str(value))

    for sev, n in target["counts"].items():
        add(f"counts.{sev}", n)
    add("waived", target["waived"])
    add("unwaived", target["unwaived"])
    add("fail_on", target["fail_on"])
    add("plugin", target["plugin"])
    if target["rules_unused"]:
        add("rules_unused", ", ".join(r["display"] for r in target["rules_unused"]))


def _add_suite(root: ET.Element, target: dict[str, Any], timestamp: str) -> tuple[int, int]:
    name = f"{target['manifest']}:{target['name']}"
    suite = ET.SubElement(root, "testsuite", name=name, timestamp=timestamp)
    _add_properties(suite, target)
    tests = failures = 0
    if target["no_logs"]:
        case = ET.SubElement(suite, "testcase", classname=name, name="(no logs)")
        ET.SubElement(case, "failure", message="no logs matched", type="failure")
        tests, failures = 1, 1
    else:
        for log in target["logs"]:
            tests += 1
            case = ET.SubElement(suite, "testcase", classname=name, name=log["path"])
            if not log["passed"]:
                failures += 1
                fails = log["failures"]
                failure = ET.SubElement(
                    case,
                    "failure",
                    message=f"{len(fails)} unwaived messages at or above {target['fail_on']}",
                    type="failure",
                )
                failure.text = "\n".join(_failure_line(f) for f in fails)
    suite.set("tests", str(tests))
    suite.set("failures", str(failures))
    suite.set("errors", "0")
    return tests, failures


def report_to_junit(report: dict[str, Any]) -> str:
    """Render a report dictionary as a JUnit XML document.

    Args:
        report: The dictionary returned by ``build_report``.

    Returns:
        The XML document, with declaration and trailing newline.
    """
    root = ET.Element("testsuites", name="sawmill")
    tests = failures = 0
    for target in report["targets"]:
        t, f = _add_suite(root, target, report["generated"])
        tests += t
        failures += f
    root.set("tests", str(tests))
    root.set("failures", str(failures))
    root.set("errors", "0")
    root.set("time", "0")
    ET.indent(root)
    data: bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    return data.decode("utf-8") + "\n"
