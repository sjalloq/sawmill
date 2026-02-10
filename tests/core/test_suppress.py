"""Tests for suppression file loading and saving."""

import pytest
import tomli

from sawmill.core.config import ConfigError
from sawmill.core.suppress import SuppressConfig, SuppressLoader


class TestSuppressLoader:
    """Tests for SuppressLoader.load()."""

    def test_load_full_config(self, tmp_path):
        """Loads patterns and message_ids from suppress.toml."""
        path = tmp_path / "suppress.toml"
        path.write_text(
            '[suppress]\npatterns = ["DEBUG:", "^INFO"]\n'
            'message_ids = ["Common 17-55", "Vivado 12-3523"]\n'
        )

        loader = SuppressLoader()
        config = loader.load(path)

        assert config.patterns == ["DEBUG:", "^INFO"]
        assert config.message_ids == ["Common 17-55", "Vivado 12-3523"]

    def test_load_missing_file_returns_defaults(self, tmp_path):
        """Missing file returns empty SuppressConfig (not an error)."""
        loader = SuppressLoader()
        config = loader.load(tmp_path / "nonexistent.toml")

        assert config.patterns == []
        assert config.message_ids == []

    def test_load_empty_file_returns_defaults(self, tmp_path):
        """Empty file returns defaults."""
        path = tmp_path / "suppress.toml"
        path.write_text("")

        loader = SuppressLoader()
        config = loader.load(path)

        assert config.patterns == []
        assert config.message_ids == []

    def test_load_invalid_toml_raises_config_error(self, tmp_path):
        """Invalid TOML raises ConfigError."""
        path = tmp_path / "suppress.toml"
        path.write_text("invalid [[[")

        loader = SuppressLoader()
        with pytest.raises(ConfigError):
            loader.load(path)

    def test_load_partial_keys(self, tmp_path):
        """Missing keys default to empty lists."""
        path = tmp_path / "suppress.toml"
        path.write_text('[suppress]\nmessage_ids = ["E-001"]\n')

        loader = SuppressLoader()
        config = loader.load(path)

        assert config.patterns == []
        assert config.message_ids == ["E-001"]


class TestSuppressLoaderFromDir:
    """Tests for SuppressLoader.load_from_dir()."""

    def test_load_from_dir(self, tmp_path):
        """Loads suppress.toml from a directory."""
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()
        (sawmill_dir / "suppress.toml").write_text('[suppress]\nmessage_ids = ["E-001"]\n')

        loader = SuppressLoader()
        config = loader.load_from_dir(sawmill_dir)

        assert config.message_ids == ["E-001"]

    def test_load_from_dir_missing_file(self, tmp_path):
        """Missing suppress.toml in dir returns defaults."""
        sawmill_dir = tmp_path / ".sawmill"
        sawmill_dir.mkdir()

        loader = SuppressLoader()
        config = loader.load_from_dir(sawmill_dir)

        assert config.patterns == []
        assert config.message_ids == []


class TestSuppressLoaderSave:
    """Tests for SuppressLoader.save()."""

    def test_save_creates_file(self, tmp_path):
        """Saves SuppressConfig to a TOML file."""
        path = tmp_path / "suppress.toml"
        config = SuppressConfig(
            patterns=["DEBUG:"],
            message_ids=["E-001", "W-001"],
        )

        loader = SuppressLoader()
        loader.save(config, path)

        assert path.exists()
        data = tomli.loads(path.read_text())
        assert data["suppress"]["patterns"] == ["DEBUG:"]
        assert data["suppress"]["message_ids"] == ["E-001", "W-001"]

    def test_save_creates_parent_dirs(self, tmp_path):
        """Save creates parent directories if needed."""
        path = tmp_path / ".sawmill" / "suppress.toml"
        config = SuppressConfig(message_ids=["E-001"])

        loader = SuppressLoader()
        loader.save(config, path)

        assert path.exists()

    def test_save_overwrites_existing(self, tmp_path):
        """Save overwrites existing file content."""
        path = tmp_path / "suppress.toml"
        path.write_text('[suppress]\nmessage_ids = ["OLD"]\n')

        config = SuppressConfig(message_ids=["NEW"])
        loader = SuppressLoader()
        loader.save(config, path)

        data = tomli.loads(path.read_text())
        assert data["suppress"]["message_ids"] == ["NEW"]

    def test_save_empty_config(self, tmp_path):
        """Saving empty config writes empty lists."""
        path = tmp_path / "suppress.toml"
        config = SuppressConfig()

        loader = SuppressLoader()
        loader.save(config, path)

        data = tomli.loads(path.read_text())
        assert data["suppress"]["message_ids"] == []
        assert data["suppress"]["patterns"] == []


class TestSuppressRoundTrip:
    """Tests for save + load round-trip."""

    def test_round_trip(self, tmp_path):
        """Saved config can be loaded back identically."""
        path = tmp_path / "suppress.toml"
        original = SuppressConfig(
            patterns=["^DEBUG", "noise.*pattern"],
            message_ids=["Common 17-55", "Synth 8-*"],
        )

        loader = SuppressLoader()
        loader.save(original, path)
        loaded = loader.load(path)

        assert loaded.patterns == original.patterns
        assert loaded.message_ids == original.message_ids
