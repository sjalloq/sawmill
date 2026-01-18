# Sawmill Project Context

This file provides context for Claude Code when working on the Sawmill project.

## Project Overview

Sawmill is a terminal-based log analysis tool for EDA (Electronic Design Automation) engineers. It provides:
- Interactive regex-based log filtering
- Plugin system for tool-specific log formats
- Multi-line message grouping
- Configuration export/sharing

## Technology Stack

- **Python 3.10+** - Core language
- **Textual** - TUI framework (terminal user interface)
- **Pydantic** - Data validation and models
- **TOML/tomli** - Configuration format
- **rich-click** - CLI argument parsing (click with rich formatting)
- **pluggy** - Plugin system (same architecture as pytest)
- **Rich** - Terminal formatting and colors
- **pytest** - Testing framework

## Development Workflow

This project uses an autonomous development loop. Key files:

| File | Purpose |
|------|---------|
| `PRD.md` | Full requirements and task definitions |
| `PROMPT.md` | Instructions for each development iteration |
| `STATUS.md` | Current state - **READ THIS FIRST** |
| `CHANGELOG.md` | History of completed work |

## Coding Standards

### Style
- Follow PEP 8
- Use type hints for all function signatures
- Docstrings for public classes and functions
- Keep functions focused and small

### Testing
- Write tests alongside or before implementation
- Test file mirrors source structure: `sawmill/core/parser.py` → `tests/core/test_parser.py`
- Use pytest fixtures for common setup
- Mark async tests with `@pytest.mark.asyncio`

### Git
- One task per commit
- Descriptive commit messages
- Always update STATUS.md after completing a task

## Common Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/core/test_parser.py -v

# Run with coverage
pytest tests/ --cov=sawmill --cov-report=term-missing

# Type checking (if configured)
mypy sawmill/

# Run the application
python -m sawmill --help
python -m sawmill path/to/logfile.log
```

## Architecture Notes

### Data Flow
```
Log File → Parser → [LogEntry] → Grouper → [MessageGroup] → Filter → Display
                                    ↑
                              Plugin (boundaries)
```

### Key Classes
- `LogEntry` - Single line from log file
- `MessageGroup` - Multi-line message unit
- `FilterDefinition` - A filter pattern with metadata
- `FilterEngine` - Applies filters to entries/groups
- `LogParser` - Loads and parses log files
- `PluginManager` - Discovers and manages plugins via pluggy
- `SawmillPlugin` - Base class for plugins
- `Waiver` - A waiver entry for accepted warnings/errors
- `WaiverMatcher` - Matches messages against waivers

### Plugin Architecture (pluggy-based)
Plugins are Python packages that register via entry points:

```toml
# In plugin's pyproject.toml
[project.entry-points."sawmill.plugins"]
my_tool = "sawmill_plugin_mytool:MyToolPlugin"
```

Plugins implement hooks:
- `can_handle(path, content) -> float` - Detection confidence
- `get_filters() -> list[FilterDefinition]` - Filter definitions
- `get_message_boundaries() -> list[MessageBoundary]` - Multi-line rules
- `parse_message(line) -> ParsedMessage | None` - Parse log lines
- `extract_file_reference(content) -> FileRef | None` - Extract file refs

## Task Dependencies

```
1.1 Project Scaffolding
 ↓
1.2 LogEntry → 1.4 MessageGroup
 ↓
1.3 FilterDefinition
 ↓
2.1 Log Loader → 2.2 Boundary Detection
 ↓
3.1 Filter Engine → 3.2 Filter Stats
 ↓
4.1-4.5 TUI Components
 ↓
5.1-5.3 Config System ←→ 6.1-6.3 Plugin System
 ↓
7.1-7.4 Filter Management
 ↓
8.1-8.2 Export
 ↓
9.1-9.3 Polish
```

## Example Log Files

The `examples/` directory contains real log files for development and testing:

### Vivado (`examples/vivado/`)
- `vivado.log` - Full Vivado build log (~3000 lines, synthesis + implementation + bitstream)
- `PATTERNS.md` - Analysis of message formats and patterns
- `plugin-spec.json` - Reference plugin specification for Vivado

**Vivado is the primary target for initial development.** Use these examples to:
1. Test the parser with real multi-line patterns
2. Develop the Vivado plugin
3. Verify filter matching works correctly

### Vivado Message Format
```
TYPE: [Category ID-Number] message [file:line]

Examples:
INFO: [Synth 8-6157] synthesizing module 'top' [/path/file.v:53]
WARNING: [Vivado 12-3523] Attempt to change 'name' is not allowed
CRITICAL WARNING: [Constraints 18-4427] Constraint override warning
```

## Known Gotchas

1. **Textual Testing**: Use `app.run_test()` context manager with `pilot` for async tests
2. **TOML Parsing**: Use `tomli` for reading (Python 3.10 compatible), `tomli_w` for writing
3. **Regex Validation**: Always validate patterns before storing in FilterDefinition
4. **Large Files**: Use generators/lazy loading for files > 100k lines
5. **Plugin Timeouts**: Always set timeouts when calling external plugins
6. **Vivado Multi-line**: Tables use `|` borders and `-` separators; group these together

## File Locations

```
sawmill/
├── __init__.py          # Package marker, version
├── __main__.py          # CLI entry: `python -m sawmill`
├── cli.py               # Main CLI with rich-click
├── core/
│   ├── parser.py        # LogParser, MessageBoundary
│   ├── filter.py        # FilterEngine, FilterStats
│   ├── config.py        # ConfigLoader, Config
│   ├── plugin.py        # PluginManager (pluggy-based)
│   └── waiver.py        # WaiverLoader, WaiverMatcher
├── plugin/
│   ├── __init__.py      # hookimpl, SawmillPlugin base
│   └── hookspec.py      # SawmillHookSpec definitions
├── plugins/
│   └── vivado.py        # Built-in Vivado plugin
├── tui/                 # (Deferred - Phase 9)
│   ├── app.py           # SawmillApp (main Textual app)
│   └── widgets/         # LogView, FilterPanel, etc.
├── models/
│   ├── log_entry.py     # LogEntry, MessageGroup
│   ├── filter_def.py    # FilterDefinition
│   ├── waiver.py        # Waiver, WaiverFile
│   └── message.py       # ParsedMessage, FileRef
└── utils/
    ├── git.py           # Git repo detection
    └── validation.py    # Regex validation helpers
```
