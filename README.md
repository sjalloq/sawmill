<p align="center">
  <img src="assets/sawmill.png" alt="Sawmill - Cutting through the noise" width="600">
</p>

<h1 align="center">Sawmill</h1>

<p align="center">
  <strong>A plugin-driven terminal log analyser</strong>
</p>

Sawmill filters, groups and waives messages from structured tool logs such as
Vivado and Slang output. A batch CLI gates CI pipelines on log
content; a terminal UI handles interactive triage. Plugins own the parsing,
so any log format can be supported.

## Install

```bash
uv tool install sawmill-parser sawmill-plugin-vivado
```

Or from a clone:

```bash
source sourceme     # creates .venv with uv and installs dev extras
```

## Usage

```bash
sawmill vivado.log                              # open one log in the TUI
sawmill init                                    # create .sawmill/manifest.toml
sawmill init --target pnr 'build/pnr/*.log'     # add a target
sawmill view                                    # TUI over every target
sawmill check --report build/report.json        # CI gate: exit 1 on unwaived failures
sawmill report --format junit -o build/sawmill.xml
sawmill rules unused                            # rules that matched nothing
sawmill plugins list
```

Targets and rules live in a checked-in `.sawmill/` directory: a
`manifest.toml` naming the targets (plugin plus log globs) and rule files
under `.sawmill/rules/` that waive expected messages.

Full documentation, including the manifest and rule formats, CLI reference,
TUI guide, CI integration and plugin authoring, is at
https://sjalloq.github.io/sawmill.

## Plugins

| Plugin | Repository |
|--------|------------|
| `vivado` | https://github.com/sjalloq/sawmill-plugin-vivado |
| `slang` | https://github.com/sjalloq/sawmill-plugin-slang |

Plugins register through the `sawmill.plugins` entry point and are
auto-detected from log content. `tools/sawmill-plugin-generator` scaffolds a
new one.

## Development

```bash
source sourceme
pytest tests/ -v
pre-commit run --all-files
```

## License

MIT
