"""
Description:
Tabele usługi `postgres` — jedyne wejście do bazy dla reszty aplikacji. Jedna klasa odpowiada
jednej tabeli: zakłada ją i wypełnia własnym SQL-em, a czyta i przeszukuje mechaniką wspólną
z `base.py`.

| gdzie      | klasa          | co trzyma tabela                                          |
|------------|----------------|-----------------------------------------------------------|
| `tickets/` | `TicketsTable` | zgłoszenie: pola sparsowanego rekordu i pełny tekst wątku |
| `docs/`    | `DocsTable`    | sekcja dokumentacji: opis z metryczki i treść             |
| `base.py`  | `TextTable`    | mechanika wspólna: szukanie, odczyt, kasowanie            |

Każda tabela ma swój katalog: klasę w `table.py` i SQL obok, w plikach `_create.sql`
i `_upsert.sql`. Nowa tabela to nowy katalog.
"""

from app.db_postgres.table.docs import DocsTable
from app.db_postgres.table.tickets import TicketsTable

__all__ = [
    "DocsTable",
    "TicketsTable",
]
