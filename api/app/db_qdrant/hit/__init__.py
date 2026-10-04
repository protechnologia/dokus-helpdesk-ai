"""
Description:
Trafienia z kolekcji Qdranta: to, co oddaje wyszukiwanie. Jeden plik na materiał, pod tą samą
nazwą co plik punktu w `point/` i plik kolekcji w `collection/`.

| plik         | klasa       | co niesie trafienie                        |
|--------------|-------------|--------------------------------------------|
| `tickets.py` | `TicketHit` | podobieństwo i karta zgłoszenia z payloadu |
| `docs.py`    | `DocHit`    | podobieństwo i opis sekcji dokumentacji    |

Trafienie to nie punkt: nie ma wektorów, a ma podobieństwo. Punkt (`point/`) wchodzi do kolekcji
i wraca z odczytu po identyfikatorze; trafienie wraca tylko z wyszukiwania.
"""

from app.db_qdrant.hit.docs import DocHit
from app.db_qdrant.hit.tickets import TicketHit

__all__ = [
    "DocHit",
    "TicketHit",
]
