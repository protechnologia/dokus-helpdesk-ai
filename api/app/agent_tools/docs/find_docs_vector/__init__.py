"""
Description:
Narzędzie pomocnicze: sekcje dokumentacji produktu podobne znaczeniowo do zapytania. Zwraca
opisy sekcji (identyfikator, dokument z wydaniem, rozdział, tytuł, opis) z podobieństwem, nie
treść — tę agent pobiera przez `read_docs`, i dopiero odczytana sekcja jest źródłem odpowiedzi.

Do czego:
Wnosi materiał, którego nie ma w korpusie zgłoszeń: jak funkcja ma działać, krok po kroku, a nie
jak jeden urząd kiedyś się na niej potknął. OPCJONALNE — instancja bez dokumentacji nie rejestruje
narzędzi dokumentacji wcale, a każdy graf musi działać z samymi zgłoszeniami.

| plik             | co zawiera                                                   |
|------------------|--------------------------------------------------------------|
| `models.py`      | zapytanie, znaleziona sekcja i wynik                         |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie           |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i tekst dla modelu   |
| `fake.py`        | `FakeFindDocsVectorTool` — ustalony zestaw sekcji, bez usług |

Status: modele i atrapa. Narzędzie właściwe (`tool.py`) na kolekcji dokumentacji powstaje w p. 8.
"""

from app.agent_tools.docs.find_docs_vector.base import FindDocsVectorToolBase
from app.agent_tools.docs.find_docs_vector.fake import FakeFindDocsVectorTool
from app.agent_tools.docs.find_docs_vector.models import (
    FindDocsVectorQuery,
    FindDocsVectorResult,
    FoundSection,
)

__all__ = [
    "FakeFindDocsVectorTool",
    "FindDocsVectorToolBase",
    "FindDocsVectorQuery",
    "FindDocsVectorResult",
    "FoundSection",
]
