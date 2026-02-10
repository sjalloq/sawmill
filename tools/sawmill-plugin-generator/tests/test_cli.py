"""Tests for the CLI entry point."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from sawmill_plugin_generator.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCli:
    """Tests for the sawmill-new-plugin CLI."""

    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--name" in result.output

    def test_missing_name_is_error(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "--name" in result.output

    def test_invalid_name_shows_error(self, runner, tmp_path):
        result = runner.invoke(main, ["--name", "BAD", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "lowercase" in result.output

    def test_successful_run_creates_directory(self, runner, tmp_path):
        result = runner.invoke(main, ["--name", "quartus", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "sawmill-plugin-quartus").is_dir()
        assert "Created sawmill-plugin-quartus" in result.output

    def test_default_description(self, runner, tmp_path):
        result = runner.invoke(main, ["--name", "mytool", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        content = (tmp_path / "sawmill-plugin-mytool" / "pyproject.toml").read_text()
        assert "Sawmill plugin for mytool" in content

    def test_custom_description_and_author(self, runner, tmp_path):
        result = runner.invoke(
            main,
            [
                "--name",
                "mytool",
                "--description",
                "My custom plugin",
                "--author",
                "Jane Doe",
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        content = (tmp_path / "sawmill-plugin-mytool" / "pyproject.toml").read_text()
        assert "My custom plugin" in content
        assert "Jane Doe" in content

    def test_next_steps_printed(self, runner, tmp_path):
        result = runner.invoke(main, ["--name", "quartus", "--output-dir", str(tmp_path)])
        assert "make install" in result.output
        assert "make test" in result.output
