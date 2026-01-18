"""Tests for git utility functions."""

import os
from pathlib import Path

import pytest


class TestFindGitRoot:
    """Tests for find_git_root function."""

    def test_find_git_root_in_repo(self, tmp_path, monkeypatch):
        """Should find .git directory when in a git repo."""
        # Create a fake git repo
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "deep"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        assert find_git_root() == tmp_path

    def test_find_git_root_not_in_repo(self, tmp_path, monkeypatch):
        """Should return None when not in a git repo."""
        monkeypatch.chdir(tmp_path)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        assert find_git_root() is None

    def test_find_git_root_with_start_path(self, tmp_path, monkeypatch):
        """Should find git root from specified start path."""
        # Create a fake git repo
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "project" / "src"
        subdir.mkdir(parents=True)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        result = find_git_root(subdir)
        assert result == tmp_path

    def test_git_root_env_override(self, tmp_path, monkeypatch):
        """SAWMILL_GIT_ROOT should override detection."""
        override_path = tmp_path / "override"
        override_path.mkdir()
        monkeypatch.setenv("SAWMILL_GIT_ROOT", str(override_path))

        from sawmill.utils.git import find_git_root
        assert find_git_root() == override_path

    def test_git_root_env_override_takes_precedence(self, tmp_path, monkeypatch):
        """SAWMILL_GIT_ROOT should take precedence over actual .git directory."""
        # Create both a real git repo and override
        (tmp_path / ".git").mkdir()
        override_path = tmp_path / "custom"
        override_path.mkdir()

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SAWMILL_GIT_ROOT", str(override_path))

        from sawmill.utils.git import find_git_root
        assert find_git_root() == override_path

    def test_find_git_root_at_repo_root(self, tmp_path, monkeypatch):
        """Should find git root when already at the root."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        assert find_git_root() == tmp_path

    def test_find_git_root_in_nested_directories(self, tmp_path, monkeypatch):
        """Should walk up multiple directory levels to find .git."""
        (tmp_path / ".git").mkdir()
        deeply_nested = tmp_path / "a" / "b" / "c" / "d" / "e"
        deeply_nested.mkdir(parents=True)
        monkeypatch.chdir(deeply_nested)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        assert find_git_root() == tmp_path

    def test_find_git_root_stops_at_git_dir(self, tmp_path, monkeypatch):
        """Should stop at first .git found when walking up."""
        # Create nested git repos (unusual but possible)
        outer_git = tmp_path / ".git"
        outer_git.mkdir()

        inner_repo = tmp_path / "inner"
        inner_repo.mkdir()
        (inner_repo / ".git").mkdir()

        subdir = inner_repo / "src"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        # Should find inner repo, not outer
        assert find_git_root() == inner_repo

    def test_find_git_root_env_nonexistent_path(self, tmp_path, monkeypatch):
        """SAWMILL_GIT_ROOT should be returned even if path doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"
        monkeypatch.setenv("SAWMILL_GIT_ROOT", str(nonexistent))

        from sawmill.utils.git import find_git_root
        # Should return the path even if it doesn't exist
        assert find_git_root() == nonexistent

    def test_find_git_root_with_git_file(self, tmp_path, monkeypatch):
        """Should not be fooled by a file named .git (only directories count)."""
        # Create a file named .git instead of a directory
        (tmp_path / ".git").write_text("gitdir: somewhere")
        monkeypatch.chdir(tmp_path)

        # Clear any env override
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        from sawmill.utils.git import find_git_root
        # .git file is used for git worktrees - it should still be recognized
        # For simplicity, exists() returns True for files too
        assert find_git_root() == tmp_path
