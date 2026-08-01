from importlib.metadata import version

import typer

from app.cli.tickets import tickets

# no_args_is_help: a bare `helpdesk` prints the subcommand tree instead of an unhelpful usage error.
cli = typer.Typer(
    help            = "Operator tooling for dokus-helpdesk-ai (indexing, search, evaluation).",
    no_args_is_help = True,
)

# Groups of related operations arrive as sub-apps, so the tree stays `helpdesk <resource> <action>`
# (`helpdesk tickets validate`) instead of flattening into ever longer single-word commands.
cli.add_typer(tickets, name="tickets")


@cli.callback()
def main() -> None:
    """
    Description:
    Root callback of the command tree. Its presence keeps Typer in subcommand mode — without it
    an app holding a single command collapses, and `helpdesk` would run that command directly
    instead of listing the tree.

    Example args:
        (none)

    Example result:
        None — Typer continues to dispatch to a subcommand
    """


@cli.command("version", help="Print the installed package version.")
def show_version() -> None:
    """
    Description:
    Prints the installed package version. Doubles as the smoke test of the whole CLI wiring:
    entry point, package installation and Typer dispatch.

    Example args:
        (none)

    Example result:
        prints "dokus-helpdesk-ai 0.1.0"
    """
    typer.echo(f"dokus-helpdesk-ai {version('dokus-helpdesk-ai')}")
