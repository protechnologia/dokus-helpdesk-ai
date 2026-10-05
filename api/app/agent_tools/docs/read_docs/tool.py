"""
Description:
Prawdziwe narzędzie `read_docs`: czyta z Postgresa treść sekcji dokumentacji o podanych
identyfikatorach. Nie woła embeddera ani LLM-a — tylko tabelę dokumentacji.

    identyfikatory sekcji → wiersze tabeli dokumentacji → opis sekcji i jej treść

Przed — zapytanie agenta:

    ReadDocsQuery(section_ids=["usr-wysylka-status-w-toku", "adm-kancelaria-edoreczenia"])

Po — wynik `search()`:

    ReadDocsResult(sections=[
        ReadSection(
            section = DocSection(section_id="usr-wysylka-status-w-toku", version="4.12", …),
            text    = "Status „W toku” przy wysyłce ePUAP oznacza nadawanie w trakcie — ponowna…",
        ),
        ReadSection(
            section = DocSection(section_id="adm-kancelaria-edoreczenia", version="4.12", …),
            text    = "Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia → …",
        ),
    ])

Co się dzieje po drodze:

1. Powtórzone identyfikatory zostają raz, w kolejności żądania.
2. Tabela oddaje sekcje, które ma, w tej samej kolejności.
3. Gdy którejś nie ma, odczyt kończy się `UnknownSectionError` z listą nieznanych
   identyfikatorów — bez wyniku częściowego.
4. Każdy wiersz staje się opisem sekcji i jej treścią, znak w znak taką jak w pliku `.md`.

O czym pamiętać przy zmianach:

- Wszystko albo nic: odczyt jednej sekcji zamiast dwóch wygląda dokładnie jak poprawny,
  a odpowiedź oparta na niepełnym materiale nie nosi po tym śladu.
- Treść wraca z kolumny `body`, czyli dosłowna, ze złamaniami linii. Tekst, w którym szukają
  wyszukiwania, ma białe znaki sprowadzone do spacji i do modelu nie idzie.
- Ile sekcji da się odczytać jednym wywołaniem, mówi model zapytania, nie to narzędzie.
"""

import logging

from app.agent_tools.docs.read_docs.base import ReadDocsToolBase
from app.agent_tools.docs.read_docs.errors import UnknownSectionError
from app.agent_tools.docs.read_docs.models import ReadDocsQuery, ReadDocsResult, ReadSection
from app.db_postgres import DocsTable

logger = logging.getLogger(__name__)


class ReadDocsTool(ReadDocsToolBase):
    """
    Description:
    `read_docs` na prawdziwym indeksie: tabela dokumentacji w Postgresie oddaje sekcje o podanych
    identyfikatorach, a narzędzie robi z nich opis i treść każdej.

    Do czego:
    Źródło wiedzy agenta w grafach `search`, `suggest_questions` i `suggest_solution`: treść
    sekcji wybranych ze spisu albo znalezionych którymkolwiek wyszukiwaniem. Jedyne narzędzie
    dokumentacji, które cytuje. Tylko do odczytu.

    Flow:
        1. `search()` czyta wiersze po identyfikatorach sekcji.
        2. Brak którejkolwiek sekcji kończy odczyt `UnknownSectionError`.
        3. Każdy wiersz staje się `ReadSection`: opis z metryczki i treść.
        4. `render_for_model()` i `cite()` z klas bazowych robią z wyniku tekst i źródła.
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
            ReadDocsTool gotowe do odczytu z tabeli `docs_text`
        """
        self._docs = docs

    async def search(
        self,
        query: ReadDocsQuery,  # np. ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia"])
    ) -> ReadDocsResult:
        """
        Description:
        Czyta sekcje o podanych identyfikatorach, w kolejności żądania.

        Example args:
            query=ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia"])

        Example result:
            ReadDocsResult(sections=[ReadSection(section=DocSection(…), text="Uprawnienie…")])

        Raises:
            UnknownSectionError: któregoś identyfikatora nie ma w dokumentacji
            DbPostgresError: Postgres jest nieosiągalny albo odpowiedział błędem
        """
        # Bez powtórzeń, w kolejności żądania.
        wanted = list(dict.fromkeys(query.section_ids))

        rows = await self._docs.read_by_id(wanted)

        # Same liczby: identyfikatory podaje model, a treść sekcji nie jest do logów.
        logger.info("read_docs asked=%d found=%d", len(wanted), len(rows))

        # --- wszystko albo nic: brak jednej sekcji unieważnia cały odczyt ---
        found   = {row.section_id for row in rows}
        unknown = [section_id for section_id in wanted if section_id not in found]

        if unknown:
            raise UnknownSectionError(unknown)

        result = ReadDocsResult(
            sections = [ReadSection(section=row.to_section(), text=row.body) for row in rows],
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
