"""Tests for the Manifest and Target models."""

from __future__ import annotations

from pathlib import Path

import pytest

from sawmill.models.manifest import Manifest, Target

MPATH = Path("/p/.sawmill/manifest.toml")


def _target(**kw: object) -> Target:
    data: dict[str, object] = {"name": "t", "plugin": "vivado", "logs": ["x.log"]}
    data.update(kw)
    return Target(**data)  # type: ignore[arg-type]


def test_root_and_rules_dir() -> None:
    m = Manifest(name="x", path=MPATH)
    assert m.root == Path("/p")
    assert m.rules_dir == Path("/p/.sawmill/rules")


def test_root_without_path_raises() -> None:
    with pytest.raises(ValueError):
        _ = Manifest(name="x").root


def test_rule_paths_plugin_wide_order() -> None:
    m = Manifest(name="x", path=MPATH, rules=["a.toml", "b.toml"])
    assert m.rule_paths() == [m.rules_dir / "a.toml", m.rules_dir / "b.toml"]


def test_rule_paths_for_target_appends_target_files() -> None:
    t = _target(rules=["t.toml"])
    m = Manifest(name="x", path=MPATH, rules=["a.toml"], targets=[t])
    assert m.rule_paths_for(t) == [m.rules_dir / "a.toml", m.rules_dir / "t.toml"]


def test_effective_fail_on_prefers_target() -> None:
    t = _target(fail_on="error")
    m = Manifest(name="x", fail_on="warning", targets=[t])
    assert m.effective_fail_on(t) == "error"


def test_effective_fail_on_falls_back_to_manifest() -> None:
    t = _target()
    m = Manifest(name="x", fail_on="warning", targets=[t])
    assert m.effective_fail_on(t) == "warning"


def test_effective_fail_on_none() -> None:
    t = _target()
    assert Manifest(name="x", targets=[t]).effective_fail_on(t) is None


def test_get_target() -> None:
    t = _target(name="synth")
    m = Manifest(name="x", targets=[t])
    assert m.get_target("synth") is t
    assert m.get_target("nope") is None


def test_report_path_resolved_and_none() -> None:
    assert Manifest(name="x", path=MPATH, report="build/r.json").report_path() == Path(
        "/p/build/r.json"
    )
    assert Manifest(name="x", path=MPATH).report_path() is None


def test_resolve_logs_sorted_deduped_files_only(tmp_path: Path) -> None:
    pnr = tmp_path / "build" / "pnr"
    for job in ("job_1", "job_0"):
        (pnr / job).mkdir(parents=True)
        (pnr / job / "vivado.log").write_text("")
    (pnr / "job_2" / "vivado.log").mkdir(parents=True)
    t = _target(logs=["build/pnr/job_*/vivado.log", "build/pnr/job_0/vivado.log"])
    assert t.resolve_logs(tmp_path) == [
        tmp_path / "build/pnr/job_0/vivado.log",
        tmp_path / "build/pnr/job_1/vivado.log",
    ]


def test_resolve_logs_double_star(tmp_path: Path) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "x.log").write_text("")
    (tmp_path / "top.log").write_text("")
    t = _target(logs=["**/*.log"])
    assert set(t.resolve_logs(tmp_path)) == {tmp_path / "a/b/x.log", tmp_path / "top.log"}


def test_resolve_logs_no_match_returns_empty(tmp_path: Path) -> None:
    assert _target(logs=["nothing/*.log"]).resolve_logs(tmp_path) == []


def test_unused_rules_default_warn() -> None:
    assert _target().unused_rules == "warn"


def test_plugin_options_default_empty() -> None:
    assert _target().plugin_options == {}
