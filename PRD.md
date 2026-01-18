# Sawmill - Product Requirements Document

## Project Overview

- **Project Name:** Sawmill
- **Tagline:** A configurable TUI for post-processing and filtering EDA tool logs
- **Technology Stack:** Python 3.10+, Textual (TUI framework), TOML (configuration)
- **Primary Use Case:** Interactive filtering and analysis of Electronic Design Automation (EDA) tool log files

## Elevator Pitch

Sawmill is a terminal-based log analysis tool that allows engineers to filter, analyze, and understand complex log files from EDA tools. Through a plugin architecture, it provides tool-specific intelligence about log formats. Engineers can quickly identify relevant errors and warnings buried in thousands of lines of output, customize filtering rules interactively, and share configurations across teams.

---

## Goals and Non-Goals

### Goals

1. **Plugin-Driven Log Analysis:** Provide powerful log filtering where plugins handle all parsing, severity detection, and message grouping
2. **Plugin Extensibility:** Enable tool-specific intelligence through a pluggy-based plugin architecture (same pattern as pytest)
3. **Multi-line Pattern Support:** Correctly handle log messages that span multiple lines (common in EDA tools) via plugin-defined boundaries
4. **Interactive Customization:** Allow users to modify and extend filter definitions in real-time through the TUI
5. **Configuration Portability:** Enable saving and sharing customized filter configurations via TOML files

### Non-Goals (for v1.0)

- **Live Log Monitoring:** Real-time tailing of actively-written log files (focus is post-processing)
- **Log Aggregation:** Combining logs from multiple sources or files
- **Advanced Analytics:** Statistical analysis, graphing, or trend detection
- **Multi-user Waiver Workflow:** Full waiver approval workflow with multiple reviewers (deferred to future version; basic waiver generation/matching IS in scope)
- **Base App Parsing:** The base application will NOT contain any parsing logic - all parsing is delegated to plugins

---

## Architecture Principles

### Core Principle: Plugin as Sole Source of Truth

The base application is an **orchestrator only**. It defines contracts (interfaces), discovers plugins, orchestrates data flow, and displays results. It does NOT:
- Parse log content
- Detect severity levels
- Group multi-line messages
- Interpret log format in any way

All content interpretation is the plugin's responsibility.

### Responsibility Boundaries

| Component | Responsibility | NOT Responsible For |
|-----------|---------------|---------------------|
| **Base App** | Define contracts (interfaces), discover plugins, orchestrate, display, apply filters | Parsing, severity detection, grouping - ANY content interpretation |
| **Plugin** | File loading, encoding, parsing, severity detection, grouping, provide filters | Display formatting, CLI handling |
| **CLI** | User interface, option parsing, output formatting | Any parsing logic |

### Data Flow

```
User runs: sawmill vivado.log --severity error

1. CLI parses arguments, calls base app
2. Base app discovers plugins via entry points
3. Base app calls plugin.can_handle(Path) on each plugin
4. Base app selects plugin (highest confidence > 0.5, error if conflict or none found)
5. Base app calls plugin.load_and_parse(Path) -> list[Message]
6. Plugin opens file, handles encoding, parses and groups into logical messages
7. Base app applies filters (from plugin.get_filters() + user CLI args + suppressions)
8. Base app displays results via CLI output formatter
```

**Key:** Plugin receives `Path` and returns a flat `list[Message]`. Each Message is a complete logical unit - the orchestrator doesn't care if it spans 1 line or 10.

**No plugin = error.** If no plugin can handle the file, sawmill exits with an error message suggesting the user install an appropriate plugin or use `--plugin` to specify one. For raw text viewing, use `less`.

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

### 1. Log Display and Navigation

**Description:** Display log files in a scrollable, searchable TUI interface.

**Requirements:**
- Display log content efficiently (100k+ lines)
- Provide smooth scrolling through large files
- Display line numbers alongside log content
- Support basic navigation (page up/down, jump to line, home/end)
- Display file metadata (name, size, line count)

**Plugin Dependency:** None for raw display; coloring requires plugin severity detection.

### 2. Interactive Regex Filtering

**Description:** Real-time filtering of log content based on user-entered regex patterns.

**Requirements:**
- Provide a search/filter input bar in the TUI
- Apply regex pattern filtering in real-time as user types
- Display only lines matching the current filter
- Support multiple active filters with AND/OR logic
- Show filter statistics (X of Y lines match)
- Allow toggling filters on/off without deleting them
- Support case-sensitive and case-insensitive matching
- Handle invalid regex gracefully with error messages

**Plugin Dependency:** Operates on ParsedMessage/MessageGroup objects provided by the plugin.

### 3. Multi-line Message Grouping

**Description:** Group related log lines into logical messages for more accurate filtering.

**Requirements:**
- Display grouped messages as cohesive units
- Apply filtering to entire grouped messages, not individual lines
- Preserve context when showing filtered results (show full message group)
- Provide visual indication of message boundaries

**Plugin Dependency:** REQUIRED. Grouping logic is entirely plugin-defined via `get_message_boundaries()` hook.

### 4. Plugin System

**Description:** Hook-based plugin architecture using pluggy (same pattern as pytest).

#### Plugin Installation

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

Plugins implement hooks to provide sawmill with parsed data:

| Hook | Purpose | Return Type | Required |
|------|---------|-------------|----------|
| `can_handle(path)` | Detect if plugin handles this file | `float` (0.0-1.0) | Yes |
| `load_and_parse(path)` | Load file, parse, and group into messages | `list[Message]` | Yes |
| `get_filters()` | Provide filter definitions | `list[FilterDefinition]` | Yes |
| `extract_file_reference(content)` | Find source file references | `FileRef \| None` | No |
| `get_categories()` | List message categories plugin understands | `list[str]` | No |
| `get_quick_filters()` | Named filter presets | `dict[str, list[str]]` | No |

**Note:** Multi-line grouping is handled internally by the plugin. The orchestrator receives a flat `list[Message]` where each Message is a complete logical unit (single or multi-line).

#### Plugin Conflict Resolution

When multiple plugins could handle a file:

1. **Explicit `--plugin X` flag always wins** - no auto-detection performed
2. **Error if >1 plugin returns confidence > 0.5** - user must specify with `--plugin`
3. **If exactly one plugin > 0.5 threshold** - that plugin is selected
4. **If no plugin > 0.5** - error with message to install appropriate plugin or force with `--plugin`

#### Built-in Vivado Plugin

Sawmill bundles a reference Vivado plugin as `sawmill.plugins.vivado`. This can be overridden by:
- User's custom plugin returning higher confidence score
- Explicit `--plugin myplugin` CLI flag

### 5. Configuration System

**Configuration File Locations (in precedence order):**

1. Command-line specified: `--config <file>`
2. Environment variable: `SAWMILL_CONFIG`
3. Current directory: `./sawmill.toml`
4. Git repo root: `<git-root>/.sawmill/config.toml`
5. User config: `~/.config/sawmill/config.toml`
6. Built-in defaults

**Configuration Schema:**

```toml
[general]
default_plugin = "vivado"
show_line_numbers = true
theme = "monokai"

[plugins]
search_paths = ["~/.config/sawmill/plugins", "./plugins"]
enabled = ["vivado", "synopsys-dc"]

# Plugin-specific configuration
[plugins.vivado]
device_family = "ultrascale"

[[filters.custom]]
id = "my-filter-1"
name = "Custom Error Pattern"
pattern = "CUSTOM_ERROR_\\d+"
severity = "error"
enabled = true

[suppress]
patterns = ["^INFO: \\[.*\\] Launching helper"]
message_ids = ["Common 17-55"]
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

**Plugin Dependency:** Filter definitions come from plugin; user can add custom filters.

### 7. Configuration Export

**Requirements:**
- Export current filter state to TOML
- Include user modifications as overrides
- Preserve filter metadata
- Generate human-readable, commented TOML
- Include provenance (plugin, timestamp, author, git commit if available)

---

## Operating Modes

### 1. CLI Streaming Mode (Primary)

Stream filtered log output to stdout for piping, viewing, or redirection.

```bash
# Filter by severity (requires plugin)
sawmill vivado.log --severity error,critical

# Filter by regex pattern
sawmill vivado.log --filter "timing|slack"

# Filter by message ID
sawmill vivado.log --id "Synth 8-*"

# Suppress noisy messages (display filtering, not CI)
sawmill vivado.log --suppress "INFO:.*Launching"
sawmill vivado.log --suppress-id "Common 17-55"

# Output formats
sawmill vivado.log --format text      # Default: human-readable
sawmill vivado.log --format json      # JSON lines (one per message)
sawmill vivado.log --format count     # Summary counts only

# Delta comparison
sawmill vivado.log --baseline previous.log
```

### 2. CI/Lint Mode

Return exit codes for use in CI pipelines and Makefiles.

```bash
# Basic CI check - fail on any error/critical warning
sawmill --ci vivado.log

# CI with waivers
sawmill --ci --waivers project.waivers.toml vivado.log

# Strict mode - also fail on regular warnings
sawmill --ci --strict vivado.log

# Generate summary report
sawmill --ci --report ci-report.json vivado.log
```

### 3. Waiver Generation Mode

Generate waiver files from log analysis.

```bash
sawmill vivado.log --generate-waivers > project.waivers.toml
sawmill vivado.log --generate-waivers --severity warning > warnings.waivers.toml
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
sawmill --list-plugins
sawmill --plugin vivado --show-info
```

---

## Suppressions vs Waivers

Sawmill distinguishes between two concepts that are often conflated:

### Suppressions (Display Filtering)

**Purpose:** "Never show me these - they're noise"

Suppressions are for **display purposes only**. They hide messages from output during interactive viewing or CLI streaming. They do NOT affect CI pass/fail decisions.

- Configured in `sawmill.toml` under `[suppress]`
- No metadata required (no reason, author, date)
- Applied during display, not during CI checks
- Use case: Hiding verbose startup messages, known-noisy categories

```toml
# In sawmill.toml
[suppress]
patterns = ["^INFO: \\[.*\\] Launching helper"]
message_ids = ["Common 17-55"]
```

CLI support:
```bash
# Suppress by regex pattern
sawmill vivado.log --suppress "INFO:.*Starting"

# Suppress by message ID
sawmill vivado.log --suppress-id "Common 17-55"

# Multiple suppressions
sawmill vivado.log --suppress "DEBUG:" --suppress "INFO:.*Launching"

# Combine with other filters
sawmill vivado.log --severity error --suppress "known_issue_pattern"
```

### Waivers (CI Acceptance)

**Purpose:** "Reviewed and accepted for CI pass/fail"

Waivers are for **CI/lint mode**. They mark specific warnings/errors as "reviewed and accepted" so they don't cause CI failures. Waivers require metadata for audit trails.

- Stored in separate `.waivers.toml` files
- Require: reason, author, date
- Optional: expiry date
- Applied only in `--ci` mode
- Use case: Known issues that are acceptable, vendor IP warnings, intentional design choices

### Key Differences

| Aspect | Suppression | Waiver |
|--------|-------------|--------|
| Purpose | Hide noise from display | Accept for CI pass/fail |
| Metadata | None required | reason, author, date required |
| Storage | `sawmill.toml` config | Separate `.waivers.toml` file |
| Applies to | Display/streaming output | CI mode exit codes |
| Audit trail | No | Yes |

---

## Waiver System

Waivers allow teams to mark specific warnings/errors as "reviewed and accepted" so they don't cause CI failures. Unlike suppressions, waivers have full metadata for audit trails.

### Waiver File Format

```toml
[metadata]
created = "2026-01-18"
tool = "vivado"
version = "1.0"

[[waiver]]
type = "id"
pattern = "Vivado 12-3523"
reason = "Component name change is intentional"
author = "shareef"
date = "2026-01-18"

[[waiver]]
type = "pattern"
pattern = "set_input_delay.*usb_fifo_clk"
reason = "USB FIFO clock is async"
author = "shareef"
date = "2026-01-18"

[[waiver]]
type = "file"
pattern = "*/ip/pcie_s7/*"
severity = ["warning", "critical"]
reason = "Xilinx IP core warnings"
author = "shareef"
date = "2026-01-18"

[[waiver]]
type = "hash"
hash = "sha256:a1b2c3d4e5f6..."
reason = "Reviewed - false positive"
author = "shareef"
date = "2026-01-18"
expires = "2026-06-01"
```

### Waiver Matching Priority

1. **Hash match** - Exact message content match (highest specificity)
2. **ID match** - Message ID pattern
3. **Pattern match** - Regex on message content
4. **File match** - Source file glob pattern (lowest specificity)

---

## Data Model Interfaces

These are **contracts** that the base app defines. Plugins create instances of these.

### Message

Represents a logical log message (single-line or multi-line - plugin handles grouping internally).

```python
@dataclass
class Message:
    # Line range (same value for single-line messages)
    start_line: int
    end_line: int

    # Content
    raw_text: str          # Full raw text (may contain newlines for multi-line)
    content: str           # Cleaned/parsed content

    # Plugin-determined metadata
    severity: str | None = None       # error, warning, critical_warning, info
    message_id: str | None = None     # e.g., "Vivado 12-3523"
    category: str | None = None       # e.g., "timing", "synthesis"
    file_ref: FileRef | None = None   # Source file reference

    def matches_filter(self, pattern: str) -> bool:
        """Check if message matches regex pattern."""
        ...
```

**Note:** The orchestrator receives a flat `list[Message]`. Whether a message spans 1 line or 10 lines is the plugin's concern - the orchestrator just sees logical messages.

### FilterDefinition

Represents a filter specification.

```python
@dataclass
class FilterDefinition:
    id: str
    name: str
    pattern: str                     # Validated regex
    enabled: bool = True
    description: str | None = None
    severity: str | None = None
    category: str | None = None
    source: str = "builtin"          # "builtin", "plugin:<name>", "user"
```

---

## Project Structure

```
sawmill/
├── __init__.py              # Package marker, version
├── __main__.py              # CLI entry: `python -m sawmill`
├── cli.py                   # Main CLI with rich-click
├── core/
│   ├── __init__.py
│   ├── filter.py            # FilterEngine, FilterStats
│   ├── config.py            # ConfigLoader, Config
│   ├── plugin.py            # PluginManager (pluggy-based)
│   └── waiver.py            # WaiverLoader, WaiverMatcher
├── plugin/
│   ├── __init__.py          # hookimpl, SawmillPlugin base
│   └── hookspec.py          # SawmillHookSpec definitions
├── plugins/
│   └── vivado.py            # Built-in Vivado plugin
├── tui/                     # (Deferred - Phase 9)
│   ├── app.py               # SawmillApp (main Textual app)
│   └── widgets/             # LogView, FilterPanel, etc.
├── models/
│   ├── __init__.py
│   ├── message.py           # Message, FileRef
│   ├── filter_def.py        # FilterDefinition
│   └── waiver.py            # Waiver, WaiverFile
└── utils/
    ├── __init__.py
    ├── git.py               # Git repo detection
    └── validation.py        # Regex validation helpers
```

---

## Implementation Phases (Summary)

See `TASKS.md` for detailed task breakdown.

### Phase 1: Core Foundation
- Project scaffolding and packaging
- Data model interfaces (contracts only)
- Basic CLI skeleton

### Phase 2: Plugin System
- Plugin hook specification
- Plugin discovery via entry points
- Plugin manager with auto-detection
- Built-in Vivado plugin (reference implementation)

### Phase 3: Filter Engine
- Regex-based filtering (operates on plugin output)
- Severity filtering
- Message ID filtering
- Filter statistics

### Phase 4: CLI Streaming Interface
- Stream filtered output to stdout
- Multiple output formats
- All filter options as CLI arguments

### Phase 5: Configuration System
- TOML configuration schema
- Hierarchical config discovery
- Config merging with precedence

### Phase 6: Waiver System
- Waiver file format and parsing
- Waiver matching engine
- Waiver generation from logs

### Phase 7: CI Mode
- Exit code logic (0/1)
- Waiver integration
- Summary report generation

### Phase 8: TUI (Human-Guided)
- Deferred - requires iterative human feedback

---

## Future Enhancements (Post-v1.0)

- Live log monitoring (tail -f mode)
- Log file comparison (diff between runs)
- Export filtered logs to file
- Statistics dashboard
- Filter templates library
- IDE integrations
- Waiver approval workflow (multi-user)
