"""Suppression file loading and saving for sawmill.

Suppressions are display filters ("hide this noise"), stored in
.sawmill/suppress.toml as a [suppress] TOML table.
"""

from dataclasses import dataclass, field
from pathlib import Path

import tomli
import tomli_w

from sawmill.core.config import ConfigError


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
        return cls(patterns=data.get("patterns", []), message_ids=data.get("message_ids", []))


class SuppressLoader:
    """Loader and saver for suppression TOML files."""

    def load(self, path: Path) -> SuppressConfig:
        """Read a suppress TOML file.

        Args:
            path: Path to the suppress.toml file.

        Returns:
            SuppressConfig with values from the file, or empty defaults
            if the file doesn't exist.

        Raises:
            ConfigError: If the file contains invalid TOML.
        """
        if not path.exists():
            return SuppressConfig()

        try:
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                return SuppressConfig()
            data = tomli.loads(content)
            suppress_data = data.get("suppress", {})
            return SuppressConfig.from_dict(suppress_data)
        except tomli.TOMLDecodeError as e:
            raise ConfigError(str(e), path=path) from e

    def load_from_dir(self, sawmill_dir: Path) -> SuppressConfig:
        """Load suppress.toml from a sawmill configuration directory.

        Args:
            sawmill_dir: Path to .sawmill/ or sawmill/ directory.

        Returns:
            SuppressConfig from <dir>/suppress.toml, or defaults if missing.
        """
        return self.load(sawmill_dir / "suppress.toml")

    def save(self, config: SuppressConfig, path: Path) -> None:
        """Write suppression config to a TOML file.

        Args:
            config: SuppressConfig to write.
            path: Path to write to.
        """
        data = {
            "suppress": {
                "message_ids": config.message_ids,
                "patterns": config.patterns,
            }
        }
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
