"""Tests for the ``sawmill init`` command."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from sawmill.cli import cli
from sawmill.core.manifest import ManifestLoader
from sawmill.core.plugin import PluginManager
from sawmill.models.message import Message
from sawmill.plugin import SawmillPlugin, hookimpl


class FakePlugin(SawmillPlugin):
    """Plugin that claims files whose first line starts with ``FAKE``."""

    name = "fake"
    version = "1.0.0"

    @hookimpl
    def can_handle(self, path: Path) -> float:
        try:
            lines = Path(path).read_text().splitlines()
        except OSError:
            return 0.0
        return 1.0 if lines and lines[0].startswith("FAKE") else 0.0

    @hookimpl
    def get_severity_levels(self) -> list[dict]:
        return [{"id": "error", "name": "Error", "level": 1}]

    @hookimpl
    def load_and_parse(self, path: Path) -> Iterator[Message]:
        return iter(())


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manager = PluginManager()
    manager.register(FakePlugin())
    monkeypatch.setattr("sawmill.cli.init.get_plugin_manager", lambda: manager)
    monkeypatch.chdir(tmp_path)


def _init(*args: str) -> Result:
    return CliRunner().invoke(cli, ["init", *args])


def _mpath(tmp_path: Path) -> Path:
    return tmp_path / ".sawmill" / "manifest.toml"


def _log(tmp_path: Path, name: str, content: str = "FAKE log\n") -> None:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_init_creates_manifest_and_rules_dir(tmp_path: Path) -> None:
    result = _init()
    assert result.exit_code == 0, result.output
    assert _mpath(tmp_path).is_file()
    assert (tmp_path / ".sawmill" / "rules").is_dir()
    m = ManifestLoader().load(_mpath(tmp_path))
    assert m.name == tmp_path.name
    assert m.targets == []


def test_init_name_option(tmp_path: Path) -> None:
    result = _init("--name", "soc")
    assert result.exit_code == 0, result.output
    assert ManifestLoader().load(_mpath(tmp_path)).name == "soc"


def test_init_template_has_every_key_commented(tmp_path: Path) -> None:
    assert _init().exit_code == 0
    text = _mpath(tmp_path).read_text()
    for key in (
        "# rules =",
        "# report =",
        "# fail_on =",
        "# [[target]]",
        "# plugin =",
        "# logs =",
        "# unused_rules =",
        "# [target.plugin_options]",
    ):
        assert key in text
    uncommented = [
        ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    assert uncommented == ["[manifest]", f'name = "{tmp_path.name}"']


def test_init_existing_manifest_exit_2(tmp_path: Path) -> None:
    assert _init().exit_code == 0
    result = _init()
    assert result.exit_code == 2
    assert "already exists" in result.output


def test_init_target_creates_manifest_when_missing_then_appends(tmp_path: Path) -> None:
    _log(tmp_path, "build/a.log")
    result = _init("--target", "pnr", "build/*.log", "--name", "proj")
    assert result.exit_code == 0, result.output
    m = ManifestLoader().load(_mpath(tmp_path))
    assert m.name == "proj"
    assert [t.name for t in m.targets] == ["pnr"]
    assert "# [[target]]" in _mpath(tmp_path).read_text()


def test_init_target_autodetects_plugin_from_first_match(tmp_path: Path) -> None:
    _log(tmp_path, "build/a.log")
    _log(tmp_path, "build/b.log", "other\n")
    result = _init("--target", "pnr", "build/*.log")
    assert result.exit_code == 0, result.output
    t = ManifestLoader().load(_mpath(tmp_path)).targets[0]
    assert t.plugin == "fake"
    assert t.logs == ["build/*.log"]
    assert t.rules == ["pnr.toml"]
    rules = tmp_path / ".sawmill" / "rules" / "pnr.toml"
    assert rules.read_text() == '[rules]\nplugin = "fake"\n'


def test_init_target_explicit_plugin_skips_detection(tmp_path: Path) -> None:
    result = _init("--target", "pnr", "build/*.log", "--plugin", "fake")
    assert result.exit_code == 0, result.output
    assert ManifestLoader().load(_mpath(tmp_path)).targets[0].plugin == "fake"


def test_init_target_unknown_plugin_exit_2_lists_installed(tmp_path: Path) -> None:
    result = _init("--target", "pnr", "build/*.log", "--plugin", "nope")
    assert result.exit_code == 2
    assert "nope" in result.output
    assert "fake" in result.output


def test_init_target_no_match_no_plugin_exit_2(tmp_path: Path) -> None:
    result = _init("--target", "pnr", "build/*.log")
    assert result.exit_code == 2
    assert "no log matches" in result.output
    assert "--plugin" in result.output


def test_init_target_detection_failure_exit_2(tmp_path: Path) -> None:
    _log(tmp_path, "build/a.log", "nothing\n")
    result = _init("--target", "pnr", "build/*.log")
    assert result.exit_code == 2


def test_init_target_absolute_glob_exit_2(tmp_path: Path) -> None:
    result = _init("--target", "pnr", str(tmp_path / "*.log"), "--plugin", "fake")
    assert result.exit_code == 2


def test_init_target_duplicate_name_exit_2(tmp_path: Path) -> None:
    assert _init("--target", "pnr", "a/*.log", "--plugin", "fake").exit_code == 0
    result = _init("--target", "pnr", "b/*.log", "--plugin", "fake")
    assert result.exit_code == 2
    assert "pnr" in result.output


def test_init_target_preserves_existing_comments_and_targets(tmp_path: Path) -> None:
    (tmp_path / ".sawmill" / "rules").mkdir(parents=True)
    _mpath(tmp_path).write_text(
        '# my precious comment\n[manifest]\nname = "p"\n\n'
        '[[target]]\nname = "syn"\nplugin = "fake"\nlogs = ["syn/*.log"]\n'
    )
    result = _init("--target", "pnr", "pnr/*.log", "--plugin", "fake")
    assert result.exit_code == 0, result.output
    assert "# my precious comment" in _mpath(tmp_path).read_text()
    m = ManifestLoader().load(_mpath(tmp_path))
    assert [t.name for t in m.targets] == ["syn", "pnr"]


def test_init_target_does_not_overwrite_existing_rules_file(tmp_path: Path) -> None:
    rules = tmp_path / ".sawmill" / "rules" / "pnr.toml"
    rules.parent.mkdir(parents=True)
    rules.write_text("# mine\n")
    result = _init("--target", "pnr", "a/*.log", "--plugin", "fake")
    assert result.exit_code == 0, result.output
    assert rules.read_text() == "# mine\n"


def test_init_target_second_append(tmp_path: Path) -> None:
    assert _init("--target", "a", "a/*.log", "--plugin", "fake").exit_code == 0
    assert _init("--target", "b", "b/*.log", "--plugin", "fake").exit_code == 0
    m = ManifestLoader().load(_mpath(tmp_path))
    assert [t.name for t in m.targets] == ["a", "b"]
    assert "# [[target]]" in _mpath(tmp_path).read_text()


def test_init_in_help() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert "init" in result.output
