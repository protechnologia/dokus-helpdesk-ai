"""
Description:
Obszar `helpdesk docs` — dokumentacja aplikacji: sprawdzenie paczki i zbudowanie z niej indeksów,
z których czytają narzędzia agenta. Importuj stąd (`from app.entry_cli.docs import docs`).

Do czego:
Plik na komendę, nazwany jak czynność; wspólne wypisywanie paczki leży w `common.py`,
a indekser i nazwy indeksów komenda bierze z `core_service/factory_docs_indexer.py`. Tutaj
tylko obiekt Typer i rejestracja — moduły komend nie importują obiektu z pakietu, więc nie ma
cyklu importów.

| komenda                   | plik          | co robi                                         |
|---------------------------|---------------|-------------------------------------------------|
| `docs validate <katalog>` | `validate.py` | manifesty wobec plików sekcji; kod 1 = błędy    |
| `docs index <katalog>`    | `index.py`    | zastępuje tabelę i kolekcję dokumentacji (pyta) |
"""

import typer

from app.entry_cli.docs import index, validate

docs = typer.Typer(
    help            = "Dokumentacja aplikacji: paczka i jej indeksy.",
    no_args_is_help = True,
)

docs.command("validate", help=validate.HELP)(validate.validate_package)
docs.command("index",    help=index.HELP)(index.index_package)

__all__ = [
    "docs",
]
