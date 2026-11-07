"""Manifest discovery and target addressing.

Manifests live at ``<project>/.sawmill/manifest.toml`` and are found by
walking down from one or more roots. Targets are addressed as
``manifest:target`` or as a bare ``target`` when unique.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pathspec import GitIgnoreSpec

from sawmill.core.manifest import ManifestLoader
from sawmill.models.manifest import Manifest, Target

_SAWMILL_DIR = ".sawmill"
_MANIFEST_FILE = "manifest.toml"
_GITIGNORE = ".gitignore"


class DiscoveryError(Exception):
    """Raised when manifests or targets cannot be discovered or resolved."""


@dataclass(frozen=True)
class TargetRef:
    """A target together with the manifest that defines it."""

    manifest: Manifest
    target: Target
    overrides: dict[str, str] = field(default_factory=dict)

    @property
    def vars(self) -> dict[str, str]:
        """Return the manifest ``[vars]`` overlaid by command-line overrides."""
        return {**self.manifest.vars, **self.overrides}

    @property
    def qualified_name(self) -> str:
        """Return ``manifest:target``."""
        return f"{self.manifest.name}:{self.target.name}"


def resolve_roots(
    root_args: Sequence[Path | str],
    config_roots: Sequence[str],
    cwd: Path | None = None,
) -> list[Path]:
    """Pick discovery roots by precedence.

    ``root_args`` (``--root``) win if non-empty, else ``config_roots`` (the
    ``[general] roots`` config entry), else ``cwd`` (default: the current
    directory). Relative entries are left relative and so resolve against
    the current working directory.
    """
    if root_args:
        return [Path(r) for r in root_args]
    if config_roots:
        return [Path(r) for r in config_roots]
    return [cwd if cwd is not None else Path.cwd()]


def _read_gitignore(directory: Path) -> GitIgnoreSpec | None:
    """Compile ``directory/.gitignore`` if present, else return None."""
    try:
        text = (directory / _GITIGNORE).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return GitIgnoreSpec.from_lines(text.splitlines())


def _is_ignored(path: Path, specs: Sequence[tuple[Path, GitIgnoreSpec]]) -> bool:
    """Return True if directory ``path`` is ignored by ``specs`` (innermost last)."""
    for base, spec in reversed(specs):
        rel = path.relative_to(base).as_posix() + "/"
        include = spec.check_file(rel).include
        if include is not None:
            return bool(include)
    return False


def _walk(root: Path) -> list[Path]:
    """Return every ``.sawmill/manifest.toml`` under ``root``.

    Hidden directories and ``.git`` are skipped and symlinked directories
    are not followed. Directories ignored by a ``.gitignore`` in ``root`` or
    below are not entered; the innermost ``.gitignore`` with a matching
    pattern decides. ``.gitignore`` files above ``root``, ``.git/info/exclude``
    and the user's global excludes are not consulted.
    """
    found: list[Path] = []
    stack: list[tuple[Path, list[tuple[Path, GitIgnoreSpec]]]] = [(root, [])]
    while stack:
        directory, parent_specs = stack.pop()
        candidate = directory / _SAWMILL_DIR / _MANIFEST_FILE
        if candidate.is_file():
            found.append(candidate)
        spec = _read_gitignore(directory)
        specs = [*parent_specs, (directory, spec)] if spec is not None else parent_specs
        try:
            with os.scandir(directory) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            child = Path(entry.path)
            if not _is_ignored(child, specs):
                stack.append((child, specs))
    return found


def discover_manifests(roots: Sequence[Path]) -> list[Manifest]:
    """Find and load every manifest under ``roots``.

    Symlinked directories are not followed; hidden directories and ``.git``
    are skipped. A manifest reached via overlapping roots is loaded once.
    Results are sorted by manifest path.

    Raises:
        DiscoveryError: If a root is missing or not a directory, or two
            manifests share a name.
        ManifestError: If a manifest is invalid.
    """
    paths: set[Path] = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            raise DiscoveryError(f"root does not exist: {root}")
        if not root.is_dir():
            raise DiscoveryError(f"root is not a directory: {root}")
        paths.update(p.resolve() for p in _walk(root))

    loader = ManifestLoader()
    manifests: list[Manifest] = []
    by_name: dict[str, Manifest] = {}
    for path in sorted(paths):
        manifest = loader.load(path)
        if manifest.name in by_name:
            raise DiscoveryError(
                f"duplicate manifest name {manifest.name!r}: "
                f"{by_name[manifest.name].path} and {manifest.path}"
            )
        by_name[manifest.name] = manifest
        manifests.append(manifest)
    return manifests


def load_single_manifest(path: Path) -> list[Manifest]:
    """Load exactly one manifest given by ``--manifest``.

    Raises:
        DiscoveryError: If ``path`` is not an existing ``manifest.toml``
            inside a ``.sawmill`` directory.
        ManifestError: If the manifest is invalid.
    """
    path = Path(path)
    if not path.is_file():
        raise DiscoveryError(f"manifest not found: {path}")
    resolved = path.resolve()
    if resolved.name != _MANIFEST_FILE or resolved.parent.name != _SAWMILL_DIR:
        raise DiscoveryError(f"manifest must be {_SAWMILL_DIR}/{_MANIFEST_FILE}: {path}")
    return [ManifestLoader().load(resolved)]


def resolve_targets(
    manifests: Sequence[Manifest],
    names: Sequence[str],
    all_targets: bool = False,
    overrides: Mapping[str, str] | None = None,
) -> list[TargetRef]:
    """Resolve user-supplied target names to :class:`TargetRef` objects.

    With no names and ``all_targets`` False, returns every target of the
    single manifest. ``all_targets`` returns every target of every manifest.
    Otherwise each name is ``manifest:target`` or a unique bare target name.
    Order follows ``names``; duplicates are collapsed.

    Every returned ref carries a copy of ``overrides`` (command-line
    variable values).

    Raises:
        DiscoveryError: On missing, unknown or ambiguous names.
    """
    ov = dict(overrides or {})
    if all_targets:
        if names:
            raise DiscoveryError("target names cannot be combined with --all")
        return [TargetRef(m, t, dict(ov)) for m in manifests for t in m.targets]

    if not names:
        if not manifests:
            raise DiscoveryError("no manifest found")
        if len(manifests) > 1:
            listed = ", ".join(m.name for m in manifests)
            raise DiscoveryError(
                f"multiple manifests found ({listed}); use --all or name targets as manifest:target"
            )
        return [TargetRef(manifests[0], t, dict(ov)) for t in manifests[0].targets]

    by_name = {m.name: m for m in manifests}
    result: list[TargetRef] = []
    seen: set[str] = set()
    for name in names:
        ref = _resolve_one(manifests, by_name, name)
        ref = TargetRef(ref.manifest, ref.target, dict(ov))
        if ref.qualified_name not in seen:
            seen.add(ref.qualified_name)
            result.append(ref)
    return result


def _resolve_one(
    manifests: Sequence[Manifest], by_name: dict[str, Manifest], name: str
) -> TargetRef:
    """Resolve a single target name."""
    if ":" in name:
        manifest_name, target_name = name.split(":", 1)
        manifest = by_name.get(manifest_name)
        if manifest is None:
            raise DiscoveryError(f"unknown manifest {manifest_name!r} in {name!r}")
        target = manifest.get_target(target_name)
        if target is None:
            raise DiscoveryError(f"manifest {manifest_name!r} has no target {target_name!r}")
        return TargetRef(manifest, target)

    matches = [TargetRef(m, t) for m in manifests if (t := m.get_target(name)) is not None]
    if not matches:
        raise DiscoveryError(f"unknown target {name!r}")
    if len(matches) > 1:
        listed = ", ".join(r.qualified_name for r in matches)
        raise DiscoveryError(f"target {name!r} is ambiguous: {listed}")
    return matches[0]
