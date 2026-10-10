import json

import pytest

from app.agent_tools.code.fake_code import ERRORS_PATH, GENERATOR_PATH
from app.agent_tools.code.find_code_text import FakeFindCodeTextTool, FindCodeTextQuery
from app.agent_tools.code.list_code_files import (
    FakeListCodeFilesTool,
    ListCodeFilesQuery,
    NoSuchCodeDirError,
)
from app.agent_tools.code.read_code_file import FakeReadCodeFileTool, ReadCodeFileQuery

NUMERACJA = ListCodeFilesQuery(path="src/lib/Urzad/Numeracja", depth=1)


async def test_the_fake_lists_the_directory_that_was_asked_for() -> None:
    """Sprawdza, czy atrapa oddaje spis tego katalogu, o który pytano: dla katalogu z wbudowanym
    plikiem PHP ten jeden plik, a dla katalogu `src` z jednym poziomem dwa podkatalogi, bez
    plików leżących głębiej.

    Wyłapuje atrapę, która na każdy spis odpowiada tym samym: test grafu nie odróżniłby wtedy
    jednego katalogu od drugiego ani jednego poziomu od całego drzewa."""
    tool = FakeListCodeFilesTool()

    leaf = await tool.list_dir(NUMERACJA)
    top  = await tool.list_dir(ListCodeFilesQuery(path="src", depth=1))

    assert [(entry.path, entry.kind) for entry in leaf.entries] == [(GENERATOR_PATH, "file")]
    assert [(entry.path, entry.kind) for entry in top.entries]  == [
        ("src/lib", "dir"), ("src/web", "dir"),
    ]
    assert (leaf.returned.has_more_depth, top.returned.has_more_depth) == (False, True)


async def test_without_a_path_the_fake_lists_from_the_code_root() -> None:
    """Sprawdza, czy spis bez ścieżki zaczyna się w katalogu głównym kodu: wynik niesie ścieżkę
    `.`, a przy dużej głębokości pokazuje oba wbudowane pliki z pełnymi ścieżkami.

    Wyłapuje atrapę, która bez ścieżki zgłasza błąd albo oddaje pusty spis: model w teście grafu
    nie miałby od czego zacząć, choć narzędzie właściwe na to samo wywołanie odpowiada."""
    result = await FakeListCodeFilesTool().list_dir(ListCodeFilesQuery(depth=9))
    files  = [entry.path for entry in result.entries if entry.kind == "file"]

    assert result.path == "."
    assert files       == [GENERATOR_PATH, ERRORS_PATH]


async def test_the_model_reads_the_result_as_json_with_both_depths() -> None:
    """Sprawdza, czy tekst, który model dostaje od atrapy, to JSON z pięcioma częściami: ścieżką
    katalogu, głębokością całego katalogu, głębokością żądaną, głębokością oddaną z trzema
    sygnałami i pozycjami ze ścieżką i rodzajem.

    Wyłapuje atrapę z własnym kształtem tekstu dla modelu: test grafu na atrapie sprawdzałby
    wtedy inny tekst niż ten, który model czyta na produkcji."""
    body = json.loads(await FakeListCodeFilesTool().run(NUMERACJA))

    assert set(body)         == {"path", "dir_info", "requested", "returned", "entries"}
    assert body["dir_info"]  == {"total_depth": 1}
    assert body["requested"] == {"depth": 1}
    assert body["returned"]  == {
        "depth": 1, "depth_cut_by_limit": False, "has_more_depth": False, "omitted_over_limit": 0,
    }
    assert body["entries"]   == [{"path": GENERATOR_PATH, "kind": "file"}]


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("src/lib/Brak",  "nie ma takiego pliku ani katalogu"),
        (GENERATOR_PATH,  "to plik, nie katalog"),
        ("src/li",        "nie ma takiego pliku ani katalogu"),
    ],
    ids=["brak katalogu", "plik", "początek nazwy katalogu"],
)
async def test_a_path_that_is_not_a_known_directory_is_an_error(path: str, message: str) -> None:
    """Sprawdza, czy spis ścieżki, pod którą atrapa nie zna katalogu, kończy się wyjątkiem
    `NoSuchCodeDirError` z powodem i ścieżką w komunikacie: dla katalogu, którego nie ma, dla
    ścieżki pliku i dla samego początku nazwy katalogu (`src/li` to nie `src/lib`).

    Wyłapuje atrapę, która oddaje coś dla dowolnej ścieżki albo dopasowuje katalog po początku
    nazwy: test grafu nie zobaczyłby wtedy, co model dostaje po pomyłce w ścieżce."""
    with pytest.raises(NoSuchCodeDirError, match=message) as caught:
        await FakeListCodeFilesTool().list_dir(ListCodeFilesQuery(path=path))

    assert path in str(caught.value)


async def test_a_fake_built_without_files_lists_nothing() -> None:
    """Sprawdza, czy atrapa zbudowana z pustym zestawem plików nie zna także plików wbudowanych:
    spis katalogu głównego jest pusty, a spis katalogu z wbudowanego zestawu kończy się
    wyjątkiem `NoSuchCodeDirError`.

    Wyłapuje atrapę, która pusty zestaw bierze za „nie podano": nie dałoby się wtedy odtworzyć
    sprawy, w której w kodzie nie ma niczego do obejrzenia."""
    tool = FakeListCodeFilesTool(files=[])

    root = await tool.list_dir(ListCodeFilesQuery())

    with pytest.raises(NoSuchCodeDirError):
        await tool.list_dir(NUMERACJA)

    assert (root.entries, root.returned.depth) == ([], 0)


async def test_every_query_is_recorded_even_a_refused_one() -> None:
    """Sprawdza, czy atrapa zapisuje na liście `queries` każde zapytanie, także to, na które
    odpowiedziała błędem.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie miałby jak sprawdzić, które
    katalogi agent próbował obejrzeć."""
    tool    = FakeListCodeFilesTool()
    unknown = ListCodeFilesQuery(path="src/lib/Brak")

    await tool.list_dir(NUMERACJA)

    with pytest.raises(NoSuchCodeDirError):
        await tool.list_dir(unknown)

    assert tool.queries == [NUMERACJA, unknown]


async def test_the_code_fakes_agree_on_paths() -> None:
    """Sprawdza, czy atrapa spisu mówi o tych samych plikach co pozostałe atrapy kodu: każdy
    plik z pełnego spisu atrapa odczytu czyta pod tą samą ścieżką, a każdy plik z wbudowanego
    wyniku szukania stoi w spisie.

    Wyłapuje atrapy rozjechane między sobą: model w teście grafu czytałby plik znaleziony
    w spisie i dostawał błąd, choć na produkcji wszystkie narzędzia kodu czytają tę samą
    paczkę."""
    listing = await FakeListCodeFilesTool().list_dir(ListCodeFilesQuery(depth=9))
    listed  = [entry.path for entry in listing.entries if entry.kind == "file"]
    found   = await FakeFindCodeTextTool().find(FindCodeTextQuery(exact="Brak sekwencji"))
    read    = FakeReadCodeFileTool()

    for path in listed:
        assert (await read.read(ReadCodeFileQuery(path=path))).path == path

    assert {line.path for line in found.lines} <= set(listed)
