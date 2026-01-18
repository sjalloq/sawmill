"""Tests for configuration discovery and merging."""

from pathlib import Path

import pytest

from sawmill.core.config import ConfigLoader, Config, ConfigError


class TestDiscoverConfigs:
    """Tests for ConfigLoader.discover_configs method."""

    def test_discover_no_configs(self, tmp_path, monkeypatch):
        """Should return empty list when no configs exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs(tmp_path)

        assert configs == []

    def test_discover_local_config(self, tmp_path, monkeypatch):
        """Should find local sawmill.toml."""
        (tmp_path / "sawmill.toml").write_text('[output]\nformat = "json"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs(tmp_path)

        assert len(configs) == 1
        assert configs[0] == tmp_path / "sawmill.toml"

    def test_discover_user_config(self, tmp_path, monkeypatch):
        """Should find user config in ~/.config/sawmill/."""
        user_config_dir = tmp_path / ".config" / "sawmill"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.toml").write_text('[output]\ncolor = false\n')

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs(tmp_path)

        assert len(configs) == 1
        assert configs[0] == user_config_dir / "config.toml"

    def test_discover_git_root_config(self, tmp_path, monkeypatch):
        """Should find config at git root."""
        # Create git repo structure
        (tmp_path / ".git").mkdir()
        (tmp_path / "sawmill.toml").write_text('[output]\nformat = "text"\n')

        # Navigate to a subdirectory
        subdir = tmp_path / "src" / "deep"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs(subdir)

        assert len(configs) == 1
        assert configs[0] == tmp_path / "sawmill.toml"

    def test_discover_multiple_configs_precedence_order(self, tmp_path, monkeypatch):
        """Should return configs in precedence order: user < git < local."""
        # User config (lowest precedence)
        user_config_dir = tmp_path / ".config" / "sawmill"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.toml").write_text('[output]\nformat = "text"\n')

        # Git root config (middle precedence)
        git_root = tmp_path / "project"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        (git_root / "sawmill.toml").write_text('[output]\nformat = "json"\n')

        # Local config (highest file precedence)
        local_dir = git_root / "subdir"
        local_dir.mkdir()
        (local_dir / "sawmill.toml").write_text('[output]\nformat = "count"\n')

        monkeypatch.chdir(local_dir)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs(local_dir)

        assert len(configs) == 3
        # Precedence order: user (0) < git (1) < local (2)
        assert configs[0] == user_config_dir / "config.toml"  # user
        assert configs[1] == git_root / "sawmill.toml"  # git root
        assert configs[2] == local_dir / "sawmill.toml"  # local

    def test_discover_deduplicates_git_and_local(self, tmp_path, monkeypatch):
        """Should not duplicate when local dir is git root."""
        # Git root with config
        (tmp_path / ".git").mkdir()
        (tmp_path / "sawmill.toml").write_text('[output]\nformat = "text"\n')

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs(tmp_path)

        # Should only be one entry, not duplicated
        assert len(configs) == 1
        assert configs[0] == tmp_path / "sawmill.toml"

    def test_discover_uses_cwd_when_no_start_path(self, tmp_path, monkeypatch):
        """Should use current working directory when start_path is None."""
        (tmp_path / "sawmill.toml").write_text('[output]\nformat = "json"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        configs = loader.discover_configs()  # No argument = use cwd

        assert len(configs) == 1
        assert configs[0] == tmp_path / "sawmill.toml"


class TestLoadMerged:
    """Tests for ConfigLoader.load_merged method."""

    def test_load_merged_no_configs_returns_defaults(self, tmp_path, monkeypatch):
        """Should return default config when no config files exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        config = loader.load_merged(tmp_path)

        # Verify default values
        assert config.output.format == "text"
        assert config.output.color is True
        assert config.general.default_plugin is None
        assert config.suppress.patterns == []
        assert config.suppress.message_ids == []

    def test_load_merged_single_config(self, tmp_path, monkeypatch):
        """Should load values from a single config file."""
        (tmp_path / "sawmill.toml").write_text(
            '[output]\nformat = "json"\ncolor = false\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        config = loader.load_merged(tmp_path)

        assert config.output.format == "json"
        assert config.output.color is False

    def test_precedence_order(self, tmp_path, monkeypatch):
        """Local config should override user config (from TASKS.md)."""
        # Local config
        (tmp_path / "sawmill.toml").write_text('[output]\nformat = "json"\n')

        # User config
        user_config = tmp_path / ".config" / "sawmill"
        user_config.mkdir(parents=True)
        (user_config / "config.toml").write_text(
            '[output]\nformat = "text"\ncolor = false\n'
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        config = loader.load_merged(tmp_path)

        assert config.output.format == "json"  # local overrides user
        assert config.output.color is False  # from user config (not in local)

    def test_values_fall_through(self, tmp_path, monkeypatch):
        """Unspecified values should fall through from lower precedence."""
        # User config sets color
        user_config = tmp_path / ".config" / "sawmill"
        user_config.mkdir(parents=True)
        (user_config / "config.toml").write_text(
            '[output]\ncolor = false\n[general]\ndefault_plugin = "vivado"\n'
        )

        # Local config only sets format (color not specified)
        (tmp_path / "sawmill.toml").write_text('[output]\nformat = "json"\n')

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        config = loader.load_merged(tmp_path)

        assert config.output.format == "json"  # from local
        assert config.output.color is False  # from user (falls through)
        assert config.general.default_plugin == "vivado"  # from user

    def test_three_level_merge(self, tmp_path, monkeypatch):
        """Should properly merge user < git root < local."""
        # User config (lowest)
        user_config = tmp_path / ".config" / "sawmill"
        user_config.mkdir(parents=True)
        (user_config / "config.toml").write_text(
            '[output]\nformat = "text"\ncolor = false\n'
            '[general]\ndefault_plugin = "generic"\n'
        )

        # Git root config (middle)
        git_root = tmp_path / "project"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        (git_root / "sawmill.toml").write_text(
            '[output]\nformat = "json"\n'
            '[general]\ndefault_plugin = "vivado"\n'
        )

        # Local config (highest)
        local_dir = git_root / "subdir"
        local_dir.mkdir()
        (local_dir / "sawmill.toml").write_text('[output]\nformat = "count"\n')

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        config = loader.load_merged(local_dir)

        assert config.output.format == "count"  # from local
        assert config.output.color is False  # from user (falls through)
        assert config.general.default_plugin == "vivado"  # from git root

    def test_suppress_patterns_merge(self, tmp_path, monkeypatch):
        """Suppress patterns should override (not merge lists)."""
        # User config with patterns
        user_config = tmp_path / ".config" / "sawmill"
        user_config.mkdir(parents=True)
        (user_config / "config.toml").write_text(
            '[suppress]\npatterns = ["noise", "debug"]\n'
        )

        # Local config with different patterns
        (tmp_path / "sawmill.toml").write_text(
            '[suppress]\npatterns = ["warning"]\n'
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        config = loader.load_merged(tmp_path)

        # Lists are replaced, not merged
        assert config.suppress.patterns == ["warning"]

    def test_invalid_toml_raises_config_error(self, tmp_path, monkeypatch):
        """Should raise ConfigError for invalid TOML."""
        (tmp_path / "sawmill.toml").write_text('invalid toml [[[')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load_merged(tmp_path)

    def test_invalid_toml_includes_path_in_error(self, tmp_path, monkeypatch):
        """ConfigError should include path to problematic file."""
        config_path = tmp_path / "sawmill.toml"
        config_path.write_text('invalid = [unclosed')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("SAWMILL_GIT_ROOT", raising=False)

        loader = ConfigLoader()
        with pytest.raises(ConfigError) as exc_info:
            loader.load_merged(tmp_path)

        assert str(config_path) in str(exc_info.value)


class TestDeepMerge:
    """Tests for ConfigLoader._deep_merge method."""

    def test_deep_merge_simple(self):
        """Should merge simple dictionaries."""
        loader = ConfigLoader()
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = loader._deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Should recursively merge nested dictionaries."""
        loader = ConfigLoader()
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3, "c": 4}}

        result = loader._deep_merge(base, override)

        assert result == {"outer": {"a": 1, "b": 3, "c": 4}}

    def test_deep_merge_replaces_lists(self):
        """Should replace lists entirely (not merge them)."""
        loader = ConfigLoader()
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}

        result = loader._deep_merge(base, override)

        assert result == {"items": [4, 5]}

    def test_deep_merge_does_not_modify_original(self):
        """Should not modify original dictionaries."""
        loader = ConfigLoader()
        base = {"a": 1, "nested": {"x": 1}}
        override = {"b": 2, "nested": {"y": 2}}

        loader._deep_merge(base, override)

        # Originals should be unchanged
        assert base == {"a": 1, "nested": {"x": 1}}
        assert override == {"b": 2, "nested": {"y": 2}}

    def test_deep_merge_empty_base(self):
        """Should handle empty base dictionary."""
        loader = ConfigLoader()
        base = {}
        override = {"a": 1, "b": 2}

        result = loader._deep_merge(base, override)

        assert result == {"a": 1, "b": 2}

    def test_deep_merge_empty_override(self):
        """Should handle empty override dictionary."""
        loader = ConfigLoader()
        base = {"a": 1, "b": 2}
        override = {}

        result = loader._deep_merge(base, override)

        assert result == {"a": 1, "b": 2}
