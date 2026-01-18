"""Core logic for sawmill.

This module provides the core functionality:
- PluginManager: Plugin discovery and registration
- FilterEngine: Regex filtering for messages
- ConfigLoader: Configuration file loading
"""

from sawmill.core.config import (
    Config,
    ConfigError,
    ConfigLoader,
    GeneralConfig,
    OutputConfig,
    SuppressConfig,
)
from sawmill.core.filter import FilterEngine, FilterStats
from sawmill.core.plugin import (
    NoPluginFoundError,
    PluginConflictError,
    PluginError,
    PluginManager,
)

__all__ = [
    "Config",
    "ConfigError",
    "ConfigLoader",
    "FilterEngine",
    "FilterStats",
    "GeneralConfig",
    "NoPluginFoundError",
    "OutputConfig",
    "PluginConflictError",
    "PluginError",
    "PluginManager",
    "SuppressConfig",
]
