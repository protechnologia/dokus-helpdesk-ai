from importlib.metadata import version

import typer

from app.cli.rag import rag
from app.cli.tickets import tickets

# --- helpdesk: całe drzewo komend ------------------------------------------------------------
#
# | komenda                    | plik         | co robi                                        |
# |----------------------------|--------------|------------------------------------------------|
# | `version`                  | cli.py       | wersja pakietu; smoke test okablowania CLI      |
# | `tickets validate <kat.>`  | tickets.py   | sprawdza artefakty wobec kontraktu ParsedTicket |
# | `tickets parse`            | tickets.py   | parsuje zgłoszenia z data/raw/ przez LLM        |
# | `rag index <kat.>`         | rag.py       | dokłada artefakty do kolekcji Qdranta           |
# | `rag reindex <kat.>`       | rag.py       | kasuje kolekcję i buduje ją od zera             |
#
# Zaplanowane: `rag search` / `rag suggest` (etapy 5-6), `gate close` / `gate reply` / `polish`
# (etapy 7-9). Bramki i „Popraw" stoją POZA grupą `rag` — z definicji działają bez indeksu.
#
# no_args_is_help: samo `helpdesk` drukuje drzewo, zamiast błędu użycia.
cli = typer.Typer(
    help            = "Operator tooling for dokus-helpdesk-ai (indexing, search, evaluation).",
    no_args_is_help = True,
)

# Grupy powiązanych operacji wchodzą jako pod-aplikacje, więc drzewo zostaje
# `helpdesk <obszar> <czynność>` zamiast płaskiej listy coraz dłuższych jednoczłonowych nazw.
cli.add_typer(tickets, name="tickets")
cli.add_typer(rag, name="rag")


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
