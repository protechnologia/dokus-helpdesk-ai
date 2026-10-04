"""
Description:
Narzędzie pomocnicze: historyczne zgłoszenia znalezione po dosłownym brzmieniu — kodzie błędu,
fragmencie komunikatu albo słowach kluczowych w dowolnej odmianie. Uzupełnia
`find_tickets_vector`, które szuka po znaczeniu. Zwraca numery zgłoszeń z informacją, czym każde
znaleziono; treść agent czyta osobno, przez `read_tickets_thread` albo `read_tickets_card`.

| plik             | co zawiera                                                      |
|------------------|-----------------------------------------------------------------|
| `models.py`      | zapytanie (`exact`, `words`), znalezione zgłoszenie i wynik     |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie              |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i tekst dla modelu      |
| `fake.py`        | `FakeFindTicketsTextTool` — ustalone numery zgłoszeń, bez usług |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) na Postgresie powstaje w p. 53, a na
prawdziwym korpusie ruszy po anonimizacji opisów (p. 19) i masowym imporcie (p. 31).
"""

from app.agent_tools.tickets.find_tickets_text.base import FindTicketsTextToolBase
from app.agent_tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.agent_tools.tickets.find_tickets_text.models import (
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
