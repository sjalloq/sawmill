"""Tests for sawmill configuration loading."""

import pytest

from sawmill.core.config import (
    Config,
    ConfigError,
    ConfigLoader,
    GeneralConfig,
    OutputConfig,
)


class TestConfigLoader:
    """Tests for ConfigLoader.load() method."""

    def test_load_basic_config(self, tmp_path):
        """Load a basic configuration file with general and output sections."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[general]
default_plugin = "vivado"

[output]
color = true
format = "text"
""")

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.general.default_plugin == "vivado"
        assert config.output.color is True
        assert config.output.format == "text"

    def test_load_partial_config(self, tmp_path):
        """Load a config with only some sections defined."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[output]
color = false
""")

        loader = ConfigLoader()
        config = loader.load(config_file)

        # Output section from file
        assert config.output.color is False
        # Format gets default
        assert config.output.format == "text"
        # General section gets defaults
        assert config.general.default_plugin is None

    def test_load_empty_config(self, tmp_path):
        """Load an empty config file returns defaults."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.output.format == "text"
        assert config.output.color is True
        assert config.general.default_plugin is None


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_values(self):
        """Load with None returns all defaults."""
        loader = ConfigLoader()
        config = loader.load(None)

        assert config.output.format == "text"
        assert config.output.color is True
        assert config.general.default_plugin is None

    def test_default_config_is_valid(self):
        """Default config can be created directly."""
        config = Config()

        assert config.output.format == "text"
        assert config.output.color is True


class TestMalformedTOML:
    """Tests for error handling with malformed TOML."""

    def test_malformed_toml_error_message(self, tmp_path):
        """Malformed TOML should give line number in error."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text('[section\nkey = "unclosed')

        loader = ConfigLoader()
        with pytest.raises(ConfigError) as exc:
            loader.load(bad_config)
        assert "line" in str(exc.value).lower()

    def test_unclosed_bracket_error(self, tmp_path):
        """Unclosed bracket should raise ConfigError."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[section")

        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load(bad_config)

    def test_unclosed_string_error(self, tmp_path):
        """Unclosed string should raise ConfigError."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text('key = "unclosed string')

        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load(bad_config)

    def test_invalid_value_type_error(self, tmp_path):
        """Invalid TOML syntax should raise ConfigError."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[output]\ncolor = not_a_bool_or_string")

        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load(bad_config)

    def test_error_includes_file_path(self, tmp_path):
        """Error message should include the file path."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text("[section\n")

        loader = ConfigLoader()
        with pytest.raises(ConfigError) as exc:
            loader.load(bad_config)
        assert str(bad_config) in str(exc.value) or "bad.toml" in str(exc.value)


class TestFileNotFound:
    """Tests for file not found handling."""

    def test_nonexistent_file_raises_error(self, tmp_path):
        """Loading a nonexistent file raises FileNotFoundError."""
        config_file = tmp_path / "nonexistent.toml"

        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(config_file)


class TestOutputConfig:
    """Tests for output configuration options."""

    def test_output_json_format(self, tmp_path):
        """JSON format can be specified."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[output]
format = "json"
""")

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.output.format == "json"

    def test_output_count_format(self, tmp_path):
        """Count format can be specified."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[output]
format = "count"
color = false
""")

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.output.format == "count"
        assert config.output.color is False


class TestGeneralConfig:
    """Tests for general configuration options."""

    def test_general_default_plugin(self, tmp_path):
        """Default plugin can be specified."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[general]
default_plugin = "vivado"
""")

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.general.default_plugin == "vivado"

    def test_general_no_default_plugin(self, tmp_path):
        """Missing default_plugin is None."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[general]
""")

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.general.default_plugin is None


class TestDataclasses:
    """Tests for the dataclass implementations."""

    def test_config_from_dict(self):
        """Config.from_dict creates correct structure."""
        data = {
            "general": {"default_plugin": "vivado"},
            "output": {"color": False, "format": "json"},
        }

        config = Config.from_dict(data)

        assert config.general.default_plugin == "vivado"
        assert config.output.color is False
        assert config.output.format == "json"

    def test_general_config_from_dict(self):
        """GeneralConfig.from_dict handles missing keys."""
        data = {}
        general = GeneralConfig.from_dict(data)
        assert general.default_plugin is None

    def test_output_config_from_dict(self):
        """OutputConfig.from_dict provides defaults for missing keys."""
        data = {}
        output = OutputConfig.from_dict(data)
        assert output.color is True
        assert output.format == "text"


class TestLoadResolved:
    """Tests for ConfigLoader.load_resolved() method."""

    def test_no_configs_returns_defaults(self, tmp_path, monkeypatch):
        """Returns default config when no config files exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))

        loader = ConfigLoader()
        config = loader.load_resolved(tmp_path)

        assert config.output.format == "text"
        assert config.output.color is True
        assert config.general.default_plugin is None

    def test_user_config_only(self, tmp_path, monkeypatch):
        """Loads user config when no local config exists."""
        user_config_dir = tmp_path / ".config" / "sawmill"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.toml").write_text(
            '[output]\ncolor = false\n[general]\ndefault_plugin = "vivado"\n'
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        # Use a subdir with no .sawmill/
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        loader = ConfigLoader()
        config = loader.load_resolved(work_dir)

        assert config.output.color is False
        assert config.general.default_plugin == "vivado"

    def test_local_config_only(self, tmp_path, monkeypatch):
        """Loads local config when no user config exists."""
        monkeypatch.setenv("HOME", str(tmp_path))  # no .config/sawmill/

        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        (sawmill_dir / "config.toml").write_text('[output]\nformat = "json"\n')

        loader = ConfigLoader()
        config = loader.load_resolved(tmp_path)

        assert config.output.format == "json"

    def test_local_overrides_user(self, tmp_path, monkeypatch):
        """Local config sections override user config sections."""
        # User config
        user_config_dir = tmp_path / ".config" / "sawmill"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.toml").write_text(
            '[output]\nformat = "text"\ncolor = false\n[general]\ndefault_plugin = "generic"\n'
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        # Local config overrides output section
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        sawmill_dir = work_dir / ".sawmill"
        sawmill_dir.mkdir()
        (sawmill_dir / "config.toml").write_text('[output]\nformat = "json"\n')

        loader = ConfigLoader()
        config = loader.load_resolved(work_dir)

        assert config.output.format == "json"  # local overrides
        # Note: shallow merge per section means entire [output] is replaced
        assert config.output.color is True  # reverts to default (local replaced section)
        assert config.general.default_plugin == "generic"  # from user (not in local)

    def test_dot_sawmill_dir_works(self, tmp_path, monkeypatch):
        """Config loads from .sawmill/ directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        (sawmill_dir / "config.toml").write_text('[general]\ndefault_plugin = "vivado"\n')

        loader = ConfigLoader()
        config = loader.load_resolved(tmp_path)
        assert config.general.default_plugin == "vivado"

    def test_plain_sawmill_dir_works(self, tmp_path, monkeypatch):
        """Config loads from sawmill/ directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        sawmill_dir = tmp_path / "sawmill"
        sawmill_dir.mkdir()
        (sawmill_dir / "config.toml").write_text('[general]\ndefault_plugin = "vivado"\n')

        loader = ConfigLoader()
        config = loader.load_resolved(tmp_path)
        assert config.general.default_plugin == "vivado"

    def test_invalid_local_toml_raises_config_error(self, tmp_path, monkeypatch):
        """Invalid TOML in local config raises ConfigError."""
        monkeypatch.setenv("HOME", str(tmp_path))
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        (sawmill_dir / "config.toml").write_text("invalid [[[")

        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load_resolved(tmp_path)
