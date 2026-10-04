"""
Description:
Źródło wiedzy: oryginalne wątki zgłoszeń odczytane po numerach — tych, które agent dostał
z wyszukiwania (`find_tickets_vector`, `find_tickets_text`). Wątek to zgłoszenie w brzmieniu
sprzed parsowania, po anonimizacji: temat, opis zgłaszającego i komentarze. Agent sięga po niego,
gdy karta nie niesie szczegółu, którego potrzebuje, albo gdy zgłoszenie karty nie ma.

| plik             | co zawiera                                                          |
|------------------|---------------------------------------------------------------------|
| `models.py`      | zapytanie (numery, najwyżej pięć), odczytany wątek i wynik          |
| `errors.py`      | `UnknownTicketError` — nieznany numer, bez wyniku częściowego       |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                  |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, wiersz → wątek, źródła     |
| `fake.py`        | `FakeReadTicketsThreadTool` — zmyślone wątki, bez usług             |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) na Postgresie powstaje w p. 56, a na
prawdziwym korpusie ruszy po anonimizacji (p. 19) i masowym imporcie (p. 31).
"""

from app.agent_tools.tickets.read_tickets_thread.base import ReadTicketsThreadToolBase
from app.agent_tools.tickets.read_tickets_thread.errors import UnknownTicketError
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.agent_tools.tickets.read_tickets_thread.models import (
    ReadTicketsThreadQuery,
    ReadTicketsThreadResult,
    TicketThread,
)

__all__ = [
    "FakeReadTicketsThreadTool",
    "ReadTicketsThreadQuery",
    "ReadTicketsThreadResult",
    "ReadTicketsThreadToolBase",
    "TicketThread",
    "UnknownTicketError",
]
