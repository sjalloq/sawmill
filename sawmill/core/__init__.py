"""Core logic for sawmill.

This module provides the core functionality:
- PluginManager: Plugin discovery and registration
"""

from sawmill.core.plugin import (
    NoPluginFoundError,
    PluginConflictError,
    PluginError,
    PluginManager,
)

__all__ = [
    "PluginManager",
    "PluginError",
    "PluginConflictError",
    "NoPluginFoundError",
]
