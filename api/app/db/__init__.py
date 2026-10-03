"""
Description:
Sposób, w jaki `api` sięga do usługi `postgres`. Reszta aplikacji używa stąd wyłącznie klas
tabel (`from app.db import TicketsTable, DocsTable`) — buduje klienta, podaje go tabeli i woła
jej metody.

Do czego:
Jeden pakiet na usługę, jak `llm/`, `embedding/` i `retrieval/` — wymiana bazy albo sterownika
ma dotknąć tylko tego katalogu. Postgres trzyma indeks wyszukiwania tekstowego z polskim
słownikiem, a od p. 29 — w osobnym schemacie i pod osobną rolą — także reguły bramek.

Każdy plik to jedna odpowiedzialność:

| plik        | co zawiera                                                    | kto używa        |
|-------------|---------------------------------------------------------------|------------------|
| `table/`    | klasa na tabelę (`TicketsTable`, `DocsTable`) i ich mechanika | reszta aplikacji |
| `row/`      | wiersze tabel: `TicketRow`, `DocRow`                          | reszta aplikacji |
| `client.py` | `PostgresClient` — połączenie i wykonanie SQL-a               | tylko `app/db/`  |
| `errors.py` | `DbError`, `DbConfigError`                                    | reszta aplikacji |

O czym pamiętać przy zmianach:

- Cały SQL jest w tym pakiecie: zakładanie i zapis w plikach `.sql` w katalogu tabeli, szukanie
  i odczyt w `table/base.py`. Metod zapytań klienta nie woła nikt spoza pakietu.
- Sterownik importuje wyłącznie `client.py` (zasada 4).
- Nowa tabela to nowy katalog w `table/` (klasa i jej pliki `.sql`) oraz model wiersza w `row/`.

Bez fabryki, jak `app.retrieval` i inaczej niż `app.llm`: droga do bazy jest jedna, więc zmienia
się adres, a adres to argument.
"""

from app.db.client import PostgresClient
from app.db.errors import DbConfigError, DbError
from app.db.row import DocRow, TicketRow
from app.db.table import DocsTable, TicketsTable

__all__ = [
    "DbConfigError",
    "DbError",
    "DocRow",
    "DocsTable",
    "PostgresClient",
    "TicketRow",
    "TicketsTable",
]
