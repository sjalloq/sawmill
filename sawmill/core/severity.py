"""Severity-level helpers for sawmill.

Provides functions to query and compare severity levels from plugins.
These are used by both the CLI and TUI layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sawmill.models.plugin_api import SeverityLevel


def get_severity_levels(plugin):
    """Get severity levels from plugin.

    Args:
        plugin: The plugin instance to get levels from.

    Returns:
        List of SeverityLevel objects.

    Raises:
        RuntimeError: If plugin doesn't implement get_severity_levels().
    """
    from sawmill.models.plugin_api import severity_levels_from_dicts

    if plugin and hasattr(plugin, "get_severity_levels"):
        severity_dicts = plugin.get_severity_levels()
        return severity_levels_from_dicts(severity_dicts)
    else:
        raise RuntimeError(
            "Plugin must implement get_severity_levels(). This hook is required for all plugins."
        )


def get_severity_style_map(plugin) -> dict[str, str]:
    """Build a severity style map from plugin's severity levels.

    Args:
        plugin: The plugin instance to get levels from.

    Returns:
        Dictionary mapping severity ID to Rich style string.
    """
    severity_levels = get_severity_levels(plugin)
    return {level.id.lower(): level.style or "" for level in severity_levels}


def get_severity_style(severity: str | None, style_map: dict[str, str]) -> str:
    """Get the Rich style for a given severity level.

    Args:
        severity: The severity level.
        style_map: Dictionary mapping severity ID to style string.

    Returns:
        Rich style string for the severity.
    """
    if severity:
        return style_map.get(severity.lower(), "")
    return ""


def get_severity_level_map(plugin) -> dict[str, int]:
    """Build a severity level map from plugin's severity levels.

    Args:
        plugin: The plugin instance to get levels from.

    Returns:
        Dictionary mapping severity ID to level number.
    """
    severity_levels = get_severity_levels(plugin)
    return {level.id.lower(): level.level for level in severity_levels}


def severity_at_or_above(
    message_severity: str | None,
    min_severity: str,
    level_map: dict[str, int],
) -> bool:
    """Check if message severity is at or above the minimum level.

    Args:
        message_severity: The message's severity (may be None).
        min_severity: The minimum severity level to show.
        level_map: Dictionary mapping severity ID to level number.

    Returns:
        True if the message should be shown.
    """
    if message_severity is None:
        return False

    msg_level = level_map.get(message_severity.lower(), -1)
    min_level = level_map.get(min_severity.lower(), 0)
    return msg_level >= min_level


def resolve_fail_on_level(fail_on: str | None, severity_levels: list[SeverityLevel]) -> int:
    """Resolve a fail-on severity name to its numeric level.

    Args:
        fail_on: Severity id, or None for the default.
        severity_levels: Severity levels defined by the plugin.

    Returns:
        Numeric level threshold. The default is the second-lowest level, or
        the only level if the plugin defines just one.

    Raises:
        ValueError: If ``fail_on`` is not a severity id defined by the plugin.
    """
    if fail_on is None:
        sorted_levels = sorted(severity_levels, key=lambda s: s.level)
        if len(sorted_levels) >= 2:
            return int(sorted_levels[1].level)
        return int(sorted_levels[0].level) if sorted_levels else 0

    level_map = {level.id.lower(): level.level for level in severity_levels}
    fail_on_lower = fail_on.lower()
    if fail_on_lower not in level_map:
        valid = sorted(level_map, key=lambda x: -level_map[x])
        raise ValueError(
            f"Unknown severity '{fail_on}'. Valid options for this plugin: {', '.join(valid)}"
        )
    return int(level_map[fail_on_lower])
