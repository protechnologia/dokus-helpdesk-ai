from pathlib import Path

import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.list_code_files import (
    MAX_ENTRIES_PER_LISTING,
    ListCodeFilesQuery,
    ListCodeFilesTool,
    NoSuchCodeDirError,
)
from app.core_service.loader_code_package import CodePackage, CodePackageConfigError

# Narzędzie stoi na prawdziwym czytniku paczki, a paczka to kilka plików w katalogu tymczasowym —
# sprawdzamy więc, co narzędzie robi z katalogiem i z odmową czytnika. Wybieranie poziomów
# i sygnały sprawdza test części wspólnej; samej granicy paczki pilnują testy czytnika, a pełną
# paczkę syntetyczną spisuje test integracyjny.

FILES = [
    "src/web/index.php",
    "src/lib/Numeracja/GeneratorNumeru.php",
    "src/lib/Numeracja/Sekwencja.php",
    "src/lib/Sesja/Kontrola.php",
]


def _tool(
    tmp_path: Path,                     # katalog tymczasowy testu
    files:    list[str] | None = None,  # np. ["src/web/index.php"]; brak znaczy `FILES`
) -> ListCodeFilesTool:
    """
    Description:
    Buduje narzędzie na paczce z podanymi plikami; treść plików nie ma tu znaczenia.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        files=None

    Example result:
        ListCodeFilesTool spisujące katalogi z <tmp_path>/paczka/repo
    """
    repo = tmp_path / "paczka" / "repo"

    for path in FILES if files is None else files:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("<?php\n", encoding="utf-8")

    return ListCodeFilesTool(package=CodePackage(tmp_path / "paczka"))


async def test_a_directory_is_listed_to_the_asked_depth(tmp_path: Path) -> None:
    """Sprawdza, czy spis katalogu `src/lib` na dwa poziomy oddaje oba podkatalogi, każdy ze
    swoimi plikami tuż pod sobą, z pełnymi ścieżkami liczonymi od katalogu głównego kodu,
    a pliku z sąsiedniego katalogu nie pokazuje.

    Wyłapuje spis ze ścieżkami liczonymi od spisywanego katalogu albo od położenia paczki na
    dysku: takiej ścieżki nie przyjęłyby odczyt pliku ani szukanie."""
    result = await _tool(tmp_path).list_dir(ListCodeFilesQuery(path="src/lib", depth=2))

    assert [(entry.path, entry.kind) for entry in result.entries] == [
        ("src/lib/Numeracja",                     "dir"),
        ("src/lib/Numeracja/GeneratorNumeru.php", "file"),
        ("src/lib/Numeracja/Sekwencja.php",       "file"),
        ("src/lib/Sesja",                         "dir"),
        ("src/lib/Sesja/Kontrola.php",            "file"),
    ]
    assert (result.returned.depth, result.returned.has_more_depth) == (2, False)


async def test_without_a_path_the_listing_starts_at_the_code_root(tmp_path: Path) -> None:
    """Sprawdza, czy spis bez ścieżki zaczyna się w katalogu głównym kodu i ma domyślną
    głębokość 2: wynik niesie ścieżkę `.` i trzy pozycje (`src`, `src/lib`, `src/web`), mówi, że
    cały katalog ma cztery poziomy i że głębiej coś jeszcze jest. Ścieżka `.` podana wprost daje
    ten sam wynik.

    Wyłapuje narzędzie, które bez ścieżki zgłasza błąd: model, który nie zna jeszcze układu
    kodu, zgadywałby nazwę pierwszego katalogu i zużywał na to wywołania."""
    tool = _tool(tmp_path)

    result = await tool.list_dir(ListCodeFilesQuery())
    dotted = await tool.list_dir(ListCodeFilesQuery(path="."))

    assert result.path                             == "."
    assert [entry.path for entry in result.entries] == ["src", "src/lib", "src/web"]
    assert result.dir_info.total_depth             == 4
    assert (result.requested.depth, result.returned.depth) == (2, 2)
    assert result.returned.has_more_depth is True
    assert dotted                                  == result


async def test_the_path_comes_back_in_one_form(tmp_path: Path) -> None:
    """Sprawdza, czy katalog zapisany przez `..` i z ukośnikiem na końcu wraca w wyniku jako
    jedna ścieżka bez `..`, a pozycje mają ścieżki zbudowane od tej postaci.

    Wyłapuje spis, który skleja ścieżki pozycji z zapisem od modelu: pozycja
    `src/web/../lib/Sesja` wskazywałaby ten sam katalog co `src/lib/Sesja`, ale jako inny napis,
    więc ten sam plik zacytowany dwiema drogami dałby dwa źródła."""
    result = await _tool(tmp_path).list_dir(ListCodeFilesQuery(path="src/web/../lib/", depth=1))

    assert result.path                              == "src/lib"
    assert [entry.path for entry in result.entries] == ["src/lib/Numeracja", "src/lib/Sesja"]


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("../..",             "wychodzi poza kod aplikacji"),
        ("src/web/index.php", "to plik, nie katalog"),
        ("src/brak",          "nie ma takiego pliku ani katalogu"),
    ],
    ids=["poza paczką", "plik", "brak katalogu"],
)
async def test_a_path_that_is_not_a_directory_of_the_package_is_an_error(
    tmp_path: Path,
    path:     str,
    message:  str,
) -> None:
    """Sprawdza, czy spis ścieżki spoza paczki, ścieżki pliku albo katalogu, którego nie ma,
    kończy się wyjątkiem `NoSuchCodeDirError`, który jest odmianą `ToolCallError` i niesie powód
    oraz ścieżkę w brzmieniu od modelu.

    Wyłapuje spis katalogu spoza paczki, czyli nazwy plików kontenera, których model nie ma
    widzieć, oraz odmowę zgłoszoną innym błędem: nie wróciłaby do modelu jako podpowiedź, tylko
    przerwała całe żądanie."""
    with pytest.raises(NoSuchCodeDirError, match=message) as caught:
        await _tool(tmp_path).list_dir(ListCodeFilesQuery(path=path))

    assert isinstance(caught.value, ToolCallError)
    assert path in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


async def test_a_directory_over_the_limit_is_cut_and_counted(tmp_path: Path) -> None:
    """Sprawdza na prawdziwym katalogu z jednym podkatalogiem i liczbą plików o pięć większą
    niż limit, czy spis oddaje dokładnie tyle pozycji, ile wynosi limit, zaczyna od podkatalogu
    i liczy sześć pominiętych plików.

    Wyłapuje narzędzie, które limitu nie stosuje do tego, co przeczytało z dysku: katalog
    z tysiącem wygenerowanych klas trafiłby do modelu w całości."""
    files = ["kod/pod/plik.php"] + [
        f"kod/klasa{number:03}.php" for number in range(MAX_ENTRIES_PER_LISTING + 5)
    ]

    result = await _tool(tmp_path, files).list_dir(ListCodeFilesQuery(path="kod", depth=1))

    assert len(result.entries)                == MAX_ENTRIES_PER_LISTING
    assert (result.entries[0].path, result.entries[0].kind) == ("kod/pod", "dir")
    assert result.returned.omitted_over_limit == 6


async def test_a_link_out_of_the_package_is_not_listed(tmp_path: Path) -> None:
    """Sprawdza, czy dowiązanie leżące w paczce, ale wskazujące katalog poza nią, nie trafia do
    spisu i nie jest przeszukiwane: spis pokazuje tylko plik, który naprawdę leży w katalogu.

    Wyłapuje spis, który wchodzi w dowiązania: model zobaczyłby nazwy plików spoza paczki,
    choć odczyt takiej ścieżki zostałby odrzucony."""
    tool    = _tool(tmp_path)
    outside = tmp_path / "poza"

    outside.mkdir()
    (outside / "tajne.php").write_text("<?php\n", encoding="utf-8")
    (tmp_path / "paczka" / "repo" / "src" / "web" / "dowiazanie").symlink_to(
        outside, target_is_directory=True,
    )

    result = await tool.list_dir(ListCodeFilesQuery(path="src/web", depth=3))

    assert [entry.path for entry in result.entries] == ["src/web/index.php"]


async def test_a_missing_package_stops_the_call_instead_of_answering_the_model(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy spis na paczce, której nie ma na dysku, kończy się wyjątkiem
    `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje brak paczki oddawany modelowi jako „nie ma takiego katalogu": instancja bez paczki
    kodu odpowiadałaby tak na każdy spis, a błąd wdrożenia zostałby niezauważony."""
    tool = ListCodeFilesTool(package=CodePackage(tmp_path / "nie-ma"))

    with pytest.raises(CodePackageConfigError) as caught:
        await tool.list_dir(ListCodeFilesQuery())

    assert not isinstance(caught.value, ToolCallError)
