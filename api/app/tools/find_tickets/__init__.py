"""
Description:
Źródło wiedzy: historyczne zgłoszenia podobne do bieżącego. Agent podaje zgłoszenie w kształcie
korpusu (`problem` + `symptoms`), narzędzie oddaje podobne zgłoszenia z przyczyną i rozwiązaniem
— jako sparsowane pola z payloadu Qdranta, nigdy jako surowy mail.

| plik        | co zawiera                                                               |
|-------------|--------------------------------------------------------------------------|
| `models.py` | zapytanie, znaleziony element i wynik                                    |
| `base.py`   | część wspólna narzędzia i atrapy: nazwa, tekst dla modelu, lista źródeł  |
| `tool.py`   | `FindTickets` — wyszukiwanie przez embedder i Qdranta                    |
| `fake.py`   | `FakeFindTickets` — ustalony zestaw zgłoszeń, bez usług                  |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.
"""

from app.tools.find_tickets.base import FindTicketsBase
from app.tools.find_tickets.fake import FakeFindTickets
from app.tools.find_tickets.models import FindTicketsQuery, FindTicketsResult, FoundTicket
from app.tools.find_tickets.tool import FindTickets

__all__ = [
    "FakeFindTickets",
    "FindTickets",
    "FindTicketsBase",
    "FindTicketsQuery",
    "FindTicketsResult",
    "FoundTicket",
]
