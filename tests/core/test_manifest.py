"""Tests for manifest loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from sawmill.core.manifest import ManifestError, ManifestLoader

SPEC = """[manifest]
name = "soc"
rules = ["vivado.toml", "slang.toml"]
report = "build/sawmill-report.json"
fail_on = "warning"

[[target]]
name = "synth"
plugin = "slang"
logs = ["build/lint/*.log"]

[[target]]
name = "pnr"
plugin = "vivado"
logs = ["build/pnr/job_*/vivado.log"]
rules = ["vivado-pnr.toml"]
fail_on = "critical_warning"
unused_rules = "warn"

[target.plugin_options]
mode = "implementation"
"""

HEAD = '[manifest]\nname = "m"\n\n'


def _err(content: str, path: Path | None = None) -> ManifestError:
    with pytest.raises(ManifestError) as exc:
        ManifestLoader().load_from_string(content, path)
    return exc.value


def _target_err(body: str) -> ManifestError:
    content = HEAD + '[[target]]\nname = "a"\nplugin = "p"\nlogs = ["a.log"]\n\n[[target]]\n' + body
    e = _err(content)
    assert e.target_index == 1
    assert e.line == 9
    return e


def test_load_full_example() -> None:
    m = ManifestLoader().load_from_string(SPEC)
    assert m.name == "soc"
    assert m.rules == ["vivado.toml", "slang.toml"]
    assert m.report == "build/sawmill-report.json"
    assert m.fail_on == "warning"
    assert len(m.targets) == 2
    synth, pnr = m.targets
    assert synth.name == "synth" and synth.index == 0 and synth.line == 7
    assert pnr.name == "pnr"
    assert pnr.plugin == "vivado"
    assert pnr.logs == ["build/pnr/job_*/vivado.log"]
    assert pnr.rules == ["vivado-pnr.toml"]
    assert pnr.fail_on == "critical_warning"
    assert pnr.unused_rules == "warn"
    assert pnr.plugin_options == {"mode": "implementation"}
    assert pnr.index == 1
    assert pnr.line == 12


def test_load_from_file(tmp_path: Path) -> None:
    path = tmp_path / ".sawmill" / "manifest.toml"
    path.parent.mkdir()
    path.write_text(SPEC)
    m = ManifestLoader().load(path)
    assert m.path == path.resolve()
    assert m.root == tmp_path.resolve()


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ManifestLoader().load(tmp_path / "nope.toml")


def test_zero_targets_valid() -> None:
    m = ManifestLoader().load_from_string(HEAD)
    assert m.targets == []


def test_missing_manifest_table() -> None:
    e = _err('[[target]]\nname = "a"\nplugin = "p"\nlogs = ["a"]\n')
    assert "[manifest]" in str(e)


def test_missing_name() -> None:
    e = _err("\n[manifest]\nrules = []\n")
    assert "name" in e.message
    assert e.line == 2


def test_empty_name() -> None:
    e = _err('[manifest]\nname = ""\n')
    assert "name" in e.message
    assert e.line == 1


def test_target_missing_name() -> None:
    assert "name" in _target_err('plugin = "p"\nlogs = ["a"]\n').message


def test_target_missing_plugin() -> None:
    assert "plugin" in _target_err('name = "b"\nlogs = ["a"]\n').message


def test_target_missing_logs() -> None:
    assert "logs" in _target_err('name = "b"\nplugin = "p"\n').message


def test_target_empty_logs() -> None:
    assert "logs" in _target_err('name = "b"\nplugin = "p"\nlogs = []\n').message


@pytest.mark.parametrize("value", ['"a.log"', "[1]", '[""]'])
def test_target_logs_wrong_type(value: str) -> None:
    assert "logs" in _target_err(f'name = "b"\nplugin = "p"\nlogs = {value}\n').message


def test_duplicate_target_names() -> None:
    e = _target_err('name = "a"\nplugin = "p"\nlogs = ["b"]\n')
    assert "'a'" in e.message or '"a"' in e.message


def test_unused_rules_invalid() -> None:
    e = _target_err('name = "b"\nplugin = "p"\nlogs = ["b"]\nunused_rules = "error"\n')
    assert "unused_rules" in e.message


def test_unknown_key_in_manifest() -> None:
    e = _err('[manifest]\nname = "m"\nbogus = 1\n')
    assert "bogus" in e.message
    assert e.line == 1


def test_unknown_key_in_target() -> None:
    e = _target_err('name = "b"\nplugin = "p"\nlogs = ["b"]\nbogus = 1\n')
    assert "bogus" in e.message


def test_plugin_options_must_be_table() -> None:
    e = _target_err('name = "b"\nplugin = "p"\nlogs = ["b"]\nplugin_options = "x"\n')
    assert "plugin_options" in e.message


def test_absolute_log_glob_rejected() -> None:
    e = _target_err('name = "b"\nplugin = "p"\nlogs = ["/abs/*.log"]\n')
    assert "logs" in e.message


def test_rules_must_be_list_of_strings() -> None:
    e = _err('[manifest]\nname = "m"\nrules = [1]\n')
    assert "rules" in e.message
    e = _target_err('name = "b"\nplugin = "p"\nlogs = ["b"]\nrules = "x.toml"\n')
    assert "rules" in e.message


def test_toml_syntax_error_reports_line() -> None:
    e = _err('[manifest]\nname = "m"\nbroken = \n')
    assert e.line == 3


def test_error_str_format() -> None:
    path = Path("/p/.sawmill/manifest.toml")
    first = '[[target]]\nname = "a"\nplugin = "p"\nlogs = ["a.log"]\n\n'
    content = HEAD + first + '[[target]]\nname = "b"\n'
    e = _err(content, path)
    assert str(e).startswith(f"Error in {path} target 2 at line 9: ")


def test_exports() -> None:
    from sawmill.core import ManifestError as CE
    from sawmill.core import ManifestLoader as CL
    from sawmill.models import Manifest, Target

    assert CE is ManifestError and CL is ManifestLoader
    assert Manifest.__name__ == "Manifest" and Target.__name__ == "Target"
