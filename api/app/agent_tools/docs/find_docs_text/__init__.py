"""
Description:
Narzędzie pomocnicze: sekcje dokumentacji znalezione po dosłownym brzmieniu — nazwie opcji,
komunikacie, kodzie — albo po słowach kluczowych w dowolnej odmianie. Uzupełnia
`find_docs_vector`, które szuka po znaczeniu. Zwraca opisy sekcji z informacją, czym każdą
znaleziono, nie treść; tę agent pobiera przez `read_docs`.

| plik             | co zawiera                                                 |
|------------------|------------------------------------------------------------|
| `models.py`      | zapytanie (`exact`, `words`), znaleziona sekcja i wynik    |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie         |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i tekst dla modelu |
| `fake.py`        | `FakeFindDocsTextTool` — ustalony zestaw sekcji, bez usług |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) na Postgresie powstaje w p. 50.
"""

from app.agent_tools.docs.find_docs_text.base import FindDocsTextToolBase
from app.agent_tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.agent_tools.docs.find_docs_text.models import (
    FindDocsTextQuery,
    FindDocsTextResult,
    MatchedSection,
)

__all__ = [
    "FakeFindDocsTextTool",
    "FindDocsTextToolBase",
    "FindDocsTextQuery",
    "FindDocsTextResult",
    "MatchedSection",
]
