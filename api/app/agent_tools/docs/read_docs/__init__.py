"""
Description:
Źródło wiedzy: treść sekcji dokumentacji odczytana po identyfikatorach — tych, które agent
dostał ze spisu treści (`list_docs`) albo z wyszukiwania (`find_docs_vector`, `find_docs_text`).
Jedyne narzędzie dokumentacji, które cytuje: źródłem odpowiedzi jest sekcja przeczytana, nie
taka, którą model tylko zobaczył w spisie.

| plik             | co zawiera                                                              |
|------------------|-------------------------------------------------------------------------|
| `models.py`      | zapytanie (identyfikatory, najwyżej pięć), odczytana sekcja i wynik     |
| `errors.py`      | `UnknownSectionError` — nieznany identyfikator, bez wyniku częściowego  |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                      |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i lista źródeł                  |
| `fake.py`        | `FakeReadDocsTool` — zmyślona dokumentacja, bez usług                   |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) powstaje w p. 52.
"""

from app.agent_tools.docs.read_docs.base import ReadDocsToolBase
from app.agent_tools.docs.read_docs.errors import UnknownSectionError
from app.agent_tools.docs.read_docs.fake import FakeReadDocsTool
from app.agent_tools.docs.read_docs.models import ReadDocsQuery, ReadDocsResult, ReadSection

__all__ = [
    "FakeReadDocsTool",
    "ReadDocsToolBase",
    "ReadDocsQuery",
    "ReadDocsResult",
    "ReadSection",
    "UnknownSectionError",
]
