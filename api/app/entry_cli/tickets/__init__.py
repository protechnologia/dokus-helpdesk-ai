"""
Description:
Obszar `helpdesk tickets` — wytwarzanie ARTEFAKTU (zasada 7): to, co powstaje raz i drogo. Co się
dzieje z artefaktem dalej, należy do `helpdesk rag`. Importuj stąd
(`from app.entry_cli.tickets import tickets`).

Do czego:
Plik na komendę, nazwany jak czynność (`helpdesk tickets validate` → `validate.py`). Parsowanie
wraca przez graf `parse_ticket` (p. 46). Tutaj tylko obiekt Typer i rejestracja — moduły komend nie
importują obiektu z pakietu, więc nie ma cyklu importów.

| komenda                   | plik          | co robi                                     |
|---------------------------|---------------|---------------------------------------------|
| `tickets validate <kat.>` | `validate.py` | artefakty wobec ParsedTicket; kod 1 = błędy |
"""

import typer

from app.entry_cli.tickets import validate

tickets = typer.Typer(
    help            = "Operacje na sparsowanych zgłoszeniach z data/parsed/.",
    no_args_is_help = True,
)

tickets.command("validate", help=validate.HELP)(validate.validate_artifacts)

__all__ = [
    "tickets",
]
