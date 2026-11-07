"""Tests for shared manifest CLI options and target selection."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from sawmill.cli import cli
from sawmill.cli.common import parse_vars, select_targets

_MANIFEST = (
    '[manifest]\nname = "{name}"\n\n[[target]]\nname = "t"\nplugin = "fake"\nlogs = ["*.log"]\n'
)


def _write_manifest(project: Path, name: str = "proj", hidden: bool = False) -> Path:
    d = project / ".sawmill"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "manifest.toml"
    p.write_text(_MANIFEST.format(name=name))
    return p


def _unwrap(output: str) -> str:
    """Strip rich-click panel borders and line wrapping from error output."""
    return re.sub(r"[\s│╭╮╰╯─]+", "", output)


@pytest.fixture
def config_roots(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    roots: list[str] = []

    class FakeLoader:
        def load_resolved(self) -> SimpleNamespace:
            return SimpleNamespace(general=SimpleNamespace(roots=list(roots)))

    monkeypatch.setattr("sawmill.cli.common.ConfigLoader", FakeLoader)
    return roots


def test_select_targets_uses_cwd_when_no_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_roots: list[str]
) -> None:
    _write_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    refs = select_targets(None, (), (), False)
    assert [r.qualified_name for r in refs] == ["proj:t"]


def test_select_targets_root_option_wins_over_config_roots(
    tmp_path: Path, config_roots: list[str]
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    config_roots.append(str(empty))
    _write_manifest(tmp_path / "p")
    refs = select_targets(None, (tmp_path / "p",), (), False)
    assert [r.qualified_name for r in refs] == ["proj:t"]


def test_select_targets_config_roots_used_when_no_root_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_roots: list[str]
) -> None:
    _write_manifest(tmp_path / "p", name="cfg")
    config_roots.append(str(tmp_path / "p"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    refs = select_targets(None, (), (), False)
    assert [r.qualified_name for r in refs] == ["cfg:t"]


def test_select_targets_manifest_path_skips_walk(tmp_path: Path, config_roots: list[str]) -> None:
    path = _write_manifest(tmp_path / ".hidden" / "p", name="hid")
    refs = select_targets(path, (), (), False)
    assert [r.qualified_name for r in refs] == ["hid:t"]


def test_manifest_and_root_together_is_usage_error(tmp_path: Path, config_roots: list[str]) -> None:
    path = _write_manifest(tmp_path)
    result = CliRunner().invoke(cli, ["check", "--manifest", str(path), "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "--manifest" in result.output


def test_discovery_error_becomes_exit_2(tmp_path: Path, config_roots: list[str]) -> None:
    result = CliRunner().invoke(cli, ["check", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "no manifest found" in result.output


def test_manifest_error_becomes_exit_2(tmp_path: Path, config_roots: list[str]) -> None:
    d = tmp_path / ".sawmill"
    d.mkdir()
    (d / "manifest.toml").write_text("[manifest\nname=")
    result = CliRunner().invoke(cli, ["check", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "manifest.toml" in _unwrap(result.output)


def test_parse_vars_happy_path() -> None:
    assert parse_vars(["build=sub", "_x1=a=b", "e="]) == {"build": "sub", "_x1": "a=b", "e": ""}


def test_parse_vars_later_wins() -> None:
    assert parse_vars(["build=a", "build=b"]) == {"build": "b"}


@pytest.mark.parametrize("arg", ["build", "=x", "1bad=x"])
def test_parse_vars_malformed_is_usage_error(arg: str) -> None:
    import click

    with pytest.raises(click.UsageError, match=re.escape(arg)):
        parse_vars([arg])
