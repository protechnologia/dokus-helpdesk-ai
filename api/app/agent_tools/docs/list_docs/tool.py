"""
Description:
Prawdziwe narzędzie `list_docs`: czyta z Postgresa spis treści dokumentacji — opis każdej sekcji
z metryczki, bez treści. Nie woła embeddera ani LLM-a — tylko tabelę dokumentacji.

    tabela dokumentacji → wszystkie sekcje w kolejności spisu → opisy sekcji

Przed — wywołanie agenta:

    ListDocsArgs()

Po — wynik `load()` (dwa dokumenty, po dwie sekcje):

    ListDocsResult(sections=[
        DocSection(section_id="adm-kancelaria-edoreczenia", title="Uprawnienie do kancelarii…", …),
        DocSection(section_id="adm-kancelaria-epuap",       title="Uprawnienie do skrzynki…", …),
        DocSection(section_id="usr-wysylka-status-w-toku",  title="Status „W toku” przy…", …),
        DocSection(section_id="usr-komunikat-brak-serwera", title="Komunikat „Nie udało się…”", …),
    ])

Co się dzieje po drodze:

1. Tabela oddaje wszystkie sekcje: dokument po dokumencie, sekcje w kolejności z metryczki.
2. Z każdego wiersza zostaje opis sekcji; treść do wyniku nie trafia.

O czym pamiętać przy zmianach:

- Spis nie ma argumentów ani limitu: model dostaje opisy wszystkich sekcji naraz. Czy spis
  właściwej dokumentacji się na to nadaje, rozstrzygnie się przy niej (p. 15).
- Kolejność ustala tabela, nie narzędzie: sekcje stoją tak, jak w dokumentach, a nie alfabetycznie
  po identyfikatorze.
- Z tabeli wraca też treść każdej sekcji, której to narzędzie nie oddaje: do modelu idzie sam
  opis, bo treść ma dać `read_docs` i tylko on cytuje.
- Pusta tabela to pusty spis, nie błąd.
"""

import logging

from app.agent_tools.docs.list_docs.base import ListDocsToolBase
from app.agent_tools.docs.list_docs.models import ListDocsResult
from app.db_postgres import DocsTable

logger = logging.getLogger(__name__)


class ListDocsTool(ListDocsToolBase):
    """
    Description:
    `list_docs` na prawdziwym indeksie: tabela dokumentacji w Postgresie oddaje wszystkie sekcje,
    a narzędzie zostawia z nich opisy.

    Do czego:
    Spis treści dokumentacji w grafach `search`, `suggest_questions` i `suggest_solution` — to,
    od czego agent zaczyna, gdy nie wie jeszcze, czego w instrukcji szukać. Tylko do odczytu.

    Flow:
        1. `load()` czyta wszystkie wiersze tabeli w kolejności spisu.
        2. Każdy wiersz staje się opisem sekcji, bez treści.
        3. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        docs: DocsTable,  # np. DocsTable(PostgresClient(host="postgres", …))
    ):
        """
        Description:
        Spina narzędzie z tabelą dokumentacji. Tabela jest wstrzykiwana, nie budowana tutaj
        (zasada 4).

        Example args:
            docs=DocsTable(PostgresClient(host="postgres", port=5432, database="helpdesk", …))

        Example result:
            ListDocsTool gotowe do czytania spisu z tabeli `docs_text`
        """
        self._docs = docs

    async def load(self) -> ListDocsResult:
        """
        Description:
        Pobiera spis treści całej dokumentacji, w kolejności dokumentów i sekcji.

        Example args:
            (brak)

        Example result:
            ListDocsResult(sections=[DocSection(section_id="adm-kancelaria-edoreczenia", …), …])

        Raises:
            DbPostgresError: Postgres jest nieosiągalny albo odpowiedział błędem
        """
        rows = await self._docs.list_all()

        logger.info("list_docs sections=%d", len(rows))

        result = ListDocsResult(
            sections = [row.to_section() for row in rows],
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
