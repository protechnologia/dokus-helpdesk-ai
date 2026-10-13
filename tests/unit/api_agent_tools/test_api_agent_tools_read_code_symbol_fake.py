import json

import pytest
from build_code_symbols import symbols_of_file

from app.agent_tools.code.fake_code import (
    GENERATOR_CODE,
    GENERATOR_PATH,
    default_files,
    default_symbol_map,
)
from app.agent_tools.code.read_code_symbol import (
    FakeReadCodeSymbolTool,
    NoSuchSymbolError,
    ReadCodeSymbolQuery,
    UnknownSymbolPathError,
)

METHOD = ReadCodeSymbolQuery(name="nastepnyNumer")


async def test_the_built_in_method_comes_back_with_its_lines() -> None:
    """Sprawdza, czy atrapa na pytanie o metodę z wbudowanego pliku oddaje jej opis i dokładnie
    jej linie z tego pliku, każdą pod jej numerem.

    Wyłapuje atrapę, która oddaje stały wynik niezależnie od pliku: numery linii z odczytu
    symbolu nie pasowałyby do numerów z atrap szukania, odczytu pliku i cytowania."""
    result = await FakeReadCodeSymbolTool().read(METHOD)
    code   = GENERATOR_CODE.split("\n")

    assert (result.symbol.path, result.symbol.scope, result.symbol.kind) == (
        GENERATOR_PATH, "GeneratorNumeru", "method",
    )
    assert [(line.line, line.text) for line in result.lines] == [
        (number, code[number - 1]) for number in range(5, 14)
    ]


def test_the_built_in_map_is_the_map_the_script_builds_for_the_built_in_files() -> None:
    """Sprawdza, czy ręcznie spisana mapa symboli atrap jest dokładnie tą, którą dla tych samych
    zmyślonych plików buduje skrypt paczki: te same pliki, nazwy, miejsca, rodzaje i linie.

    Wyłapuje mapę atrap rozjechaną z plikami atrap po zmianie pliku: atrapa oddawałaby funkcję
    pod złymi liniami, a testy grafów sprawdzałyby tekst, którego narzędzie właściwe nigdy by
    nie dało."""
    built = {}
    for path, code in default_files().items():
        symbols = symbols_of_file(path, code.encode("utf-8"))
        if symbols:
            built[path] = [
                (symbol.name, symbol.scope, symbol.kind, symbol.from_line, symbol.to_line)
                for symbol in symbols
            ]

    by_hand = {
        path: [(s.name, s.scope, s.kind, s.from_line, s.to_line) for s in symbols]
        for path, symbols in default_symbol_map().files.items()
    }

    assert by_hand == built


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje każde zapytanie w kolejności wywołań, także to, które
    skończyło się błędem.

    Wyłapuje atrapę, która gubi zapytania: test grafu nie mógłby sprawdzić, o którą funkcję
    agent prosił."""
    tool    = FakeReadCodeSymbolTool()
    missing = ReadCodeSymbolQuery(name="nieMaTakiej")

    await tool.read(METHOD)
    with pytest.raises(NoSuchSymbolError):
        await tool.read(missing)

    assert tool.queries == [METHOD, missing]


@pytest.mark.parametrize("path", ["src/lib", "src/lib/Urzad/Numeracja", GENERATOR_PATH])
async def test_a_path_above_the_file_still_finds_the_method(path: str) -> None:
    """Sprawdza, czy atrapa znajduje metodę także wtedy, gdy zapytanie zawęża ją do katalogu nad
    plikiem albo do samego pliku.

    Wyłapuje atrapę, która zna tylko dokładną ścieżkę pliku: scenariusz, w którym model zawęża
    odczyt do katalogu, kończyłby się w testach błędem, którego narzędzie właściwe nie daje."""
    query  = ReadCodeSymbolQuery(name="nastepnyNumer", path=path)
    result = await FakeReadCodeSymbolTool().read(query)

    assert result.symbol.path == GENERATOR_PATH


async def test_a_path_the_fake_does_not_know_is_an_error() -> None:
    """Sprawdza, czy zawężenie do ścieżki, pod którą atrapa nie zna żadnego pliku, kończy się
    wyjątkiem `UnknownSymbolPathError` ze ścieżką w komunikacie.

    Wyłapuje atrapę, która nieznaną ścieżkę bierze za katalog bez definicji: model dostałby
    „nie ma takiej funkcji" zamiast „nie ma takiego katalogu"."""
    query = ReadCodeSymbolQuery(name="nastepnyNumer", path="src/brak")

    with pytest.raises(UnknownSymbolPathError, match="src/brak"):
        await FakeReadCodeSymbolTool().read(query)


async def test_own_files_without_a_map_have_no_definitions() -> None:
    """Sprawdza, czy atrapa zbudowana z własnymi plikami, ale bez mapy, nie zna żadnej definicji,
    także tych z zestawu wbudowanego.

    Wyłapuje atrapę, która do własnych plików dokłada wbudowaną mapę: w scenariuszu „w kodzie
    nic nie ma" odczyt symbolu oddawałby linie pliku, którego pozostałe atrapy nie znają."""
    tool = FakeReadCodeSymbolTool(files={})

    with pytest.raises(NoSuchSymbolError):
        await tool.read(METHOD)


async def test_the_model_reads_the_result_as_json_with_the_symbol_and_its_lines() -> None:
    """Sprawdza, czy tekst, który model dostaje od atrapy, to JSON z sześcioma częściami wyniku,
    w którym definicja ma plik, nazwę, miejsce, rodzaj i linie, a każda linia numer i treść.

    Wyłapuje atrapę z własnym kształtem tekstu dla modelu: test grafu na atrapie sprawdzałby
    wtedy inny tekst niż ten, który model czyta na produkcji."""
    body = json.loads(await FakeReadCodeSymbolTool().run(METHOD))

    assert set(body) == {
        "requested", "symbol", "returned", "lines", "candidates", "omitted_over_limit",
    }
    assert set(body["symbol"])   == {"path", "name", "scope", "kind", "from_line", "to_line"}
    assert set(body["lines"][0]) == {"line", "text"}
    assert body["requested"]     == {"name": "nastepnyNumer", "path": None}
