"""
Description:
Obszar `helpdesk rag` — baza wektorowa (noga 1). Importuj stąd (`from app.cli.rag
import rag`).

Do czego:
Plik na komendę, nazwany jak czynność (`helpdesk rag index` → `index.py`); wspólny przebieg
indeksacji leży w `common.py`. Wyszukiwanie z konsoli wraca przez graf `search` (p. 46). Tutaj tylko
obiekt Typer i rejestracja — moduły komend nie importują obiektu z pakietu, więc nie ma cyklu
importów. Bramki i „Popraw" tu NIE trafią: z definicji działają bez indeksu.

| komenda                 | plik         | co robi                                          |
|-------------------------|--------------|--------------------------------------------------|
| `rag index <katalog>`   | `index.py`   | dokłada artefakty, nadpisując punkty tych samych |
| `rag reindex <katalog>` | `reindex.py` | kasuje kolekcję i buduje od zera (pyta)          |
"""

import typer

from app.cli.rag import index, reindex

rag = typer.Typer(
    help            = "RAG: baza wektorowa.",
    no_args_is_help = True,
)

rag.command("index",   help=index.HELP)(index.index_artifacts)
rag.command("reindex", help=reindex.HELP)(reindex.reindex_artifacts)

__all__ = [
    "rag",
]
