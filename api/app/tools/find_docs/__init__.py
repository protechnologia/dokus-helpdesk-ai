"""
Description:
Źródło wiedzy: fragmenty dokumentacji produktu. OPCJONALNE — instancja bez skonfigurowanej
kolekcji dokumentacji w ogóle nie rejestruje tego narzędzia, a każdy graf musi działać z samym
`find_tickets`.

Do czego:
Wnosi materiał, którego nie ma w korpusie zgłoszeń: jak funkcja ma działać, krok po kroku, a nie
jak jeden urząd kiedyś się na niej potknął. Każdy fragment niesie wersję i datę dokumentu, bo
instrukcja do starszego wydania wprowadza w błąd dokładnie tak jak odmowa obalona później nowszym
zgłoszeniem (CLAUDE.md -> „Ryzyka jakości treści").

Status: modele (tymczasowe) i atrapa (`FakeFindDocs`). Czy dokumentacja w ogóle istnieje
i w jakiej formie, to otwarta decyzja (CLAUDE.md -> „Plan i TODO", p. 12); `tool.py` powstaje
w p. 9, wczytanie kolekcji w p. 20.
"""

from app.tools.find_docs.fake import FakeFindDocs
from app.tools.find_docs.models import FindDocsQuery, FindDocsResult, FoundDoc

__all__ = [
    "FakeFindDocs",
    "FindDocsQuery",
    "FindDocsResult",
    "FoundDoc",
]
