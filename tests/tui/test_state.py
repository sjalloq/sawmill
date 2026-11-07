"""Tests for per-target TUI state."""

from __future__ import annotations

from sawmill.models.rule import Rule
from sawmill.tui.state import SORT_LINE, TargetState
from tests.tui.conftest import make_message, make_target_result


def _result(severity_levels):
    return make_target_result(
        {
            "a.log": [
                make_message("a1", "error", "E-1", line=1),
                make_message("a2", "warning", "W-1", line=2),
            ],
            "b.log": [
                make_message("b1", "info", "I-1", line=1),
                make_message("b2", "error", "E-2", line=2),
            ],
        },
        severity_levels,
        rules=[Rule(id="W-1", comment="ok")],
    )


def test_waived_ids_computed_from_result(severity_levels) -> None:
    result = _result(severity_levels)
    state = TargetState(result)
    waived = [m for log in result.logs for m, _ in log.waived]
    assert len(waived) == 1
    assert state.waived_ids == frozenset(id(m) for m in waived)


def test_base_messages_excludes_waived_and_hidden_by_default(severity_levels) -> None:
    state = TargetState(_result(severity_levels))
    state.hidden_ids = {"I-1"}
    assert [m.content for m in state.base_messages()] == ["a1", "b2"]


def test_base_messages_show_all_includes_everything(severity_levels) -> None:
    state = TargetState(_result(severity_levels))
    state.hidden_ids = {"I-1"}
    state.show_all = True
    assert [m.content for m in state.base_messages()] == ["a1", "a2", "b1", "b2"]


def test_base_messages_preserves_log_order(severity_levels) -> None:
    result = make_target_result(
        {
            "a.log": [make_message("a1", "info", line=1), make_message("a2", "info", line=5)],
            "b.log": [make_message("b1", "info", line=1), make_message("b2", "info", line=3)],
        },
        severity_levels,
    )
    msgs = TargetState(result).base_messages()
    assert [(m.log_path, m.start_line) for m in msgs] == [
        ("a.log", 1),
        ("a.log", 5),
        ("b.log", 1),
        ("b.log", 3),
    ]


def test_defaults(severity_levels) -> None:
    state = TargetState(_result(severity_levels))
    assert state.filter_text == ""
    assert state.severity_filter == {}
    assert state.sort_mode == SORT_LINE
    assert state.hidden_ids == set()
    assert state.show_all is False
    assert state.cursor_index == 0
    assert state.window_start == 0


def test_set_result_recomputes_waived_ids(severity_levels) -> None:
    state = TargetState(_result(severity_levels))
    new = make_target_result(
        {"a.log": [make_message("x", "error", "E-9", line=1)]},
        severity_levels,
        rules=[Rule(id="E-9", comment="ok")],
    )
    state.set_result(new)
    assert state.result is new
    assert state.waived_ids == frozenset(id(m) for log in new.logs for m, _ in log.waived)
    assert len(state.waived_ids) == 1
