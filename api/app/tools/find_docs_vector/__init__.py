"""
Description:
Źródło wiedzy: fragmenty dokumentacji produktu. OPCJONALNE — instancja bez skonfigurowanej
kolekcji dokumentacji w ogóle nie rejestruje tego narzędzia, a każdy graf musi działać z samym
`find_tickets_vector`.

Do czego:
Wnosi materiał, którego nie ma w korpusie zgłoszeń: jak funkcja ma działać, krok po kroku, a nie
jak jeden urząd kiedyś się na niej potknął. Każdy fragment niesie wersję i datę dokumentu, bo
instrukcja do starszego wydania wprowadza w błąd dokładnie tak jak odmowa obalona później nowszym
zgłoszeniem (CLAUDE.md -> „Ryzyka jakości treści").

Status: modele (tymczasowe) i atrapa (`FakeFindDocsVector`). Czy dokumentacja w ogóle istnieje
i w jakiej formie, to otwarta decyzja (CLAUDE.md -> „Plan i TODO", p. 15); `tool.py` i wczytanie
kolekcji powstają w p. 8.
"""

from app.tools.find_docs_vector.fake import FakeFindDocsVector
from app.tools.find_docs_vector.models import FindDocsVectorQuery, FindDocsVectorResult, FoundDoc

__all__ = [
    "FakeFindDocsVector",
    "FindDocsVectorQuery",
    "FindDocsVectorResult",
    "FoundDoc",
]
