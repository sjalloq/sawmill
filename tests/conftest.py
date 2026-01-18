"""Shared pytest fixtures for Sawmill tests."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def vivado_log(project_root):
    """Full Vivado log file for integration tests."""
    return project_root / "examples/vivado/vivado.log"


@pytest.fixture
def small_log(tmp_path):
    """Minimal multi-format log for unit tests."""
    content = """\
INFO: [Synth 8-6157] synthesizing module 'top' [/path/file.v:10]
WARNING: [Vivado 12-3523] Component name change
  Additional detail line
  Another detail line
CRITICAL WARNING: [Constraints 18-4427] Override warning
ERROR: [Route 35-9] Routing failed
Plain text line with no format
"""
    f = tmp_path / "test.log"
    f.write_text(content)
    return f


@pytest.fixture
def empty_log(tmp_path):
    """Empty log file."""
    f = tmp_path / "empty.log"
    f.write_text("")
    return f


@pytest.fixture
def large_log(tmp_path):
    """100k line log file for performance tests."""
    f = tmp_path / "large.log"
    lines = [f"INFO: [Test {i % 100}-{i}] Message number {i}" for i in range(100000)]
    f.write_text("\n".join(lines))
    return f


# Pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
