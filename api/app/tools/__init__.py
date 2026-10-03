"""
Description:
Wszystko, co może wywołać pętla agenta. Wspólne kontrakty i `SourceRef` importuje się stąd
(`from app.tools import KnowledgeSource`); to, co należy do jednego narzędzia — jego modele —
z pakietu tego narzędzia (`from app.tools.tickets.find_tickets_vector import FoundTicket`).

Każdy materiał ma dwie drogi wyszukiwania: `_vector` po znaczeniu (Qdrant) i `_text` po
dosłownym brzmieniu (Postgres). Zgłoszenia wracają od razu w całości, bo są krótkie, a przyczyny
z kilku trafień model ma zobaczyć razem. Dokumentacja idzie dwustopniowo: spis treści
i wyszukiwarki oddają wiersze z identyfikatorem sekcji, a treść daje dopiero odczyt.

Do czego:
Dwa rodzaje narzędzi, rozdzielone kontraktem (patrz `base.py`):
    * `KnowledgeSource` — zwraca materiał, który odpowiedź może cytować, i sam mówi który
      (`cite()`);
    * `AuxiliaryTool`   — zwraca wyłącznie tekst, więc jego wynik nigdy nie zostanie źródłem.

Celowo NIE ma tu anonimizatora ani modelu. Anonimizacja to stały węzeł, przez który przechodzi
każdy graf, a nie coś, co agent może wywołać albo pominąć; model jest wołającym te narzędzia, nie
jednym z nich (CLAUDE.md -> „Trwa zmiana architektury").

Trzy poziomy, na każdym `base.py` z tym, co wspólne poziom niżej:

    tools/base.py, models.py        kontrakty i `SourceRef` — wspólne dla wszystkich narzędzi
    tools/<materiał>/base.py        tekst wspólny dla narzędzi jednego materiału
    tools/<materiał>/<narzędzie>/   narzędzie: `tool.py`, `fake.py`, `base.py`, `models.py`

Materiały są dwa — `tickets/` i `docs/` — i nazywają się tak jak `SourceRef.source`. W katalogu
narzędzia: implementacja (`tool.py`), jej atrapa (`fake.py`), ich część wspólna (`base.py`: nazwa,
tekst dla modelu, lista źródeł) i `models.py` z własnym zapytaniem, znalezionym elementem
i wynikiem — bez wspólnej bazy — oraz `errors.py`, gdy narzędzie ma własne błędy do zgłoszenia.
Nowe narzędzie to nowy katalog w folderze swojego materiału. Opis, który czyta MODEL, leży obok
adaptera w każdym grafie, nie tutaj: to treść promptu, czytana zdanie po zdaniu, i może się
różnić między grafami używającymi tego samego narzędzia.

| narzędzie             | rodzaj        | zapytanie agenta      | co oddaje                       |
|-----------------------|---------------|-----------------------|---------------------------------|
| `find_tickets_vector` | źródło wiedzy | `problem`, `symptoms` | zgłoszenia z podobieństwem      |
| `find_tickets_text`   | źródło wiedzy | `exact`, `words`      | zgłoszenia z etykietą trafienia |
| `list_docs`           | pomocnicze    | —                     | spis treści dokumentacji        |
| `find_docs_vector`    | pomocnicze    | `text`                | wiersze spisu z podobieństwem   |
| `find_docs_text`      | pomocnicze    | `exact`, `words`      | wiersze spisu z fragmentem      |
| `read_docs`           | źródło wiedzy | `section_ids`         | treść sekcji; jedyne cytuje     |

`find_tickets_vector` ma narzędzie właściwe i atrapę; pozostałe na razie same modele i atrapy
(p. 8 i 50–53). Narzędzia dokumentacji są opcjonalne: bez dokumentacji nie trafiają do rejestru.
"""

from app.tools.base import AgentTool, AuxiliaryTool, KnowledgeSource
from app.tools.models import SourceRef

__all__ = [
    "AgentTool",
    "AuxiliaryTool",
    "KnowledgeSource",
    "SourceRef",
]
