"""
Description:
Obszar `helpdesk tickets` — sparsowane zgłoszenia: sprawdzenie artefaktów i zbudowanie z nich
indeksu, w którym agent szuka podobnych spraw. Importuj stąd
(`from app.entry_cli.tickets import tickets`).

Do czego:
Plik na komendę, nazwany jak czynność (`helpdesk tickets index` → `index.py`); wspólny przebieg
indeksacji leży w `common.py`. Parsowanie zgłoszeń i wyszukiwanie z konsoli wracają przez grafy
(p. 46). Tutaj tylko obiekt Typer i rejestracja — moduły komend nie importują obiektu z pakietu,
więc nie ma cyklu importów.

| komenda                     | plik          | co robi                                          |
|-----------------------------|---------------|--------------------------------------------------|
| `tickets validate <kat.>`   | `validate.py` | artefakty wobec ParsedTicket; kod 1 = błędy      |
| `tickets index <katalog>`   | `index.py`    | dokłada artefakty, nadpisując punkty tych samych |
| `tickets reindex <katalog>` | `reindex.py`  | kasuje kolekcję i buduje od zera (pyta)          |
"""

import typer

from app.entry_cli.tickets import index, reindex, validate

tickets = typer.Typer(
    help            = "Sparsowane zgłoszenia z data/unsafe/parsed/: walidacja i indeks.",
    no_args_is_help = True,
)

tickets.command("validate", help=validate.HELP)(validate.validate_artifacts)
tickets.command("index",    help=index.HELP)(index.index_artifacts)
tickets.command("reindex",  help=reindex.HELP)(reindex.reindex_artifacts)

__all__ = [
    "tickets",
]
