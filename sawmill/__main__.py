"""Entry point for sawmill CLI."""

import rich_click as click

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True


@click.command()
@click.argument("logfile", required=False, type=click.Path(exists=True))
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx: click.Context, logfile: str | None, version: bool) -> None:
    """Sawmill - A terminal-based log analysis tool for EDA engineers.

    Analyze and filter log files from EDA tools like Vivado.
    """
    if version:
        from sawmill import __version__
        click.echo(f"sawmill {__version__}")
        return

    if logfile is None:
        click.echo(ctx.get_help())
        return

    click.echo(f"Processing: {logfile}")


if __name__ == "__main__":
    cli()
