"""
Description:
Źródło wiedzy: oryginalny wątek zgłoszenia odczytany po numerze — tym, który agent dostał
z wyszukiwania (`find_tickets_vector`, `find_tickets_text`). Wątek to zgłoszenie w brzmieniu
sprzed parsowania, po anonimizacji: temat, opis zgłaszającego i komentarze. Agent sięga po niego,
gdy karta nie niesie szczegółu, którego potrzebuje, albo gdy zgłoszenie karty nie ma. Jedno
wywołanie to jeden wątek, więc limit wywołań jest limitem wątków przeczytanych w sprawie.

| plik             | co zawiera                                                          |
|------------------|---------------------------------------------------------------------|
| `models.py`      | zapytanie (jeden numer) i odczytany wątek                           |
| `errors.py`      | `UnknownTicketError` — nieznany numer                               |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                  |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, wiersz → wątek, źródła     |
| `tool.py`        | `ReadTicketsThreadTool` — odczyt z tabeli zgłoszeń w Postgresie     |
| `fake.py`        | `FakeReadTicketsThreadTool` — zmyślone wątki, bez usług             |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.

Narzędzie właściwe jest sprawdzone na zmyślonych wątkach. Tabela zgłoszeń dostanie prawdziwe
wątki dopiero po anonimizacji (p. 19) i masowym imporcie (p. 31) — do tego czasu jest pusta.
"""

from app.agent_tools.tickets.read_tickets_thread.base import ReadTicketsThreadToolBase
from app.agent_tools.tickets.read_tickets_thread.errors import UnknownTicketError
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.agent_tools.tickets.read_tickets_thread.models import (
    ReadTicketsThreadQuery,
    TicketThread,
)
from app.agent_tools.tickets.read_tickets_thread.tool import ReadTicketsThreadTool

__all__ = [
    "FakeReadTicketsThreadTool",
    "ReadTicketsThreadQuery",
    "ReadTicketsThreadTool",
    "ReadTicketsThreadToolBase",
    "TicketThread",
    "UnknownTicketError",
]
