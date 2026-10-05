"""
Description:
Wszystko, co może wywołać pętla agenta. Wspólne kontrakty i `SourceRef` importuje się stąd
(`from app.agent_tools import KnowledgeSource`); to, co należy do jednego narzędzia — jego modele —
z pakietu tego narzędzia (`from app.agent_tools.tickets.find_tickets_vector import FoundTicket`).

Oba materiały idą dwustopniowo. Wyszukiwanie — `_vector` po znaczeniu (Qdrant), `_text` po
dosłownym brzmieniu (Postgres) — oddaje identyfikatory: numery zgłoszeń albo opisy sekcji
dokumentacji. Treść dają dopiero odczyty i tylko one cytują, więc na liście źródeł jest to, co
model przeczytał. Wynik każdego narzędzia trafia do modelu jako JSON (`result_as_json()`).

Do czego:
Dwa rodzaje narzędzi, rozdzielone kontraktem (patrz `base.py`):
    * `KnowledgeSource` — odczyt: zwraca materiał, który odpowiedź może cytować, i sam mówi
      który (`cite()`);
    * `AuxiliaryTool`   — wyszukiwanie i spis: zwraca wyłącznie tekst, więc jego wynik nigdy
      nie zostanie źródłem.

Celowo NIE ma tu anonimizatora ani modelu. Anonimizacja to stały węzeł, przez który przechodzi
każdy graf, a nie coś, co agent może wywołać albo pominąć; model jest wołającym te narzędzia, nie
jednym z nich (CLAUDE.md -> „Jak to działa").

Trzy poziomy, na każdym `base.py` z tym, co wspólne poziom niżej:

    agent_tools/base.py, models.py        kontrakty, JSON wyniku i błędu, `SourceRef` — wspólne
    agent_tools/errors.py                 `ToolCallError` — błąd, który wraca do modelu
    agent_tools/<materiał>/fake_*.py      zmyślony materiał, na którym stoją atrapy jego narzędzi
    agent_tools/<materiał>/<narzędzie>/   narzędzie: `tool.py`, `fake.py`, `base.py`, `models.py`
                                    i `description.md`

Materiały są dwa — `tickets/` i `docs/` — i nazywają się tak jak `SourceRef.source`. W katalogu
narzędzia: implementacja (`tool.py`), jej atrapa (`fake.py`), ich część wspólna (`base.py`: nazwa
i — w odczytach — lista źródeł) i `models.py` z własnym zapytaniem i wynikiem — bez wspólnej
bazy — oraz `errors.py`, gdy narzędzie ma własne błędy do zgłoszenia. Taki błąd dziedziczy po
`ToolCallError`: węzeł `run_tools` oddaje go modelowi jako wynik narzędzia zamiast przerywać
przebieg.
Nowe narzędzie to nowy katalog w folderze swojego materiału. Opis, który czyta MODEL, leży
w katalogu narzędzia (`description.md`) i jest ten sam w każdym grafie: mówi, jak pytać
narzędzie i co ono oddaje. Po co wyniki w danej funkcji, mówi prompt grafu.

| narzędzie             | rodzaj        | zapytanie agenta      | co oddaje                        |
|-----------------------|---------------|-----------------------|----------------------------------|
| `find_tickets_vector` | pomocnicze    | `problem`, `symptoms` | numery zgłoszeń z podobieństwem  |
| `find_tickets_text`   | pomocnicze    | `exact`, `words`      | numery zgłoszeń, czym znaleziono |
| `read_tickets_card`   | źródło wiedzy | `ticket_ids`          | karty zgłoszeń; cytuje           |
| `read_tickets_thread` | źródło wiedzy | `ticket_id`           | oryginalny wątek; cytuje         |
| `list_docs`           | pomocnicze    | —                     | spis treści: opisy sekcji        |
| `find_docs_vector`    | pomocnicze    | `text`                | opisy sekcji z podobieństwem     |
| `find_docs_text`      | pomocnicze    | `exact`, `words`      | opisy sekcji, czym znaleziono    |
| `read_docs`           | źródło wiedzy | `section_ids`         | treść sekcji; cytuje             |

Każde ma narzędzie właściwe i atrapę. Wyszukiwanie po znaczeniu i karty stoją na Qdrancie,
reszta na Postgresie. Tabela zgłoszeń w Postgresie dostanie prawdziwe wątki po anonimizacji
(p. 19) i masowym imporcie (p. 31), więc `find_tickets_text` i `read_tickets_thread` są
sprawdzone na zmyślonych. Narzędzia dokumentacji są opcjonalne: bez dokumentacji nie trafiają do
rejestru.
"""

from app.agent_tools.base import AgentTool, AuxiliaryTool, KnowledgeSource
from app.agent_tools.errors import ToolCallError
from app.agent_tools.models import SourceRef

__all__ = [
    "AgentTool",
    "AuxiliaryTool",
    "KnowledgeSource",
    "SourceRef",
    "ToolCallError",
]
