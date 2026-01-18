# Sawmill Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Project Setup
- Initial PRD.md with full requirements
- Development loop infrastructure (PROMPT.md, STATUS.md, CLAUDE.md)
- Docker-based sandbox environment
- ralph-loop.sh automation script

---

## [2026-01-18] Architecture Realignment

### Changed
- **PRD.md**: Complete rewrite with corrected architecture
  - Plugin is now sole source of truth for all parsing
  - Base app is orchestrator only (no parsing logic)
  - Removed "generic mode" fallback - no plugin = error
  - Fixed Goal 1: "Plugin-Driven Log Analysis"
  - Removed Goal 6: "Graceful Degradation" - plugin is required
  - Added explicit "Architecture Principles" section
  - Reduced from ~2,475 lines to ~550 lines

- **TASKS.md**: New file with restructured task breakdown
  - Removed Task 2.3 (Basic Severity Detection) - was architecture violation
  - Moved plugin system to Stage 2 (earlier, since everything depends on it)
  - Renamed LogEntry to ParsedMessage (plugin creates these)
  - Added `load_and_parse()` hook - plugins do all loading and parsing
  - 22 tasks across 8 stages (was 27 tasks across 9 stages)

- **CLAUDE.md**: Updated architecture documentation
  - New data flow diagram showing plugin-centric architecture
  - Updated key classes (ParsedMessage instead of LogEntry)
  - Updated plugin hooks (added load_and_parse)
  - Updated task dependencies to match TASKS.md

- **STATUS.md**: Reset to Task 1.0
  - Updated task list to match TASKS.md
  - Added architecture reminder in hints

### Removed
- Tasks 2.1-2.3 from base app (Log Loader, Boundary Detection, Severity Detection)
  - These are now plugin responsibilities in Task 2.4 (Vivado Plugin)
- "Generic mode" / "line-only mode" - no plugin = error
- Redundant inline code examples (moved to documentation)

### Architecture Violations Fixed
1. **Task 2.3 removed** - Base app no longer does severity detection
2. **Goal 6 removed** - Plugin is required, no "graceful degradation"
3. **Data flow corrected** - Plugin receives Path and creates all ParsedMessage/MessageGroup
4. **"Override" semantics removed** - Plugins PROVIDE, they don't "override"
5. **No plugin = error** - Not a degraded mode, just an error

---

## Development Log

## [2026-01-18] Task 6.3: Waiver Generation

### Added
- `sawmill/core/waiver.py` - Added `WaiverGenerator` class
  - `generate(messages, tool)` method returning valid TOML string
  - Support for generating waivers from errors/warnings/critical_warnings
  - Uses type="id" for messages with message_id
  - Uses type="hash" (SHA-256) for messages without message_id
- `tests/test_waiver_generation.py` - 27 tests for waiver generation
- Updated `sawmill/core/__init__.py` to export WaiverGenerator

### CLI
- Added `--generate-waivers` option to CLI
  - Outputs valid waiver TOML to stdout
  - Can be redirected to file: `sawmill log --generate-waivers > waivers.toml`
  - Error messages go to stderr to keep stdout clean for TOML

### Features
- Generated waivers include:
  - Metadata section with tool name and generation date
  - Placeholder author and reason for user to fill in
  - Comments with severity, content preview, and line number
- TOML escaping for special characters in patterns
- Filters out INFO messages by default (configurable)

---

## [2026-01-18] Task 6.2: Waiver Matching Engine

### Added
- `sawmill/core/waiver.py` - Added `WaiverMatcher` class
  - `is_waived(message)` method returning matching Waiver or None
  - Support for all four waiver types with correct priority
- `tests/core/test_waiver_matching.py` - 29 tests for waiver matching
- Updated `sawmill/core/__init__.py` to export WaiverMatcher

### Features
- **Match Types:**
  - ID: Exact match on message.message_id
  - Pattern: Regex match on message.raw_text (with DOTALL for multiline)
  - File: Exact, endswith, or glob-style match on file_ref.path
  - Hash: SHA-256 hash match on message.raw_text
- **Priority Order:** hash > id > pattern > file (highest to lowest)
- Pre-organizes waivers by type for efficient matching

### Notes
- Pattern matching uses DOTALL flag to handle multiline log messages
- File matching supports glob-style wildcards (* matches any characters)
- First matching waiver is returned (based on priority and order)

---

## [2026-01-18] Task 6.1: Waiver Data Model and Parser

### Added
- `sawmill/core/waiver.py` - Waiver loading and validation
  - `WaiverLoader` class for reading TOML waiver files
  - `WaiverValidationError` exception with context (path, line, waiver index)
  - `load()` method for loading from file path
  - `load_from_string()` method for testing convenience
- `tests/core/test_waiver.py` - 25 tests for waiver loading and validation
- Updated `sawmill/core/__init__.py` to export WaiverLoader and WaiverValidationError

### Features
- Support all four waiver types: id, pattern, file, hash
- Validate required fields: type, pattern, reason, author, date
- Validate regex patterns for pattern type waivers
- Support optional fields: expires, ticket
- Parse [metadata] section with optional tool field
- Error messages include file path, waiver entry index, and line number
- Handle single waiver (dict) and multiple waivers (list) TOML formats

### Notes
- Waivers are for CI acceptance (pass/fail with audit trail)
- Different from suppressions which are for display filtering (no metadata)
- In TOML, regex backslashes must be escaped or use literal strings
- Total tests: 304 (279 existing + 25 new)

---

## [2026-01-18] Task 5.2: Configuration Discovery and Merging

### Added
- `sawmill/utils/git.py` - Git repository utilities
  - `find_git_root()` function to locate git repository root
  - Walks up directory tree looking for .git directory
  - Supports `SAWMILL_GIT_ROOT` environment variable override
- `tests/utils/__init__.py` - Test package marker
- `tests/utils/test_git.py` - 10 tests for git utilities
- `tests/core/test_config_discovery.py` - 21 tests for config discovery

### Changed
- `sawmill/core/config.py` - Added discovery and merging methods
  - `ConfigLoader.discover_configs(start_path)` - Find config files in precedence order
  - `ConfigLoader.load_merged(start_path)` - Load and merge configs
  - `ConfigLoader._deep_merge()` - Deep merge dictionaries for config merging
- `sawmill/utils/__init__.py` - Export find_git_root function

### Features
- Hierarchical configuration discovery
- Config precedence: CLI > local > git root > user > defaults
- Deep merge preserves unspecified values from lower precedence configs
- Lists are replaced entirely (not merged)
- Git root detection walks up directory tree
- SAWMILL_GIT_ROOT environment variable overrides git detection

### Notes
- Total tests: 279 (248 existing + 31 new)
- Discovery deduplicates when local dir equals git root
- Uses os.path.expanduser for user config directory

---

## [2026-01-18] Task 5.1: TOML Configuration Loader

### Added
- `sawmill/core/config.py` - Configuration loading and parsing
  - `ConfigLoader` class for reading TOML configuration files
  - `Config` dataclass with general, output, and suppress sections
  - `GeneralConfig` dataclass with default_plugin setting
  - `OutputConfig` dataclass with color and format settings
  - `SuppressConfig` dataclass with patterns and message_ids lists
  - `ConfigError` exception with line number support for TOML parse errors
- `tests/core/test_config.py` - 23 tests for configuration functionality
- Updated `sawmill/core/__init__.py` to export all config classes

### Features
- Load configuration from TOML files with full validation
- Sensible defaults for all missing configuration keys
- Clear error messages with line numbers for malformed TOML
- Support for [general], [output], and [suppress] configuration sections
- Suppress section supports patterns (regex list) and message_ids (ID list)
- Load defaults when no config file specified (ConfigLoader.load(None))

### Notes
- Uses tomli for TOML parsing (Python 3.10 compatible)
- Suppressions are for display filtering, distinct from waivers (CI acceptance)
- Total tests: 248 (225 existing + 23 new)

---

## [2026-01-18] Task 4.4: CLI Integration Tests

### Added
- `tests/test_cli_integration.py` - 26 integration tests using real Vivado log file
  - TestFullPipeline: Tests for loading and processing with all output formats
  - TestSeverityFilter: Tests for severity filtering on real logs
  - TestFilterPatterns: Tests for regex pattern filtering
  - TestSuppressionPatterns: Tests for suppression pattern filtering
  - TestSuppressIdFilter: Tests for message ID suppression
  - TestIdFilter: Tests for message ID pattern filtering with wildcards
  - TestCategoryFilter: Tests for category filtering
  - TestCombinedFilters: Tests for multiple filters working together
  - TestEdgeCases: Tests for edge cases (empty results, no matches)
  - TestOutputFormat: Tests for JSON and count format correctness
  - TestPluginSelection: Tests for plugin selection and error handling

### Features Verified
- Full pipeline: CLI -> plugin.load_and_parse() -> filter -> format
- Auto-detection of Vivado plugin from log content
- All output formats (text, json, count) produce correct output
- Severity filtering at all levels (info, warning, error, critical)
- Regex pattern filtering and suppression
- Message ID filtering with wildcards (*, ?)
- Category filtering (case-insensitive)
- Multiple filters applied together correctly (AND behavior)
- Empty results handled gracefully
- Invalid plugin name produces clear error

### Notes
- Tests marked with @pytest.mark.integration for easy filtering
- Uses real `examples/vivado/vivado.log` file (~3000 lines)
- Verifies JSON output produces valid JSONL with all expected fields
- Confirms count output includes all severity categories
- Total tests: 225 (199 existing + 26 new integration tests)

---

## [2026-01-18] Task 4.3: Message ID Filtering

### Added
- `sawmill/__main__.py` - Added --id and --category options for message filtering
  - `--id` option filters by message ID pattern (supports fnmatch wildcards)
  - `--category` option filters by message category (case-insensitive)
  - `_match_message_id()` helper function for glob-style pattern matching
- `tests/test_cli_id_filter.py` - 17 tests for ID and category filtering

### Features
- Exact ID matching: `--id "Vivado 12-3523"` matches specific ID
- Wildcard matching: `--id "Synth 8-*"` matches all Synth 8-xxxx messages
- Question mark wildcard: `--id "Synth 8-1?"` matches Synth 8-10, 8-11, etc.
- Category filter: `--category synth` matches all messages with synth category
- Multiple `--id` options are OR'd (match any)
- Multiple `--category` options are OR'd (match any)
- `--id` and `--category` together are AND'd (must match both)
- Works with all existing options (--severity, --filter, --suppress, --format)

### Notes
- Uses Python's fnmatch for glob-style pattern matching
- Category matching is case-insensitive
- Category is extracted by Vivado plugin from message ID prefix (e.g., "Synth" -> "synth")

---

## [2026-01-18] Task 4.2: Output Formats

### Added
- `sawmill/__main__.py` - Added --format option for output format selection
  - `--format text` (default) - Human-readable output with severity-based coloring
  - `--format json` - JSONL format (one JSON object per line)
  - `--format count` - Summary statistics (total, errors, critical_warnings, warnings, info)
- `tests/test_cli_formats.py` - 21 tests for output format functionality

### Features
- Text format preserves original colorized output behavior
- JSON format includes all message fields (start_line, end_line, raw_text, content, severity, message_id, category, file_ref)
- Count format shows summary: `total=N errors=N critical_warnings=N warnings=N info=N`
- All formats work correctly with existing filters (--severity, --filter, --suppress, --suppress-id)
- Case-insensitive format selection (--format JSON, --format Count, etc.)

### Notes
- JSON output uses print() for clean JSONL output (one object per line)
- Count format categorizes messages by severity including "other" for unknown severities
- Filters are applied before format output, so counts reflect filtered results

---

## [2026-01-18] Task 4.1: Basic CLI with Stdout Output

### Added
- `sawmill/__main__.py` - Extended CLI with log file processing
  - `--severity` option to filter by severity level (info/warning/error/critical)
  - `--filter` option for regex pattern filtering (include matches)
  - `--suppress` option for regex pattern suppression (exclude matches, repeatable)
  - `--suppress-id` option to exclude messages by ID (repeatable)
  - `_process_log_file()` function for orchestrating log processing
  - `_get_severity_style()` for Rich-based severity colorization
  - `_severity_at_or_above()` for severity level comparison
- `tests/test_cli.py` - 17 tests for CLI log processing

### Features
- Auto-detects plugin based on file content (errors if no plugin matches)
- Manual plugin selection with `--plugin` option
- Severity filter shows messages at or above specified level
- Regex filter includes only matching messages
- Suppression patterns hide matching messages (accumulative)
- ID-based suppression hides specific message IDs
- Colorized output based on severity (cyan=info, yellow=warning, red=error, bold red=critical)
- Proper handling of Rich markup in log content (file paths with brackets)

### Notes
- Uses FilterEngine from Task 3.1 for pattern filtering
- Uses PluginManager.auto_detect() from Task 2.3 for plugin selection
- Output uses markup=False to prevent Rich from interpreting log content as markup

---

## [2026-01-18] Task 3.2: Filter Statistics

### Added
- `FilterStats` dataclass in `sawmill/core/filter.py`
  - `total_messages` - Total count of messages processed
  - `matched_messages` - Count of messages matching all enabled filters
  - `match_percentage` - Percentage of matched messages (0.0-100.0)
  - `per_filter` - Dict mapping filter IDs to individual match counts
- `FilterEngine.get_stats()` method for calculating filter statistics
- `tests/core/test_filter_stats.py` - 17 tests for filter statistics
- Updated `sawmill/core/__init__.py` to export FilterStats

### Features
- Correctly counts total and matched messages
- Calculates accurate percentages (handles edge cases like 0 total)
- Provides per-filter breakdown for enabled filters only
- Disabled filters excluded from per_filter stats
- Uses AND mode for matched_messages (consistent with apply_filters)
- Handles empty message lists and no-filter scenarios

### Notes
- per_filter shows individual matches per filter (not dependent on other filters)
- matched_messages uses AND mode (all filters must match)
- Useful for displaying filter effectiveness in CLI/TUI

---

## [2026-01-18] Task 3.1: Basic Regex Filter Engine

### Added
- `sawmill/core/filter.py` - FilterEngine class for regex filtering
  - `apply_filter(pattern, messages)` - Single filter matching
  - `apply_filters(filters, messages, mode)` - Multi-filter with AND/OR modes
  - `apply_suppressions(patterns, messages)` - Remove matching messages
- `tests/core/test_filter.py` - 23 tests for filter functionality
- Updated `sawmill/core/__init__.py` to export FilterEngine

### Features
- Single filter matches against message raw_text
- Case-sensitive and case-insensitive matching
- AND mode requires all enabled filters to match
- OR mode requires any enabled filter to match
- Disabled filters are ignored in multi-filter mode
- Suppression patterns remove matching messages from results
- Invalid regex patterns are handled gracefully (return empty/skip)
- Preserves original message order in results

### Notes
- FilterEngine operates on list[Message] provided by plugins
- FilterDefinition validation ensures only valid regex patterns at model level
- Suppressions are for display filtering, distinct from waivers (CI acceptance)

---

## [2026-01-18] Task 2.5: Plugin Discovery CLI

### Added
- `sawmill/__main__.py` - Updated CLI with plugin discovery commands
  - `--list-plugins` option to enumerate all installed plugins
  - `--show-info` option (with `--plugin`) to display plugin capabilities
  - `_get_plugin_manager()` helper for consistent plugin setup
  - `_get_implemented_hooks()` helper for hook introspection
- `tests/test_cli_plugin_discovery.py` - 12 tests for plugin discovery CLI

### Features
- `--list-plugins` shows table with name, version, description for all plugins
- `--show-info` displays: version, description, implemented hooks, filter count/details
- Filter table shows ID, name, enabled status, and description
- Error handling for unknown plugins with list of available alternatives
- Rich-formatted output with tables and styling

### Notes
- Built-in Vivado plugin is automatically registered
- External plugins discovered via entry points
- Implemented hooks detected via `sawmill_impl` attribute on methods

---

## [2026-01-18] Task 2.4: Built-in Vivado Plugin

### Added
- `sawmill/plugins/vivado.py` - VivadoPlugin class implementing all hooks
  - `can_handle(path)` - Detects Vivado logs via header and message IDs
  - `load_and_parse(path)` - Parses log files with multi-line message grouping
  - `get_filters()` - 10 pre-defined filters for common Vivado message types
  - `extract_file_reference(content)` - Extracts [file.v:line] references
- `tests/plugins/__init__.py` - Test package marker
- `tests/plugins/test_vivado.py` - 28 tests covering all hooks and integration

### Features
- High-confidence detection (0.95) via Vivado header pattern (`# Vivado v...`)
- Medium-confidence detection via message ID patterns (Synth, Vivado, IP_Flow, etc.)
- Parses all severity levels: INFO, WARNING, CRITICAL WARNING, ERROR
- Extracts message IDs (e.g., "Synth 8-6157", "Vivado 12-3523")
- Groups multi-line messages (continuation lines start with spaces or |)
- Extracts file references in bracketed `[/path/file.v:53]` and inline formats
- Provides 10 filters: errors, critical-warnings, warnings, info, timing-issues, synthesis, drc, constraints, ip-flow, routing

### Notes
- Plugin follows architecture principle: plugin is sole source of truth
- Multi-line grouping handles indented continuation lines and table rows
- File reference extraction handles both bracketed and inline formats
- Real Vivado log integration tests pass (~3000 line example log)

---

## [2026-01-18] Task 2.3: Auto-Detection and Plugin Selection

### Added
- `PluginManager.auto_detect(path)` method in `sawmill/core/plugin.py`
  - Calls `can_handle` on all registered plugins
  - Returns plugin name with highest confidence (>= 0.5)
  - Raises `NoPluginFoundError` if no plugin has confidence >= 0.5
  - Raises `PluginConflictError` if multiple plugins have confidence >= 0.5
  - Error messages include helpful diagnostics (best match, conflicting plugins)
- `tests/core/test_plugin_autodetect.py` - 12 tests for auto-detection
  - Tests for selecting highest confidence plugin
  - Tests for no plugin match error
  - Tests for conflict error when multiple plugins match
  - Tests for boundary conditions (exactly 0.5 confidence)
  - Tests for error handling (plugin exceptions)
  - Tests for path-specific confidence

### Notes
- Plugin conflict detection threshold is >= 0.5 (inclusive)
- Error messages suggest using `--plugin` to resolve conflicts
- Plugins that throw exceptions during `can_handle` are skipped gracefully

---

## [2026-01-18] Task 2.2: Plugin Manager with Entry Point Discovery

### Added
- `sawmill/core/plugin.py` - PluginManager class with complete plugin infrastructure
  - `PluginManager` - Main class for plugin management
  - `register(plugin)` - Register a plugin instance
  - `unregister(name)` - Remove a registered plugin
  - `discover()` - Discover plugins via `sawmill.plugins` entry points
  - `list_plugins()` - List all registered plugin names
  - `get_plugin(name)` - Get plugin instance by name
  - `get_plugin_info(name)` - Get plugin metadata (name, version, description)
- `sawmill/core/__init__.py` - Updated to export PluginManager and exceptions
- Exception classes for error handling:
  - `PluginError` - Base exception for plugin errors
  - `PluginConflictError` - When multiple plugins claim high confidence
  - `NoPluginFoundError` - When no plugin can handle a file
- `tests/core/__init__.py` - Test package marker
- `tests/core/test_plugin_manager.py` - 15 tests for plugin manager

### Notes
- Uses pluggy for hook management (same architecture as pytest)
- Entry point discovery uses `importlib.metadata.entry_points`
- Compatible with Python 3.10+ entry points API
- Plugins registered with pluggy can be called via `pm.hook.<hookname>()`

---

## [2026-01-18] Task 2.1: Plugin Hook Specification

### Added
- `sawmill/plugin/hookspec.py` - SawmillHookSpec class defining plugin hooks
  - `can_handle(path)` - Returns confidence score (0.0-1.0) for file handling
  - `load_and_parse(path)` - Load and parse log file into Message list
  - `get_filters()` - Return plugin-provided filter definitions
  - `extract_file_reference(content)` - Extract file:line references
- `sawmill/plugin/__init__.py` - Updated with full plugin infrastructure
  - `hookimpl` decorator for plugins to mark hook implementations
  - `SawmillPlugin` base class with default implementations
  - Default implementations return 0.0/[]/None (opt-out pattern)
- `tests/plugin/__init__.py` - Test package marker
- `tests/plugin/test_hookspec.py` - 8 tests for hook specification

### Notes
- Uses pluggy for hook management (same as pytest)
- SawmillPlugin can be subclassed with @hookimpl decorated methods
- Base class defaults allow incremental plugin implementation

---

## [2026-01-18] Task 1.2: Data Model Interfaces

### Added
- `sawmill/models/message.py` - Message and FileRef Pydantic models
  - Message: represents a logical log message (single or multi-line)
  - FileRef: represents source file references
  - Message.matches_filter() for regex matching against raw_text
- `sawmill/models/filter_def.py` - FilterDefinition model with regex validation
  - Uses Pydantic field_validator to validate regex patterns
  - Invalid patterns raise ValueError during instantiation
- `sawmill/models/waiver.py` - Waiver and WaiverFile models
  - Waiver: CI acceptance entry with type, pattern, reason, author, date
  - WaiverFile: collection of waivers for a tool
- `sawmill/models/__init__.py` - Exports all model classes
- `tests/models/test_message.py` - 11 tests for message models
- `tests/models/test_filter_def.py` - 10 tests for filter definitions

### Notes
- All models use Pydantic v2 for validation
- Message model supports both single-line and multi-line messages
- FilterDefinition validates regex patterns at construction time
- Optional fields default to None as expected

---

## [2026-01-18] Task 1.1: Project Scaffolding

### Added
- `sawmill/__init__.py` - Package marker with version
- `sawmill/__main__.py` - CLI entry point with rich-click
- `sawmill/cli.py` - CLI re-export for convenience
- `sawmill/core/__init__.py` - Core logic package
- `sawmill/models/__init__.py` - Data models package
- `sawmill/plugin/__init__.py` - Plugin system package
- `sawmill/plugins/__init__.py` - Built-in plugins package
- `sawmill/tui/__init__.py` - TUI package
- `sawmill/tui/widgets/__init__.py` - TUI widgets package
- `sawmill/utils/__init__.py` - Utilities package
- `tests/test_project_setup.py` - Package import and CLI tests

### Notes
- CLI skeleton uses rich-click for formatted help output
- Package can be installed with `pip install -e .`
- `python -m sawmill --help` works correctly
- All package imports resolve

---

## [2026-01-18] Task 1.0: Test Infrastructure

### Added
- `tests/__init__.py` - Test package marker
- `tests/conftest.py` - Shared pytest fixtures
  - `project_root` - Returns project root directory
  - `vivado_log` - Path to example Vivado log file
  - `small_log` - Minimal multi-format log for unit tests
  - `empty_log` - Empty log file
  - `large_log` - 100k line log for performance tests
  - Pytest markers: `slow`, `integration`
- `tests/test_fixtures.py` - Verification tests for fixtures

### Notes
- All fixtures use Path objects for cross-platform compatibility
- large_log fixture creates file at test time (not stored in repo)
- Markers allow selective test execution (`pytest -m "not slow"`)

---

*This file is updated by the development agent after each completed task.*
