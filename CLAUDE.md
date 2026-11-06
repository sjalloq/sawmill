# Sawmill

Terminal log analyser for structured tool logs. Plugins parse tool-specific
formats (Vivado, Slang, Synplify, ...); the base app filters, groups, waives
and reports. Batch CLI for CI, Textual TUI for interactive triage.

## Setup

```bash
source sourceme          # creates .venv with uv, installs dev extras, installs pre-commit
source sourceme --clean  # rebuild the venv
pytest tests/ -v
python -m sphinx -b html docs docs/_build/html   # needs `uv sync --all-extras`
```

Always use `uv`, never `pip`. Activate `.venv` before running anything.

## Layout

```
sawmill/
  __main__.py      CLI entry point
  cli/             rich-click commands, processing, reporting, formatting
  core/            filter, severity, aggregation, config, plugin manager, waivers
  models/          pydantic models: Message, FilterDefinition, Waiver, plugin API
  plugin/          SawmillPlugin base class and pluggy hookspec
  tui/             Textual app, session persistence, widgets
  utils/           dirs, git, toml, author helpers
tests/             mirrors sawmill/ (sawmill/core/filter.py -> tests/core/test_filter.py)
tools/bench/       synthetic log generator and benchmark runner
tools/sawmill-plugin-generator/   scaffolds a new plugin package
docs/              Sphinx, furo theme; built by .github/workflows/docs.yml
```

Plugins live in their own repositories and register through the
`sawmill.plugins` entry point. There are no built-in plugins.

## Architecture rules

**The plugin is the sole source of truth for the log format.** The base app
never parses log content, detects severity, or assumes severity names exist.

- Plugins implement `can_handle`, `load_and_parse` (an iterator of `Message`,
  plugin API 2), `get_severity_levels` (required), and optionally
  `get_filters`, `get_grouping_fields`, `extract_file_reference`.
- Severity comparisons in the base app use `SeverityLevel.level` (an int),
  never the string id. Any severity scheme a plugin defines must work.
- Large logs are streamed; see `docs/performance/` before touching the
  load path or the TUI table.

## In-progress redesign

The waiver and suppression system is being replaced by a manifest and rule
model. The design, decisions and task plan are in
`docs/development/manifest-design.rst`. Read it before changing anything
under `core/waiver.py`, `core/suppress.py`, `core/config.py`, the CLI
options, or TUI session persistence. The user guide pages on waivers and the
`.sawmill` directory describe the old behaviour until Stage D of that plan.

## Coding standards

- PEP 8, type hints on every signature, docstrings on public classes and
  functions. Ruff and mypy run in pre-commit.
- Tests alongside or before implementation. Async Textual tests use
  `app.run_test()` with `pilot`.
- `tomli` for reading TOML, `tomli_w` for writing. Validate regexes before
  storing them.

## Git

- Short, conventional commit messages. One logical change per commit.
- No `Co-Authored-By` or generated-by lines.
- Never modify git config.
- Use git worktrees for parallel work.
