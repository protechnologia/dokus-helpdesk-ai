"""
Description:
Źródło wiedzy: historyczne zgłoszenia podobne do bieżącego. Agent podaje zgłoszenie w kształcie
korpusu (`problem` + `symptoms`), narzędzie oddaje podobne zgłoszenia z przyczyną i rozwiązaniem
— jako sparsowane pola z payloadu Qdranta, nigdy jako surowy mail.

| plik        | co zawiera                                                              |
|-------------|-------------------------------------------------------------------------|
| `models.py` | zapytanie, znaleziony element i wynik                                   |
| `base.py`   | część wspólna narzędzia i atrapy: nazwa, tekst dla modelu, lista źródeł |
| `tool.py`   | `FindTicketsVector` — wyszukiwanie przez embedder i Qdranta             |
| `fake.py`   | `FakeFindTicketsVector` — ustalony zestaw zgłoszeń, bez usług           |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.
"""

from app.tools.find_tickets_vector.base import FindTicketsVectorBase
from app.tools.find_tickets_vector.fake import FakeFindTicketsVector
from app.tools.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)
from app.tools.find_tickets_vector.tool import FindTicketsVector

__all__ = [
    "FakeFindTicketsVector",
    "FindTicketsVector",
    "FindTicketsVectorBase",
    "FindTicketsVectorQuery",
    "FindTicketsVectorResult",
    "FoundTicket",
]
