"""
Description:
Sprawdza, na czym stoją dziś narzędzia agenta: czy każdy indeks materiału istnieje i ile niesie
elementów. Nic nie zakłada i niczego nie naprawia — tylko liczy.

| indeks                   | gdzie leży                          | `count`                      |
|--------------------------|-------------------------------------|------------------------------|
| karty zgłoszeń           | kolekcja `QDRANT_COLLECTION`        | punkty (`count()` kolekcji)  |
| wątki zgłoszeń           | tabela `tickets_text`               | wiersze (`count()` tabeli)   |
| sekcje dokumentacji      | tabela `docs_text`                  | wiersze                      |
| fragmenty dokumentacji   | kolekcja `QDRANT_DOCS_COLLECTION`   | punkty                       |
| paczka kodu              | katalog `CODE_PACKAGE_DIR`          | pliki według metryczki       |

Przed — instancja pokazowa z kartami golden200, pustą tabelą wątków, bez dokumentacji i z kodem:

    kolekcja „tickets": 171 punktów, tabela „tickets_text": 0 wierszy,
    tabeli „docs_text" i kolekcji „docs" nie ma, paczka kodu z metryczką na 11 424 pliki

Po — `await inspector.inspect()`:

    IndexReport(
        indexes=[
            IndexStatus(material="tickets", index="cards",     count=171),   # state="built"
            IndexStatus(material="tickets", index="threads",   count=0),     # state="empty"
            IndexStatus(material="docs",    index="sections",  count=None),  # state="missing"
            IndexStatus(material="docs",    index="fragments", count=None),  # state="missing"
            IndexStatus(material="code",    index="package",   count=11424), # state="built"
        ],
        code_package=CodePackageInfo(branch="/main/stage-gminy/…", built_on=date(2026, 10, 7)),
    )

O czym pamiętać przy zmianach:

- Brak indeksu to tu stan, nie błąd: brakująca tabela albo kolekcja daje `count=None`. Każda
  inna awaria bazy (brak połączenia, odmowa) wychodzi jako błąd jej warstwy, a trasa oddaje 503
  — „nie wiem" nie może wyglądać jak „nie ma".
- Paczka kodu jest zbudowana, gdy da się odczytać jej metryczkę i opis projektu: bez nich
  narzędzia kodu kończą się błędem konfiguracji. Mapy symboli nie czyta (7 MB i 0,18 s na
  paczce Dokusa), bo skrypt paczki buduje ją zawsze razem z metryczką.
- Indeksy liczy się po kolei, bez współbieżności: wszystkie razem to milisekundy, poza pierwszym
  zapytaniem do Postgresa, które zakłada pulę (około 0,6 s na słownik).
- Nowy materiał to nowy wpis w `inspect()` i nowa wartość w `IndexStatus`.
"""

from app.core_model.code.code_package_info import CodePackageInfo
from app.core_model.instance.index_report import IndexReport
from app.core_model.instance.index_status import IndexStatus
from app.core_service.loader_code_description import CodeDescription
from app.core_service.loader_code_package import CodePackageConfigError
from app.db_postgres import DbPostgresMissingTableError, DocsTable, TicketsTable
from app.db_qdrant import DbQdrantMissingCollectionError, DocsCollection, TicketsCollection


class IndexInspector:
    """
    Description:
    Stan indeksów, na których stoją narzędzia agenta: brak, pusty albo ile elementów.

    Do czego:
    Na tym stoi trasa `GET /instance`, a z niej belka frontu: kto ogląda przebieg, widzi, czy
    „nic nie znaleziono w instrukcjach" znaczy, że instrukcje milczą, czy że indeks jest pusty.
    Dostaje te same kolekcje, tabele i paczkę, na których budowane są narzędzia, więc liczy
    dokładnie to, co narzędzia czytają.

    Flow:
        1. Konstruktor zapamiętuje kolekcje, tabele i opis paczki kodu; z niczym się nie łączy.
        2. `inspect()` liczy każdy indeks (`_count()`) i czyta paczkę kodu (`_read_code()`).
        3. `aclose()` zamyka klientów kolekcji i tabel.
    """

    def __init__(
        self,
        tickets_cards:   TicketsCollection,  # np. TicketsCollection(qdrant, "tickets", 768)
        tickets_threads: TicketsTable,       # np. TicketsTable(postgres)
        docs_sections:   DocsTable,          # np. DocsTable(postgres)
        docs_fragments:  DocsCollection,     # np. DocsCollection(qdrant, "docs", 768)
        code:            CodeDescription,    # np. CodeDescription(Path("/code/data/unsafe/code"))
    ):
        """
        Description:
        Zapamiętuje indeksy do policzenia. Nie łączy się z niczym i nie dotyka dysku.

        Example args:
            tickets_cards=TicketsCollection(qdrant, "tickets", 768)
            tickets_threads=TicketsTable(postgres)
            docs_sections=DocsTable(postgres)
            docs_fragments=DocsCollection(qdrant, "docs", 768)
            code=CodeDescription(Path("/code/data/unsafe/code"))

        Example result:
            IndexInspector liczący pięć indeksów
        """
        self._tickets_cards   = tickets_cards
        self._tickets_threads = tickets_threads
        self._docs_sections   = docs_sections
        self._docs_fragments  = docs_fragments
        self._code            = code

    async def inspect(self) -> IndexReport:
        """
        Description:
        Liczy wszystkie indeksy i czyta metryczkę paczki kodu. Brak tabeli, kolekcji albo paczki
        daje stan „missing", a nie błąd.

        Example args:
            (brak)

        Example result:
            IndexReport(indexes=[IndexStatus(material="tickets", index="cards", count=171), …],
                        code_package=CodePackageInfo(branch="/main/stage-gminy", …))

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odpowiedział błędem innym niż brak kolekcji
            DbPostgresError: Postgres nie odpowiedział albo odrzucił zapytanie
        """
        code_package, code_files = self._read_code()

        indexes = [
            IndexStatus(
                material = "tickets",
                index    = "cards",
                count    = await self._count(self._tickets_cards),
            ),
            IndexStatus(
                material = "tickets",
                index    = "threads",
                count    = await self._count(self._tickets_threads),
            ),
            IndexStatus(
                material = "docs",
                index    = "sections",
                count    = await self._count(self._docs_sections),
            ),
            IndexStatus(
                material = "docs",
                index    = "fragments",
                count    = await self._count(self._docs_fragments),
            ),
            IndexStatus(material="code", index="package", count=code_files),
        ]

        report = IndexReport(indexes=indexes, code_package=code_package)

        return report

    async def aclose(self) -> None:
        """
        Description:
        Zamyka klientów, na których stoją kolekcje i tabele. Klienci bywają wspólni, więc
        zamykają się po kilka razy; powtórne zamknięcie nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        for index in (
            self._tickets_cards,
            self._tickets_threads,
            self._docs_sections,
            self._docs_fragments,
        ):
            await index.aclose()

    async def _count(
        self,
        index: TicketsCollection | TicketsTable | DocsTable | DocsCollection,  # np. DocsTable(…)
    ) -> int | None:
        """
        Description:
        Liczba elementów jednego indeksu albo `None`, gdy tabeli lub kolekcji nie ma.

        Example args:
            index=DocsTable(postgres)

        Example result:
            None — tabeli `docs_text` nikt nie założył

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odpowiedział błędem innym niż brak kolekcji
            DbPostgresError: Postgres nie odpowiedział albo odrzucił zapytanie
        """
        try:
            counted = await index.count()
        except (
            DbQdrantMissingCollectionError,  # kolekcji nie ma: indeksu nikt nie zbudował
            DbPostgresMissingTableError,     # tabeli nie ma: indeksu nikt nie zbudował
        ):
            return None

        return counted

    def _read_code(self) -> tuple[CodePackageInfo | None, int | None]:
        """
        Description:
        Gałąź, dzień budowy i liczba plików paczki kodu albo dwa razy `None`, gdy paczki nie da
        się użyć: brak metryczki albo opisu projektu kończy wywołania narzędzi kodu błędem.

        Example args:
            (brak)

        Example result:
            (CodePackageInfo(branch="/main/stage-gminy", built_on=date(2026, 10, 7)), 11424)
        """
        try:
            info  = self._code.read_package_info()
            files = self._code.read_file_count()

            # Treść opisu nie jest tu potrzebna; odczyt sprawdza, że opis jest i nie jest pusty.
            self._code.read_text()
        except CodePackageConfigError:  # paczki nie ma albo jest niekompletna
            return None, None

        return info, files
