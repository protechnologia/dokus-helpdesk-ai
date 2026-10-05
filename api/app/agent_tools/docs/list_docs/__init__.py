"""
Description:
Narzędzie pomocnicze: spis treści dokumentacji produktu — opis każdej sekcji: identyfikator,
dokument i wydanie, rozdział, tytuł i krótki opis. Agent wybiera z niego sekcje do odczytu
(`read_docs`) tak, jak człowiek zaczyna od spisu treści instrukcji.

| plik             | co zawiera                                                 |
|------------------|------------------------------------------------------------|
| `models.py`      | argumenty (brak) i wynik — lista sekcji                    |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie         |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i tekst dla modelu |
| `tool.py`        | `ListDocsTool` — spis z tabeli dokumentacji w Postgresie   |
| `fake.py`        | `FakeListDocsTool` — ustalony spis, bez usług              |

Przykład wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie `base.py`.
"""

from app.agent_tools.docs.list_docs.base import ListDocsToolBase
from app.agent_tools.docs.list_docs.fake import FakeListDocsTool
from app.agent_tools.docs.list_docs.models import ListDocsArgs, ListDocsResult
from app.agent_tools.docs.list_docs.tool import ListDocsTool

__all__ = [
    "FakeListDocsTool",
    "ListDocsArgs",
    "ListDocsTool",
    "ListDocsToolBase",
    "ListDocsResult",
]
