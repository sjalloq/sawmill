"""Top-level CLI group for sawmill.

Defines the ``sawmill`` command group, registers subcommands and implements
the ``sawmill LOGFILE`` alias for ``sawmill view LOGFILE``.
"""

from __future__ import annotations

from pathlib import Path

import rich_click as click

from sawmill import __version__
from sawmill.cli.check import check
from sawmill.cli.init import init
from sawmill.cli.plugins import plugins
from sawmill.cli.report import report
from sawmill.cli.rules import rules
from sawmill.cli.view import view

click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.COMMAND_GROUPS = {
    "sawmill": [
        {
            "name": "Commands",
            "commands": ["init", "view", "check", "report", "rules", "plugins"],
        }
    ],
}
click.rich_click.OPTION_GROUPS = {
    "sawmill": [{"name": "Options", "options": ["--version", "--help"]}],
}


class SawmillGroup(click.RichGroup):
    """Command group that treats ``sawmill <file> ...`` as ``sawmill view <file> ...``."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Rewrite a leading log file argument into a ``view`` invocation."""
        for index, arg in enumerate(args):
            if arg.startswith("-"):
                continue
            if arg not in self.commands and Path(arg).is_file():
                args = [*args[:index], "view", *args[index:]]
            break
        return super().parse_args(ctx, args)


@click.group(
    cls=SawmillGroup,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="sawmill", message="%(prog)s %(version)s")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Sawmill: terminal log analyser for structured tool logs.

    [bold]sawmill LOGFILE[/bold] is shorthand for [bold]sawmill view LOGFILE[/bold].
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli.add_command(view)
cli.add_command(check)
cli.add_command(report)
cli.add_command(plugins)
cli.add_command(rules)
cli.add_command(init)
