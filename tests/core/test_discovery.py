"""Tests for manifest discovery and target resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sawmill.core.discovery import (
    DiscoveryError,
    TargetRef,
    discover_manifests,
    load_single_manifest,
    resolve_roots,
    resolve_targets,
)
from sawmill.core.manifest import ManifestError


def _write(directory: Path, name: str, targets: list[str] | None = None) -> Path:
    """Write a minimal manifest at ``directory/.sawmill/manifest.toml``."""
    sawmill_dir = directory / ".sawmill"
    sawmill_dir.mkdir(parents=True, exist_ok=True)
    lines = [f'[manifest]\nname = "{name}"\n']
    for t in targets if targets is not None else ["t"]:
        lines.append(f'[[target]]\nname = "{t}"\nplugin = "p"\nlogs = ["*.log"]\n')
    path = sawmill_dir / "manifest.toml"
    path.write_text("\n".join(lines))
    return path


def test_discover_single_manifest_in_root(tmp_path: Path) -> None:
    path = _write(tmp_path, "m")
    result = discover_manifests([tmp_path])
    assert [m.name for m in result] == ["m"]
    assert result[0].path == path.resolve()


def test_discover_nested_manifests_sorted_by_path(tmp_path: Path) -> None:
    _write(tmp_path / "b", "mb")
    _write(tmp_path / "a" / "sub", "ma")
    assert [m.name for m in discover_manifests([tmp_path])] == ["ma", "mb"]


def test_discover_skips_hidden_dirs_and_git(tmp_path: Path) -> None:
    _write(tmp_path / ".hidden", "hidden")
    _write(tmp_path / ".git", "git")
    _write(tmp_path, "top")
    assert [m.name for m in discover_manifests([tmp_path])] == ["top"]


def test_discover_does_not_follow_symlinked_dirs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    other = tmp_path / "other"
    _write(other, "other")
    try:
        os.symlink(other, root / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    assert discover_manifests([root]) == []


def test_discover_duplicate_names_raises(tmp_path: Path) -> None:
    p1 = _write(tmp_path / "a", "x")
    p2 = _write(tmp_path / "b", "x")
    with pytest.raises(DiscoveryError) as exc:
        discover_manifests([tmp_path])
    assert str(p1.resolve()) in str(exc.value)
    assert str(p2.resolve()) in str(exc.value)


def test_discover_overlapping_roots_dedupes(tmp_path: Path) -> None:
    _write(tmp_path / "a", "m")
    assert len(discover_manifests([tmp_path, tmp_path / "a"])) == 1


def test_discover_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError):
        discover_manifests([tmp_path / "nope"])


def test_discover_root_is_file_raises(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("")
    with pytest.raises(DiscoveryError):
        discover_manifests([f])


def test_discover_manifest_error_propagates(tmp_path: Path) -> None:
    (tmp_path / ".sawmill").mkdir()
    (tmp_path / ".sawmill" / "manifest.toml").write_text("not = [valid")
    with pytest.raises(ManifestError):
        discover_manifests([tmp_path])


def test_load_single_manifest_ok(tmp_path: Path) -> None:
    path = _write(tmp_path, "m")
    result = load_single_manifest(path)
    assert len(result) == 1
    assert result[0].name == "m"


def test_load_single_manifest_wrong_name_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "m")
    other = path.with_name("other.toml")
    other.write_text(path.read_text())
    with pytest.raises(DiscoveryError):
        load_single_manifest(other)


def test_load_single_manifest_not_in_sawmill_dir_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "m")
    moved = tmp_path / "manifest.toml"
    moved.write_text(path.read_text())
    with pytest.raises(DiscoveryError):
        load_single_manifest(moved)


def test_load_single_manifest_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError):
        load_single_manifest(tmp_path / ".sawmill" / "manifest.toml")


def test_resolve_roots_precedence(tmp_path: Path) -> None:
    cwd = tmp_path
    assert resolve_roots(["a", Path("b")], ["c"], cwd) == [Path("a"), Path("b")]
    assert resolve_roots([], ["c", "/d"], cwd) == [Path("c"), Path("/d")]
    assert resolve_roots([], [], cwd) == [cwd]


def _manifests(tmp_path: Path, spec: dict[str, list[str]]) -> list:
    for name, targets in spec.items():
        _write(tmp_path / name, name, targets)
    return discover_manifests([tmp_path])


def _names(refs: list[TargetRef]) -> list[str]:
    return [r.qualified_name for r in refs]


def test_resolve_targets_default_single_manifest_all_targets(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m": ["a", "b"]})
    assert _names(resolve_targets(ms, [])) == ["m:a", "m:b"]


def test_resolve_targets_default_no_manifest_raises() -> None:
    with pytest.raises(DiscoveryError, match="no manifest found"):
        resolve_targets([], [])


def test_resolve_targets_default_multiple_manifests_raises(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m1": ["a"], "m2": ["b"]})
    with pytest.raises(DiscoveryError) as exc:
        resolve_targets(ms, [])
    msg = str(exc.value)
    assert "m1" in msg and "m2" in msg and "--all" in msg


def test_resolve_targets_all_flag_spans_manifests(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m1": ["a", "b"], "m2": ["c"]})
    assert _names(resolve_targets(ms, [], all_targets=True)) == ["m1:a", "m1:b", "m2:c"]


def test_resolve_targets_all_with_names_raises(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m": ["a"]})
    with pytest.raises(DiscoveryError):
        resolve_targets(ms, ["a"], all_targets=True)


def test_resolve_targets_qualified_name(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m1": ["t"], "m2": ["t"]})
    refs = resolve_targets(ms, ["m2:t"])
    assert _names(refs) == ["m2:t"]
    assert refs[0].manifest.name == "m2"


def test_resolve_targets_bare_name_unique_across_manifests(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m1": ["a"], "m2": ["b"]})
    assert _names(resolve_targets(ms, ["b"])) == ["m2:b"]


def test_resolve_targets_bare_name_ambiguous_raises(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m1": ["t"], "m2": ["t"]})
    with pytest.raises(DiscoveryError) as exc:
        resolve_targets(ms, ["t"])
    assert "m1:t" in str(exc.value) and "m2:t" in str(exc.value)


def test_resolve_targets_bare_name_unknown_raises(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m": ["a"]})
    with pytest.raises(DiscoveryError):
        resolve_targets(ms, ["zz"])


def test_resolve_targets_unknown_manifest_raises(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m": ["a"]})
    with pytest.raises(DiscoveryError):
        resolve_targets(ms, ["nope:a"])


def test_resolve_targets_unknown_target_raises(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m": ["a"]})
    with pytest.raises(DiscoveryError):
        resolve_targets(ms, ["m:nope"])


def test_resolve_targets_order_and_dedupe(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m1": ["a", "b"], "m2": ["c"]})
    refs = resolve_targets(ms, ["c", "m1:b", "a", "m2:c", "b"])
    assert _names(refs) == ["m2:c", "m1:b", "m1:a"]


def test_target_ref_qualified_name(tmp_path: Path) -> None:
    ms = _manifests(tmp_path, {"m": ["t"]})
    ref = TargetRef(manifest=ms[0], target=ms[0].targets[0])
    assert ref.qualified_name == "m:t"


def _write_vars(directory: Path, name: str) -> None:
    sawmill_dir = directory / ".sawmill"
    sawmill_dir.mkdir(parents=True, exist_ok=True)
    (sawmill_dir / "manifest.toml").write_text(
        f'[manifest]\nname = "{name}"\n\n[vars]\nbuild = "top"\nmode = "fast"\n\n'
        '[[target]]\nname = "a"\nplugin = "p"\nlogs = ["*.log"]\n\n'
        '[[target]]\nname = "b"\nplugin = "p"\nlogs = ["*.log"]\n'
    )


def test_target_ref_vars_merges_overrides(tmp_path: Path) -> None:
    _write_vars(tmp_path, "m")
    m = discover_manifests([tmp_path])[0]
    assert TargetRef(m, m.targets[0]).vars == {"build": "top", "mode": "fast"}
    ref = TargetRef(m, m.targets[0], overrides={"build": "sub", "x": "1"})
    assert ref.vars == {"build": "sub", "mode": "fast", "x": "1"}


def test_resolve_targets_overrides_on_every_ref(tmp_path: Path) -> None:
    _write_vars(tmp_path, "m")
    ms = discover_manifests([tmp_path])
    for refs in (
        resolve_targets(ms, [], overrides={"build": "sub"}),
        resolve_targets(ms, [], all_targets=True, overrides={"build": "sub"}),
        resolve_targets(ms, ["m:a", "b"], overrides={"build": "sub"}),
    ):
        assert len(refs) == 2
        assert all(r.overrides == {"build": "sub"} for r in refs)
        assert all(r.vars["build"] == "sub" for r in refs)


def test_resolve_targets_overrides_default_empty(tmp_path: Path) -> None:
    _write_vars(tmp_path, "m")
    refs = resolve_targets(discover_manifests([tmp_path]), [])
    assert all(r.overrides == {} for r in refs)
