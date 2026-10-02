"""
Description:
Wszystko, co może wywołać pętla agenta. Wspólne kontrakty i `SourceRef` importuje się stąd
(`from app.tools import KnowledgeSource`); to, co należy do jednego narzędzia — jego modele —
z pakietu tego narzędzia (`from app.tools.find_tickets import FoundTicket`).

Do czego:
Dwa rodzaje narzędzi, rozdzielone kontraktem (patrz `base.py`):
    * `KnowledgeSource` — zwraca materiał, który odpowiedź może cytować, i sam mówi który
      (`cite()`);
    * `AuxiliaryTool`   — zwraca wyłącznie tekst, więc jego wynik nigdy nie zostanie źródłem.

Celowo NIE ma tu anonimizatora ani modelu. Anonimizacja to stały węzeł, przez który przechodzi
każdy graf, a nie coś, co agent może wywołać albo pominąć; model jest wołającym te narzędzia, nie
jednym z nich (CLAUDE.md -> „Trwa zmiana architektury").

Tutaj: wspólne kontrakty (`base.py`) i jedyny model wspólny dla wszystkich narzędzi, `SourceRef`
(`models.py`). W katalogu każdego narzędzia: implementacja (`tool.py`), jej atrapa (`fake.py`)
i `models.py` z własnym zapytaniem, znalezionym elementem i wynikiem — bez wspólnej bazy — oraz
`errors.py`, gdy narzędzie będzie miało własne błędy do zgłoszenia. Nowe narzędzie to nowy
katalog. Opis, który czyta MODEL, leży obok adaptera w każdym grafie, nie tutaj: to treść
promptu, czytana zdanie po zdaniu, i może się różnić między grafami używającymi tego samego
narzędzia.

Narzędzia (CLAUDE.md -> „Plan i TODO", blok 0; dziś tylko modele — atrapy p. 2, właściwe p. 9):

| narzędzie      | rodzaj                    | zapytanie agenta              | na czym stoi        |
|----------------|---------------------------|-------------------------------|---------------------|
| `find_tickets` | źródło wiedzy             | `problem` + `symptoms`        | embedder → Qdrant   |
| `find_docs`    | źródło wiedzy, opcjonalne | zagadnienie / słowa kluczowe  | kolekcja dokumentów |
"""

from app.tools.base import AuxiliaryTool, KnowledgeSource
from app.tools.models import SourceRef

__all__ = [
    "AuxiliaryTool",
    "KnowledgeSource",
    "SourceRef",
]
