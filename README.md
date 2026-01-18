# Sawmill

A configurable TUI for post-processing and filtering EDA tool logs.

## Overview

Sawmill is a terminal-based log analysis tool that allows engineers to filter, analyze, and understand complex log files from EDA tools. Through a plugin architecture, it provides tool-specific intelligence about log formats while remaining generic enough to handle any text-based log file.

## Features

- **Interactive Regex Filtering**: Real-time filtering as you type
- **Multi-line Message Grouping**: Correctly handle messages that span multiple lines
- **Plugin System**: Tool-specific intelligence via subprocess-based plugins
- **Configuration Sharing**: Export and share filter configurations via TOML files
- **Zero Configuration Start**: Works immediately on any log file

## Installation

```bash
# From source
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Start

```bash
# Open a log file
sawmill path/to/logfile.log

# With a specific config
sawmill --config myconfig.toml logfile.log
```

## Development

This project uses an autonomous development loop. See:
- `PRD.md` - Full requirements
- `PROMPT.md` - Development loop instructions
- `STATUS.md` - Current development state

### Running Tests

```bash
pytest tests/ -v
```

### Running the Development Loop

```bash
# Single iteration
./ralph-loop.sh

# Continuous until complete
./ralph-loop.sh --continuous

# Without Docker (local development)
./ralph-loop.sh --no-docker
```

## License

MIT
