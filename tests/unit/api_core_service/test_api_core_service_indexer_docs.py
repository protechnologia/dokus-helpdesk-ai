from pathlib import Path

import pytest

from app.core_model.docs.doc_directory import DocDirectory
from app.core_model.docs.doc_manifest import DocManifest
from app.core_model.docs.doc_package import DocPackage
from app.core_service.indexer_docs import (
    EMBED_BATCH_SIZE,
    DocsIndexer,
    DocsIndexRefused,
    check_indexable,
)
from app.db_postgres import DocRow
from app.db_qdrant import DocPoint, point_id_for
from app.engine_embedding import EmbeddingError

# Importer na paczce zbudowanej w pamięci i na atrapach embeddera, tabeli i kolekcji: sprawdzamy,
# CO i w jakiej KOLEJNOŚCI indekser robi. Że bazy to przyjmują, sprawdza test na stacku.

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
    co indekser zrobił.
    """

    def __init__(
        self,
        synthetic:      bool = False,             # rodzaj indeksu, do którego pisze indekser
        fragment_chars: int = 1500,               # limit długości fragmentu
        embed_error:    Exception | None = None,  # błąd, którym odpowiada embedder
    ) -> None:
        """
        Description:
        Buduje atrapy ze wspólnym zapisem wywołań i indekser na nich.

        Example args:
            synthetic=False
            fragment_chars=1500
            embed_error=None

        Example result:
            Stack z `indexer`, `embedder`, `table`, `collection` i pustym `calls`
        """
        self.calls: list[str] = []
        self.embedder   = FakeEmbedder(error=embed_error)
        self.table      = FakeTable(self.calls)
        self.collection = FakeCollection(self.calls)
        self.indexer   = DocsIndexer(
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
    """Sprawdza, czy każda sekcja paczki staje się wierszem tabeli z numerem miejsca w swoim
    dokumencie, liczonym od zera w każdym dokumencie osobno: dwa dokumenty, pierwszy z sekcjami `a`
    i `b`, drugi z sekcją `c`, dają wiersze o numerach 0, 1 i 0, a wiersz sekcji `c` niesie nazwę
    swojego dokumentu.

    Wyłapuje numerację ciągnącą się przez całą paczkę albo sekcję przypisaną do cudzego dokumentu:
    po tych numerach układa się spis treści, więc sekcje stałyby w nim w złej kolejności albo pod
    złym dokumentem."""
    stack   = Stack()
    package = _package(_directory("administrator", ("a", "b")), _directory("uzytkownik", ("c",)))

    await stack.indexer.rebuild(package)

    assert [(row.section_id, row.ordinal) for row in stack.table.rows] == [
        ("a", 0),
        ("b", 1),
        ("c", 0),
    ]
    assert stack.table.rows[2].document == "Instrukcja uzytkownik"


async def test_the_row_carries_the_whole_body() -> None:
    """Sprawdza, czy wiersz tabeli niesie całą treść sekcji, znak w znak, także gdy sekcja jest
    dłuższa niż limit fragmentu: tu dwa akapity przy limicie 25 znaków.

    Wyłapuje pociętą albo przyciętą treść w tabeli: z tabeli agent czyta sekcję w całości, a cięcie
    na fragmenty dotyczy tylko wektorów."""
    body  = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji.\n"
    stack = Stack(fragment_chars=25)

    await stack.indexer.rebuild(_package(_directory("administrator", body=body)))

    assert stack.table.rows[0].body == body


# --- punkty kolekcji ----------------------------------------------------------------------

async def test_a_short_section_becomes_one_point() -> None:
    """Sprawdza, czy sekcja krótsza niż limit fragmentu daje w kolekcji jeden punkt,
    o identyfikatorze wyliczonym z `wstep#0`, czyli z identyfikatora sekcji i numeru fragmentu zero.

    Wyłapuje sekcję, która nie dostała punktu albo dostała ich kilka, oraz identyfikator punktu
    liczony inaczej niż z sekcji i numeru fragmentu: krótka sekcja bez punktu nie dałaby się znaleźć
    wyszukiwaniem po znaczeniu."""
    stack = Stack()

    await stack.indexer.rebuild(_package(_directory("administrator")))

    assert [point.point_id for point in stack.collection.points] == [point_id_for("wstep#0")]


async def test_a_long_section_becomes_a_point_per_fragment() -> None:
    """Sprawdza, czy długa sekcja daje punkt na każdy fragment: trzy akapity przy limicie
    mieszczącym jeden dają trzy punkty o identyfikatorach z `wstep#0`, `wstep#1` i `wstep#2`,
    wszystkie z tym samym identyfikatorem sekcji i tym samym opisem sekcji.

    Wyłapuje dwie usterki: fragmenty o tym samym identyfikatorze, które nadpisałyby się w kolekcji
    i zostawiły po sekcji jeden punkt, oraz fragment z innym opisem, przez który trafienie w niego
    wskazywałoby inną sekcję."""
    body  = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji.\n\nTrzeci akapit sekcji."
    stack = Stack(fragment_chars=25)

    await stack.indexer.rebuild(_package(_directory("administrator", body=body)))

    points = stack.collection.points

    assert [point.point_id for point in points] == [
        point_id_for("wstep#0"),
        point_id_for("wstep#1"),
        point_id_for("wstep#2"),
    ]
    assert {point.section_id for point in points} == {"wstep"}
    assert points[0].payload                      == points[2].payload


async def test_the_embedded_text_is_the_title_and_the_fragment() -> None:
    """Sprawdza, czy do embeddera, w trybie dla tekstów indeksowanych (passage), idzie tytuł sekcji
    i sam fragment: sekcja pocięta na dwa fragmenty daje dwa teksty, każdy z tytułem „Tytuł wstep"
    w pierwszej linii i jednym akapitem pod nim.

    Wyłapuje tekst bez tytułu, z całą sekcją zamiast fragmentu albo wysłany w innym trybie: wektor
    fragmentu nie pasowałby wtedy do zapytań, z którymi jest porównywany."""
    body  = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji."
    stack = Stack(fragment_chars=25)

    await stack.indexer.rebuild(_package(_directory("administrator", body=body)))

    assert stack.embedder.passage_batches == [
        ["Tytuł wstep\nPierwszy akapit sekcji.", "Tytuł wstep\nDrugi akapit sekcji."]
    ]


async def test_fragments_are_embedded_in_batches() -> None:
    """Sprawdza, czy fragmenty idą do embeddera paczkami: przy liczbie fragmentów o trzy większej,
    niż mieści jedna paczka (`EMBED_BATCH_SIZE`), są dwa wywołania, pełna paczka i trzy fragmenty,
    a punktów powstaje tyle, ile fragmentów.

    Wyłapuje dwie usterki: wszystkie fragmenty wysłane jednym żądaniem, które zależałoby od jednego
    limitu czasu embeddera, oraz fragment zgubiony albo powtórzony na granicy paczek."""
    count   = EMBED_BATCH_SIZE + 3
    stack   = Stack()
    package = _package(_directory("administrator", tuple(f"s{number}" for number in range(count))))

    await stack.indexer.rebuild(package)

    assert [len(batch) for batch in stack.embedder.passage_batches] == [EMBED_BATCH_SIZE, 3]
    assert len(stack.collection.points)                             == count


async def test_two_imports_give_the_same_points() -> None:
    """Sprawdza, czy ta sama paczka zaindeksowana dwa razy daje punkty o tych samych
    identyfikatorach: identyfikator wynika z sekcji i numeru fragmentu.

    Wyłapuje identyfikatory losowe albo zależne od przebiegu: ten sam fragment miałby po każdej
    indeksacji inny identyfikator, więc dwóch przebiegów na tej samej paczce nie dałoby się
    porównać."""
    package = _package(_directory("administrator", ("a", "b")))
    first   = Stack()
    second  = Stack()

    await first.indexer.rebuild(package)
    await second.indexer.rebuild(package)

    assert [p.point_id for p in first.collection.points] == [
        p.point_id for p in second.collection.points
    ]


# --- zastąpienie indeksu ------------------------------------------------------------------

async def test_the_old_index_is_replaced_not_extended() -> None:
    """Sprawdza, czy indeksacja zastępuje indeks: tabela jest najpierw kasowana, potem zakładana
    i dopiero wtedy zapisywana, a po niej w tej samej kolejności kolekcja.

    Wyłapuje indeksację, która dokłada do starego indeksu: zostałyby w nim sekcje usunięte z paczki
    i punkty dawnych fragmentów, a agent dalej by je znajdował."""
    stack = Stack()

    await stack.indexer.rebuild(_package(_directory("administrator")))

    assert stack.calls == [
        "table.drop",
        "table.create",
        "table.upsert",
        "collection.drop",
        "collection.ensure",
        "collection.upsert",
    ]


async def test_nothing_is_dropped_when_the_embedder_fails() -> None:
    """Sprawdza, czy awaria embeddera przerywa indeksację błędem `EmbeddingError`, zanim tabela albo
    kolekcja dostaną jakiekolwiek wywołanie.

    Wyłapuje kasowanie starego indeksu przed policzeniem wektorów nowego: po awarii embeddera
    zostałby pusty indeks zamiast poprzedniego, działającego."""
    stack = Stack(embed_error=EmbeddingError("Embedder timed out"))

    with pytest.raises(EmbeddingError):
        await stack.indexer.rebuild(_package(_directory("administrator")))

    assert stack.calls == []


async def test_aclose_closes_everything_the_importer_stands_on() -> None:
    """Sprawdza, czy zamknięcie indeksera zamyka wszystko, na czym on stoi: embedder, tabelę
    i kolekcję.

    Wyłapuje połączenie zostawione otwarte: kto dostał sam indekser, na przykład komenda, sprząta
    jednym wywołaniem i nie ma jak zamknąć reszty osobno."""
    stack = Stack()

    await stack.indexer.aclose()

    assert stack.embedder.closed
    assert stack.calls == ["table.aclose", "collection.aclose"]


# --- raport -------------------------------------------------------------------------------

async def test_the_report_counts_documents_sections_and_fragments() -> None:
    """Sprawdza, czy raport z indeksacji podaje właściwe liczby i przenosi ostrzeżenia paczki: dwa
    dokumenty i trzy sekcje, z których jedna jest pocięta na dwa fragmenty, dają w raporcie
    2 dokumenty, 3 sekcje i 4 fragmenty oraz ostrzeżenie o długiej sekcji.

    Wyłapuje raport z pomylonymi liczbami albo bez ostrzeżeń: człowiek, który uruchomił indeksację,
    nie zobaczyłby, ile naprawdę trafiło do indeksu ani że paczka wymaga uwagi."""
    body    = "Pierwszy akapit sekcji.\n\nDrugi akapit sekcji."
    stack   = Stack(fragment_chars=25)
    package = _package(
        _directory("administrator", ("a",), body=body, warnings=("sekcja a jest długa",)),
        _directory("uzytkownik", ("b", "c")),
    )

    report = await stack.indexer.rebuild(package)

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
    """Sprawdza, czy paczka, której nie wolno zaindeksować, dostaje odmowę `DocsIndexRefused`
    z powodem w komunikacie. Sześć przypadków: błąd w katalogu dokumentu, błąd całej paczki, pusta
    paczka, dokument zmyślony do właściwego indeksu, paczka mieszana do właściwego indeksu
    i dokument prawdziwy do indeksu syntetycznego.

    Wyłapuje przyjęcie takiej paczki albo odmowę, która nie mówi dlaczego: indeksacja zastępuje
    indeks, więc pusta paczka skasowałaby działający, a zmyślona zmieszałaby się z dokumentacją,
    z której odpowiada agent."""
    with pytest.raises(DocsIndexRefused, match=message):
        check_indexable(package, synthetic)


@pytest.mark.parametrize("package, synthetic, message", REFUSED)
async def test_a_refused_import_touches_nothing(
    package:   DocPackage,
    synthetic: bool,
    message:   str,
) -> None:
    """Sprawdza, czy odmowa w `rebuild()` pada, zanim indekser cokolwiek zrobi: dla każdej z tych
    samych sześciu paczek ani embedder, ani tabela, ani kolekcja nie dostają wywołania.

    Wyłapuje sprawdzenie paczki wykonane za późno: odmowa po skasowaniu tabeli albo kolekcji
    zostawiałaby pusty indeks, a odmowa po liczeniu wektorów marnowałaby pracę embeddera."""
    stack = Stack(synthetic=synthetic)

    with pytest.raises(DocsIndexRefused):
        await stack.indexer.rebuild(package)

    assert stack.calls                    == []
    assert stack.embedder.passage_batches == []


async def test_a_synthetic_package_goes_into_the_synthetic_index() -> None:
    """Sprawdza, czy dokument zmyślony przechodzi do indeksu syntetycznego: indeksacja kończy się
    raportem z jedną sekcją.

    Wyłapuje odmowę zbyt szeroką, która odrzuca każdą paczkę zmyśloną: indeksu syntetycznego nie
    dałoby się wtedy zbudować wcale."""
    stack = Stack(synthetic=True)

    report = await stack.indexer.rebuild(_package(_directory("zmyslony", synthetic=True)))

    assert report.sections == 1
