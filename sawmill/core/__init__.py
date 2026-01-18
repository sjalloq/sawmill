"""Core logic for sawmill.

This module provides the core functionality:
- PluginManager: Plugin discovery and registration
- FilterEngine: Regex filtering for messages
"""

from sawmill.core.filter import FilterEngine
from sawmill.core.plugin import (
    NoPluginFoundError,
    PluginConflictError,
    PluginError,
    PluginManager,
)

__all__ = [
    "FilterEngine",
    "PluginManager",
    "PluginError",
    "PluginConflictError",
    "NoPluginFoundError",
]
