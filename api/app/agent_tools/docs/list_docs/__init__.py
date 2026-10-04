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
| `fake.py`        | `FakeListDocsTool` — ustalony spis, bez usług              |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) powstaje w p. 51.
"""

from app.agent_tools.docs.list_docs.base import ListDocsToolBase
from app.agent_tools.docs.list_docs.fake import FakeListDocsTool
from app.agent_tools.docs.list_docs.models import ListDocsArgs, ListDocsResult

__all__ = [
    "FakeListDocsTool",
    "ListDocsArgs",
    "ListDocsToolBase",
    "ListDocsResult",
]
