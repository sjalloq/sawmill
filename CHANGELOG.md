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
