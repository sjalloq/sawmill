"""Tests for sawmill configuration loading."""

import pytest
from pathlib import Path

from sawmill.core.config import (
    ConfigLoader,
    ConfigError,
    Config,
    GeneralConfig,
    OutputConfig,
    SuppressConfig,
)


class TestConfigLoader:
    """Tests for ConfigLoader.load() method."""

    def test_load_basic_config(self, tmp_path):
        """Load a basic configuration file with general and output sections."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[general]
default_plugin = "vivado"

[output]
color = true
format = "text"
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.general.default_plugin == "vivado"
        assert config.output.color is True
        assert config.output.format == "text"

    def test_load_partial_config(self, tmp_path):
        """Load a config with only some sections defined."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[output]
color = false
''')

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
        config_file.write_text('')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.output.format == "text"
        assert config.output.color is True
        assert config.general.default_plugin is None
        assert config.suppress.patterns == []
        assert config.suppress.message_ids == []


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_values(self):
        """Load with None returns all defaults."""
        loader = ConfigLoader()
        config = loader.load(None)

        assert config.output.format == "text"
        assert config.output.color is True
        assert config.general.default_plugin is None
        assert config.suppress.patterns == []
        assert config.suppress.message_ids == []

    def test_default_config_is_valid(self):
        """Default config can be created directly."""
        config = Config()

        assert config.output.format == "text"
        assert config.output.color is True
        assert isinstance(config.suppress.patterns, list)


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
        bad_config.write_text('[section')

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
        bad_config.write_text('[output]\ncolor = not_a_bool_or_string')

        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load(bad_config)

    def test_error_includes_file_path(self, tmp_path):
        """Error message should include the file path."""
        bad_config = tmp_path / "bad.toml"
        bad_config.write_text('[section\n')

        loader = ConfigLoader()
        with pytest.raises(ConfigError) as exc:
            loader.load(bad_config)
        assert str(bad_config) in str(exc.value) or "bad.toml" in str(exc.value)


class TestSuppressConfig:
    """Tests for suppress section configuration."""

    def test_suppress_config(self, tmp_path):
        """Suppress patterns should be loaded from config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[suppress]
patterns = ["^INFO: \\\\[.*\\\\] Launching", "DEBUG:"]
message_ids = ["Common 17-55", "Vivado 12-3523"]
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert len(config.suppress.patterns) == 2
        assert "^INFO: \\[.*\\] Launching" in config.suppress.patterns
        assert "DEBUG:" in config.suppress.patterns
        assert "Common 17-55" in config.suppress.message_ids
        assert "Vivado 12-3523" in config.suppress.message_ids

    def test_suppress_empty_patterns(self, tmp_path):
        """Empty suppress patterns list is valid."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[suppress]
patterns = []
message_ids = []
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.suppress.patterns == []
        assert config.suppress.message_ids == []

    def test_suppress_patterns_only(self, tmp_path):
        """Only patterns defined, message_ids defaults to empty."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[suppress]
patterns = ["DEBUG:"]
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.suppress.patterns == ["DEBUG:"]
        assert config.suppress.message_ids == []

    def test_suppress_message_ids_only(self, tmp_path):
        """Only message_ids defined, patterns defaults to empty."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[suppress]
message_ids = ["Common 17-55"]
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.suppress.patterns == []
        assert config.suppress.message_ids == ["Common 17-55"]


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
        config_file.write_text('''
[output]
format = "json"
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.output.format == "json"

    def test_output_count_format(self, tmp_path):
        """Count format can be specified."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[output]
format = "count"
color = false
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.output.format == "count"
        assert config.output.color is False


class TestGeneralConfig:
    """Tests for general configuration options."""

    def test_general_default_plugin(self, tmp_path):
        """Default plugin can be specified."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[general]
default_plugin = "vivado"
''')

        loader = ConfigLoader()
        config = loader.load(config_file)

        assert config.general.default_plugin == "vivado"

    def test_general_no_default_plugin(self, tmp_path):
        """Missing default_plugin is None."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[general]
''')

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
            "suppress": {
                "patterns": ["DEBUG:"],
                "message_ids": ["Test 1-1"]
            }
        }

        config = Config.from_dict(data)

        assert config.general.default_plugin == "vivado"
        assert config.output.color is False
        assert config.output.format == "json"
        assert config.suppress.patterns == ["DEBUG:"]
        assert config.suppress.message_ids == ["Test 1-1"]

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

    def test_suppress_config_from_dict(self):
        """SuppressConfig.from_dict provides empty lists for missing keys."""
        data = {}
        suppress = SuppressConfig.from_dict(data)
        assert suppress.patterns == []
        assert suppress.message_ids == []
