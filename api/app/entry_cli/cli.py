from importlib.metadata import version

import typer

from app.entry_cli.docs import docs
from app.entry_cli.rag import rag
from app.entry_cli.tickets import tickets

# --- helpdesk: całe drzewo komend ------------------------------------------------------------
#
# Obszar to pakiet w `entry_cli/`, czynność to plik w nim:
# `helpdesk rag index` → `entry_cli/rag/index.py`.
#
# | komenda                   | plik                  | co robi                          |
# |---------------------------|-----------------------|----------------------------------|
# | `version`                 | `cli.py`              | wersja pakietu; smoke test CLI   |
# | `tickets validate <kat.>` | `tickets/validate.py` | artefakty wobec ParsedTicket     |
# | `rag index <kat.>`        | `rag/index.py`        | artefakty do kolekcji Qdranta    |
# | `rag reindex <kat.>`      | `rag/reindex.py`      | kolekcja od zera                 |
# | `docs validate <kat.>`    | `docs/validate.py`    | paczka dokumentacji wobec plików |
# | `docs index <kat.>`       | `docs/index.py`       | indeks dokumentacji od zera      |
#
# Zaplanowane (p. 46): komendy na grafach — wyszukiwanie, parsowanie zgłoszeń, propozycje; bramki
# i „Popraw" stoją POZA obszarem `rag`, bo z definicji działają bez indeksu.
#
# no_args_is_help: samo `helpdesk` drukuje drzewo, zamiast błędu użycia.
cli = typer.Typer(
    help            = "Narzędzia operatora: walidacja artefaktów, indeksacja i dokumentacja.",
    no_args_is_help = True,
)

# Obszary wchodzą jako pod-aplikacje, więc drzewo zostaje `helpdesk <obszar> <czynność>` zamiast
# płaskiej listy coraz dłuższych jednoczłonowych nazw.
cli.add_typer(tickets, name="tickets")
cli.add_typer(rag, name="rag")
cli.add_typer(docs, name="docs")


@cli.callback()
def main() -> None:
    """
    Description:
    Callback korzenia drzewa komend. Jego obecność trzyma Typer w trybie podkomend — bez niego
    aplikacja z jedną komendą się zwija i `helpdesk` uruchomiłby ją wprost, zamiast pokazać drzewo.

    Example args:
        (brak)

    Example result:
        None — Typer przechodzi dalej do podkomendy
    """


@cli.command("version", help="Wypisz zainstalowaną wersję pakietu.")
def show_version() -> None:
    """
    Description:
    Wypisuje zainstalowaną wersję pakietu. Przy okazji smoke test całego okablowania CLI: entry
    point, instalacja pakietu i rozsyłanie Typera.

    Example args:
        (brak)

    Example result:
        wypisuje „dokus-helpdesk-ai 0.1.0"
    """
    typer.echo(f"dokus-helpdesk-ai {version('dokus-helpdesk-ai')}")
