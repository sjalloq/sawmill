# Sawmill Project Context

This file provides context for Claude Code when working on the Sawmill project.

## Project Overview

Sawmill is a terminal-based log analysis tool for EDA (Electronic Design Automation) engineers. It provides:
- Plugin-driven log parsing and analysis
- Interactive regex-based log filtering
- Plugin system for tool-specific log formats
- Multi-line message grouping (via plugins)
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

## Architecture Principle

**Plugin is the sole source of truth.** The base application is an orchestrator only:
- Base app defines contracts (interfaces)
- Base app discovers plugins and orchestrates data flow
- **Plugins do ALL parsing** - loading files, detecting severity, grouping messages
- **Plugins define severity levels** - the base app has NO hardcoded severity knowledge
- Base app applies filters and displays results

The base app does NOT:
- Parse log content or detect severity
- Interpret log format
- Assume any specific severity names exist (no "error", "warning", "info" assumptions)
- Use hardcoded severity styling or ordering

**Severity Handling**: The base app uses numeric `level` values from `SeverityLevel.level` for all comparisons and sorting, never string IDs. This allows plugins to define any severity scheme (e.g., FATAL/ERROR/WARN/NOTE or CRITICAL/MAJOR/MINOR).

## Development Workflow

This project uses an autonomous development loop. Key files:

| File | Purpose |
|------|---------|
| `PRD.md` | Requirements and architecture |
| `TASKS.md` | Detailed task breakdown with tests |
| `PROMPT.md` | Instructions for each development iteration |
| `STATUS.md` | Current state - **READ THIS FIRST** |
| `CHANGELOG.md` | History of completed work |

**Note**: The project uses `uv` and you should activate the local `.venv` before doing anything.

## Coding Standards

### Style
- Follow PEP 8
- Use type hints for all function signatures
- Docstrings for public classes and functions
- Keep functions focused and small

### Testing
- Write tests alongside or before implementation
- Test file mirrors source structure: `sawmill/core/filter.py` → `tests/core/test_filter.py`
- Use pytest fixtures for common setup
- Mark async tests with `@pytest.mark.asyncio`

### Git
- One task per commit
- Descriptive commit messages
- Always update STATUS.md after completing a task
- Do NOT add "Co-Authored-By" lines to commit messages - keep commits clean and to the point
- **NEVER modify git config** (user.name, user.email, etc.) - this is the user's personal configuration

## Common Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/core/test_filter.py -v

# Run with coverage
pytest tests/ --cov=sawmill --cov-report=term-missing

# Type checking (if configured)
mypy sawmill/

# Run the application
python -m sawmill --help
python -m sawmill path/to/logfile.log
```

## Architecture Notes

### Data Flow (Plugin-Centric)
```
User: sawmill vivado.log --severity error

1. CLI parses arguments
2. Base app discovers plugins via entry points
3. Base app calls plugin.can_handle(Path) → select plugin
4. Base app calls plugin.load_and_parse(Path) → List[ParsedMessage]
5. Plugin: opens file, handles encoding, parses every line
6. Base app calls plugin.group_messages() → List[MessageGroup]
7. Base app applies filters (from plugin + user CLI args)
8. Base app displays results

Without plugin: error (user must install appropriate plugin or use --plugin)
```

### Key Classes
- `Message` - A logical log message (single or multi-line, plugin handles grouping)
- `FilterDefinition` - A filter pattern with metadata
- `FilterEngine` - Applies filters to messages
- `PluginManager` - Discovers and manages plugins via pluggy
- `SawmillPlugin` - Base class for plugins
- `Waiver` - A waiver entry for CI acceptance (has reason, author, date)
- `WaiverMatcher` - Matches messages against waivers in CI mode

### Suppressions vs Waivers
- **Suppressions**: Display filtering ("hide this noise") - in `[suppress]` config, no metadata
- **Waivers**: CI acceptance ("reviewed and accepted") - separate `.waivers.toml`, requires metadata

### Plugin Architecture (pluggy-based)
Plugins are Python packages that register via entry points:

```toml
# In plugin's pyproject.toml
[project.entry-points."sawmill.plugins"]
my_tool = "sawmill_plugin_mytool:MyToolPlugin"
```

Plugins implement hooks:
- `can_handle(path) -> float` - Detection confidence (0.0-1.0)
- `load_and_parse(path) -> list[Message]` - **Load, parse, and group into messages**
- `get_severity_levels() -> list[SeverityLevel]` - **REQUIRED: Define severity levels with id, name, level (int), style**
- `get_filters() -> list[FilterDefinition]` - Filter definitions
- `extract_file_reference(content) -> FileRef | None` - Extract file refs

**Required Hook**: `get_severity_levels()` MUST be implemented by all plugins. The base app has no default severity levels. Each `SeverityLevel` has:
- `id`: Internal identifier (e.g., "error", "warning")
- `name`: Display name (e.g., "Error", "Warning")
- `level`: Numeric level for comparisons (higher = more severe)
- `style`: Rich format string for display (e.g., "red bold")

**Note:** Plugins do ALL parsing and grouping. Base app receives a flat `list[Message]`.

## Task Dependencies

```
1.0 Test Infrastructure
 ↓
1.1 Project Scaffolding
 ↓
1.2 Data Model Interfaces
 ↓
2.1 Plugin Hook Specification
 ↓
2.2 Plugin Manager → 2.3 Auto-Detection → 2.4 Vivado Plugin → 2.5 Plugin CLI
 ↓
3.1 Filter Engine → 3.2 Filter Stats
 ↓
4.1 CLI Output → 4.2 Formats → 4.3 ID Filter → 4.4 Integration
 ↓
5.1 Config Loader → 5.2 Config Discovery
 ↓
6.1 Waiver Model → 6.2 Waiver Matching → 6.3 Waiver Generation
 ↓
7.1 CI Exit Codes → 7.2 CI Waivers → 7.3 CI Report
 ↓
8.x TUI (Human-Guided)
```

## Example Log Files

The `examples/` directory contains real log files for development and testing:

### Vivado (`examples/vivado/`)
- `vivado.log` - Full Vivado build log (~3000 lines, synthesis + implementation + bitstream)
- `PATTERNS.md` - Analysis of message formats and patterns

**Vivado is the primary target for initial development.** Use these examples to:
1. Test the plugin with real multi-line patterns
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
4. **Large Files**: Plugins should use generators/lazy loading for files > 100k lines
5. **Plugin Timeouts**: Always set timeouts when calling external plugins
6. **Vivado Multi-line**: Tables use `|` borders and `-` separators; group these together
7. **Severity Levels**: NEVER hardcode severity names ("error", "warning", etc.) in base app code. Always use `SeverityLevel.level` (numeric) for comparisons and get severity info from plugins via `get_severity_levels()`. The base app must work with ANY severity scheme a plugin defines.

## File Locations

```
sawmill/
├── __init__.py          # Package marker, version
├── __main__.py          # CLI entry: `python -m sawmill`
├── cli.py               # Main CLI with rich-click
├── core/
│   ├── filter.py        # FilterEngine, FilterStats
│   ├── config.py        # ConfigLoader, Config
│   ├── plugin.py        # PluginManager (pluggy-based)
│   └── waiver.py        # WaiverLoader, WaiverMatcher
├── plugin/
│   ├── __init__.py      # hookimpl, SawmillPlugin base
│   └── hookspec.py      # SawmillHookSpec definitions
├── plugins/
│   └── vivado.py        # Built-in Vivado plugin
├── tui/                 # (Deferred - Stage 8)
│   ├── app.py           # SawmillApp (main Textual app)
│   └── widgets/         # LogView, FilterPanel, etc.
├── models/
│   ├── message.py       # Message, FileRef
│   ├── filter_def.py    # FilterDefinition
│   └── waiver.py        # Waiver, WaiverFile
└── utils/
    ├── git.py           # Git repo detection
    └── validation.py    # Regex validation helpers
```
