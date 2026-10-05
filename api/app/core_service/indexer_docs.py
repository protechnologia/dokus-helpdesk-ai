"""
Description:
Indeksacja dokumentacji: z paczki wczytanej z dysku buduje od zera oba indeksy — tabelę
w Postgresie, z której agent czyta całe sekcje i w której szuka po słowach, oraz kolekcję
w Qdrancie, w której szuka po znaczeniu. Nie woła LLM-a, tylko embedder i obie bazy, więc
przebieg da się powtórzyć jedną komendą.

    paczka (manifesty + pliki .md) ─┬─ cała sekcja ──────────────────────────→ Postgres
                                    └─ fragmenty → embedder (tytuł + fragment) → Qdrant

Przed — sekcja w paczce:

    manifest.json:  {"section_id": "adm-wykaz-uprawnien", "title": "Wykaz uprawnień", …}
    adm-wykaz-uprawnien.md:  20 tys. znaków — wstęp i 22 bloki z kodami uprawnień

Po — jeden wiersz w tabeli i dwadzieścia siedem punktów w kolekcji:

    DocRow(section_id="adm-wykaz-uprawnien", ordinal=12, title="Wykaz uprawnień", body="…całość…")

    DocPoint(point_id=uuid("adm-wykaz-uprawnien#0"),  payload={"section_id": "adm-wykaz-…", …})
    DocPoint(point_id=uuid("adm-wykaz-uprawnien#1"),  payload={…ten sam opis sekcji…})
    …
    DocPoint(point_id=uuid("adm-wykaz-uprawnien#26"), payload={…})

Co się dzieje po drodze:

1. Paczka z błędami, pusta albo niezgodna z rodzajem indeksu jest odrzucana, zanim cokolwiek
   zostanie zmienione (`check_indexable()`).
2. Z każdej sekcji powstaje wiersz: opis z manifestu, miejsce w dokumencie i cała treść.
3. Treść każdej sekcji jest cięta po akapitach na fragmenty, a embedder liczy wektor każdego
   fragmentu w trybie passage — z nim porównywane jest zapytanie agenta.
4. Dopiero z kompletem wierszy i wektorów indekser kasuje starą tabelę i kolekcję i zapisuje
   nowe.

O czym pamiętać przy zmianach:

- Indeksacja ZASTĘPUJE indeks, nie dokłada do niego: po niej w indeksie jest dokładnie to, co
  w paczce. Sekcja usunięta z paczki znika, a sekcja pocięta teraz na mniej fragmentów nie
  zostawia starych punktów.
- Kolejność z punktu 4 jest celowa: awaria embeddera nie zostawia pustego indeksu, bo do tego
  miejsca nic nie zostało skasowane.
- Dokument zmyślony (`synthetic: true`) nie trafia do właściwego indeksu, a prawdziwy do
  syntetycznego. O rodzaju indeksu mówi wołający, przy budowie indeksera.
- W logach na INFO same liczby i nazwy, nigdy treść sekcji.
"""

import logging

from app.core_model.docs.doc_package import DocPackage
from app.core_model.docs.doc_section import DocSection
from app.core_model.docs.docs_index_report import DocsIndexReport
from app.core_service.builder_doc_embedding_text import build_fragment_text, split_into_fragments
from app.db_postgres import DocRow, DocsTable
from app.db_qdrant import DocPoint, DocsCollection
from app.engine_embedding import EmbeddingClient

logger = logging.getLogger(__name__)

# Ile fragmentów idzie do embeddera w jednym wywołaniu. Mniej niż przy zgłoszeniach, bo fragment
# jest kilka razy dłuższy od karty, a jedno wywołanie ma zmieścić się w timeoucie embeddera.
EMBED_BATCH_SIZE = 16


class DocsIndexRefused(Exception):
    """
    Description:
    Paczki nie wolno zaindeksować: ma błędy, jest pusta albo jej dokumenty nie pasują do rodzaju
    indeksu. Zgłaszany, zanim indekser cokolwiek zmieni — ponowienie tej samej komendy nic nie da,
    trzeba poprawić paczkę albo wskazać inny indeks.
    """


def check_indexable(
    package:   DocPackage,  # np. load_doc_package(Path("data/unsafe/instruction"))
    synthetic: bool,        # True, gdy celem jest indeks syntetyczny
) -> None:
    """
    Description:
    Sprawdza, czy paczkę wolno wgrać do indeksu danego rodzaju. Osobna funkcja, żeby wołający
    mógł odmówić przed pytaniem o potwierdzenie; `DocsIndexer.rebuild()` woła ją i tak.

    Example args:
        package=DocPackage(path=Path("data/safe/instruction"), directories=[…])
        synthetic=False

    Example result:
        None — paczkę wolno zaindeksować

    Raises:
        DocsIndexRefused: paczka ma błędy, jest pusta albo jej dokumenty nie pasują do indeksu
    """
    # --- paczka z błędami: nie zgadujemy, co autor miał na myśli ---
    if not package.ok:
        raise DocsIndexRefused(
            f"paczka {package.path} ma błędy — popraw je; pokazuje je `helpdesk docs validate`"
        )

    # --- pusta paczka: indeksacja zastępuje indeks, więc skasowałaby działający ---
    if not package.directories:
        raise DocsIndexRefused(f"w paczce {package.path} nie ma żadnego dokumentu")

    mismatched = [
        directory.path.name
        for directory in package.directories
        if directory.manifest.synthetic != synthetic
    ]

    # --- dokument zmyślony do właściwego indeksu ---
    if mismatched and not synthetic:
        raise DocsIndexRefused(
            f"dokument syntetyczny nie może trafić do właściwego indeksu: {', '.join(mismatched)} "
            f"— paczkę zmyśloną indeksuje się do osobnego indeksu (`--synthetic`)"
        )

    # --- dokument prawdziwy do indeksu syntetycznego ---
    if mismatched:
        raise DocsIndexRefused(
            f"indeks syntetyczny przyjmuje tylko dokumenty z `synthetic: true`: "
            f"{', '.join(mismatched)}"
        )

    return None


class DocsIndexer:
    """
    Description:
    Buduje indeksy dokumentacji z wczytanej paczki: wiersze do tabeli w Postgresie, fragmenty
    z wektorami do kolekcji w Qdrancie.

    Do czego:
    Oba indeksy są pochodną plików, nigdy źródłem prawdy (zasada 8), więc indekser je zastępuje,
    zamiast uzupełniać. Paczkę czyta `load_doc_package()`; ten serwis rozmawia wyłącznie
    z embedderem i dwiema bazami.

    Flow:
        1. `rebuild()` odrzuca paczkę, której nie wolno zaindeksować (`check_indexable()`).
        2. `_rows()` buduje wiersz na sekcję, `_points()` tnie sekcje na fragmenty i liczy ich
           wektory paczkami.
        3. Tabela i kolekcja są kasowane i zapisywane od nowa.
        4. Raport niesie liczby i ostrzeżenia z wczytania paczki.
        5. `aclose()` zamyka połączenia, na których indekser stoi.
    """

    def __init__(
        self,
        embedder:       EmbeddingClient,  # np. EmbeddingClient(base_url="http://embedder:8000")
        table:          DocsTable,        # np. DocsTable(PostgresClient(…))
        collection:     DocsCollection,   # np. DocsCollection(QdrantClient(…), "docs", 768)
        fragment_chars: int,              # np. 1000 — RAG_DOCS_FRAGMENT_CHARS
        synthetic:      bool,             # True, gdy tabela i kolekcja to indeks syntetyczny
    ):
        """
        Description:
        Spina indekser z embedderem, tabelą i kolekcją. Wszystkie są wstrzykiwane: o tym, do
        którego indeksu indekser pisze, decyduje wołający — i on mówi, czy to indeks syntetyczny.

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            table=DocsTable(PostgresClient(host="postgres", …))
            collection=DocsCollection(QdrantClient(base_url="http://qdrant:6333"), "docs", 768)
            fragment_chars=1000
            synthetic=False

        Example result:
            DocsIndexer piszący do tabeli `docs_text` i kolekcji `docs`
        """
        self._embedder       = embedder
        self._table          = table
        self._collection     = collection
        self._fragment_chars = fragment_chars
        self._synthetic      = synthetic

    async def rebuild(
        self,
        package: DocPackage,  # np. load_doc_package(Path("data/unsafe/instruction"))
    ) -> DocsIndexReport:
        """
        Description:
        Zastępuje indeks dokumentacji zawartością paczki i zwraca, co zrobił. Stary indeks znika
        dopiero wtedy, gdy wiersze i wektory nowego są gotowe.

        Example args:
            package=DocPackage(path=Path("data/unsafe/instruction"), directories=[…])

        Example result:
            DocsIndexReport(documents=2, sections=27, fragments=58, warnings=[])

        Raises:
            DocsIndexRefused: paczki nie wolno zaindeksować w tym indeksie
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił zapis
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
        """
        check_indexable(package, self._synthetic)

        rows   = self._rows(package)
        points = await self._points(package)

        # --- tabela: cała sekcja, do odczytu i wyszukiwania tekstowego ---
        await self._table.drop()
        await self._table.create()
        await self._table.upsert(rows)

        # --- kolekcja: fragmenty, do wyszukiwania po znaczeniu ---
        await self._collection.drop()
        await self._collection.ensure()
        await self._collection.upsert(points)

        logger.info(
            "docs index table=%s collection=%s documents=%d sections=%d fragments=%d",
            self._table.name,
            self._collection.name,
            len(package.directories),
            len(rows),
            len(points),
        )

        report = DocsIndexReport(
            documents = len(package.directories),
            sections  = len(rows),
            fragments = len(points),
            warnings  = package.warnings,
        )

        return report

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia embeddera, Postgresa i Qdranta. Sprzątający woła tylko to i nie musi
        wiedzieć, z czego indekser jest zbudowany.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._embedder.aclose()
        await self._table.aclose()
        await self._collection.aclose()

    def _rows(
        self,
        package: DocPackage,  # np. DocPackage(directories=[DocDirectory(…), …])
    ) -> list[DocRow]:
        """
        Description:
        Buduje wiersz tabeli na każdą sekcję paczki: opis z manifestu, cała treść i miejsce
        sekcji w jej dokumencie, liczone od zera w kolejności manifestu.

        Example args:
            package=DocPackage(directories=[DocDirectory(manifest=DocManifest(…), bodies={…})])

        Example result:
            [DocRow(section_id="adm-kancelaria-edoreczenia", ordinal=0, body="Uprawnienie…", …)]
        """
        rows = [
            DocRow.from_section(
                section = section,
                body    = directory.bodies[section.section_id],
                ordinal = ordinal,
            )
            for directory in package.directories
            for ordinal, section in enumerate(directory.manifest.to_sections())
        ]

        return rows

    async def _points(
        self,
        package: DocPackage,  # np. DocPackage(directories=[DocDirectory(…), …])
    ) -> list[DocPoint]:
        """
        Description:
        Tnie każdą sekcję na fragmenty, liczy ich wektory paczkami i buduje punkt na fragment.
        Wektory wracają w kolejności tekstów, więc zipują się z powrotem na fragmenty;
        `strict=True` zamienia rozjazd długości w błąd zamiast w po cichu obciętą paczkę.

        Example args:
            package=DocPackage(directories=[DocDirectory(manifest=DocManifest(…), bodies={…})])

        Example result:
            [DocPoint(point_id="bc925b88-…", payload={"section_id": "adm-kancelaria-…", …}), …]

        Raises:
            EmbeddingError: embedder jest nieosiągalny albo zwrócił inną liczbę wektorów
        """
        # Każdy fragment z sekcją, z której pochodzi, numerem w tej sekcji i tekstem do embeddingu.
        fragments: list[tuple[DocSection, int, str]] = [
            (section, number, build_fragment_text(section.title, fragment))
            for directory in package.directories
            for section in directory.manifest.to_sections()
            for number, fragment in enumerate(
                split_into_fragments(directory.bodies[section.section_id], self._fragment_chars)
            )
        ]

        points: list[DocPoint] = []

        for start in range(0, len(fragments), EMBED_BATCH_SIZE):
            batch   = fragments[start : start + EMBED_BATCH_SIZE]
            vectors = await self._embedder.embed_passage([text for _, _, text in batch])

            points.extend(
                DocPoint.from_fragment(section, number, vector)
                for (section, number, _), vector in zip(batch, vectors, strict=True)
            )

        return points
