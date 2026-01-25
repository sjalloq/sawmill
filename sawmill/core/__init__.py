"""Core logic for sawmill.

This module provides the core functionality:
- PluginManager: Plugin discovery and registration
- FilterEngine: Regex filtering for messages
- ConfigLoader: Configuration file loading
- WaiverLoader: Waiver file loading and validation
- Aggregator: Message aggregation and grouping
"""

from sawmill.core.aggregation import (
    Aggregator,
    MessageStats,
    SeverityStats,
    SEVERITY_ORDER,
)
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
from sawmill.core.waiver import WaiverGenerator, WaiverLoader, WaiverMatcher, WaiverValidationError

__all__ = [
    "Aggregator",
    "Config",
    "ConfigError",
    "ConfigLoader",
    "FilterEngine",
    "FilterStats",
    "GeneralConfig",
    "MessageStats",
    "NoPluginFoundError",
    "OutputConfig",
    "PluginConflictError",
    "PluginError",
    "PluginManager",
    "SEVERITY_ORDER",
    "SeverityStats",
    "SuppressConfig",
    "WaiverGenerator",
    "WaiverLoader",
    "WaiverMatcher",
    "WaiverValidationError",
]
