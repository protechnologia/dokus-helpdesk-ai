"""
Description:
Sposób, w jaki `api` sięga do usługi `qdrant`. Reszta aplikacji używa stąd wyłącznie klas
kolekcji (`from app.db_qdrant import TicketsCollection, DocsCollection`) — buduje klienta,
podaje go kolekcji i woła jej metody.

Do czego:
Jeden pakiet na usługę, jak `engine_llm/`, `engine_embedding/` i `db_postgres/` — wymiana bazy
wektorowej ma dotknąć tylko tego katalogu. Qdrant jest indeksem, nigdy źródłem prawdy (zasada 8):
każda kolekcja odbudowuje się z plików jedną komendą, więc jej skasowanie to zwykła operacja.

Każdy plik to jedna odpowiedzialność:

| plik          | co zawiera                                                | kto używa        |
|---------------|-----------------------------------------------------------|------------------|
| `collection/` | klasa na kolekcję (`TicketsCollection`, `DocsCollection`) | reszta aplikacji |
| `point/`      | punkty — to, co zapisujemy: `TicketPoint`, `DocPoint`     | reszta aplikacji |
| `hit/`        | trafienia — wynik szukania: `TicketHit`, `DocHit`         | reszta aplikacji |
| `client.py`   | `QdrantClient` — żądanie HTTP i tłumaczenie błędów        | tylko ten pakiet |
| `errors.py`   | `DbQdrantError`, `DbQdrantConfigError`                    | reszta aplikacji |

O czym pamiętać przy zmianach:

- Kształt żądań i odpowiedzi Qdranta zna wyłącznie ten pakiet: ścieżki w `collection/base.py`,
  kształt punktu w `point/`, trafienia w `hit/`. Metod żądań klienta nie woła nikt spoza pakietu.
- `httpx` importuje wyłącznie `client.py` (zasada 4).
- Nowa kolekcja to nowy plik w `collection/`, model punktu w `point/` i trafienia w `hit/`.
- Modele punktów i trafień leżą tutaj, a nie w `core_model/`: opisują to, co idzie po drucie
  do jednej usługi (CLAUDE.md -> „Warstwy kodu").

Bez fabryki, jak `app.db_postgres` i inaczej niż `app.engine_llm`: droga do bazy jest jedna, więc
zmienia się adres, a adres to argument.
"""

from app.db_qdrant.client import QdrantClient
from app.db_qdrant.collection import DocsCollection, TicketsCollection
from app.db_qdrant.errors import DbQdrantConfigError, DbQdrantError
from app.db_qdrant.hit import DocHit, TicketHit
from app.db_qdrant.point import (
    VECTOR_PROBLEM,
    VECTOR_SECTION,
    VECTOR_STS,
    DocPoint,
    TicketPoint,
    point_id_for,
)

__all__ = [
    "VECTOR_PROBLEM",
    "VECTOR_SECTION",
    "VECTOR_STS",
    "DbQdrantConfigError",
    "DbQdrantError",
    "DocHit",
    "DocPoint",
    "DocsCollection",
    "QdrantClient",
    "TicketHit",
    "TicketPoint",
    "TicketsCollection",
    "point_id_for",
]
