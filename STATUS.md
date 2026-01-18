# Sawmill Development Status

> **Last Updated:** 2026-01-18
> **Last Agent Session:** Session 5 - Task 2.2 Complete

---

## Current State

| Field | Value |
|-------|-------|
| **current_task** | `2.3` |
| **task_name** | Auto-Detection and Plugin Selection |
| **stage** | Stage 2: Plugin System |
| **tests_passing** | `true` |
| **blocked** | `false` |

---

## Task Progress

### Stage 1: Project Setup (Ralph Loop)
- [x] **Task 1.0:** Test Infrastructure
- [x] **Task 1.1:** Project Scaffolding
- [x] **Task 1.2:** Data Model Interfaces

### Stage 2: Plugin System (Ralph Loop)
- [x] **Task 2.1:** Plugin Hook Specification
- [x] **Task 2.2:** Plugin Manager with Entry Point Discovery
- [ ] **Task 2.3:** Auto-Detection and Plugin Selection
- [ ] **Task 2.4:** Built-in Vivado Plugin
- [ ] **Task 2.5:** Plugin Discovery CLI

### Stage 3: Filter Engine (Ralph Loop)
- [ ] **Task 3.1:** Basic Regex Filter Engine
- [ ] **Task 3.2:** Filter Statistics

### Stage 4: CLI Streaming Interface (Ralph Loop)
- [ ] **Task 4.1:** Basic CLI with Stdout Output
- [ ] **Task 4.2:** Output Formats
- [ ] **Task 4.3:** Message ID Filtering
- [ ] **Task 4.4:** CLI Integration Tests

### Stage 5: Configuration System (Ralph Loop)
- [ ] **Task 5.1:** TOML Configuration Loader
- [ ] **Task 5.2:** Configuration Discovery and Merging

### Stage 6: Waiver System (Ralph Loop)
- [ ] **Task 6.1:** Waiver Data Model and Parser
- [ ] **Task 6.2:** Waiver Matching Engine
- [ ] **Task 6.3:** Waiver Generation

### Stage 7: CI Mode (Ralph Loop)
- [ ] **Task 7.1:** Exit Code Logic
- [ ] **Task 7.2:** Waiver Integration in CI
- [ ] **Task 7.3:** CI Summary Report

### Stage 8: TUI (Human-Guided - NOT for Ralph Loop)
- [ ] **Task 8.1:** Basic TUI Shell
- [ ] **Task 8.2:** Interactive Filtering
- [ ] **Task 8.3:** Waiver Management UI

---

## Current Task Details

### Task 2.3: Auto-Detection and Plugin Selection

**Objective:** Automatically detect log type and select appropriate plugin.

**Deliverables:**
- [ ] Method: `PluginManager.auto_detect(path) -> Optional[str]`
- [ ] Method: `PluginManager.get_plugin(name) -> SawmillPlugin`
- [ ] CLI option: `--plugin <name>` to force specific plugin
- [ ] Conflict detection when >1 plugin has confidence > 0.5

**Success Criteria:**
- [ ] Selects plugin with highest confidence score
- [ ] Raises NoPluginFoundError if no plugin has confidence > 0.5
- [ ] Raises PluginConflictError if >1 plugin has confidence > 0.5
- [ ] `--plugin vivado` forces Vivado plugin (bypasses auto-detect)

**Test Files:** `tests/core/test_plugin_autodetect.py`

---

## Blockers

(none)

---

## Hints for Next Session

- PluginManager is complete in `sawmill/core/plugin.py`
- Already has `register()`, `unregister()`, `get_plugin()`, `list_plugins()`, `get_plugin_info()`, `discover()`
- Need to add `auto_detect(path)` method that:
  1. Calls `can_handle` hook for all plugins
  2. Checks confidence scores
  3. Raises NoPluginFoundError if max < 0.5
  4. Raises PluginConflictError if >1 plugin has confidence > 0.5
  5. Returns plugin name with highest confidence
- Exception classes already exist: `PluginConflictError`, `NoPluginFoundError`

### Architecture Reminder

**Plugin is the sole source of truth.** The base app is just an orchestrator:
- Base app defines contracts (Message, FilterDefinition, etc.)
- Plugins do ALL parsing - loading files, detecting severity, grouping messages
- Base app applies filters and displays results

### Example Files Available
- `examples/vivado/vivado.log` - Real Vivado log for testing (~3000 lines)
- `examples/vivado/PATTERNS.md` - Analysis of Vivado message patterns

### Task Definitions
- Full task details with tests are in `TASKS.md`
- High-level requirements and architecture are in `PRD.md`

**Primary target: Xilinx Vivado logs.** Use the example log for testing.

---

## Session Log

### Session 5 (completed)
- **Started:** 2026-01-18
- **Task:** 2.2 - Plugin Manager with Entry Point Discovery
- **Outcome:** Complete
- **Files Created:**
  - `sawmill/core/plugin.py` - PluginManager class with discovery and registration
  - `sawmill/core/__init__.py` - Updated to export PluginManager and exceptions
  - `tests/core/__init__.py` - Test package marker
  - `tests/core/test_plugin_manager.py` - 15 tests for plugin manager
- **Tests:** 52 passing

### Session 4 (completed)
- **Started:** 2026-01-18
- **Task:** 2.1 - Plugin Hook Specification
- **Outcome:** Complete
- **Files Created:**
  - `sawmill/plugin/hookspec.py` - SawmillHookSpec with all hook definitions
  - `sawmill/plugin/__init__.py` - Updated with hookimpl and SawmillPlugin base class
  - `tests/plugin/__init__.py` - Test package marker
  - `tests/plugin/test_hookspec.py` - 8 tests for hook specification
- **Tests:** 37 passing

### Session 3 (completed)
- **Started:** 2026-01-18
- **Task:** 1.2 - Data Model Interfaces
- **Outcome:** Complete
- **Files Created:**
  - `sawmill/models/message.py` - Message and FileRef models
  - `sawmill/models/filter_def.py` - FilterDefinition with regex validation
  - `sawmill/models/waiver.py` - Waiver and WaiverFile models
  - `tests/models/__init__.py` - Test package marker
  - `tests/models/test_message.py` - 11 tests for message models
  - `tests/models/test_filter_def.py` - 10 tests for filter definitions
- **Tests:** 29 passing

### Session 2 (completed)
- **Started:** 2026-01-18
- **Task:** 1.1 - Project Scaffolding
- **Outcome:** Complete
- **Files Created:**
  - `sawmill/__init__.py`
  - `sawmill/__main__.py`
  - `sawmill/cli.py`
  - `sawmill/core/__init__.py`
  - `sawmill/models/__init__.py`
  - `sawmill/plugin/__init__.py`
  - `sawmill/plugins/__init__.py`
  - `sawmill/tui/__init__.py`
  - `sawmill/tui/widgets/__init__.py`
  - `sawmill/utils/__init__.py`
  - `tests/test_project_setup.py`
- **Tests:** 8 passing

### Session 1 (completed)
- **Started:** 2026-01-18
- **Task:** 1.0 - Test Infrastructure
- **Outcome:** Complete
- **Files Created:**
  - `tests/__init__.py`
  - `tests/conftest.py`
  - `tests/test_fixtures.py`
- **Tests:** 6 passing

---

## Notes

This file is updated by the development agent at the end of each session.
Human reviewers may also add notes or adjust the current_task if needed.

### How to Reset
If you need to restart a task:
1. Set `current_task` to the desired task number
2. Set `blocked` to `false`
3. Clear any stale hints
4. Optionally revert git to a known good state

### Project Summary

**Total: 22 tasks across 8 stages**
- **19 tasks** suitable for ralph loop (Stages 1-7)
- **3 tasks** require human guidance (Stage 8 - TUI)
