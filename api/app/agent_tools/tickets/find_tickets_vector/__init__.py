"""
Description:
Narzędzie pomocnicze: historyczne zgłoszenia o problemie podobnym do bieżącego. Agent podaje
zgłoszenie w kształcie korpusu (`problem` + `symptoms`), narzędzie oddaje numery podobnych
zgłoszeń z podobieństwem. Treść agent czyta osobno: kartę przez `read_tickets_card`, oryginalny
wątek przez `read_tickets_thread` — i dopiero odczyt jest źródłem odpowiedzi.

| plik             | co zawiera                                                        |
|------------------|-------------------------------------------------------------------|
| `models.py`      | zapytanie, znalezione zgłoszenie (numer i podobieństwo) i wynik   |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i tekst dla modelu        |
| `tool.py`        | `FindTicketsVectorTool` — wyszukiwanie przez embedder i Qdranta   |
| `fake.py`        | `FakeFindTicketsVectorTool` — ustalone numery zgłoszeń, bez usług |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.
"""

from app.agent_tools.tickets.find_tickets_vector.base import FindTicketsVectorToolBase
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.agent_tools.tickets.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)
from app.agent_tools.tickets.find_tickets_vector.tool import FindTicketsVectorTool

__all__ = [
    "FakeFindTicketsVectorTool",
    "FindTicketsVectorTool",
    "FindTicketsVectorToolBase",
    "FindTicketsVectorQuery",
    "FindTicketsVectorResult",
    "FoundTicket",
]
