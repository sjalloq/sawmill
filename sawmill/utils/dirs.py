"""Directory resolution utilities for sawmill.

Locates the .sawmill/ or sawmill/ configuration directory
relative to a given starting path (defaults to CWD).
"""

from pathlib import Path

from sawmill.core.config import ConfigError


def resolve_sawmill_dir(start_path: Path | None = None) -> Path | None:
    """Find an existing .sawmill/ or sawmill/ directory.

    Args:
        start_path: Directory to search in. Defaults to CWD.

    Returns:
        Path to the directory if exactly one exists, None if neither exists.

    Raises:
        ConfigError: If both .sawmill/ and sawmill/ exist (ambiguous).
    """
    base = Path.cwd() if start_path is None else Path(start_path).resolve()

    dot_dir = base / ".sawmill"
    plain_dir = base / "sawmill"

    has_dot = dot_dir.is_dir()
    has_plain = plain_dir.is_dir()

    if has_dot and has_plain:
        raise ConfigError(
            f"Ambiguous config: both .sawmill/ and sawmill/ exist in {base}. Remove one to resolve."
        )

    if has_dot:
        return dot_dir
    if has_plain:
        return plain_dir
    return None


def ensure_sawmill_dir(start_path: Path | None = None) -> Path:
    """Find or create the .sawmill/ configuration directory.

    Calls resolve_sawmill_dir first. If no directory is found,
    creates .sawmill/ in the start_path (or CWD).

    Args:
        start_path: Directory to search/create in. Defaults to CWD.

    Returns:
        Path to the existing or newly created directory.

    Raises:
        ConfigError: If both .sawmill/ and sawmill/ exist (ambiguous).
    """
    existing = resolve_sawmill_dir(start_path)
    if existing is not None:
        return existing

    base = Path.cwd() if start_path is None else Path(start_path).resolve()
    new_dir = base / ".sawmill"
    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir
