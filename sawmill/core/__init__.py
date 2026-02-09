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
)
from sawmill.core.config import (
    Config,
    ConfigError,
    ConfigLoader,
    GeneralConfig,
    OutputConfig,
    SuppressConfig,
)
from sawmill.core.filter import FilterEngine, FilterStats, match_message_id
from sawmill.core.plugin import (
    NoPluginFoundError,
    PluginConflictError,
    PluginError,
    PluginManager,
    get_plugin_manager,
)
from sawmill.core.severity import (
    get_severity_level_map,
    get_severity_levels,
    get_severity_style,
    get_severity_style_map,
    severity_at_or_above,
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
    "SeverityStats",
    "SuppressConfig",
    "WaiverGenerator",
    "WaiverLoader",
    "WaiverMatcher",
    "WaiverValidationError",
    "get_plugin_manager",
    "get_severity_level_map",
    "get_severity_levels",
    "get_severity_style",
    "get_severity_style_map",
    "match_message_id",
    "severity_at_or_above",
]
