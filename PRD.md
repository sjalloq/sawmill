# Sawmill - Product Requirements Document

## Project Overview

- **Project Name:** Sawmill
- **Tagline:** A configurable TUI for post-processing and filtering EDA tool logs
- **Technology Stack:** Python 3.10+, Textual (TUI framework), TOML (configuration)
- **Primary Use Case:** Interactive filtering and analysis of Electronic Design Automation (EDA) tool log files

## Elevator Pitch

Sawmill is a terminal-based log analysis tool that allows engineers to filter, analyze, and understand complex log files from EDA tools. Through a plugin architecture, it provides tool-specific intelligence about log formats while remaining generic enough to handle any text-based log file. Engineers can quickly identify relevant errors and warnings buried in thousands of lines of output, customize filtering rules interactively, and share configurations across teams.

---

## Goals and Non-Goals

### Goals

1. **Generic Log Filtering:** Provide powerful regex-based filtering for any text log file without tool-specific configuration
2. **Plugin Extensibility:** Enable tool-specific intelligence through a pluggy-based plugin architecture (same pattern as pytest)
3. **Multi-line Pattern Support:** Correctly handle log messages that span multiple lines (common in EDA tools)
4. **Interactive Customization:** Allow users to modify and extend filter definitions in real-time through the TUI
5. **Configuration Portability:** Enable saving and sharing customized filter configurations via TOML files
6. **Zero Configuration Start:** Work immediately on any log file with basic regex filtering, no setup required

### Non-Goals (for v1.0)

- **Live Log Monitoring:** Real-time tailing of actively-written log files (focus is post-processing)
- **Log Aggregation:** Combining logs from multiple sources or files
- **Advanced Analytics:** Statistical analysis, graphing, or trend detection
- **Multi-user Waiver Workflow:** Full waiver approval workflow with multiple reviewers (deferred to future version; basic waiver generation/matching IS in scope)

---

## User Personas

### Primary Persona: Hardware Design Engineer (Shareef)

- Works with multiple EDA tools (Synopsys, Cadence, open-source)
- Generates large log files from synthesis, timing analysis, place-and-route
- Needs to quickly find relevant errors/warnings among thousands of info messages
- Wants to customize filtering rules based on project-specific needs
- Comfortable with terminal tools and configuration files

### Secondary Persona: Verification Engineer

- Runs simulations that generate extensive debug output
- Needs to filter simulation logs for specific signal patterns or events
- May work with custom in-house tools with unique log formats
- Wants to share filter configurations with team members

### Tertiary Persona: DevOps/Build Engineer

- Processes CI/CD build logs from various tools
- Needs generic filtering capabilities across different log types
- Values automation and scriptability

---

## Core Features

### 1. Basic Log Viewing and Navigation

**Description:** Display log files in a scrollable, searchable TUI interface.

**Requirements:**

- Load and display log files of arbitrary size efficiently
- Provide smooth scrolling through large files (100k+ lines)
- Display line numbers alongside log content
- Support basic navigation (page up/down, jump to line, home/end)
- Highlight current line/cursor position
- Display file metadata (name, size, line count)

**User Stories:**

- As an engineer, I want to open a log file and scroll through it smoothly
- As an engineer, I want to see line numbers so I can reference specific locations
- As an engineer, I want to jump to a specific line number quickly

### 2. Interactive Regex Filtering

**Description:** Real-time filtering of log content based on user-entered regex patterns.

**Requirements:**

- Provide a search/filter input bar in the TUI
- Apply regex pattern filtering in real-time as user types
- Display only lines matching the current filter
- Support multiple active filters with AND/OR logic
- Show filter statistics (X of Y lines match)
- Allow toggling filters on/off without deleting them
- Highlight matched portions of lines
- Support case-sensitive and case-insensitive matching
- Handle invalid regex gracefully with error messages

### 3. Multi-line Message Grouping

**Description:** Group related log lines into logical messages for more accurate filtering.

**Requirements:**

- Support configurable message boundary patterns
- Allow plugins to define how lines should be grouped
- Display grouped messages as cohesive units
- Apply filtering to entire grouped messages, not individual lines
- Preserve context when showing filtered results (show full message group)
- Handle nested or complex grouping rules
- Provide visual indication of message boundaries

**Technical Notes:**

- Common pattern: timestamp/severity header + indented continuation lines
- Example: Error message on line 1, stack trace on lines 2-5
- Grouping happens during initial parse, before filtering

### 4. Plugin System

**Description:** Hook-based plugin architecture using pluggy (same pattern as pytest).

**Plugin Architecture:**

Plugins are Python packages that register via entry points and implement hooks.

#### Installation

```bash
# Install a plugin
pip install sawmill-plugin-vivado

# Or develop locally
pip install -e ./my-plugin
```

#### Plugin Registration (pyproject.toml)

```toml
[project.entry-points."sawmill.plugins"]
vivado = "sawmill_plugin_vivado:VivadoPlugin"
```

#### Hook Specification

Plugins implement hooks to customize sawmill behavior:

```python
from sawmill.plugin import SawmillPlugin, hookimpl, SAWMILL_PLUGIN_API_VERSION
from sawmill.models import FilterDefinition, MessageBoundary, ParsedMessage, FileRef

class VivadoPlugin(SawmillPlugin):
    """Plugin for Xilinx Vivado logs."""

    name = "vivado"
    version = "1.0.0"
    api_version = SAWMILL_PLUGIN_API_VERSION  # Required: declares API compatibility
    description = "Xilinx Vivado synthesis and implementation logs"

    @hookimpl
    def can_handle(self, path: Path, content: str) -> float:
        """Return confidence score 0.0-1.0 for handling this file."""
        if "Vivado v" in content or "[Synth " in content:
            return 0.9
        return 0.0

    @hookimpl
    def get_filters(self) -> list[FilterDefinition]:
        """Return filter definitions for this tool."""
        return [
            FilterDefinition(
                id="errors",
                name="Errors",
                pattern=r"^ERROR:",
                severity="error",
                enabled_by_default=True,
            ),
            FilterDefinition(
                id="critical-warnings",
                name="Critical Warnings",
                pattern=r"^CRITICAL WARNING:",
                severity="critical",
                enabled_by_default=True,
            ),
            # ... more filters
        ]

    @hookimpl
    def get_message_boundaries(self) -> list[MessageBoundary]:
        """Return rules for grouping multi-line messages."""
        return [
            MessageBoundary(
                start_pattern=r"^(INFO|WARNING|CRITICAL WARNING|ERROR):",
                continuation_pattern=r"^(\s{2,}|\t)",
                max_lines=20,
            ),
        ]

    @hookimpl
    def parse_message(self, line: str) -> ParsedMessage | None:
        """Parse a log line into structured data."""
        import re
        match = re.match(
            r'^(INFO|WARNING|CRITICAL WARNING|ERROR):\s*\[([^\]]+)\]\s*(.+)',
            line
        )
        if match:
            return ParsedMessage(
                severity=match.group(1).lower().replace(" ", "_"),
                message_id=match.group(2),
                content=match.group(3),
                raw=line,
            )
        return None

    @hookimpl
    def extract_file_reference(self, content: str) -> FileRef | None:
        """Extract source file references from message content."""
        import re
        match = re.search(r'\[([^\]]+\.(v|vhd|sv|xdc)):(\d+)\]', content)
        if match:
            return FileRef(path=match.group(1), line=int(match.group(3)))
        return None
```

#### Available Hooks

| Hook | Purpose | Return Type |
|------|---------|-------------|
| `can_handle(path, content)` | Detect if plugin handles this file | `float` (0.0-1.0) |
| `get_filters()` | Provide filter definitions | `list[FilterDefinition]` |
| `get_message_boundaries()` | Define multi-line grouping rules | `list[MessageBoundary]` |
| `parse_message(line)` | Parse line into structured data | `ParsedMessage \| None` |
| `extract_severity(message)` | Determine severity from message | `str \| None` |
| `extract_file_reference(content)` | Find source file references | `FileRef \| None` |
| `format_message(message, format)` | Custom output formatting | `str` |
| `get_categories()` | List message categories plugin understands | `list[str]` |
| `get_quick_filters()` | Named filter presets (e.g., 'timing_focus') | `dict[str, list[str]]` |

#### Plugin Discovery

Plugins are discovered via Python entry points:

```python
# sawmill/core/plugin.py
import importlib.metadata
import pluggy

SAWMILL_PLUGIN_API_VERSION = 1  # Increment when hook signatures change

class PluginManager:
    def __init__(self):
        self.pm = pluggy.PluginManager("sawmill")
        self.pm.add_hookspecs(SawmillHookSpec)
        self._load_plugins()

    def _load_plugins(self):
        """Load all installed plugins."""
        for ep in importlib.metadata.entry_points(group="sawmill.plugins"):
            plugin = ep.load()()
            # Check API version compatibility
            if hasattr(plugin, 'api_version') and plugin.api_version != SAWMILL_PLUGIN_API_VERSION:
                logger.warning(f"Plugin {plugin.name} uses API v{plugin.api_version}, expected v{SAWMILL_PLUGIN_API_VERSION}")
            self.pm.register(plugin)
```

#### Plugin Conflict Resolution

When multiple plugins could handle a file:

1. **Explicit `--plugin X` flag always wins** - no auto-detection performed
2. **Error if >1 plugin returns confidence > 0.5** - user must specify with `--plugin`
3. **If exactly one plugin > 0.5 threshold** - that plugin is selected
4. **If no plugin > 0.5** - generic mode (no plugin-specific features)

This ensures deterministic behavior and prevents silent conflicts.

#### Built-in Plugins

Sawmill includes a reference Vivado plugin as `sawmill.plugins.vivado`.

### 5. Configuration System

**Configuration File Locations (in precedence order):**

1. Command-line specified: `--config <file>`
2. Current directory: `./sawmill.toml`
3. Git repo root: `<git-root>/.sawmill/config.toml`
4. User config: `~/.config/sawmill/config.toml`
5. Built-in defaults

**Configuration Schema:**

```toml
[general]
default_plugin = "synopsys-dc"
show_line_numbers = true
theme = "monokai"

[plugins]
search_paths = ["~/.config/sawmill/plugins", "./plugins"]
enabled = ["synopsys-dc", "cadence-genus"]

# Plugin-specific configuration
[plugins.vivado]
device_family = "ultrascale"
timing_threshold = -0.5

[[filters.custom]]
id = "my-filter-1"
name = "Custom Error Pattern"
pattern = "CUSTOM_ERROR_\\d+"
severity = "error"
enabled = true

# Suppression rules for display filtering (distinct from waivers for CI pass/fail)
# Suppressions hide messages from output but don't affect CI exit codes
[suppress]
patterns = [
    "^INFO: \\[.*\\] Launching helper",  # Verbose startup noise
    "^INFO: \\[Vivado 12-627\\]",         # Always-present message
]
message_ids = ["Common 17-55"]           # Suppress specific message IDs
```

### 6. Interactive Filter Customization

**Requirements:**

- Display filters in sidebar panel
- Show filter metadata (name, pattern, description, source)
- Toggle filters on/off
- Edit filter regex patterns in-place
- Create new custom filters
- Mark user-modified filters distinctly
- "Reset to default" for modified filters
- Real-time match counts

### 7. Configuration Export

**Requirements:**

- Export current filter state to TOML
- Include user modifications as overrides
- Preserve filter metadata
- Generate human-readable, commented TOML
- Include provenance (plugin, timestamp, author)

**Export Format:**

```toml
# Sawmill Filter Configuration
# Generated: 2026-01-18 14:30:00
# Base Plugin: synopsys-dc v1.0.0

[metadata]
base_plugin = "synopsys-dc"
plugin_version = "1.0.0"
created_by = "shareef"
created_at = "2026-01-18T14:30:00Z"
git_commit = "abc123def"          # Git commit hash (if in repo)
git_dirty = false                  # Whether working tree had uncommitted changes

[[filters.modified]]
id = "critical-timing"
pattern = "slack.*-[5-9]\\d+\\.\\d+"
enabled = true

[[filters.custom]]
id = "project-specific-error"
name = "KASLI Board Errors"
pattern = "KASLI.*ERROR"
severity = "error"
enabled = true
```

---

## Technical Architecture

### Project Structure

```
sawmill/
├── __init__.py
├── __main__.py              # CLI entry point
├── core/
│   ├── __init__.py
│   ├── parser.py            # Log parsing, message grouping
│   ├── filter.py            # Filter engine, regex matching
│   ├── config.py            # Configuration loading/merging
│   └── plugin.py            # Plugin discovery/communication
├── tui/
│   ├── __init__.py
│   ├── app.py               # Main Textual application
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── log_view.py      # Scrollable log display
│   │   ├── filter_panel.py  # Filter management UI
│   │   ├── search_input.py  # Regex input widget
│   │   └── status_bar.py    # Status and statistics
│   └── screens/
│       ├── __init__.py
│       ├── main.py          # Main log viewing screen
│       └── export.py        # Configuration export dialog
├── models/
│   ├── __init__.py
│   ├── log_entry.py         # LogEntry, MessageGroup
│   ├── filter_def.py        # FilterDefinition
│   └── plugin_spec.py       # Plugin response schemas
└── utils/
    ├── __init__.py
    ├── git.py               # Git repository detection
    └── validation.py        # Regex validation
```

---

## Operating Modes

Sawmill supports multiple operating modes to fit different workflows:

### 1. CLI Streaming Mode (Primary)
Stream filtered log output to stdout for piping, viewing, or redirection.

```bash
# Filter by severity
sawmill vivado.log --severity error,critical
sawmill vivado.log --severity warning --format json

# Filter by pattern
sawmill vivado.log --filter "timing|slack"
sawmill vivado.log --id "Synth 8-*"

# Filter by message category
sawmill vivado.log --category timing,constraints

# Output formats
sawmill vivado.log --format text      # Default: human-readable
sawmill vivado.log --format json      # JSON lines (one per message)
sawmill vivado.log --format count     # Summary counts only

# Delta/Baseline comparison - show only NEW messages not in baseline
sawmill vivado.log --baseline previous.log
sawmill vivado.log --baseline previous.log --severity error,critical
```

### 2. CI/Lint Mode
Return exit codes for use in CI pipelines and Makefiles.

```bash
# Basic CI check - fail on any error/critical warning
sawmill --ci vivado.log
echo $?  # 0 = pass, 1 = fail

# CI with waivers - ignore known acceptable issues
sawmill --ci --waivers project.waivers.toml vivado.log

# Strict mode - also fail on regular warnings
sawmill --ci --strict vivado.log

# Generate summary report
sawmill --ci --report ci-report.json vivado.log
```

### 3. Waiver Generation Mode
Generate waiver files from log analysis.

```bash
# Generate waivers for all current errors/warnings
sawmill vivado.log --generate-waivers > project.waivers.toml

# Generate waivers only for specific categories
sawmill vivado.log --generate-waivers --severity warning > warnings.waivers.toml

# Interactive waiver generation (TUI mode)
sawmill vivado.log --interactive  # Then use TUI to select waivers
```

### 4. Interactive TUI Mode (Future)
Full interactive terminal interface for exploration and waiver management.

```bash
sawmill vivado.log              # Opens TUI
sawmill vivado.log --tui        # Explicit TUI mode
```

**Note:** TUI mode is deferred to later development phases as it requires human feedback for UX decisions.

### 5. Plugin Discovery Mode
Query installed plugins and their capabilities.

```bash
# List all discovered plugins
sawmill --list-plugins

# Show detailed plugin information
sawmill --plugin vivado --show-info
# Output: version, hooks implemented, categories, filter counts, etc.
```

---

## Waiver System

Waivers allow teams to mark specific warnings/errors as "accepted" so they don't cause CI failures.

### Waiver File Format

```toml
# project.waivers.toml

[metadata]
created = "2026-01-18"
tool = "vivado"
version = "1.0"
description = "Accepted warnings for captain project"

# Waive by message ID (e.g., [Vivado 12-3523])
[[waiver]]
type = "id"
pattern = "Vivado 12-3523"
reason = "Component name change is intentional"
author = "shareef"
date = "2026-01-18"

# Waive by regex pattern on message content
[[waiver]]
type = "pattern"
pattern = "set_input_delay.*usb_fifo_clk"
reason = "USB FIFO clock is async, constraints not applicable"
author = "shareef"
date = "2026-01-18"

# Waive by source file (glob pattern)
[[waiver]]
type = "file"
pattern = "*/ip/pcie_s7/*"
severity = ["warning", "critical"]
reason = "Xilinx IP core warnings - vendor code, not actionable"
author = "shareef"
date = "2026-01-18"

# Waive specific instance by content hash (for exact matches)
[[waiver]]
type = "hash"
hash = "sha256:a1b2c3d4e5f6..."
reason = "Reviewed and accepted - false positive"
author = "shareef"
date = "2026-01-18"
expires = "2026-06-01"  # Optional expiry
```

### Waiver Matching Priority

1. **Hash match** - Exact message content match (highest specificity)
2. **ID match** - Message ID pattern (e.g., `Vivado 12-*`)
3. **Pattern match** - Regex on message content
4. **File match** - Source file glob pattern (lowest specificity)

### Waiver Reporting

```bash
# Show what would be waived (dry run)
sawmill --ci --waivers project.waivers.toml --show-waived vivado.log

# Report unused waivers (cleanup stale entries)
sawmill --ci --waivers project.waivers.toml --report-unused vivado.log
```

---

## Implementation Phases

### Phase 1: Core Foundation
- Project scaffolding and packaging
- Data models (LogEntry, FilterDefinition, MessageGroup)
- Basic CLI skeleton with rich-click

**Deliverable:** Installable package with `sawmill --help`

### Phase 2: Log Parsing
- Efficient file loading (100k+ lines)
- Multi-line message boundary detection
- Message grouping logic

**Deliverable:** Parse log files into structured message groups

### Phase 3: Filter Engine
- Regex-based filtering
- Severity filtering
- Message ID filtering
- Filter statistics (counts, percentages)

**Deliverable:** Filter messages by various criteria

### Phase 4: CLI Streaming Interface
- Stream filtered output to stdout
- Multiple output formats (text, JSON, count)
- All filter options as CLI arguments
- Colorized output with Rich

**Deliverable:** Fully functional CLI for filtering and viewing logs

### Phase 5: Plugin System
- Plugin discovery via entry points
- pluggy hook-based architecture
- Auto-detection based on log content
- Reference plugin (Vivado)
- Plugin discovery CLI (`--list-plugins`, `--show-info`)

**Deliverable:** Auto-detect tool and load tool-specific filters

### Phase 6: Configuration System
- TOML configuration schema
- Hierarchical config discovery
- Config merging with precedence
- Git repository detection

**Deliverable:** Load and merge configs from multiple sources

### Phase 7: Waiver System
- Waiver file format and parsing
- Waiver matching engine
- Waiver generation from logs
- Unused waiver detection

**Deliverable:** Full waiver lifecycle support

### Phase 8: CI Mode
- Exit code logic (0/1)
- Waiver integration
- Summary report generation
- Strict mode option

**Deliverable:** CI-ready linting mode for build pipelines

### Phase 9: TUI (Deferred - Human-Guided)
- Basic log viewing
- Interactive filtering
- Waiver selection and generation
- Configuration export

**Deliverable:** Interactive terminal interface

**Note:** Phase 9 is developed iteratively with human feedback, not via automated ralph loop.

---

## Future Enhancements (Post-v1.0)

- Live log monitoring (tail -f mode)
- Log file comparison (diff between runs)
- Export filtered logs to file
- Statistics dashboard
- Filter templates library
- IDE integrations (VS Code, etc.)
- Waiver approval workflow (multi-user)

---

## Example Use Cases

### Use Case 1: CI Pipeline Integration

```yaml
# .github/workflows/build.yml
- name: Build FPGA
  run: vivado -mode batch -source build.tcl

- name: Check for errors
  run: |
    sawmill --ci --waivers .sawmill/waivers.toml build/vivado.log
```

### Use Case 2: Initial Log Triage

```bash
# Quick error check
sawmill vivado.log --severity error,critical

# See timing-related messages
sawmill vivado.log --category timing --format text

# Count by severity
sawmill vivado.log --format count
# Output: errors=0 critical=19 warnings=325 info=546
```

### Use Case 3: Generating Waivers

```bash
# First build - lots of warnings
sawmill --ci vivado.log
# Exit code: 1 (19 critical warnings)

# Review and generate waivers for acceptable ones
sawmill vivado.log --severity critical --format text
# ... review each one ...

# Generate waiver file
sawmill vivado.log --generate-waivers --severity critical > project.waivers.toml
# Edit file to remove waivers for issues that should be fixed

# Now CI passes
sawmill --ci --waivers project.waivers.toml vivado.log
# Exit code: 0
```

### Use Case 4: Creating a Plugin

```bash
# Create plugin script
cat > sawmill-plugin-vivado << 'EOF'
#!/usr/bin/env python3
import sys, json

if "--can-handle" in sys.argv:
    # Check if file looks like Vivado log
    with open(sys.argv[-1]) as f:
        content = f.read(1000)
    confidence = 0.9 if "Vivado v" in content else 0.0
    print(json.dumps({"confidence": confidence, "tool_name": "Xilinx Vivado"}))

elif "--get-filters" in sys.argv:
    print(json.dumps({
        "plugin_metadata": {"name": "vivado", "version": "1.0.0"},
        "filters": [
            {"id": "errors", "pattern": "^ERROR:", "severity": "error", "enabled_by_default": True},
            {"id": "timing", "pattern": "WNS|TNS|slack", "severity": "warning", "enabled_by_default": True}
        ]
    }))
EOF
chmod +x sawmill-plugin-vivado

# Test it
./sawmill-plugin-vivado --can-handle vivado.log
./sawmill-plugin-vivado --get-filters
```

### Use Case 5: Team Configuration Sharing

```bash
# Project structure
myproject/
├── .sawmill/
│   ├── config.toml      # Project-wide settings
│   └── waivers.toml     # Shared waivers
├── build/
│   └── vivado.log
└── ...

# Team members automatically get project config
cd myproject
sawmill build/vivado.log  # Uses .sawmill/config.toml
```

---

## Staged Implementation Plan

This section breaks down implementation into discrete, testable tasks. Each task is designed to:
- Fit within a single context window
- Have clear success criteria
- Include specific tests that must pass before proceeding
- Be implementable by an automated agent (ralph loop) without UX decisions

**Note:** TUI tasks (Stage 9) are marked as "Human-Guided" and should not be attempted by the ralph loop.

---

## Stage 1: Project Setup and Data Models

### Task 1.0: Test Infrastructure

**Objective:** Set up shared test fixtures and utilities for consistent testing.

**Deliverables:**
- `tests/conftest.py` with common fixtures
- Pytest markers for categorizing tests (slow, integration)
- Shared fixtures: `vivado_log`, `small_log`, `empty_log`, `large_log`, `sample_log_entries`

**Success Criteria:**
- [ ] `pytest --collect-only` shows fixtures available
- [ ] Fixtures work in other test files via import

**Tests:**
```python
# tests/conftest.py
"""Shared pytest fixtures for Sawmill tests."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def vivado_log(project_root):
    """Full Vivado log file for integration tests."""
    return project_root / "examples/vivado/vivado.log"


@pytest.fixture
def small_log(tmp_path):
    """Minimal multi-format log for unit tests."""
    content = """\
INFO: [Synth 8-6157] synthesizing module 'top' [/path/file.v:10]
WARNING: [Vivado 12-3523] Component name change
  Additional detail line
  Another detail line
CRITICAL WARNING: [Constraints 18-4427] Override warning
ERROR: [Route 35-9] Routing failed
Plain text line with no format
"""
    f = tmp_path / "test.log"
    f.write_text(content)
    return f


@pytest.fixture
def empty_log(tmp_path):
    """Empty log file."""
    f = tmp_path / "empty.log"
    f.write_text("")
    return f


@pytest.fixture
def large_log(tmp_path):
    """100k line log file for performance tests."""
    f = tmp_path / "large.log"
    lines = [f"INFO: [Test {i % 100}-{i}] Message number {i}" for i in range(100000)]
    f.write_text("\n".join(lines))
    return f


@pytest.fixture
def sample_log_entries():
    """Pre-built LogEntry objects for filter tests."""
    from sawmill.models.log_entry import LogEntry
    return [
        LogEntry(line_number=1, content="ERROR: [Test 1-1] error msg", raw_text="ERROR: [Test 1-1] error msg", severity="error"),
        LogEntry(line_number=2, content="WARNING: [Test 2-1] warning msg", raw_text="WARNING: [Test 2-1] warning msg", severity="warning"),
        LogEntry(line_number=3, content="CRITICAL WARNING: [Test 3-1] critical", raw_text="CRITICAL WARNING: [Test 3-1] critical", severity="critical"),
        LogEntry(line_number=4, content="INFO: [Test 4-1] info msg", raw_text="INFO: [Test 4-1] info msg", severity="info"),
        LogEntry(line_number=5, content="Plain text no format", raw_text="Plain text no format", severity=None),
    ]


# Pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
```

---

### Task 1.1: Project Scaffolding

**Objective:** Create the basic project structure with proper Python packaging.

**Deliverables:**
- Directory structure as defined in Technical Architecture
- Empty `__init__.py` files in all packages
- Basic `__main__.py` entry point with rich-click CLI skeleton

**Success Criteria:**
- [ ] `pip install -e .` succeeds
- [ ] `python -m sawmill --help` runs without errors
- [ ] All imports resolve correctly

**Tests:**
```python
# tests/test_project_setup.py
def test_package_imports():
    """All core packages should be importable."""
    import sawmill
    import sawmill.core
    import sawmill.tui
    import sawmill.models
    import sawmill.utils

def test_cli_entry_point():
    """CLI should respond to --help."""
    from click.testing import CliRunner
    from sawmill.__main__ import cli
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'sawmill' in result.output.lower()
```

---

### Task 1.2: LogEntry Data Model

**Objective:** Create the core data model for representing log lines.

**Deliverables:**
- `sawmill/models/log_entry.py` with `LogEntry` dataclass/Pydantic model
- Fields: `line_number`, `content`, `raw_text`, `timestamp` (optional), `severity` (optional)

**Success Criteria:**
- [ ] `LogEntry` can be instantiated with required fields
- [ ] Optional fields default to `None`
- [ ] Equality comparison works correctly
- [ ] String representation is readable

**Tests:**
```python
# tests/models/test_log_entry.py
def test_log_entry_creation():
    entry = LogEntry(line_number=1, content="Error: something failed", raw_text="Error: something failed")
    assert entry.line_number == 1
    assert entry.content == "Error: something failed"
    assert entry.severity is None

def test_log_entry_with_severity():
    entry = LogEntry(line_number=5, content="Warning: deprecated", raw_text="Warning: deprecated", severity="warning")
    assert entry.severity == "warning"

def test_log_entry_equality():
    e1 = LogEntry(line_number=1, content="test", raw_text="test")
    e2 = LogEntry(line_number=1, content="test", raw_text="test")
    assert e1 == e2
```

---

### Task 1.3: FilterDefinition Data Model

**Objective:** Create the data model for filter specifications.

**Deliverables:**
- `sawmill/models/filter_def.py` with `FilterDefinition` class
- Fields: `id`, `name`, `pattern`, `description`, `severity`, `enabled`, `category`, `source`
- Regex validation on `pattern` field

**Success Criteria:**
- [ ] Valid regex patterns are accepted
- [ ] Invalid regex patterns raise validation errors
- [ ] Filters can be enabled/disabled
- [ ] Source tracks where filter came from (builtin/plugin/user)

**Tests:**
```python
# tests/models/test_filter_def.py
def test_filter_creation():
    f = FilterDefinition(
        id="test-filter",
        name="Test Filter",
        pattern=r"Error:\s+\w+",
        enabled=True
    )
    assert f.id == "test-filter"
    assert f.enabled is True

def test_invalid_regex_rejected():
    with pytest.raises(ValidationError):
        FilterDefinition(
            id="bad",
            name="Bad",
            pattern=r"[invalid(regex",  # Unclosed bracket
            enabled=True
        )

def test_filter_toggle():
    f = FilterDefinition(id="t", name="T", pattern="test", enabled=True)
    f.enabled = False
    assert f.enabled is False

def test_filter_source_tracking():
    f = FilterDefinition(id="t", name="T", pattern="test", enabled=True, source="plugin:synopsys-dc")
    assert f.source == "plugin:synopsys-dc"

def test_redos_pattern_rejected():
    """Regex patterns known to cause ReDoS should be rejected."""
    with pytest.raises(ValidationError):
        FilterDefinition(
            id="bad",
            name="Bad",
            pattern=r"(a+)+$",  # Known ReDoS pattern
            enabled=True
        )
```

---

### Task 1.4: MessageGroup Data Model

**Objective:** Create the data model for multi-line message groups.

**Deliverables:**
- `MessageGroup` class in `sawmill/models/log_entry.py`
- Fields: `entries` (list of LogEntry), `start_line`, `end_line`, `primary_severity`
- Methods: `full_text()`, `matches_filter(pattern)`

**Success Criteria:**
- [ ] MessageGroup correctly aggregates multiple LogEntry objects
- [ ] `full_text()` returns concatenated content
- [ ] `matches_filter()` searches across all lines in group

**Tests:**
```python
# tests/models/test_message_group.py
def test_message_group_creation():
    entries = [
        LogEntry(line_number=1, content="Error: main", raw_text="Error: main"),
        LogEntry(line_number=2, content="  detail 1", raw_text="  detail 1"),
        LogEntry(line_number=3, content="  detail 2", raw_text="  detail 2"),
    ]
    group = MessageGroup(entries=entries)
    assert group.start_line == 1
    assert group.end_line == 3
    assert len(group.entries) == 3

def test_message_group_full_text():
    entries = [
        LogEntry(line_number=1, content="Line 1", raw_text="Line 1"),
        LogEntry(line_number=2, content="Line 2", raw_text="Line 2"),
    ]
    group = MessageGroup(entries=entries)
    assert "Line 1" in group.full_text()
    assert "Line 2" in group.full_text()

def test_message_group_matches_filter():
    entries = [
        LogEntry(line_number=1, content="Error: timing violation", raw_text="Error: timing violation"),
        LogEntry(line_number=2, content="  slack: -0.5ns", raw_text="  slack: -0.5ns"),
    ]
    group = MessageGroup(entries=entries)
    assert group.matches_filter(r"slack.*-\d+\.\d+") is True
    assert group.matches_filter(r"DRC violation") is False
```

---

## Stage 2: Core Log Parsing

### Task 2.1: Basic Log File Loader

**Objective:** Implement efficient log file loading with lazy evaluation for large files.

**Deliverables:**
- `sawmill/core/parser.py` with `LogParser` class
- Method: `load_file(path) -> List[LogEntry]`
- Support for files up to 100k+ lines
- Proper encoding handling (UTF-8 with fallback)

**Success Criteria:**
- [ ] Can load a 100k line file in under 2 seconds
- [ ] Handles UTF-8 and Latin-1 encoded files
- [ ] Returns correct line numbers
- [ ] Handles empty files gracefully

**Tests:**
```python
# tests/core/test_parser.py
def test_load_simple_file(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("Line 1\nLine 2\nLine 3\n")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert len(entries) == 3
    assert entries[0].line_number == 1
    assert entries[0].content == "Line 1"

def test_load_empty_file(tmp_path):
    log_file = tmp_path / "empty.log"
    log_file.write_text("")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert len(entries) == 0

def test_load_large_file(tmp_path):
    """Performance test: 100k lines should load quickly."""
    log_file = tmp_path / "large.log"
    log_file.write_text("\n".join(f"Line {i}" for i in range(100000)))

    parser = LogParser()
    import time
    start = time.time()
    entries = parser.load_file(log_file)
    elapsed = time.time() - start

    assert len(entries) == 100000
    assert elapsed < 2.0  # Must complete in under 2 seconds

def test_load_utf8_file(tmp_path):
    log_file = tmp_path / "utf8.log"
    log_file.write_text("Error: Invalid character \u2603\n", encoding="utf-8")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert "\u2603" in entries[0].content

def test_load_binary_file_gracefully(tmp_path):
    """Binary files should fail with clear error, not crash."""
    from sawmill.core.parser import LogParseError

    binary_file = tmp_path / "binary.log"
    binary_file.write_bytes(b'\x00\x01\x02\xff\xfe')

    parser = LogParser()
    with pytest.raises(LogParseError) as exc:
        parser.load_file(binary_file)
    assert "binary" in str(exc.value).lower() or "decode" in str(exc.value).lower()

def test_load_nonexistent_file():
    """Missing file should raise FileNotFoundError."""
    parser = LogParser()
    with pytest.raises(FileNotFoundError):
        parser.load_file(Path("/nonexistent/file.log"))
```

---

### Task 2.2: Message Boundary Detection

**Objective:** Implement pattern-based detection of message boundaries.

**Deliverables:**
- `MessageBoundary` dataclass with `start_pattern`, `continuation_pattern`, `max_lines`
- Method: `LogParser.detect_boundaries(entries, boundary_rules) -> List[MessageGroup]`

**Success Criteria:**
- [ ] Correctly identifies message start lines
- [ ] Groups continuation lines with their parent
- [ ] Respects `max_lines` limit
- [ ] Handles overlapping boundary patterns

**Tests:**
```python
# tests/core/test_parser_boundaries.py
def test_simple_error_grouping():
    """Error with indented continuation lines."""
    entries = [
        LogEntry(1, "Error: main error", "Error: main error"),
        LogEntry(2, "  detail line 1", "  detail line 1"),
        LogEntry(3, "  detail line 2", "  detail line 2"),
        LogEntry(4, "Info: next message", "Info: next message"),
    ]
    boundary = MessageBoundary(
        start_pattern=r"^(Error|Warning|Info):",
        continuation_pattern=r"^\s+",
        max_lines=10
    )

    parser = LogParser()
    groups = parser.detect_boundaries(entries, [boundary])

    assert len(groups) == 2
    assert len(groups[0].entries) == 3  # Error + 2 details
    assert len(groups[1].entries) == 1  # Info alone

def test_max_lines_limit():
    """Continuation should stop at max_lines."""
    entries = [LogEntry(i, f"  line {i}" if i > 1 else "Error: start", f"  line {i}" if i > 1 else "Error: start")
               for i in range(1, 20)]
    boundary = MessageBoundary(
        start_pattern=r"^Error:",
        continuation_pattern=r"^\s+",
        max_lines=5
    )

    parser = LogParser()
    groups = parser.detect_boundaries(entries, [boundary])

    assert len(groups[0].entries) == 5  # Limited to max_lines

def test_no_boundaries_single_line_groups():
    """Without boundaries, each line is its own group."""
    entries = [
        LogEntry(1, "Line 1", "Line 1"),
        LogEntry(2, "Line 2", "Line 2"),
    ]

    parser = LogParser()
    groups = parser.detect_boundaries(entries, [])

    assert len(groups) == 2
    assert len(groups[0].entries) == 1
```

---

### Task 2.3: Basic Severity Detection

**Objective:** Add regex-based severity extraction to LogParser for common patterns. This breaks the CLI→Plugin circular dependency by providing basic severity detection before plugins are loaded.

**Deliverables:**
- Add `severity` field population to `LogParser.load_file()`
- Support common patterns: `^ERROR:`, `^WARNING:`, `^CRITICAL WARNING:`, `^INFO:`
- Plugins can override via `parse_message()` hook later

**Success Criteria:**
- [ ] LogEntry.severity populated for standard message formats
- [ ] Unknown formats get severity=None (not an error)
- [ ] Case-insensitive matching for severity keywords

**Tests:**
```python
# tests/core/test_parser_severity.py
from pathlib import Path

def test_severity_detection_error(tmp_path):
    """ERROR: lines should have severity='error'."""
    log_file = tmp_path / "test.log"
    log_file.write_text("ERROR: [Test 1-1] something failed\nINFO: normal\n")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert entries[0].severity == "error"
    assert entries[1].severity == "info"

def test_severity_detection_critical_warning(tmp_path):
    """CRITICAL WARNING: should have severity='critical_warning'."""
    log_file = tmp_path / "test.log"
    log_file.write_text("CRITICAL WARNING: [Test 1-1] important\n")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert entries[0].severity == "critical_warning"

def test_severity_detection_unknown_format(tmp_path):
    """Unknown formats should have severity=None."""
    log_file = tmp_path / "test.log"
    log_file.write_text("Some random log line\nAnother plain line\n")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert all(e.severity is None for e in entries)

def test_severity_detection_case_insensitive(tmp_path):
    """Severity detection should be case-insensitive."""
    log_file = tmp_path / "test.log"
    log_file.write_text("error: lowercase\nERROR: uppercase\nError: mixed\n")

    parser = LogParser()
    entries = parser.load_file(log_file)

    assert all(e.severity == "error" for e in entries)
```

---

## Stage 3: Filter Engine

### Task 3.1: Basic Regex Filter Engine

**Objective:** Implement the core filtering logic.

**Deliverables:**
- `sawmill/core/filter.py` with `FilterEngine` class
- Method: `apply_filter(pattern, entries) -> List[LogEntry]`
- Method: `apply_filters(filters, groups, mode='AND'|'OR') -> List[MessageGroup]`

**Success Criteria:**
- [ ] Single filter correctly matches entries
- [ ] AND mode requires all filters to match
- [ ] OR mode requires any filter to match
- [ ] Invalid regex returns empty results with error flag

**Tests:**
```python
# tests/core/test_filter.py
def test_single_filter_match():
    entries = [
        LogEntry(1, "Error: test", "Error: test"),
        LogEntry(2, "Info: test", "Info: test"),
        LogEntry(3, "Error: another", "Error: another"),
    ]
    engine = FilterEngine()
    results = engine.apply_filter(r"^Error:", entries)

    assert len(results) == 2
    assert all("Error:" in e.content for e in results)

def test_filter_case_insensitive():
    entries = [
        LogEntry(1, "ERROR: test", "ERROR: test"),
        LogEntry(2, "error: test", "error: test"),
    ]
    engine = FilterEngine()
    results = engine.apply_filter(r"error:", entries, case_sensitive=False)

    assert len(results) == 2

def test_multiple_filters_and_mode():
    groups = [
        MessageGroup([LogEntry(1, "Error: timing slack -0.5", "Error: timing slack -0.5")]),
        MessageGroup([LogEntry(2, "Error: DRC violation", "Error: DRC violation")]),
        MessageGroup([LogEntry(3, "Warning: timing slack -0.2", "Warning: timing slack -0.2")]),
    ]
    filters = [
        FilterDefinition(id="1", name="Errors", pattern=r"^Error:", enabled=True),
        FilterDefinition(id="2", name="Timing", pattern=r"timing", enabled=True),
    ]

    engine = FilterEngine()
    results = engine.apply_filters(filters, groups, mode='AND')

    assert len(results) == 1  # Only first matches both

def test_multiple_filters_or_mode():
    groups = [
        MessageGroup([LogEntry(1, "Error: timing", "Error: timing")]),
        MessageGroup([LogEntry(2, "Error: DRC", "Error: DRC")]),
        MessageGroup([LogEntry(3, "Info: done", "Info: done")]),
    ]
    filters = [
        FilterDefinition(id="1", name="Timing", pattern=r"timing", enabled=True),
        FilterDefinition(id="2", name="DRC", pattern=r"DRC", enabled=True),
    ]

    engine = FilterEngine()
    results = engine.apply_filters(filters, groups, mode='OR')

    assert len(results) == 2  # First two match

def test_disabled_filters_ignored():
    groups = [MessageGroup([LogEntry(1, "Error: test", "Error: test")])]
    filters = [
        FilterDefinition(id="1", name="Disabled", pattern=r"Error", enabled=False),
    ]

    engine = FilterEngine()
    results = engine.apply_filters(filters, groups, mode='AND')

    assert len(results) == 1  # Disabled filter doesn't restrict
```

---

### Task 3.2: Filter Statistics

**Objective:** Track and report filter match statistics.

**Deliverables:**
- `FilterStats` dataclass with `total_lines`, `matched_lines`, `match_percentage`
- Method: `FilterEngine.get_stats(filters, groups) -> FilterStats`
- Per-filter match counts

**Success Criteria:**
- [ ] Correctly counts total and matched lines
- [ ] Calculates accurate percentages
- [ ] Provides per-filter breakdown

**Tests:**
```python
# tests/core/test_filter_stats.py
def test_basic_stats():
    # Create 100 lines: Line 0 through Line 99
    groups = [MessageGroup([LogEntry(i, f"Line {i}", f"Line {i}")]) for i in range(100)]
    # Pattern matches lines ending in 0,2,4,6,8 (all even numbers)
    # That's: 0,2,4,6,8,10,12,...98 = 50 total matches
    filters = [FilterDefinition(id="1", name="Even", pattern=r"Line [02468]$", enabled=True)]

    engine = FilterEngine()
    stats = engine.get_stats(filters, groups)

    assert stats.total_lines == 100
    assert stats.matched_lines == 50  # All even numbers: 0,2,4,...98

def test_stats_percentage():
    groups = [MessageGroup([LogEntry(i, "Match" if i < 25 else "NoMatch", "...")]) for i in range(100)]
    filters = [FilterDefinition(id="1", name="Match", pattern=r"^Match$", enabled=True)]

    engine = FilterEngine()
    stats = engine.get_stats(filters, groups)

    assert stats.match_percentage == 25.0

def test_per_filter_stats():
    groups = [
        MessageGroup([LogEntry(1, "Error: test", "Error: test")]),
        MessageGroup([LogEntry(2, "Warning: test", "Warning: test")]),
        MessageGroup([LogEntry(3, "Info: test", "Info: test")]),
    ]
    filters = [
        FilterDefinition(id="errors", name="Errors", pattern=r"^Error:", enabled=True),
        FilterDefinition(id="warnings", name="Warnings", pattern=r"^Warning:", enabled=True),
    ]

    engine = FilterEngine()
    stats = engine.get_stats(filters, groups)

    assert stats.per_filter["errors"] == 1
    assert stats.per_filter["warnings"] == 1
```

---

## Stage 4: CLI Streaming Interface

### Task 4.1: Basic CLI with Stdout Output

**Objective:** Create a CLI that reads a log file and streams filtered output to stdout.

**Deliverables:**
- `sawmill/cli.py` with main CLI using rich-click
- Accept log file as positional argument
- `--severity` option to filter by severity level
- `--filter` option for regex pattern
- Stream matching lines to stdout with Rich formatting

**Success Criteria:**
- [ ] `sawmill logfile.log` prints all lines
- [ ] `sawmill logfile.log --severity error` filters to errors only
- [ ] `sawmill logfile.log --filter "pattern"` filters by regex
- [ ] Output is colorized based on severity

**Tests:**
```python
# tests/test_cli.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_cli_basic_output(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("INFO: [Test 1-1] message\nERROR: [Test 2-1] error\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file)])

    assert result.exit_code == 0
    assert "INFO:" in result.output
    assert "ERROR:" in result.output

def test_cli_severity_filter(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("INFO: info\nWARNING: warn\nERROR: error\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--severity', 'error'])

    assert result.exit_code == 0
    assert "ERROR:" in result.output
    assert "INFO:" not in result.output

def test_cli_regex_filter(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("timing slack -0.5\nDRC violation\ntiming slack -0.2\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--filter', 'timing'])

    assert result.exit_code == 0
    assert "timing" in result.output
    assert "DRC" not in result.output
```

---

### Task 4.2: Output Formats

**Objective:** Support multiple output formats (text, JSON, count).

**Deliverables:**
- `--format` option with choices: text, json, count
- Text format: human-readable with colors (default)
- JSON format: one JSON object per line (JSONL)
- Count format: summary statistics only

**Success Criteria:**
- [ ] `--format text` outputs colored, readable text
- [ ] `--format json` outputs valid JSONL
- [ ] `--format count` outputs summary: `errors=N warnings=M info=K`

**Tests:**
```python
# tests/test_cli_formats.py
import json

def test_json_format(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("ERROR: [Test 1-1] message\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--format', 'json'])

    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data['severity'] == 'error'
    assert 'message' in data

def test_count_format(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("ERROR: e1\nERROR: e2\nWARNING: w1\nINFO: i1\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--format', 'count'])

    assert result.exit_code == 0
    assert "error=2" in result.output.lower()
    assert "warning=1" in result.output.lower()
```

---

### Task 4.3: Message ID Filtering

**Objective:** Support filtering by Vivado-style message IDs.

**Deliverables:**
- `--id` option to filter by message ID pattern
- Support wildcards: `--id "Synth 8-*"` matches all Synth 8-xxxx
- `--category` option for high-level categories (timing, synthesis, etc.)

**Success Criteria:**
- [ ] `--id "Vivado 12-3523"` matches exact ID
- [ ] `--id "Synth 8-*"` matches all Synth 8-xxxx messages
- [ ] `--category timing` matches timing-related messages

**Tests:**
```python
# tests/test_cli_id_filter.py
def test_exact_id_filter(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("WARNING: [Vivado 12-3523] msg1\nWARNING: [Vivado 12-4739] msg2\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--id', 'Vivado 12-3523'])

    assert "12-3523" in result.output
    assert "12-4739" not in result.output

def test_wildcard_id_filter(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("INFO: [Synth 8-6157] a\nINFO: [Synth 8-6155] b\nINFO: [Vivado 12-1] c\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--id', 'Synth 8-*'])

    assert "8-6157" in result.output
    assert "8-6155" in result.output
    assert "Vivado" not in result.output
```

---

### Task 4.4: CLI Integration Tests

**Objective:** Verify full pipeline works end-to-end with real Vivado logs.

**Deliverables:**
- Integration tests using `examples/vivado/vivado.log`
- Test full pipeline: load → parse → group → filter → format
- Verify counts match analyzed values from `PATTERNS.md`

**Success Criteria:**
- [ ] Full pipeline executes without error
- [ ] Output matches expected format
- [ ] All filter options work together correctly

**Tests:**
```python
# tests/test_cli_integration.py
from pathlib import Path
import pytest

@pytest.mark.integration
def test_vivado_log_loads_successfully(vivado_log):
    """Full Vivado log should load and process without errors."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(vivado_log), '--format', 'count'])

    assert result.exit_code == 0
    assert "error" in result.output.lower() or "warning" in result.output.lower()

@pytest.mark.integration
def test_vivado_severity_filter(vivado_log):
    """Severity filtering should work on real Vivado logs."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(vivado_log), '--severity', 'error,critical'])

    assert result.exit_code == 0
    # Should not contain INFO messages
    assert "INFO:" not in result.output

@pytest.mark.integration
def test_vivado_combined_filters(vivado_log):
    """Multiple filters should work together."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        str(vivado_log),
        '--severity', 'warning',
        '--filter', 'timing',
        '--format', 'count'
    ])

    assert result.exit_code == 0

@pytest.mark.integration
def test_pipeline_parser_to_filter_to_output(small_log):
    """Test complete pipeline from parsing to output."""
    runner = CliRunner()

    # Test text output
    result = runner.invoke(cli, [str(small_log), '--format', 'text'])
    assert result.exit_code == 0

    # Test JSON output
    result = runner.invoke(cli, [str(small_log), '--format', 'json'])
    assert result.exit_code == 0

    # Test count output
    result = runner.invoke(cli, [str(small_log), '--format', 'count'])
    assert result.exit_code == 0
```

---

## Stage 5: Plugin System

### Task 5.1: Plugin Hook Specification

**Objective:** Define the pluggy hook specification for sawmill plugins.

**Deliverables:**
- `sawmill/plugin/__init__.py` with hook markers and base class
- `sawmill/plugin/hookspec.py` with `SawmillHookSpec` class
- All hook definitions with proper signatures

**Success Criteria:**
- [ ] Hook specification defines all required hooks
- [ ] `hookimpl` decorator available for plugins
- [ ] `SawmillPlugin` base class provides sensible defaults

**Tests:**
```python
# tests/plugin/test_hookspec.py
from pathlib import Path
from sawmill.plugin import SawmillPlugin, hookimpl, SawmillHookSpec

def test_hookspec_defines_required_hooks():
    spec = SawmillHookSpec()
    assert hasattr(spec, 'can_handle')
    assert hasattr(spec, 'get_filters')
    assert hasattr(spec, 'get_message_boundaries')
    assert hasattr(spec, 'parse_message')

def test_base_plugin_has_defaults():
    class TestPlugin(SawmillPlugin):
        name = "test"

    plugin = TestPlugin()
    # Default implementations should not crash
    assert plugin.can_handle(Path("test.log"), "content") == 0.0
    assert plugin.get_filters() == []
```

---

### Task 5.2: Plugin Manager with Entry Point Discovery

**Objective:** Implement plugin discovery via Python entry points.

**Deliverables:**
- `sawmill/core/plugin.py` with `PluginManager` class
- Discovery via `importlib.metadata.entry_points`
- Plugin registration with pluggy

**Success Criteria:**
- [ ] Discovers plugins from `sawmill.plugins` entry point group
- [ ] Registers plugins with pluggy PluginManager
- [ ] Lists available plugins with metadata

**Tests:**
```python
# tests/core/test_plugin_manager.py
from pathlib import Path
import pluggy
from sawmill.core.plugin import PluginManager
from sawmill.plugin import SawmillPlugin, hookimpl

class MockPlugin(SawmillPlugin):
    name = "mock"
    version = "1.0.0"

    @hookimpl
    def can_handle(self, path, content):
        return 0.9 if "MOCK" in content else 0.0

    @hookimpl
    def get_filters(self):
        return [FilterDefinition(id="mock", name="Mock", pattern="MOCK", enabled=True)]

def test_register_plugin():
    manager = PluginManager()
    manager.register(MockPlugin())

    assert "mock" in manager.list_plugins()

def test_plugin_hooks_called():
    manager = PluginManager()
    manager.register(MockPlugin())

    results = manager.pm.hook.can_handle(path=Path("test.log"), content="MOCK content")
    assert 0.9 in results
```

---

### Task 5.3: Auto-Detection and Plugin Integration

**Objective:** Automatically detect log type and apply plugin hooks.

**Deliverables:**
- Method: `PluginManager.auto_detect(path) -> Optional[str]`
- Method: `PluginManager.get_active_filters() -> List[FilterDefinition]`
- CLI option: `--plugin <name>` to force specific plugin

**Success Criteria:**
- [ ] Selects plugin with highest confidence score
- [ ] Returns None if no plugin has confidence > threshold (0.5)
- [ ] **Errors if >1 plugin has confidence > 0.5** (conflict resolution)
- [ ] `--plugin vivado` forces Vivado plugin (bypasses auto-detect)
- [ ] Aggregates filters from active plugin

**Tests:**
```python
# tests/core/test_plugin_autodetect.py
from pathlib import Path
from sawmill.core.plugin import PluginConflictError, PluginManager
from sawmill.plugin import SawmillPlugin, hookimpl

def test_auto_detect_selects_highest_confidence():
    manager = PluginManager()

    class LowPlugin(SawmillPlugin):
        name = "low"
        @hookimpl
        def can_handle(self, path, content):
            return 0.3

    class HighPlugin(SawmillPlugin):
        name = "high"
        @hookimpl
        def can_handle(self, path, content):
            return 0.9

    manager.register(LowPlugin())
    manager.register(HighPlugin())

    selected = manager.auto_detect(Path("test.log"), "content")
    assert selected == "high"

def test_auto_detect_returns_none_below_threshold():
    manager = PluginManager()

    class WeakPlugin(SawmillPlugin):
        name = "weak"
        @hookimpl
        def can_handle(self, path, content):
            return 0.2

    manager.register(WeakPlugin())

    selected = manager.auto_detect(Path("test.log"), "content")
    assert selected is None

def test_auto_detect_errors_on_conflict():
    """If multiple plugins both return >0.5, raise error."""
    manager = PluginManager()

    class PluginA(SawmillPlugin):
        name = "plugin_a"
        @hookimpl
        def can_handle(self, path, content):
            return 0.8

    class PluginB(SawmillPlugin):
        name = "plugin_b"
        @hookimpl
        def can_handle(self, path, content):
            return 0.75

    manager.register(PluginA())
    manager.register(PluginB())

    with pytest.raises(PluginConflictError) as exc:
        manager.auto_detect(Path("test.log"), "content")
    assert "plugin_a" in str(exc.value) or "plugin_b" in str(exc.value)

def test_cli_plugin_option(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("INFO: test")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado'])

    assert result.exit_code == 0
```

---

### Task 5.4: Built-in Vivado Plugin

**Objective:** Create the reference Vivado plugin as a built-in.

**Deliverables:**
- `sawmill/plugins/vivado.py` with `VivadoPlugin` class
- All hooks implemented for Vivado log format
- Register as built-in plugin (not via entry point)

**Success Criteria:**
- [ ] Detects Vivado logs with high confidence
- [ ] Provides comprehensive filter set
- [ ] Parses Vivado message format correctly
- [ ] Extracts file references from messages

**Tests:**
```python
# tests/plugins/test_vivado.py
from pathlib import Path
from sawmill.plugins.vivado import VivadoPlugin

def test_vivado_detects_vivado_logs():
    plugin = VivadoPlugin()
    content = "# Vivado v2025.2 (64-bit)\nINFO: [Synth 8-6157] test"

    confidence = plugin.can_handle(Path("vivado.log"), content)
    assert confidence >= 0.9

def test_vivado_does_not_detect_other_logs():
    plugin = VivadoPlugin()
    content = "Some random log file content"

    confidence = plugin.can_handle(Path("other.log"), content)
    assert confidence < 0.5

def test_vivado_parses_message_format():
    plugin = VivadoPlugin()

    result = plugin.parse_message("WARNING: [Vivado 12-3523] Component name change")

    assert result is not None
    assert result.severity == "warning"
    assert result.message_id == "Vivado 12-3523"
    assert "Component name" in result.content

def test_vivado_parses_critical_warning():
    plugin = VivadoPlugin()

    result = plugin.parse_message("CRITICAL WARNING: [Constraints 18-4427] Override warning")

    assert result is not None
    assert result.severity == "critical_warning"
    assert result.message_id == "Constraints 18-4427"

def test_vivado_extracts_file_reference():
    plugin = VivadoPlugin()

    ref = plugin.extract_file_reference("synthesizing module 'top' [/path/to/file.v:53]")

    assert ref is not None
    assert ref.path == "/path/to/file.v"
    assert ref.line == 53

def test_vivado_filters_cover_common_cases(example_vivado_log):
    plugin = VivadoPlugin()
    filters = plugin.get_filters()

    filter_ids = [f.id for f in filters]
    assert "errors" in filter_ids
    assert "critical-warnings" in filter_ids
    assert "warnings" in filter_ids
    assert "timing-failures" in filter_ids
```

---

### Task 5.5: Plugin Discovery CLI

**Objective:** Implement CLI commands for plugin discovery and introspection.

**Deliverables:**
- `--list-plugins` option to enumerate discovered plugins
- `--show-info` option (with `--plugin`) to display plugin capabilities
- Show: version, hooks implemented, categories, filter counts

**Success Criteria:**
- [ ] `sawmill --list-plugins` shows all installed plugins
- [ ] `sawmill --plugin vivado --show-info` shows Vivado plugin details
- [ ] Output includes plugin version and implemented hooks

**Tests:**
```python
# tests/test_cli_plugin_discovery.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_list_plugins():
    """--list-plugins should enumerate all plugins."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--list-plugins'])

    assert result.exit_code == 0
    assert "vivado" in result.output.lower()

def test_show_plugin_info():
    """--show-info should display plugin capabilities."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--plugin', 'vivado', '--show-info'])

    assert result.exit_code == 0
    assert "vivado" in result.output.lower()
    assert "version" in result.output.lower() or "1.0" in result.output

def test_show_info_requires_plugin():
    """--show-info without --plugin should error."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--show-info'])

    # Should fail or provide helpful message
    assert result.exit_code != 0 or "plugin" in result.output.lower()

def test_list_plugins_shows_metadata():
    """Plugin list should include basic metadata."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--list-plugins'])

    assert result.exit_code == 0
    # Should show at least name and possibly version
    assert "vivado" in result.output.lower()
```

---

## Stage 6: Configuration System

### Task 6.1: TOML Configuration Loader

**Objective:** Implement configuration file parsing.

**Deliverables:**
- `sawmill/core/config.py` with `ConfigLoader` class
- `Config` dataclass with all settings
- Parse and validate TOML configuration

**Success Criteria:**
- [ ] Parses valid TOML files correctly
- [ ] Returns sensible defaults for missing keys
- [ ] Handles malformed TOML with clear errors

**Tests:**
```python
# tests/core/test_config.py
def test_load_basic_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[general]
default_severity = ["error", "critical"]

[output]
color = true
format = "text"
''')

    loader = ConfigLoader()
    config = loader.load(config_file)

    assert config.general.default_severity == ["error", "critical"]
    assert config.output.color is True

def test_default_values():
    loader = ConfigLoader()
    config = loader.load(None)  # No file

    assert config.output.format == "text"  # default
    assert config.output.color is True  # default

def test_malformed_toml_error_message(tmp_path):
    """Malformed TOML should give line number in error."""
    from sawmill.core.config import ConfigError

    bad_config = tmp_path / "bad.toml"
    bad_config.write_text('[section\nkey = "unclosed')

    loader = ConfigLoader()
    with pytest.raises(ConfigError) as exc:
        loader.load(bad_config)
    assert "line" in str(exc.value).lower()
```

---

### Task 6.2: Configuration Discovery and Merging

**Objective:** Implement hierarchical configuration discovery and merging.

**Deliverables:**
- Method: `ConfigLoader.discover_configs(start_path) -> List[Path]`
- Method: `ConfigLoader.merge_configs(configs) -> Config`
- Precedence: CLI > local > git root > user > defaults
- `sawmill/utils/git.py` with `find_git_root()` function

**Git Detection Requirements:**
The `sawmill/utils/git.py` module should:
1. Find git root by walking up from current directory looking for `.git/`
2. Return `None` if not in a git repo (don't error)
3. Work with both git directories and git worktrees
4. Be fast (cache result for session)
5. Support `SAWMILL_GIT_ROOT` env var override for submodules/bare repos

**Success Criteria:**
- [ ] Finds configs in correct precedence order
- [ ] Later configs override earlier values
- [ ] Unspecified values fall through
- [ ] Git root detection works correctly

**Tests:**
```python
# tests/core/test_config_discovery.py
def test_precedence_order(tmp_path, monkeypatch):
    # Local config
    (tmp_path / "sawmill.toml").write_text('[output]\nformat = "json"\n')

    # User config
    user_config = tmp_path / ".config" / "sawmill"
    user_config.mkdir(parents=True)
    (user_config / "config.toml").write_text('[output]\nformat = "text"\ncolor = false\n')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    loader = ConfigLoader()
    config = loader.load_merged(tmp_path)

    assert config.output.format == "json"  # local overrides user
    assert config.output.color is False  # from user config

# tests/utils/test_git.py
def test_find_git_root_in_repo(tmp_path, monkeypatch):
    """Should find .git directory."""
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "deep"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    from sawmill.utils.git import find_git_root
    assert find_git_root() == tmp_path

def test_find_git_root_not_in_repo(tmp_path, monkeypatch):
    """Should return None outside git repo."""
    monkeypatch.chdir(tmp_path)

    from sawmill.utils.git import find_git_root
    assert find_git_root() is None

def test_git_root_env_override(tmp_path, monkeypatch):
    """SAWMILL_GIT_ROOT should override detection."""
    override_path = tmp_path / "override"
    override_path.mkdir()
    monkeypatch.setenv("SAWMILL_GIT_ROOT", str(override_path))

    from sawmill.utils.git import find_git_root
    assert find_git_root() == override_path
```

---

## Stage 7: Waiver System

### Task 7.1: Waiver Data Model and Parser

**Objective:** Define waiver data structures and parse waiver files.

**Deliverables:**
- `sawmill/models/waiver.py` with `Waiver`, `WaiverFile` classes
- `sawmill/core/waiver.py` with `WaiverLoader` class
- Support all waiver types: id, pattern, file, hash

**Success Criteria:**
- [ ] Parse valid waiver TOML files
- [ ] Validate waiver entries (required fields, valid patterns)
- [ ] Handle malformed waiver files with clear errors

**Tests:**
```python
# tests/models/test_waiver.py
def test_parse_waiver_file(tmp_path):
    waiver_file = tmp_path / "waivers.toml"
    waiver_file.write_text('''
[metadata]
tool = "vivado"

[[waiver]]
type = "id"
pattern = "Vivado 12-3523"
reason = "Intentional"
author = "test"
date = "2026-01-18"
''')

    loader = WaiverLoader()
    waivers = loader.load(waiver_file)

    assert len(waivers.waivers) == 1
    assert waivers.waivers[0].type == "id"
    assert waivers.waivers[0].pattern == "Vivado 12-3523"

def test_invalid_waiver_rejected(tmp_path):
    waiver_file = tmp_path / "bad.toml"
    waiver_file.write_text('''
[[waiver]]
type = "id"
# Missing required fields: pattern, reason
''')

    loader = WaiverLoader()
    with pytest.raises(WaiverValidationError):
        loader.load(waiver_file)
```

---

### Task 7.2: Waiver Matching Engine

**Objective:** Implement waiver matching against log messages.

**Deliverables:**
- `sawmill/core/waiver.py` with `WaiverMatcher` class
- Method: `is_waived(message, waivers) -> Optional[Waiver]`
- Support all match types with correct priority

**Success Criteria:**
- [ ] ID patterns match message IDs
- [ ] Regex patterns match message content
- [ ] File patterns match source file paths
- [ ] Hash matches exact message content
- [ ] Priority order: hash > id > pattern > file

**Tests:**
```python
# tests/core/test_waiver_matching.py
def test_id_match():
    waiver = Waiver(type="id", pattern="Vivado 12-3523", reason="test")
    message = LogEntry(1, "WARNING: [Vivado 12-3523] some message", "...")

    matcher = WaiverMatcher([waiver])
    result = matcher.is_waived(message)

    assert result == waiver

def test_pattern_match():
    waiver = Waiver(type="pattern", pattern="usb_fifo_clk", reason="async clock")
    message = LogEntry(1, "WARNING: set_input_delay usb_fifo_clk", "...")

    matcher = WaiverMatcher([waiver])
    result = matcher.is_waived(message)

    assert result == waiver

def test_no_match_returns_none():
    waiver = Waiver(type="id", pattern="Vivado 12-9999", reason="test")
    message = LogEntry(1, "WARNING: [Vivado 12-3523] different", "...")

    matcher = WaiverMatcher([waiver])
    result = matcher.is_waived(message)

    assert result is None
```

---

### Task 7.3: Waiver Generation

**Objective:** Generate waiver file from current log messages.

**Deliverables:**
- CLI option: `--generate-waivers`
- Output valid waiver TOML to stdout
- Include message metadata for review

**Success Criteria:**
- [ ] Generates valid TOML waiver file
- [ ] Includes all unwaived errors/warnings
- [ ] User can redirect to file: `sawmill log --generate-waivers > waivers.toml`

**Tests:**
```python
# tests/test_waiver_generation.py
def test_generate_waivers(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("ERROR: [Test 1-1] error message\nWARNING: [Test 2-1] warning\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--generate-waivers'])

    assert result.exit_code == 0
    assert "[[waiver]]" in result.output
    assert "Test 1-1" in result.output

    # Output should be valid TOML
    import tomli
    parsed = tomli.loads(result.output)
    assert len(parsed['waiver']) == 2
```

---

## Stage 8: CI Mode

### Task 8.1: Exit Code Logic

**Objective:** Implement CI mode with pass/fail exit codes.

**Deliverables:**
- CLI option: `--ci` to enable CI mode
- Exit 0 if no errors/critical warnings
- Exit 1 if errors or critical warnings present
- `--strict` to also fail on regular warnings

**Success Criteria:**
- [ ] `sawmill --ci log` exits 0 on clean log
- [ ] `sawmill --ci log` exits 1 on errors
- [ ] `sawmill --ci --strict log` exits 1 on warnings

**Tests:**
```python
# tests/test_ci_mode.py
def test_ci_pass_on_clean_log(tmp_path):
    log_file = tmp_path / "clean.log"
    log_file.write_text("INFO: all good\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', str(log_file)])

    assert result.exit_code == 0

def test_ci_fail_on_error(tmp_path):
    log_file = tmp_path / "errors.log"
    log_file.write_text("ERROR: [Test 1-1] something failed\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', str(log_file)])

    assert result.exit_code == 1

def test_ci_fail_on_critical_warning(tmp_path):
    log_file = tmp_path / "critical.log"
    log_file.write_text("CRITICAL WARNING: [Test 1-1] important\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', str(log_file)])

    assert result.exit_code == 1

def test_ci_strict_fails_on_warning(tmp_path):
    log_file = tmp_path / "warnings.log"
    log_file.write_text("WARNING: [Test 1-1] minor issue\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--strict', str(log_file)])

    assert result.exit_code == 1
```

---

### Task 8.2: Waiver Integration in CI

**Objective:** Apply waivers in CI mode to ignore accepted issues.

**Deliverables:**
- CLI option: `--waivers <file>` to load waiver file
- Waived messages don't count toward failure
- `--show-waived` to display what was waived
- `--report-unused` to find stale waivers

**Success Criteria:**
- [ ] Waived errors don't cause CI failure
- [ ] `--show-waived` lists waived messages
- [ ] `--report-unused` identifies waivers that didn't match anything

**Tests:**
```python
# tests/test_ci_waivers.py
def test_ci_pass_with_waiver(tmp_path):
    log_file = tmp_path / "errors.log"
    log_file.write_text("ERROR: [Test 1-1] known issue\n")

    waiver_file = tmp_path / "waivers.toml"
    waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--waivers', str(waiver_file), str(log_file)])

    assert result.exit_code == 0

def test_show_waived(tmp_path):
    log_file = tmp_path / "errors.log"
    log_file.write_text("ERROR: [Test 1-1] known issue\n")

    waiver_file = tmp_path / "waivers.toml"
    waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--waivers', str(waiver_file), '--show-waived', str(log_file)])

    assert "waived" in result.output.lower()
    assert "Test 1-1" in result.output
```

---

### Task 8.3: CI Summary Report

**Objective:** Generate structured summary report for CI systems.

**Deliverables:**
- CLI option: `--report <file>` to write JSON report
- Include: counts, waived items, unwaived issues, timing

**Success Criteria:**
- [ ] Generates valid JSON report
- [ ] Includes error/warning counts
- [ ] Includes list of unwaived issues
- [ ] Includes waiver statistics

**Tests:**
```python
# tests/test_ci_report.py
def test_ci_report_generation(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("ERROR: e1\nWARNING: w1\nWARNING: w2\nINFO: i1\n")

    report_file = tmp_path / "report.json"

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--report', str(report_file), str(log_file)])

    assert report_file.exists()

    import json
    report = json.loads(report_file.read_text())

    assert report['summary']['errors'] == 1
    assert report['summary']['warnings'] == 2
    assert report['summary']['info'] == 1
    assert report['exit_code'] == 1
```

---

## Stage 9: TUI (Deferred - Human-Guided)

> **Note:** This stage requires iterative human feedback for UX decisions.
> It should NOT be attempted by the automated ralph loop.
> Develop interactively with user testing.

### Task 9.1: Basic TUI Shell

**Objective:** Create minimal Textual application with log viewing.

**Approach:** Develop iteratively with human feedback on:
- Layout decisions
- Color schemes
- Keyboard shortcuts
- Scroll behavior

---

### Task 9.2: Interactive Filtering

**Objective:** Add filter controls to TUI.

**Approach:** Develop iteratively with human feedback on:
- Filter panel placement
- Toggle UX
- Real-time feedback

---

### Task 9.3: Waiver Management UI

**Objective:** Allow selecting and generating waivers from TUI.

**Approach:** Develop iteratively with human feedback on:
- Selection mechanism
- Preview display
- Export workflow

---

## Summary: Task Checklist

### Stage 1: Project Setup (Ralph Loop)
- [ ] Task 1.0: Test Infrastructure
- [ ] Task 1.1: Project Scaffolding
- [ ] Task 1.2: LogEntry Data Model
- [ ] Task 1.3: FilterDefinition Data Model
- [ ] Task 1.4: MessageGroup Data Model

### Stage 2: Core Log Parsing (Ralph Loop)
- [ ] Task 2.1: Basic Log File Loader
- [ ] Task 2.2: Message Boundary Detection
- [ ] Task 2.3: Basic Severity Detection

### Stage 3: Filter Engine (Ralph Loop)
- [ ] Task 3.1: Basic Regex Filter Engine
- [ ] Task 3.2: Filter Statistics

### Stage 4: CLI Streaming Interface (Ralph Loop)
- [ ] Task 4.1: Basic CLI with Stdout Output
- [ ] Task 4.2: Output Formats
- [ ] Task 4.3: Message ID Filtering
- [ ] Task 4.4: CLI Integration Tests

### Stage 5: Plugin System (Ralph Loop)
- [ ] Task 5.1: Plugin Hook Specification
- [ ] Task 5.2: Plugin Manager with Entry Point Discovery
- [ ] Task 5.3: Auto-Detection and Plugin Integration
- [ ] Task 5.4: Built-in Vivado Plugin
- [ ] Task 5.5: Plugin Discovery CLI

### Stage 6: Configuration System (Ralph Loop)
- [ ] Task 6.1: TOML Configuration Loader
- [ ] Task 6.2: Configuration Discovery and Merging

### Stage 7: Waiver System (Ralph Loop)
- [ ] Task 7.1: Waiver Data Model and Parser
- [ ] Task 7.2: Waiver Matching Engine
- [ ] Task 7.3: Waiver Generation

### Stage 8: CI Mode (Ralph Loop)
- [ ] Task 8.1: Exit Code Logic
- [ ] Task 8.2: Waiver Integration in CI
- [ ] Task 8.3: CI Summary Report

### Stage 9: TUI (Human-Guided - NOT for Ralph Loop)
- [ ] Task 9.1: Basic TUI Shell
- [ ] Task 9.2: Interactive Filtering
- [ ] Task 9.3: Waiver Management UI

---

**Total: 27 tasks across 9 stages**
- **24 tasks** suitable for ralph loop (Stages 1-8)
- **3 tasks** require human guidance (Stage 9)

Each task is designed to be:
1. **Self-contained**: Can be implemented independently
2. **Testable**: Has specific tests that must pass
3. **Context-friendly**: Small enough for a single session
4. **Incremental**: Builds on previous tasks without requiring future ones
