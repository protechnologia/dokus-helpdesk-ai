"""
Description:
Obszar `helpdesk tickets` — wytwarzanie ARTEFAKTU (zasada 7): to, co powstaje raz i drogo. Co się
dzieje z artefaktem dalej, należy do `helpdesk rag`. Importuj stąd (`from app.cli.tickets import
tickets`).

Do czego:
Plik na komendę, nazwany jak czynność (`helpdesk tickets parse` → `parse.py`). Tutaj tylko obiekt
Typer i rejestracja — moduły komend nie importują obiektu z pakietu, więc nie ma cyklu importów.

| komenda                   | plik          | co robi                                         |
|---------------------------|---------------|-------------------------------------------------|
| `tickets validate <kat.>` | `validate.py` | artefakty wobec ParsedTicket; kod 1 = błędy     |
| `tickets parse`           | `parse.py`    | parsuje data/raw/ przez LLM, zapisuje artefakty |
"""

import typer

from app.cli.tickets import parse, validate

tickets = typer.Typer(
    help            = "Operacje na sparsowanych zgłoszeniach z data/parsed/.",
    no_args_is_help = True,
)

tickets.command("validate", help=validate.HELP)(validate.validate_artifacts)
tickets.command("parse",    help=parse.HELP)(parse.parse_tickets)

__all__ = [
    "tickets",
]
