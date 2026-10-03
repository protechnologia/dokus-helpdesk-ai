"""
Description:
Źródło wiedzy: historyczne zgłoszenia znalezione po dosłownym brzmieniu — kodzie błędu,
fragmencie komunikatu albo słowach kluczowych w dowolnej odmianie. Uzupełnia
`find_tickets_vector`, które szuka po znaczeniu, i oddaje te same sparsowane zgłoszenia.

| plik        | co zawiera                                                              |
|-------------|-------------------------------------------------------------------------|
| `models.py` | zapytanie (`exact`, `words`), znalezione zgłoszenie i wynik             |
| `base.py`   | część wspólna narzędzia i atrapy: nazwa, tekst dla modelu, lista źródeł |
| `fake.py`   | `FakeFindTicketsTextTool` — ustalony zestaw zgłoszeń, bez usług         |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) na Postgresie powstaje w p. 53, a na
prawdziwym korpusie ruszy po anonimizacji opisów (p. 19) i masowym imporcie (p. 31).
"""

from app.tools.tickets.find_tickets_text.base import FindTicketsTextToolBase
from app.tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.tools.tickets.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
    MatchedTicket,
)

__all__ = [
    "FakeFindTicketsTextTool",
    "FindTicketsTextToolBase",
    "FindTicketsTextQuery",
    "FindTicketsTextResult",
    "MatchedTicket",
]
