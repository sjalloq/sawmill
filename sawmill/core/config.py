"""Configuration loading and parsing for sawmill.

This module provides the ConfigLoader class for reading TOML configuration files
and the Config dataclass for storing configuration values.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tomli

from sawmill.utils.git import find_git_root


class ConfigError(Exception):
    """Exception raised for configuration parsing errors.

    Attributes:
        message: Error description
        line: Line number where error occurred (if available)
        path: Path to the config file (if available)
    """

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        path: Optional[Path] = None
    ):
        self.line = line
        self.path = path

        # Build error message with line number if available
        parts = []
        if path:
            parts.append(f"Error in {path}")
        if line is not None:
            parts.append(f"at line {line}")
        if parts:
            full_message = f"{' '.join(parts)}: {message}"
        else:
            full_message = message

        super().__init__(full_message)


@dataclass
class GeneralConfig:
    """General configuration settings."""

    default_plugin: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "GeneralConfig":
        """Create GeneralConfig from a dictionary."""
        return cls(
            default_plugin=data.get("default_plugin")
        )


@dataclass
class OutputConfig:
    """Output configuration settings."""

    color: bool = True
    format: str = "text"

    @classmethod
    def from_dict(cls, data: dict) -> "OutputConfig":
        """Create OutputConfig from a dictionary."""
        return cls(
            color=data.get("color", True),
            format=data.get("format", "text")
        )


@dataclass
class SuppressConfig:
    """Suppression configuration settings.

    Suppressions are for display filtering (hiding noise), distinct from
    waivers (CI acceptance with audit trail).
    """

    patterns: list[str] = field(default_factory=list)
    message_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "SuppressConfig":
        """Create SuppressConfig from a dictionary."""
        return cls(
            patterns=data.get("patterns", []),
            message_ids=data.get("message_ids", [])
        )


@dataclass
class Config:
    """Complete sawmill configuration.

    Attributes:
        general: General settings like default_plugin
        output: Output settings like color and format
        suppress: Suppression settings for display filtering
    """

    general: GeneralConfig = field(default_factory=GeneralConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    suppress: SuppressConfig = field(default_factory=SuppressConfig)

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
            suppress=SuppressConfig.from_dict(data.get("suppress", {}))
        )


class ConfigLoader:
    """Loader for sawmill TOML configuration files.

    Example usage:
        loader = ConfigLoader()
        config = loader.load(Path("sawmill.toml"))

        # Or load defaults when no file exists
        config = loader.load(None)
    """

    def load(self, path: Optional[Path]) -> Config:
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

    def _extract_line_number(self, error_message: str) -> Optional[int]:
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

    def discover_configs(self, start_path: Optional[Path] = None) -> list[Path]:
        """Discover configuration files in order of precedence.

        Searches for configuration files in standard locations, returning them
        in order from lowest to highest precedence. When merging, later files
        override earlier ones.

        Precedence order (lowest to highest):
        1. User config: ~/.config/sawmill/config.toml
        2. Git root: <git_root>/sawmill.toml
        3. Local (start_path): <start_path>/sawmill.toml

        CLI arguments have highest precedence but are handled separately.

        Args:
            start_path: Starting directory for local config search. If None,
                uses current working directory.

        Returns:
            List of existing config file paths in precedence order (lowest first).
        """
        if start_path is None:
            start_path = Path.cwd()
        else:
            start_path = Path(start_path).resolve()

        configs: list[Path] = []

        # 1. User config (lowest precedence)
        user_config_dir = Path(os.path.expanduser("~")) / ".config" / "sawmill"
        user_config = user_config_dir / "config.toml"
        if user_config.exists():
            configs.append(user_config)

        # 2. Git root config
        git_root = find_git_root(start_path)
        if git_root:
            git_config = git_root / "sawmill.toml"
            if git_config.exists():
                # Don't add duplicate if git root is same as start_path
                if git_config.resolve() not in [c.resolve() for c in configs]:
                    configs.append(git_config)

        # 3. Local config (highest file precedence)
        local_config = start_path / "sawmill.toml"
        if local_config.exists():
            # Don't add duplicate if already in list
            if local_config.resolve() not in [c.resolve() for c in configs]:
                configs.append(local_config)

        return configs

    def load_merged(self, start_path: Optional[Path] = None) -> Config:
        """Load and merge configuration from all discovered config files.

        Loads config files in precedence order, merging them so that later
        (higher precedence) files override values from earlier files.
        Unspecified values fall through from lower precedence configs or defaults.

        Precedence order (lowest to highest):
        1. Defaults (hardcoded)
        2. User config: ~/.config/sawmill/config.toml
        3. Git root: <git_root>/sawmill.toml
        4. Local: <start_path>/sawmill.toml
        5. CLI arguments (handled by caller)

        Args:
            start_path: Starting directory for config discovery. If None,
                uses current working directory.

        Returns:
            Config instance with merged values from all sources.

        Raises:
            ConfigError: If any config file contains invalid TOML.
        """
        # Start with default config
        merged_data: dict = {}

        # Discover and load configs in precedence order
        config_paths = self.discover_configs(start_path)

        for config_path in config_paths:
            try:
                content = config_path.read_text(encoding="utf-8")
                data = tomli.loads(content)
                # Deep merge the configuration
                merged_data = self._deep_merge(merged_data, data)
            except tomli.TOMLDecodeError as e:
                line = self._extract_line_number(str(e))
                raise ConfigError(str(e), line=line, path=config_path) from e

        return Config.from_dict(merged_data)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries.

        Values from override take precedence over base. Nested dictionaries
        are merged recursively. Lists and other values are replaced entirely.

        Args:
            base: Base dictionary (lower precedence)
            override: Override dictionary (higher precedence)

        Returns:
            New dictionary with merged values.
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override value
                result[key] = value

        return result
