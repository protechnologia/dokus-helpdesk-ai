"""
Description:
Obszar `helpdesk tickets` — korpus zgłoszeń: sprawdzenie kart i zbudowanie z korpusu obu
indeksów, w których agent szuka podobnych spraw (kolekcja kart, tabela wątków), oraz masowy
import zgłoszeń z eksportu zrzutu do korpusu (p. 31). Importuj stąd
(`from app.entry_cli.tickets import tickets`).

Do czego:
Plik na komendę, nazwany jak czynność (`helpdesk tickets index` → `index.py`); wspólny przebieg
indeksacji leży w `common.py`. Komenda `import` leży w `import_.py`, bo `import` to słowo
kluczowe Pythona. Tutaj tylko obiekt Typer i rejestracja — moduły komend nie importują obiektu
z pakietu, więc nie ma cyklu importów.

Argumentem każdej komendy jest katalog korpusu (`cards/`, `anonymized/`); bez niego korpus
z `TICKETS_CORPUS_DIR`.

| komenda                       | plik          | co robi                                          |
|-------------------------------|---------------|--------------------------------------------------|
| `tickets validate [<korpus>]` | `validate.py` | karty wobec ParsedTicket; kod 1 = błędy          |
| `tickets index [<korpus>]`    | `index.py`    | dokłada karty i wątki, nadpisując te same numery |
| `tickets reindex [<korpus>]`  | `reindex.py`  | kasuje oba indeksy i buduje od zera (pyta)       |
| `tickets import [<korpus>]`   | `import_.py`  | eksport z raw-db/ na wątki i karty; płatne       |
"""

import typer

from app.entry_cli.tickets import import_, index, reindex, validate

tickets = typer.Typer(
    help            = "Korpus zgłoszeń (data/unsafe/corpus/): import, walidacja kart i indeksy.",
    no_args_is_help = True,
)

tickets.command("validate", help=validate.HELP)(validate.validate_artifacts)
tickets.command("index",    help=index.HELP)(index.index_artifacts)
tickets.command("reindex",  help=reindex.HELP)(reindex.reindex_artifacts)
tickets.command("import",   help=import_.HELP)(import_.import_tickets)

__all__ = [
    "tickets",
]
