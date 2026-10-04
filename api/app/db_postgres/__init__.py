"""
Description:
Sposób, w jaki `api` sięga do usługi `postgres`. Reszta aplikacji używa stąd wyłącznie klas
tabel (`from app.db_postgres import TicketsTable, DocsTable`) — buduje klienta, podaje go
tabeli i woła jej metody.

Do czego:
Jeden pakiet na usługę, jak `llm/`, `embedding/` i `db_qdrant/` — wymiana bazy albo sterownika
ma dotknąć tylko tego katalogu. Postgres trzyma indeks wyszukiwania tekstowego z polskim
słownikiem, a od p. 29 — w osobnym schemacie i pod osobną rolą — także reguły bramek.

Każdy plik to jedna odpowiedzialność:

| plik        | co zawiera                                                    | kto używa        |
|-------------|---------------------------------------------------------------|------------------|
| `table/`    | klasa na tabelę (`TicketsTable`, `DocsTable`) i ich mechanika | reszta aplikacji |
| `row/`      | wiersze tabel: `TicketRow`, `DocRow`                          | reszta aplikacji |
| `client.py` | `PostgresClient` — połączenie i wykonanie SQL-a               | tylko ten pakiet |
| `errors.py` | `DbPostgresError`, `DbPostgresConfigError`                    | reszta aplikacji |

O czym pamiętać przy zmianach:

- Cały SQL jest w tym pakiecie: zakładanie i zapis w plikach `.sql` w katalogu tabeli, szukanie
  i odczyt w `table/base.py`. Metod zapytań klienta nie woła nikt spoza pakietu.
- Sterownik importuje wyłącznie `client.py` (zasada 4).
- Nowa tabela to nowy katalog w `table/` (klasa i jej pliki `.sql`) oraz model wiersza w `row/`.

Bez fabryki, jak `app.db_qdrant` i inaczej niż `app.llm`: droga do bazy jest jedna, więc zmienia
się adres, a adres to argument.

Błędy nazywają się `DbPostgres…`, nie `Postgres…`: `PostgresError` to klasa sterownika `asyncpg`
i dwie klasy o tej samej nazwie w jednym pliku łatwo pomylić.
"""

from app.db_postgres.client import PostgresClient
from app.db_postgres.errors import DbPostgresConfigError, DbPostgresError
from app.db_postgres.row import DocRow, TicketRow
from app.db_postgres.table import DocsTable, TicketsTable

__all__ = [
    "DbPostgresConfigError",
    "DbPostgresError",
    "DocRow",
    "DocsTable",
    "PostgresClient",
    "TicketRow",
    "TicketsTable",
]
