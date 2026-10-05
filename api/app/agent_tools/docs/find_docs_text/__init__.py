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
| `tool.py`        | `FindDocsTextTool` — wyszukiwanie w tabeli w Postgresie    |
| `fake.py`        | `FakeFindDocsTextTool` — ustalony zestaw sekcji, bez usług |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.
"""

from app.agent_tools.docs.find_docs_text.base import FindDocsTextToolBase
from app.agent_tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.agent_tools.docs.find_docs_text.models import (
    FindDocsTextQuery,
    FindDocsTextResult,
    MatchedSection,
)
from app.agent_tools.docs.find_docs_text.tool import FindDocsTextTool

__all__ = [
    "FakeFindDocsTextTool",
    "FindDocsTextTool",
    "FindDocsTextToolBase",
    "FindDocsTextQuery",
    "FindDocsTextResult",
    "MatchedSection",
]
