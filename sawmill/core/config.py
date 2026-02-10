"""Configuration loading and parsing for sawmill.

This module provides the ConfigLoader class for reading TOML configuration files
and the Config dataclass for storing configuration values.
"""

from dataclasses import dataclass, field
from pathlib import Path

import tomli


class ConfigError(Exception):
    """Exception raised for configuration parsing errors.

    Attributes:
        message: Error description
        line: Line number where error occurred (if available)
        path: Path to the config file (if available)
    """

    def __init__(self, message: str, line: int | None = None, path: Path | None = None):
        self.line = line
        self.path = path

        # Build error message with line number if available
        parts = []
        if path:
            parts.append(f"Error in {path}")
        if line is not None:
            parts.append(f"at line {line}")
        full_message = f"{' '.join(parts)}: {message}" if parts else message

        super().__init__(full_message)


@dataclass
class GeneralConfig:
    """General configuration settings."""

    default_plugin: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "GeneralConfig":
        """Create GeneralConfig from a dictionary."""
        return cls(default_plugin=data.get("default_plugin"))


@dataclass
class OutputConfig:
    """Output configuration settings."""

    color: bool = True
    format: str = "text"

    @classmethod
    def from_dict(cls, data: dict) -> "OutputConfig":
        """Create OutputConfig from a dictionary."""
        return cls(color=data.get("color", True), format=data.get("format", "text"))


@dataclass
class Config:
    """Complete sawmill configuration.

    Attributes:
        general: General settings like default_plugin
        output: Output settings like color and format
    """

    general: GeneralConfig = field(default_factory=GeneralConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create Config from a dictionary.

        Args:
            data: Dictionary parsed from TOML file

        Returns:
            Config instance with values from dictionary
        """
        return cls(
            general=GeneralConfig.from_dict(data.get("general", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
        )


class ConfigLoader:
    """Loader for sawmill TOML configuration files.

    Example usage:
        loader = ConfigLoader()
        config = loader.load(Path("sawmill.toml"))

        # Or load defaults when no file exists
        config = loader.load(None)

        # Or load resolved (user + local merge)
        config = loader.load_resolved()
    """

    def load(self, path: Path | None) -> Config:
        """Load configuration from a TOML file.

        Args:
            path: Path to the TOML configuration file, or None to use defaults

        Returns:
            Config instance with values from file or defaults

        Raises:
            ConfigError: If the file exists but contains invalid TOML
            FileNotFoundError: If the path is specified but file doesn't exist
        """
        if path is None:
            return Config()

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            data = tomli.loads(content)
            return Config.from_dict(data)
        except tomli.TOMLDecodeError as e:
            # Extract line number from tomli error message if available
            line = self._extract_line_number(str(e))
            raise ConfigError(str(e), line=line, path=path) from e

    def load_resolved(self, start_path: Path | None = None) -> Config:
        """Load and merge configuration from user and local config files.

        Two-level merge: user config (~/.config/sawmill/config.toml)
        is the base, local config (<.sawmill|sawmill>/config.toml)
        overrides per-section.

        Args:
            start_path: Starting directory for local config discovery.
                If None, uses current working directory.

        Returns:
            Config instance with merged values from all sources.

        Raises:
            ConfigError: If any config file contains invalid TOML,
                or if both .sawmill/ and sawmill/ exist.
        """
        from sawmill.utils.dirs import resolve_sawmill_dir

        merged_data: dict = {}

        # 1. User config (lowest precedence)
        user_config = Path.home() / ".config" / "sawmill" / "config.toml"
        if user_config.exists():
            merged_data = self._load_toml(user_config)

        # 2. Local config from .sawmill/ or sawmill/ directory
        sawmill_dir = resolve_sawmill_dir(start_path)
        if sawmill_dir is not None:
            local_config = sawmill_dir / "config.toml"
            if local_config.exists():
                local_data = self._load_toml(local_config)
                # Shallow merge per section (local overrides user)
                for key, value in local_data.items():
                    merged_data[key] = value

        if not merged_data:
            return Config()

        return Config.from_dict(merged_data)

    def _load_toml(self, path: Path) -> dict:
        """Load and parse a TOML file, returning the raw dict.

        Args:
            path: Path to the TOML file.

        Returns:
            Parsed dictionary.

        Raises:
            ConfigError: If the file contains invalid TOML.
        """
        try:
            content = path.read_text(encoding="utf-8")
            return tomli.loads(content)
        except tomli.TOMLDecodeError as e:
            line = self._extract_line_number(str(e))
            raise ConfigError(str(e), line=line, path=path) from e

    def _extract_line_number(self, error_message: str) -> int | None:
        """Extract line number from tomli error message.

        Args:
            error_message: The error message from tomli

        Returns:
            Line number if found, None otherwise
        """
        import re

        # tomli error messages often contain "at line N" or "line N"
        match = re.search(r"(?:at )?line (\d+)", error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None
