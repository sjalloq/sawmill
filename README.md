<p align="center">
  <img src="assets/sawmill.png" alt="Sawmill - Cutting through EDA logs" width="600">
</p>

<h1 align="center">Sawmill</h1>

<p align="center">
  <strong>A terminal-based log analysis tool for EDA engineers</strong>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#plugins">Plugins</a> •
  <a href="#ci-integration">CI Integration</a>
</p>

---

Sawmill helps you filter, analyze, and understand complex log files from EDA tools like Vivado. Through a plugin architecture, it provides tool-specific intelligence while remaining extensible to any log format.

## Features

- **Smart Parsing** - Plugins understand tool-specific message formats, multi-line grouping, and file references
- **Summary Views** - Quick overview of errors and warnings by severity and message ID
- **Flexible Grouping** - Group messages by severity, ID, file, category, or plugin-defined fields
- **Regex Filtering** - Include or exclude messages with powerful pattern matching
- **CI Integration** - Exit codes and waiver system for build pipeline integration
- **Extensible** - Write plugins for any log format with full customization

## Installation

```bash
# Install from source
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

```bash
# Analyze a log file (auto-detects format)
sawmill vivado.log

# Show summary by severity with ID breakdown
sawmill vivado.log --summary

# Group messages by ID, file, or category
sawmill vivado.log --group-by id
sawmill vivado.log --group-by file
sawmill vivado.log --group-by category

# Filter by severity level
sawmill vivado.log --severity warning

# Filter with regex pattern
sawmill vivado.log --filter "timing"

# Exclude messages by pattern or ID
sawmill vivado.log --suppress "Synth 8-7129"
sawmill vivado.log --suppress-id "Synth 8-7129"
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--summary` | Show summary counts by severity and message ID |
| `--group-by` | Group output by `severity`, `id`, `file`, or `category` |
| `--top N` | Limit messages per group (default: 5, 0 = no limit) |
| `--severity` | Filter to severity level and above |
| `--filter` | Regex pattern to include messages |
| `--suppress` | Regex pattern to exclude messages |
| `--suppress-id` | Exclude specific message IDs |
| `--format` | Output format: `text`, `json`, or `count` |
| `--ci` | CI mode: exit 1 on errors/critical warnings |
| `--waivers` | Path to waiver TOML file |

## Plugins

Sawmill uses a plugin architecture to support different log formats. Plugins are auto-detected based on log content.

### Built-in Plugins

| Plugin | Description |
|--------|-------------|
| `vivado` | Xilinx Vivado synthesis and implementation logs |

### External Plugins

Plugins can be installed separately and auto-register with sawmill:

```bash
# List available plugins
sawmill --list-plugins

# List available grouping fields
sawmill --list-groupings --plugin vivado
```

### Writing Plugins

Plugins implement the `SawmillPlugin` interface with hooks for:

- `can_handle(path)` - Detect if plugin can parse a file
- `load_and_parse(path)` - Parse file into `Message` objects
- `get_filters()` - Provide pre-defined filter definitions
- `get_severity_levels()` - Define severity ordering and styling
- `get_grouping_fields()` - Declare available grouping dimensions

## CI Integration

Sawmill can be used in CI pipelines to fail builds on errors:

```bash
# Exit 1 if errors or critical warnings found
sawmill vivado.log --ci

# Also fail on regular warnings
sawmill vivado.log --ci --strict

# Use waivers to allow known issues
sawmill vivado.log --ci --waivers waivers.toml
```

### Waiver Files

Waiver files are TOML files that specify known issues to ignore:

```toml
[[waiver]]
id = "Synth 8-7129"
reason = "Expected warning for RAM inference"
expires = "2025-12-31"

[[waiver]]
pattern = "timing.*slack"
reason = "Timing constraints not finalized"
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=sawmill

# Check linting
ruff check sawmill/
```

## License

MIT
