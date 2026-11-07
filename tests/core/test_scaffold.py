"""Tests for manifest scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest

from sawmill.core.manifest import ManifestLoader
from sawmill.core.rules import RuleLoader
from sawmill.core.scaffold import add_target, write_manifest_template


def _mpath(tmp_path: Path) -> Path:
    return tmp_path / ".sawmill" / "manifest.toml"


def test_write_manifest_template_creates_manifest_and_rules_dir_and_loads(
    tmp_path: Path,
) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    assert m.is_file()
    assert (m.parent / "rules").is_dir()
    manifest = ManifestLoader().load(m)
    assert manifest.name == "proj"
    assert manifest.targets == []


def test_write_manifest_template_existing_raises(tmp_path: Path) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    m.write_text("# mine\n" + m.read_text())
    with pytest.raises(FileExistsError):
        write_manifest_template(m, "other")
    assert m.read_text().startswith("# mine\n")


def test_add_target_appends_and_scaffolds_rules_file(tmp_path: Path) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    rules = add_target(m, "pnr", "vivado", "build/*.log")
    assert rules == m.parent / "rules" / "pnr.toml"
    assert rules.read_text() == '[rules]\nplugin = "vivado"\n'
    assert RuleLoader().load(rules).plugin == "vivado"
    target = ManifestLoader().load(m).get_target("pnr")
    assert target is not None
    assert target.plugin == "vivado"
    assert target.logs == ["build/*.log"]
    assert target.rules == ["pnr.toml"]


def test_add_target_custom_rules_file_name(tmp_path: Path) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    rules = add_target(m, "pnr", "vivado", "a.log", rules_file="vivado.toml")
    assert rules == m.parent / "rules" / "vivado.toml"
    assert rules.is_file()
    assert not (m.parent / "rules" / "pnr.toml").exists()
    target = ManifestLoader().load(m).get_target("pnr")
    assert target is not None
    assert target.rules == ["vivado.toml"]


def test_add_target_duplicate_name_raises(tmp_path: Path) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    add_target(m, "pnr", "vivado", "a.log")
    before = m.read_text()
    with pytest.raises(ValueError, match="pnr"):
        add_target(m, "pnr", "vivado", "b.log")
    assert m.read_text() == before


def test_add_target_does_not_overwrite_rules_file(tmp_path: Path) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    existing = m.parent / "rules" / "pnr.toml"
    existing.write_text('# keep\n[rules]\nplugin = "vivado"\n')
    add_target(m, "pnr", "vivado", "a.log")
    assert existing.read_text() == '# keep\n[rules]\nplugin = "vivado"\n'


def test_add_target_preserves_comments(tmp_path: Path) -> None:
    m = _mpath(tmp_path)
    write_manifest_template(m, "proj")
    add_target(m, "a", "vivado", "a.log")
    add_target(m, "b", "vivado", "b.log")
    text = m.read_text()
    assert "# report = " in text
    assert "# [[target]]" in text
    assert [t.name for t in ManifestLoader().load(m).targets] == ["a", "b"]
