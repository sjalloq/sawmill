"""Tests for the plugin generator core logic."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from sawmill_plugin_generator.generator import generate, get_git_author
from sawmill_plugin_generator.names import derive_names


@pytest.fixture
def quartus_project(tmp_path: Path) -> Path:
    """Generate a 'quartus' plugin and return the project directory."""
    names = derive_names("quartus")
    return generate(
        names=names,
        description="Sawmill plugin for quartus",
        author="Test Author",
        output_dir=tmp_path,
    )


@pytest.fixture
def multi_word_project(tmp_path: Path) -> Path:
    """Generate a 'quartus-prime' plugin and return the project directory."""
    names = derive_names("quartus-prime")
    return generate(
        names=names,
        description="Sawmill plugin for quartus-prime",
        author="Test Author",
        output_dir=tmp_path,
    )


class TestGenerateFiles:
    """Tests that all expected files are created."""

    EXPECTED_FILES: ClassVar[list[str]] = [
        "pyproject.toml",
        "README.md",
        "Makefile",
        "src/sawmill_plugin_quartus/__init__.py",
        "src/sawmill_plugin_quartus/plugin.py",
        "src/sawmill_plugin_quartus/patterns.py",
        "tests/conftest.py",
        "tests/test_detection.py",
        "tests/test_parsing.py",
        "tests/test_severity.py",
        "tests/test_plugin_contract.py",
        "examples/sample.log",
    ]

    def test_all_files_exist(self, quartus_project):
        for rel_path in self.EXPECTED_FILES:
            full_path = quartus_project / rel_path
            assert full_path.exists(), f"Missing: {rel_path}"

    def test_returns_project_directory(self, quartus_project):
        assert quartus_project.name == "sawmill-plugin-quartus"
        assert quartus_project.is_dir()


class TestPyprojectToml:
    """Tests for the generated pyproject.toml."""

    def test_is_valid_toml(self, quartus_project):
        content = (quartus_project / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        assert "project" in data

    def test_has_correct_name(self, quartus_project):
        content = (quartus_project / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        assert data["project"]["name"] == "sawmill-plugin-quartus"

    def test_has_correct_entry_point(self, quartus_project):
        content = (quartus_project / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        entry_points = data["project"]["entry-points"]["sawmill.plugins"]
        assert entry_points["quartus"] == "sawmill_plugin_quartus:QuartusPlugin"

    def test_has_plugin_api_version(self, quartus_project):
        content = (quartus_project / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        assert data["tool"]["sawmill"]["plugin_api"] == "1"

    def test_custom_description(self, tmp_path):
        names = derive_names("mytool")
        project = generate(
            names=names,
            description="My custom description",
            author="Custom Author",
            output_dir=tmp_path,
        )
        content = (project / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        assert data["project"]["description"] == "My custom description"
        assert data["project"]["authors"][0]["name"] == "Custom Author"


class TestPluginPy:
    """Tests for the generated plugin.py."""

    def test_contains_class_name(self, quartus_project):
        content = (quartus_project / "src/sawmill_plugin_quartus/plugin.py").read_text()
        assert "class QuartusPlugin" in content

    def test_contains_hookimpl(self, quartus_project):
        content = (quartus_project / "src/sawmill_plugin_quartus/plugin.py").read_text()
        assert "@hookimpl" in content

    def test_contains_all_hooks(self, quartus_project):
        content = (quartus_project / "src/sawmill_plugin_quartus/plugin.py").read_text()
        for hook in [
            "can_handle",
            "load_and_parse",
            "get_severity_levels",
            "get_filters",
            "extract_file_reference",
            "get_grouping_fields",
        ]:
            assert f"def {hook}" in content, f"Missing hook: {hook}"


class TestInitPy:
    """Tests for the generated __init__.py."""

    def test_imports_plugin_class(self, quartus_project):
        content = (quartus_project / "src/sawmill_plugin_quartus/__init__.py").read_text()
        assert "from sawmill_plugin_quartus.plugin import QuartusPlugin" in content
        assert "QuartusPlugin" in content


class TestMultiWordName:
    """Tests for multi-word plugin names."""

    def test_module_directory_uses_underscores(self, multi_word_project):
        assert (multi_word_project / "src/sawmill_plugin_quartus_prime/__init__.py").exists()

    def test_class_name_is_camel_case(self, multi_word_project):
        content = (multi_word_project / "src/sawmill_plugin_quartus_prime/plugin.py").read_text()
        assert "class QuartusPrimePlugin" in content

    def test_entry_point_correct(self, multi_word_project):
        content = (multi_word_project / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        entry_points = data["project"]["entry-points"]["sawmill.plugins"]
        assert "quartus-prime" in entry_points


class TestGetGitAuthor:
    """Tests for git author detection."""

    def test_returns_string_or_none(self):
        result = get_git_author()
        assert result is None or isinstance(result, str)
