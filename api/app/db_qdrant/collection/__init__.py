"""
Description:
Kolekcje usługi `qdrant` — jedyne wejście do bazy wektorowej dla reszty aplikacji. Jedna klasa
odpowiada jednej kolekcji: mówi, jakie ma wektory i jakie punkty przyjmuje, a żądania wysyła
mechaniką wspólną z `base.py`.

| plik         | klasa               | co trzyma kolekcja                                     |
|--------------|---------------------|--------------------------------------------------------|
| `tickets.py` | `TicketsCollection` | karty zgłoszeń, wektory `problem` i `sts`              |
| `docs.py`    | `DocsCollection`    | fragmenty sekcji dokumentacji, wektor `section`        |
| `base.py`    | `VectorCollection`  | mechanika wspólna: zakładanie, zapis, szukanie, odczyt |

Kolekcja to plik, nie katalog jak tabela w `db_postgres/`: nie ma obok plików `.sql`, a jej
schemat to krotka nazw wektorów. Nowa kolekcja to nowy plik tutaj oraz modele punktu w `point/`
i trafienia w `hit/`.
"""

from app.db_qdrant.collection.docs import DocsCollection
from app.db_qdrant.collection.tickets import TicketsCollection

__all__ = [
    "DocsCollection",
    "TicketsCollection",
]
