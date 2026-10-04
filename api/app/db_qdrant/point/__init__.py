"""
Description:
Punkty kolekcji Qdranta: to, co aplikacja zapisuje w usłudze. Jeden plik na materiał, pod tą samą
nazwą co plik kolekcji w `collection/` i plik trafienia w `hit/`.

| plik         | co zawiera       | co niesie punkt                              |
|--------------|------------------|----------------------------------------------|
| `tickets.py` | `TicketPoint`    | karta zgłoszenia, wektory `problem` i `sts`  |
| `docs.py`    | `DocPoint`       | opis sekcji dokumentacji, wektor `section`   |
| `base.py`    | `point_id_for()` | identyfikator punktu z identyfikatora źródła |

W tym samym kształcie punkt wchodzi do kolekcji i wraca z odczytu po identyfikatorze. Wynik
wyszukiwania to trafienie (`hit/`): zamiast wektorów niesie podobieństwo.
"""

from app.db_qdrant.point.base import point_id_for
from app.db_qdrant.point.docs import VECTOR_SECTION, DocPoint
from app.db_qdrant.point.tickets import VECTOR_PROBLEM, VECTOR_STS, TicketPoint

__all__ = [
    "VECTOR_PROBLEM",
    "VECTOR_SECTION",
    "VECTOR_STS",
    "DocPoint",
    "TicketPoint",
    "point_id_for",
]
