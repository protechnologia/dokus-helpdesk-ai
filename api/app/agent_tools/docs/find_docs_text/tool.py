"""
Description:
Prawdziwe narzędzie `find_docs_text`: znajduje w Postgresie sekcje dokumentacji po dosłownym
brzmieniu i po słowach kluczowych i oddaje ich opisy z informacją, czym każdą znaleziono. Nie
woła embeddera ani LLM-a — tylko tabelę dokumentacji.

    `exact` → podciąg ──────────────────────┐
                                            ├→ jedna lista, każda sekcja raz → limit → opisy sekcji
    `words` → słowa przez polski słownik ───┘

Przed — zapytanie agenta:

    FindDocsTextQuery(exact="PDP-203", words="sekwencja numeracja")

Po — wynik `find()` (limit 5; frazę znaleziono w jednej sekcji, słowa w innej):

    FindDocsTextResult(
        sections = [
            MatchedSection(matched_by="exact", section=DocSection(section_id="adm-podpis-…", …)),
            MatchedSection(matched_by="words", section=DocSection(section_id="adm-numeracja-…", …)),
        ],
        omitted_over_limit = 0,
    )

Co się dzieje po drodze:

1. Fraza z `exact` jest szukana dosłownie, bez względu na wielkość liter i na to, jak tekst
   złamano między liniami; `words` — przez słownik, w dowolnej odmianie i kolejności.
2. Wyniki łączą się w jedną listę: najpierw sekcje znalezione frazą, potem słowami. Sekcja
   znaleziona obiema drogami stoi raz, jako znaleziona frazą.
3. Lista jest cięta do `RAG_TOP_K`; reszta jest policzona w `omitted_over_limit`.
4. Opisy sekcji, które zostały, narzędzie czyta z tabeli po identyfikatorach.

O czym pamiętać przy zmianach:

- Pola szukają niezależnie i wyniki się sumują. Sekcja nie musi pasować do obu.
- `exact` to jedna fraza, nie lista: przy kilku frazach wynik nie mówiłby, która trafiła,
  a „którakolwiek z fraz" obok „wszystkie słowa" trzeba by modelowi tłumaczyć. Kilka fraz to
  kilka wywołań.
- Fraza idzie przez podciąg, nie przez słownik: „dosłownie" znaczy bez odmiany, a parser
  pełnotekstowy skleja kod z interpunkcją w jeden token, więc fragmentu kodu („0417"
  z „EDR-0417") słowami nie znajdzie.
- Ile zwrócić, ustawia konfiguracja, nie agent — zapytanie niesie tylko to, czego szukać.
- Z odczytu wraca też treść sekcji, której to narzędzie nie oddaje: do modelu idzie sam opis,
  bo treść ma dać `read_docs` i tylko on cytuje.
"""

import logging

from app.agent_tools.base import label_matches
from app.agent_tools.docs.find_docs_text.base import FindDocsTextToolBase
from app.agent_tools.docs.find_docs_text.models import (
    FindDocsTextQuery,
    FindDocsTextResult,
    MatchedSection,
)
from app.db_postgres import DocsTable

logger = logging.getLogger(__name__)


class FindDocsTextTool(FindDocsTextToolBase):
    """
    Description:
    `find_docs_text` na prawdziwym indeksie: tabela dokumentacji w Postgresie znajduje sekcje
    po frazie i po słowach, a narzędzie łączy wyniki, tnie je limitem i oddaje opisy sekcji.

    Do czego:
    Wyszukiwanie w dokumentacji po dosłownym brzmieniu w grafach `search`, `suggest_questions`
    i `suggest_solution`. Tylko do odczytu: nic tu nie zapisuje do indeksu.

    Flow:
        1. `find()` pyta tabelę o frazę z `exact` i o `words`; dostaje identyfikatory.
        2. `label_matches()` łączy je w jedną listę z etykietami.
        3. Lista jest cięta do `limit`, a opisy pozostałych sekcji czytane z tabeli.
        4. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        docs:  DocsTable,  # np. DocsTable(PostgresClient(host="postgres", …))
        limit: int,        # np. 5 — RAG_TOP_K
    ):
        """
        Description:
        Spina narzędzie z tabelą dokumentacji i z limitem długości wyniku. Tabela jest
        wstrzykiwana, nie budowana tutaj (zasada 4).

        Example args:
            docs=DocsTable(PostgresClient(host="postgres", port=5432, database="helpdesk", …))
            limit=5

        Example result:
            FindDocsTextTool gotowe do wyszukiwania w tabeli `docs_text`
        """
        self._docs  = docs
        self._limit = limit

    async def find(
        self,
        query: FindDocsTextQuery,  # np. FindDocsTextQuery(words="uprawnienie kancelaria")
    ) -> FindDocsTextResult:
        """
        Description:
        Znajduje sekcje dokumentacji zawierające frazę z `exact` albo wszystkie słowa z `words`,
        znalezione frazą najpierw, przycięte limitem.

        Example args:
            query=FindDocsTextQuery(exact="PDP-203", words="sekwencja numeracja")

        Example result:
            FindDocsTextResult(sections=[MatchedSection(matched_by="exact", …),
                                         MatchedSection(matched_by="words", …)],
                               omitted_over_limit=0)

        Raises:
            DbPostgresError: Postgres jest nieosiągalny albo odpowiedział błędem
        """
        # --- fraza: dosłownie; słowa: przez słownik, najlepiej dopasowane pierwsze ---
        exact_ids = await self._docs.substring(query.exact) if query.exact else []
        words_ids = await self._docs.words(query.words) if query.words else []

        # --- jedna lista, cięta limitem; resztę liczymy, zamiast gubić ---
        matched = label_matches(exact_ids, words_ids)
        kept    = list(matched)[: self._limit]
        omitted = len(matched) - len(kept)

        # --- opisy sekcji, w kolejności listy; bez trafień nie ma czego czytać ---
        rows = await self._docs.read_by_id(kept) if kept else []

        # Same liczby: zapytanie agenta niesie treść zgłoszenia.
        logger.info(
            "find_docs_text exact=%s words=%s matched=%d omitted=%d",
            bool(query.exact),
            bool(query.words),
            len(matched),
            omitted,
        )

        result = FindDocsTextResult(
            sections = [
                MatchedSection(matched_by=matched[row.section_id], section=row.to_section())
                for row in rows
            ],
            omitted_over_limit = omitted,
        )

        return result

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenie z Postgresem. Sprzątający woła tylko to i nie musi wiedzieć, z czego
        narzędzie jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._docs.aclose()
