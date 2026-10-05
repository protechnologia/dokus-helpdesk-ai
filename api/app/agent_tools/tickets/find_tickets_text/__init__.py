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
| `tool.py`        | `FindTicketsTextTool` — wyszukiwanie w tabeli w Postgresie      |
| `fake.py`        | `FakeFindTicketsTextTool` — ustalone numery zgłoszeń, bez usług |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.

Narzędzie właściwe jest sprawdzone na zmyślonych wątkach. Tabela zgłoszeń dostanie prawdziwe
wątki dopiero po anonimizacji (p. 19) i masowym imporcie (p. 31) — do tego czasu jest pusta.
"""

from app.agent_tools.tickets.find_tickets_text.base import FindTicketsTextToolBase
from app.agent_tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.agent_tools.tickets.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
    MatchedTicket,
)
from app.agent_tools.tickets.find_tickets_text.tool import FindTicketsTextTool

__all__ = [
    "FakeFindTicketsTextTool",
    "FindTicketsTextTool",
    "FindTicketsTextToolBase",
    "FindTicketsTextQuery",
    "FindTicketsTextResult",
    "MatchedTicket",
]
