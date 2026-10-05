from pathlib import Path

import pytest

from app.core_model.doc_directory import DocDirectory
from app.core_model.doc_manifest import DocManifest
from app.core_model.doc_package import DocPackage
from app.core_service.importer_docs import (
    EMBED_BATCH_SIZE,
    DocsImporter,
    DocsImportRefused,
    check_importable,
)
from app.db_postgres import DocRow
from app.db_qdrant import DocPoint, point_id_for
from app.engine_embedding import EmbeddingError

# Importer na paczce zbudowanej w pamięci i na atrapach embeddera, tabeli i kolekcji: sprawdzamy,
# CO i w jakiej KOLEJNOŚCI importer robi. Że bazy to przyjmują, sprawdza test na stacku.

VECTOR_SIZE = 4


class FakeEmbedder:
    """
    Description:
    Zastępuje `EmbeddingClient`: oddaje wektor na tekst i zapisuje każdą paczkę tekstów.

    Stub, a nie atrapa z produkcji: `FakeEncoder` stoi po drugiej stronie HTTP, w usłudze
    `embedder`, więc klient nie ma własnej wersji offline.
    """

    def __init__(
        self,
        error: Exception | None = None,  # np. EmbeddingError("Embedder timed out")
    ) -> None:
        """
        Description:
        Buduje stub z pustym zapisem wywołań; z `error` każde wywołanie kończy się tym błędem.

        Example args:
            error=None

        Example result:
            FakeEmbedder z pustym `passage_batches`
        """
        self.passage_batches: list[list[str]] = []
        self.closed = False
        self._error = error

    async def embed_passage(
        self,
        texts: list[str],  # np. ["Tytuł wstep\nTreść sekcji."]
    ) -> list[list[float]]:
        """
        Description:
        Zapisuje paczkę i oddaje wektor na każdy tekst.

        Example args:
            texts=["Tytuł wstep\\nTreść sekcji."]

        Example result:
            [[1.0, 1.0, 1.0, 1.0]]

        Raises:
            Exception: błąd podany przy budowie
        """
        if self._error is not None:
            raise self._error

        self.passage_batches.append(texts)

        return [[1.0] * VECTOR_SIZE for _ in texts]

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje, że embedder został zamknięty.

        Example args:
            (brak)

        Example result:
            None
        """
        self.closed = True


class FakeTable:
    """
    Description:
    Zastępuje `DocsTable`: zapisuje kolejność wywołań i wiersze — do wspólnej listy `calls`,
    żeby dało się sprawdzić kolejność między tabelą a kolekcją.
    """

    name = "docs_text"

    def __init__(
        self,
        calls: list[str],  # wspólny zapis wywołań tabeli i kolekcji
    ) -> None:
        """
        Description:
        Buduje stub piszący do podanego zapisu wywołań.

        Example args:
            calls=[]

        Example result:
            FakeTable z pustym `rows`
        """
        self.calls = calls
        self.rows:  list[DocRow] = []

    async def drop(self) -> None:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            None
        """
        self.calls.append("table.drop")

    async def create(self) -> None:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            None
        """
        self.calls.append("table.create")

    async def upsert(
        self,
        rows: list[DocRow],  # np. [DocRow(section_id="wstep", …)]
    ) -> None:
        """
        Description:
        Zapisuje wywołanie i wiersze.

        Example args:
            rows=[DocRow(section_id="wstep", ordinal=0, …)]

        Example result:
            None
        """
        self.calls.append("table.upsert")
        self.rows.extend(rows)

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            None
        """
        self.calls.append("table.aclose")


class FakeCollection:
    """
    Description:
    Zastępuje `DocsCollection`: zapisuje kolejność wywołań i punkty, do tego samego zapisu co
    `FakeTable`.
    """

    name = "docs"

    def __init__(
        self,
        calls: list[str],  # wspólny zapis wywołań tabeli i kolekcji
    ) -> None:
        """
        Description:
        Buduje stub piszący do podanego zapisu wywołań.

        Example args:
            calls=[]

        Example result:
            FakeCollection z pustym `points`
        """
        self.calls = calls
        self.points: list[DocPoint] = []

    async def drop(self) -> bool:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            True
        """
        self.calls.append("collection.drop")

        return True

    async def ensure(self) -> bool:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            True
        """
        self.calls.append("collection.ensure")

        return True

    async def upsert(
        self,
        points: list[DocPoint],  # np. [DocPoint(point_id="bc92…", …)]
    ) -> int:
        """
        Description:
        Zapisuje wywołanie i punkty; oddaje ich liczbę.

        Example args:
            points=[DocPoint(point_id="bc925b88-…", …)]

        Example result:
            1
        """
        self.calls.append("collection.upsert")
        self.points.extend(points)

        return len(points)

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje wywołanie.

        Example args:
            (brak)

        Example result:
            None
        """
        self.calls.append("collection.aclose")


class Stack:
    """
    Description:
    Importer razem z atrapami, na których stoi — żeby test miał pod ręką i wynik, i zapis tego,
    co importer zrobił.
    """

    def __init__(
        self,
        synthetic:      bool = False,             # rodzaj indeksu, do którego pisze importer
        fragment_chars: int = 1500,               # limit długości fragmentu
        embed_error:    Exception | None = None,  # błąd, którym odpowiada embedder
    ) -> None:
        """
        Description:
        Buduje atrapy ze wspólnym zapisem wywołań i importer na nich.

        Example args:
            synthetic=False
            fragment_chars=1500
            embed_error=None

        Example result:
            Stack z `importer`, `embedder`, `table`, `collection` i pustym `calls`
        """
        self.calls: list[str] = []
        self.embedder   = FakeEmbedder(error=embed_error)
        self.table      = FakeTable(self.calls)
        self.collection = FakeCollection(self.calls)
        self.importer   = DocsImporter(
            embedder       = self.embedder,
            table          = self.table,
            collection     = self.collection,
            fragment_chars = fragment_chars,
            synthetic      = synthetic,
        )


def _directory(
    name:        str,                           # nazwa katalogu dokumentu, np. "administrator"
    section_ids: tuple[str, ...] = ("wstep",),  # sekcje dokumentu, w kolejności manifestu
    synthetic:   bool = False,                  # flaga z manifestu
    body:        str = "Treść sekcji.",         # treść każdej sekcji
    errors:      tuple[str, ...] = (),          # błędy katalogu, np. ("brak pliku a.md",)
    warnings:    tuple[str, ...] = (),          # ostrzeżenia katalogu
) -> DocDirectory:
    """
    Description:
    Buduje wczytany katalog jednego dokumentu, tak jak oddaje go `load_doc_package()`.

    Example args:
        name="administrator"
        section_ids=("wstep", "uprawnienia")

    Example result:
        DocDirectory(path=Path("administrator"), manifest=DocManifest(…), bodies={…})
    """
    manifest = DocManifest(
        document  = f"Instrukcja {name}",
        version   = "4.12",
        synthetic = synthetic,
        sections  = [
            {"section_id": section_id, "title": f"Tytuł {section_id}", "description": "Opis"}
            for section_id in section_ids
        ],
    )

    directory = DocDirectory(
        path     = Path(name),
        manifest = manifest,
        bodies   = {section_id: body for section_id in section_ids},
        errors   = list(errors),
        warnings = list(warnings),
    )

    return directory


def _package(
    *directories: DocDirectory,          # np. _directory("administrator")
    errors:       tuple[str, ...] = (),  # błędy ponad katalogami
) -> DocPackage:
    """
    Description:
    Buduje wczytaną paczkę z podanych katalogów.

    Example args:
        directories=(_directory("administrator"),)

    Example result:
        DocPackage(path=Path("paczka"), directories=[DocDirectory(…)])
    """
    return DocPackage(path=Path("paczka"), directories=list(directories), errors=list(errors))


# --- wiersze tabeli -----------------------------------------------------------------------

async def test_every_section_becomes_a_row_with_its_place_in_the_document() -> None:
    """Dwa dokumenty → wiersz na sekcję, a `ordinal` liczony od zera w każdym dokumencie
    osobno: po nim układa się spis treści."""
    stack   = Stack()
    package = _package(_directory("administrator", ("a", "b")), _directory("uzytkownik", ("c",)))

    await stack.importer.run(package)

    assert [(row.section_id, row.ordinal) for row in stack.table.rows] == [
        ("a", 0),
        ("b", 1),
        ("c", 0),
    ]
    assert stack.table.rows[2].document == "Instrukcja uzytkownik"


async def test_the_row_carries_the_whole_body() -> None:
    """Sekcja dłuższa niż limit fragmentu → w wierszu cała treść, niepocięta: w tej postaci
    czyta ją agent."""
    body  = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji.\n"
    stack = Stack(fragment_chars=25)

    await stack.importer.run(_package(_directory("administrator", body=body)))

    assert stack.table.rows[0].body == body


# --- punkty kolekcji ----------------------------------------------------------------------

async def test_a_short_section_becomes_one_point() -> None:
    """Sekcja krótsza niż limit → jeden punkt, o identyfikatorze fragmentu zerowego."""
    stack = Stack()

    await stack.importer.run(_package(_directory("administrator")))

    assert [point.point_id for point in stack.collection.points] == [point_id_for("wstep#0")]


async def test_a_long_section_becomes_a_point_per_fragment() -> None:
    """Sekcja z trzech akapitów przy limicie mieszczącym jeden → trzy punkty o różnych
    identyfikatorach, każdy z tym samym opisem sekcji."""
    body  = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji.\n\nTrzeci akapit sekcji."
    stack = Stack(fragment_chars=25)

    await stack.importer.run(_package(_directory("administrator", body=body)))

    points = stack.collection.points

    assert [point.point_id for point in points] == [
        point_id_for("wstep#0"),
        point_id_for("wstep#1"),
        point_id_for("wstep#2"),
    ]
    assert {point.section_id for point in points} == {"wstep"}
    assert points[0].payload                      == points[2].payload


async def test_the_embedded_text_is_the_title_and_the_fragment() -> None:
    """Fragment → do embeddera idzie tytuł sekcji i sam fragment, w trybie passage."""
    body  = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji."
    stack = Stack(fragment_chars=25)

    await stack.importer.run(_package(_directory("administrator", body=body)))

    assert stack.embedder.passage_batches == [
        ["Tytuł wstep\nPierwszy akapit sekcji.", "Tytuł wstep\nDrugi akapit sekcji."]
    ]


async def test_fragments_are_embedded_in_batches() -> None:
    """Więcej fragmentów niż jedna paczka → kilka wywołań embeddera, razem z każdym fragmentem
    raz; jedno wielkie żądanie zależałoby od jednego timeoutu."""
    count   = EMBED_BATCH_SIZE + 3
    stack   = Stack()
    package = _package(_directory("administrator", tuple(f"s{number}" for number in range(count))))

    await stack.importer.run(package)

    assert [len(batch) for batch in stack.embedder.passage_batches] == [EMBED_BATCH_SIZE, 3]
    assert len(stack.collection.points)                             == count


async def test_two_imports_give_the_same_points() -> None:
    """Ta sama paczka zaimportowana dwa razy → te same identyfikatory punktów, bo wynikają
    z sekcji i numeru fragmentu."""
    package = _package(_directory("administrator", ("a", "b")))
    first   = Stack()
    second  = Stack()

    await first.importer.run(package)
    await second.importer.run(package)

    assert [p.point_id for p in first.collection.points] == [
        p.point_id for p in second.collection.points
    ]


# --- zastąpienie indeksu ------------------------------------------------------------------

async def test_the_old_index_is_replaced_not_extended() -> None:
    """Import → tabela i kolekcja są kasowane i zakładane przed zapisem; inaczej zostałyby
    sekcje usunięte z paczki i punkty dawnych fragmentów."""
    stack = Stack()

    await stack.importer.run(_package(_directory("administrator")))

    assert stack.calls == [
        "table.drop",
        "table.create",
        "table.upsert",
        "collection.drop",
        "collection.ensure",
        "collection.upsert",
    ]


async def test_nothing_is_dropped_when_the_embedder_fails() -> None:
    """Embedder pada → błąd wychodzi, a tabela i kolekcja są nietknięte: stary indeks znika
    dopiero, gdy wektory nowego są gotowe."""
    stack = Stack(embed_error=EmbeddingError("Embedder timed out"))

    with pytest.raises(EmbeddingError):
        await stack.importer.run(_package(_directory("administrator")))

    assert stack.calls == []


async def test_aclose_closes_everything_the_importer_stands_on() -> None:
    """`aclose()` importera → zamknięty embedder, tabela i kolekcja: kto dostał sam importer,
    może po sobie posprzątać jednym wywołaniem."""
    stack = Stack()

    await stack.importer.aclose()

    assert stack.embedder.closed
    assert stack.calls == ["table.aclose", "collection.aclose"]


# --- raport -------------------------------------------------------------------------------

async def test_the_report_counts_documents_sections_and_fragments() -> None:
    """Dwa dokumenty, trzy sekcje, jedna pocięta na dwa fragmenty → takie liczby w raporcie,
    razem z ostrzeżeniami paczki."""
    body    = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji."
    stack   = Stack(fragment_chars=25)
    package = _package(
        _directory("administrator", ("a",), body=body, warnings=("sekcja a jest długa",)),
        _directory("uzytkownik", ("b", "c")),
    )

    report = await stack.importer.run(package)

    assert report.documents == 2
    assert report.sections  == 3
    assert report.fragments == 4
    assert report.warnings  == ["sekcja a jest długa"]


# --- odmowa -------------------------------------------------------------------------------

REFUSED = [
    pytest.param(
        _package(_directory("administrator", errors=("brak pliku wstep.md",))),
        False,
        "ma błędy",
        id="błąd w katalogu",
    ),
    pytest.param(
        _package(_directory("administrator"), errors=("section_id wstep jest w kilku…",)),
        False,
        "ma błędy",
        id="błąd paczki",
    ),
    pytest.param(_package(), False, "żadnego dokumentu", id="pusta paczka"),
    pytest.param(
        _package(_directory("zmyslony", synthetic=True)),
        False,
        "zmyslony",
        id="syntetyczny do właściwego indeksu",
    ),
    pytest.param(
        _package(_directory("prawdziwy"), _directory("zmyslony", ("b",), synthetic=True)),
        False,
        "zmyslony",
        id="paczka mieszana do właściwego indeksu",
    ),
    pytest.param(
        _package(_directory("prawdziwy")),
        True,
        "prawdziwy",
        id="prawdziwy do indeksu syntetycznego",
    ),
]


@pytest.mark.parametrize("package, synthetic, message", REFUSED)
def test_a_package_that_does_not_fit_is_refused(
    package:   DocPackage,
    synthetic: bool,
    message:   str,
) -> None:
    """Paczka z błędami, pusta albo niezgodna z rodzajem indeksu → odmowa mówiąca dlaczego."""
    with pytest.raises(DocsImportRefused, match=message):
        check_importable(package, synthetic)


@pytest.mark.parametrize("package, synthetic, message", REFUSED)
async def test_a_refused_import_touches_nothing(
    package:   DocPackage,
    synthetic: bool,
    message:   str,
) -> None:
    """Odmowa w `run()` → ani embedder, ani tabela, ani kolekcja nie dostają żadnego wywołania."""
    stack = Stack(synthetic=synthetic)

    with pytest.raises(DocsImportRefused):
        await stack.importer.run(package)

    assert stack.calls                    == []
    assert stack.embedder.passage_batches == []


async def test_a_synthetic_package_goes_into_the_synthetic_index() -> None:
    """Dokument zmyślony i indeks syntetyczny → import przechodzi."""
    stack = Stack(synthetic=True)

    report = await stack.importer.run(_package(_directory("zmyslony", synthetic=True)))

    assert report.sections == 1
