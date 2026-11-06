<p align="center">
  <img src="assets/sawmill.png" alt="Sawmill - Cutting through the noise" width="600">
</p>

<h1 align="center">Sawmill</h1>

<p align="center">
  <strong>A plugin-driven terminal log analyser</strong>
</p>

Sawmill filters, groups and waives messages from structured tool logs such as
Vivado, Slang and Synplify output. A batch CLI gates CI pipelines on log
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
sawmill vivado.log            # open the TUI
sawmill vivado.log --summary  # batch summary by severity and message ID
sawmill vivado.log --check    # exit 1 on unwaived messages
sawmill --help
```

Full documentation, including the CLI reference, TUI guide, CI integration
and plugin authoring, is at https://sjalloq.github.io/sawmill.

The CLI and waiver format are being reworked around a project manifest.
See `docs/development/manifest-design.rst`.

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
