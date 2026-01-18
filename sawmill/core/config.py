"""Configuration loading and parsing for sawmill.

This module provides the ConfigLoader class for reading TOML configuration files
and the Config dataclass for storing configuration values.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tomli


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
