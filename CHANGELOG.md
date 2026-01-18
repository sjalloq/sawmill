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
