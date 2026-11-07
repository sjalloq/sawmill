"""Tests for the Rule and RuleFile models."""

from __future__ import annotations

from pathlib import Path

from sawmill.models.rule import Rule, RuleFile


def test_rule_display_uses_index_when_no_name() -> None:
    rule = Rule(id="X", comment="c", source=Path("/a/vivado.toml"), index=1)
    assert rule.display == "vivado.toml#2"


def test_rule_display_uses_name() -> None:
    rule = Rule(id="X", comment="c", source=Path("/a/vivado.toml"), index=1, name="dbg")
    assert rule.display == "vivado.toml:dbg"


def test_rule_display_without_source() -> None:
    assert Rule(id="X", comment="c", index=1).display == "#2"
    assert Rule(id="X", comment="c", index=1, name="dbg").display == "dbg"


def test_match_keys_only_present() -> None:
    rule = Rule(id="X", logs=["a/*.log"], comment="c")
    assert rule.match_keys() == {"id": "X", "logs": ["a/*.log"]}


def test_per_defaults_to_log() -> None:
    assert Rule(id="X", comment="c").per == "log"


def test_rule_file_defaults() -> None:
    assert RuleFile(plugin="vivado").rules == []
