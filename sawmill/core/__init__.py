"""Core logic for sawmill.

This module provides the core functionality:
- PluginManager: Plugin discovery and registration
- FilterEngine: Regex filtering for messages
- ConfigLoader: Configuration file loading
- Aggregator: Message aggregation and grouping
- rules / rule_matcher: Rule file loading, appending and matching
- manifest / discovery: Manifest loading and target discovery
- runner: Running targets and re-applying rules
- report / junit: Report building and JUnit output
- scaffold: Manifest and target scaffolding
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
)
from sawmill.core.discovery import (
    DiscoveryError,
    TargetRef,
    discover_manifests,
    load_single_manifest,
    resolve_roots,
    resolve_targets,
)
from sawmill.core.filter import FilterEngine, match_message_id
from sawmill.core.junit import report_to_junit
from sawmill.core.manifest import ManifestError, ManifestLoader
from sawmill.core.plugin import (
    NoPluginFoundError,
    PluginConflictError,
    PluginError,
    PluginManager,
    get_plugin_manager,
)
from sawmill.core.report import build_report, rule_ref
from sawmill.core.rule_matcher import MatchResult, Overflow, RuleMatcher
from sawmill.core.rules import RuleLoader, RuleValidationError, append_rule, ensure_rule_file
from sawmill.core.runner import (
    LogResult,
    RunnerError,
    TargetResult,
    load_rule_files_for,
    reapply_rules,
    rerun_target,
    run_single_log,
    run_target,
)
from sawmill.core.scaffold import add_target, write_manifest_template
from sawmill.core.severity import (
    get_severity_level_map,
    get_severity_levels,
    get_severity_style,
    get_severity_style_map,
    severity_at_or_above,
)

__all__ = [
    "Aggregator",
    "Config",
    "ConfigError",
    "ConfigLoader",
    "DiscoveryError",
    "FilterEngine",
    "GeneralConfig",
    "LogResult",
    "ManifestError",
    "ManifestLoader",
    "MatchResult",
    "MessageStats",
    "NoPluginFoundError",
    "OutputConfig",
    "Overflow",
    "PluginConflictError",
    "PluginError",
    "PluginManager",
    "RuleLoader",
    "RuleMatcher",
    "RuleValidationError",
    "RunnerError",
    "SeverityStats",
    "TargetRef",
    "TargetResult",
    "add_target",
    "append_rule",
    "build_report",
    "discover_manifests",
    "ensure_rule_file",
    "get_plugin_manager",
    "get_severity_level_map",
    "get_severity_levels",
    "get_severity_style",
    "get_severity_style_map",
    "load_rule_files_for",
    "load_single_manifest",
    "match_message_id",
    "reapply_rules",
    "report_to_junit",
    "rerun_target",
    "resolve_roots",
    "resolve_targets",
    "rule_ref",
    "run_single_log",
    "run_target",
    "severity_at_or_above",
    "write_manifest_template",
]
