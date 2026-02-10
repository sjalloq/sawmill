"""Core generation logic for sawmill plugin scaffolding."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jinja2 import Environment, PackageLoader

SAWMILL_PLUGIN_API = "1"

# Template file → output path (relative to project root)
_FILE_MAP = {
    "pyproject.toml.j2": "pyproject.toml",
    "readme.md.j2": "README.md",
    "makefile.j2": "Makefile",
    "init.py.j2": "src/{module_name}/__init__.py",
    "plugin.py.j2": "src/{module_name}/plugin.py",
    "patterns.py.j2": "src/{module_name}/patterns.py",
    "conftest.py.j2": "tests/conftest.py",
    "test_detection.py.j2": "tests/test_detection.py",
    "test_parsing.py.j2": "tests/test_parsing.py",
    "test_severity.py.j2": "tests/test_severity.py",
    "test_plugin_contract.py.j2": "tests/test_plugin_contract.py",
    "sample_log.j2": "examples/sample.log",
}


def generate(
    names: dict[str, str],
    description: str,
    author: str,
    output_dir: Path,
) -> Path:
    """Generate a sawmill plugin project.

    Args:
        names: Dict from derive_names() with all identifier forms.
        description: One-line description for pyproject.toml.
        author: Author name for pyproject.toml.
        output_dir: Parent directory where the project folder is created.

    Returns:
        Path to the created project directory.
    """
    project_dir = output_dir / names["directory_name"]

    env = Environment(
        loader=PackageLoader("sawmill_plugin_generator", "templates"),
        keep_trailing_newline=True,
    )

    context = {
        **names,
        "description": description,
        "author": author,
        "plugin_api_version": SAWMILL_PLUGIN_API,
    }

    for template_name, output_path_template in _FILE_MAP.items():
        output_path = project_dir / output_path_template.format(**names)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template = env.get_template(template_name)
        content = template.render(context)
        output_path.write_text(content)

    return project_dir


def get_git_author() -> str | None:
    """Try to get the author name from git config.

    Returns:
        The git user.name, or None if unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
