"""CLI entry point for the sawmill plugin generator."""

from __future__ import annotations

from pathlib import Path

import click

from sawmill_plugin_generator.generator import generate, get_git_author
from sawmill_plugin_generator.names import derive_names, validate_name


@click.command()
@click.option(
    "--name",
    required=True,
    help="Plugin name (lowercase, letters/digits/hyphens). E.g. 'quartus'.",
)
@click.option(
    "--description",
    default=None,
    help="One-line description. Default: 'Sawmill plugin for <name>'.",
)
@click.option(
    "--author",
    default=None,
    help="Author name. Default: git user.name or 'Plugin Author'.",
)
@click.option(
    "--output-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Where to create the project directory. Default: current directory.",
)
def main(name: str, description: str | None, author: str | None, output_dir: Path) -> None:
    """Generate a sawmill plugin project scaffold."""
    validate_name(name)

    names = derive_names(name)

    if description is None:
        description = f"Sawmill plugin for {name}"

    if author is None:
        author = get_git_author() or "Plugin Author"

    project_dir = generate(
        names=names,
        description=description,
        author=author,
        output_dir=output_dir,
    )

    click.echo(f"Created {project_dir.name}/")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  cd {project_dir.name}")
    click.echo("  make install")
    click.echo("  make test")
    click.echo()
    click.echo("Then fill in the TODOs in src/*/plugin.py")
