"""Core logic for sawmill.

This module provides the core functionality:
- PluginManager: Plugin discovery and registration
- FilterEngine: Regex filtering for messages
- ConfigLoader: Configuration file loading
- WaiverLoader: Waiver file loading and validation
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
from sawmill.core.waiver import WaiverLoader, WaiverMatcher, WaiverValidationError

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
    "WaiverLoader",
    "WaiverMatcher",
    "WaiverValidationError",
]
