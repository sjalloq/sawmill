"""Tests for directory resolution utilities."""

import pytest

from sawmill.core.config import ConfigError
from sawmill.utils.dirs import ensure_sawmill_dir, resolve_sawmill_dir


class TestResolveSawmillDir:
    """Tests for resolve_sawmill_dir."""

    def test_neither_dir_returns_none(self, tmp_path):
        """Returns None when neither .sawmill/ nor sawmill/ exists."""
        result = resolve_sawmill_dir(tmp_path)
        assert result is None

    def test_dot_sawmill_only(self, tmp_path):
        """Returns .sawmill/ path when only .sawmill/ exists."""
        (tmp_path / ".sawmill").mkdir()
        result = resolve_sawmill_dir(tmp_path)
        assert result == tmp_path / ".sawmill"

    def test_sawmill_only(self, tmp_path):
        """Returns sawmill/ path when only sawmill/ exists."""
        (tmp_path / "sawmill").mkdir()
        result = resolve_sawmill_dir(tmp_path)
        assert result == tmp_path / "sawmill"

    def test_both_dirs_raises_config_error(self, tmp_path):
        """Raises ConfigError when both .sawmill/ and sawmill/ exist."""
        (tmp_path / ".sawmill").mkdir()
        (tmp_path / "sawmill").mkdir()
        with pytest.raises(ConfigError, match="Ambiguous"):
            resolve_sawmill_dir(tmp_path)

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        """Uses CWD when start_path is None."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".sawmill").mkdir()
        result = resolve_sawmill_dir()
        assert result == tmp_path / ".sawmill"

    def test_ignores_files_named_sawmill(self, tmp_path):
        """Files (not dirs) named .sawmill or sawmill are ignored."""
        (tmp_path / ".sawmill").write_text("not a dir")
        (tmp_path / "sawmill").write_text("not a dir")
        result = resolve_sawmill_dir(tmp_path)
        assert result is None


class TestEnsureSawmillDir:
    """Tests for ensure_sawmill_dir."""

    def test_creates_dot_sawmill_when_none_exist(self, tmp_path):
        """Creates .sawmill/ when neither directory exists."""
        result = ensure_sawmill_dir(tmp_path)
        assert result == tmp_path / ".sawmill"
        assert result.is_dir()

    def test_returns_existing_dot_sawmill(self, tmp_path):
        """Returns existing .sawmill/ without creating anything."""
        (tmp_path / ".sawmill").mkdir()
        result = ensure_sawmill_dir(tmp_path)
        assert result == tmp_path / ".sawmill"

    def test_returns_existing_sawmill(self, tmp_path):
        """Returns existing sawmill/ without creating anything."""
        (tmp_path / "sawmill").mkdir()
        result = ensure_sawmill_dir(tmp_path)
        assert result == tmp_path / "sawmill"

    def test_both_dirs_raises_config_error(self, tmp_path):
        """Raises ConfigError when both directories exist."""
        (tmp_path / ".sawmill").mkdir()
        (tmp_path / "sawmill").mkdir()
        with pytest.raises(ConfigError, match="Ambiguous"):
            ensure_sawmill_dir(tmp_path)

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        """Uses CWD when start_path is None."""
        monkeypatch.chdir(tmp_path)
        result = ensure_sawmill_dir()
        assert result == tmp_path / ".sawmill"
        assert result.is_dir()
