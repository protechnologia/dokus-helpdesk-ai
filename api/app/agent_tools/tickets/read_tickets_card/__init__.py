"""
Description:
Źródło wiedzy: karty zgłoszeń odczytane po numerach — tych, które agent dostał z wyszukiwania
(`find_tickets_vector`, `find_tickets_text`). Karta to streszczenie zgłoszenia w polach
`problem`, `symptoms`, `cause`, `solution` i kilku pomocniczych. Z kart agent dowiaduje się, co
było przyczyną i co pomogło; oryginalne brzmienie daje `read_tickets_thread`.

| plik             | co zawiera                                                              |
|------------------|-------------------------------------------------------------------------|
| `models.py`      | zapytanie (do dwudziestu numerów) i wynik: karty oraz numery bez kart   |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                      |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, tekst dla modelu, lista źródeł |
| `tool.py`        | `ReadTicketsCardTool` — odczyt z kolekcji zgłoszeń w Qdrancie           |
| `fake.py`        | `FakeReadTicketsCardTool` — zmyślone karty, bez usług                   |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.
"""

from app.agent_tools.tickets.read_tickets_card.base import ReadTicketsCardToolBase
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_card.models import (
    ReadTicketsCardQuery,
    ReadTicketsCardResult,
)
from app.agent_tools.tickets.read_tickets_card.tool import ReadTicketsCardTool

__all__ = [
    "FakeReadTicketsCardTool",
    "ReadTicketsCardQuery",
    "ReadTicketsCardResult",
    "ReadTicketsCardTool",
    "ReadTicketsCardToolBase",
]
