"""Tests to verify that conftest fixtures work correctly."""

import pytest
from pathlib import Path


def test_project_root_fixture(project_root):
    """project_root fixture returns correct path."""
    assert isinstance(project_root, Path)
    assert project_root.exists()
    assert (project_root / "pyproject.toml").exists()


def test_vivado_log_fixture(vivado_log):
    """vivado_log fixture returns path to example log."""
    assert isinstance(vivado_log, Path)
    assert vivado_log.exists()
    assert vivado_log.suffix == ".log"


def test_small_log_fixture(small_log):
    """small_log fixture creates temporary test log."""
    assert isinstance(small_log, Path)
    assert small_log.exists()
    content = small_log.read_text()
    assert "INFO:" in content
    assert "WARNING:" in content
    assert "CRITICAL WARNING:" in content
    assert "ERROR:" in content


def test_empty_log_fixture(empty_log):
    """empty_log fixture creates empty file."""
    assert isinstance(empty_log, Path)
    assert empty_log.exists()
    assert empty_log.read_text() == ""


@pytest.mark.slow
def test_large_log_fixture(large_log):
    """large_log fixture creates 100k line file."""
    assert isinstance(large_log, Path)
    assert large_log.exists()
    content = large_log.read_text()
    lines = content.split("\n")
    assert len(lines) == 100000


@pytest.mark.integration
def test_vivado_log_has_content(vivado_log):
    """vivado_log fixture file has meaningful content."""
    content = vivado_log.read_text()
    assert len(content) > 1000
