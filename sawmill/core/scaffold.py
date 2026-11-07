"""Scaffold a manifest and append targets to it.

Pure functions shared by ``sawmill init`` and the TUI; no CLI concerns.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit.items import AoT

_TEMPLATE = """\
[manifest]
name = "{name}"
# rules = ["vivado.toml"]                  # plugin-wide rule files in .sawmill/rules/
# report = "build/sawmill-report.json"     # default output path for `sawmill report`
# fail_on = "warning"                      # default failure severity for all targets

# [[target]]
# name = "pnr"                             # unique target name
# plugin = "vivado"                        # plugin that parses these logs
# logs = ["build/pnr/job_*/vivado.log"]    # globs relative to the project root
# rules = ["vivado-pnr.toml"]              # target rule files in .sawmill/rules/
# fail_on = "critical_warning"             # overrides [manifest] fail_on
# unused_rules = "warn"                    # warn (default) | ignore
#
# [target.plugin_options]                  # passed through to the plugin
# mode = "implementation"
"""


def write_manifest_template(manifest_path: Path, name: str) -> None:
    """Create the template manifest and its ``rules/`` directory.

    Args:
        manifest_path: Path of the manifest to create.
        name: Value for ``[manifest] name``.

    Raises:
        FileExistsError: If the manifest already exists.
    """
    if manifest_path.exists():
        raise FileExistsError(f"{manifest_path} already exists")
    (manifest_path.parent / "rules").mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(_TEMPLATE.format(name=name), encoding="utf-8")


def add_target(
    manifest_path: Path,
    name: str,
    plugin: str,
    glob: str,
    rules_file: str | None = None,
) -> Path:
    """Append a ``[[target]]`` to a manifest and scaffold its rules file.

    Comments and formatting in the manifest are preserved. An existing
    rules file is never overwritten.

    Args:
        manifest_path: Existing manifest to append to.
        name: Unique target name.
        plugin: Plugin that parses the target's logs.
        glob: Log glob relative to the project root.
        rules_file: Rules file name in ``rules/``; defaults to ``<name>.toml``.

    Returns:
        Path of the target's rules file.

    Raises:
        ValueError: If a target called ``name`` already exists.
        tomlkit.exceptions.TOMLKitError: If the manifest is not valid TOML.
    """
    rules_name = rules_file if rules_file is not None else f"{name}.toml"
    doc = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
    existing = doc.get("target", [])
    if any(t.get("name") == name for t in existing):
        raise ValueError(f"target '{name}' already exists in {manifest_path}")

    entry = tomlkit.table()
    entry.add("name", name)
    entry.add("plugin", plugin)
    entry.add("logs", [glob])
    entry.add("rules", [rules_name])
    targets = doc.get("target")
    if isinstance(targets, AoT):
        targets.append(entry)
    else:
        aot = tomlkit.aot()
        aot.append(entry)
        doc.append("target", aot)
    manifest_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    rules_path = manifest_path.parent / "rules" / rules_name
    if not rules_path.exists():
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(f'[rules]\nplugin = "{plugin}"\n', encoding="utf-8")
    return rules_path


__all__ = ["add_target", "write_manifest_template"]
