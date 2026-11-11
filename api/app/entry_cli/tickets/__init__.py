"""
Description:
Obszar `helpdesk tickets` — korpus zgłoszeń: sprawdzenie kart i zbudowanie z korpusu obu
indeksów, w których agent szuka podobnych spraw (kolekcja kart, tabela wątków). Importuj stąd
(`from app.entry_cli.tickets import tickets`).

Do czego:
Plik na komendę, nazwany jak czynność (`helpdesk tickets index` → `index.py`); wspólny przebieg
indeksacji leży w `common.py`. Parsowanie zgłoszeń do korpusu dojdzie z masowym importem
(p. 31). Tutaj tylko obiekt Typer i rejestracja — moduły komend nie importują obiektu z pakietu,
więc nie ma cyklu importów.

Argumentem każdej komendy jest katalog korpusu (`cards/`, `anonymized/`); bez niego korpus
z `TICKETS_CORPUS_DIR`.

| komenda                       | plik          | co robi                                          |
|-------------------------------|---------------|--------------------------------------------------|
| `tickets validate [<korpus>]` | `validate.py` | karty wobec ParsedTicket; kod 1 = błędy          |
| `tickets index [<korpus>]`    | `index.py`    | dokłada karty i wątki, nadpisując te same numery |
| `tickets reindex [<korpus>]`  | `reindex.py`  | kasuje oba indeksy i buduje od zera (pyta)       |
"""

import typer

from app.entry_cli.tickets import index, reindex, validate

tickets = typer.Typer(
    help            = "Korpus zgłoszeń (data/unsafe/corpus/): walidacja kart i indeksy.",
    no_args_is_help = True,
)

tickets.command("validate", help=validate.HELP)(validate.validate_artifacts)
tickets.command("index",    help=index.HELP)(index.index_artifacts)
tickets.command("reindex",  help=reindex.HELP)(reindex.reindex_artifacts)

__all__ = [
    "tickets",
]
