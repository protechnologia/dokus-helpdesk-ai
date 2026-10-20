from pathlib import Path

import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.read_code_symbol import (
    NoSuchSymbolError,
    ReadCodeSymbolQuery,
    ReadCodeSymbolTool,
    UnknownSymbolPathError,
)
from app.core_model.code.code_symbol import CodeSymbol
from app.core_model.code.code_symbol_map import CodeSymbolMap
from app.core_service.loader_code_package import CodePackage, CodePackageConfigError
from app.core_service.loader_code_symbols import CodeSymbols
from tests._helpers.numbered_lines import numbered_pairs

# Mała paczka w katalogu tymczasowym: dwa pliki PHP w `repo/` i ręcznie zapisana mapa symboli
# obok, więc test nie potrzebuje parsera ani paczki zbudowanej skryptem.

NUMER = "src/lib/Numeracja/Numer.php"
BAZA  = "src/lib/Baza/Polaczenie.php"
CODE  = {
    NUMER: [
        "<?php",
        "class Numer",
        "{",
        "    public function nastepny()",
        "    {",
        "        return 1;",
        "    }",
        "}",
    ],
    BAZA: [
        "<?php",
        "function polacz()",
        "{",
        "}",
    ],
}
SYMBOL_MAP = CodeSymbolMap(
    built_on      = "2026-10-13",
    syntax_errors = ["src/lib/Zepsuty.php"],
    files         = {
        NUMER: [
            CodeSymbol(name="Numer", scope=None, kind="class", from_line=2, to_line=8),
            CodeSymbol(name="nastepny", scope="Numer", kind="method", from_line=4, to_line=7),
        ],
        BAZA: [
            CodeSymbol(name="polacz", scope=None, kind="function", from_line=2, to_line=4),
        ],
    },
)


def _tool(
    tmp_path: Path,              # katalog tymczasowy testu
    with_map: bool = True,       # False: paczka bez pliku mapy symboli
) -> ReadCodeSymbolTool:
    """
    Description:
    Zakłada paczkę z dwoma plikami PHP i mapą symboli i oddaje narzędzie na tej paczce.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        with_map=True

    Example result:
        ReadCodeSymbolTool czytające definicje z <tmp_path>/paczka
    """
    package = tmp_path / "paczka"
    for path, lines in CODE.items():
        file = package / "repo" / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (package / "repo" / "src/lib/Zepsuty.php").write_text("<?php class {\n", encoding="utf-8")

    if with_map:
        (package / "symbols.json").write_text(SYMBOL_MAP.model_dump_json(), encoding="utf-8")

    return ReadCodeSymbolTool(package=CodePackage(package), symbols=CodeSymbols(package))


async def test_a_method_comes_back_with_the_lines_of_its_file(tmp_path: Path) -> None:
    """Sprawdza, czy narzędzie na paczce oddaje metodę z granicami z mapy symboli i liniami
    z pliku na dysku, znak w znak, z wcięciem.

    Wyłapuje narzędzie, które bierze linie skądinąd niż z pliku paczki albo zdejmuje wcięcie:
    odczyt symbolu ma dawać ten sam tekst co odczyt pliku w tych samych liniach."""
    result = await _tool(tmp_path).read(ReadCodeSymbolQuery(name="nastepny", path=NUMER))

    assert (result.symbol.scope, result.symbol.from_line, result.symbol.to_line) == ("Numer", 4, 7)
    assert numbered_pairs(result.numbered_lines) == [
        (number, CODE[NUMER][number - 1]) for number in range(4, 8)
    ]


@pytest.mark.parametrize(
    ("path", "requested"),
    [
        ("src/lib/Baza/../Numeracja", "src/lib/Numeracja"),
        ("src/lib/Numeracja/",        "src/lib/Numeracja"),
        (".",                         None),
        ("src/..",                    None),
    ],
    ids=["przez ..", "z ukośnikiem na końcu", "katalog główny", "katalog główny przez .."],
)
async def test_the_narrowing_comes_back_in_one_form(
    tmp_path:  Path,
    path:      str,
    requested: str | None,
) -> None:
    """Sprawdza, czy zawężenie zapisane przez `..` albo z ukośnikiem na końcu działa jak
    zapisane wprost i wraca w wyniku w jednej postaci, a zawężenie do katalogu głównego kodu
    znaczy to samo co brak zawężenia.

    Wyłapuje porównanie ścieżki od modelu ze ścieżkami z mapy bez sprowadzenia do jednej
    postaci: definicja byłaby w mapie, a narzędzie odpowiadałoby, że jej nie ma."""
    result = await _tool(tmp_path).read(ReadCodeSymbolQuery(name="nastepny", path=path))

    assert result.symbol.path    == NUMER
    assert result.requested.path == requested


@pytest.mark.parametrize(
    "path",
    ["../..", "/etc", "src/brak"],
    ids=["w górę", "bezwzględna", "nie istnieje"],
)
async def test_a_narrowing_that_is_not_in_the_package_is_an_error(
    tmp_path: Path,
    path:     str,
) -> None:
    """Sprawdza, czy zawężenie do ścieżki spoza paczki albo takiej, której nie ma, kończy się
    wyjątkiem `UnknownSymbolPathError`, który jest odmianą `ToolCallError` i niesie ścieżkę
    w komunikacie.

    Wyłapuje nieistniejący katalog brany za katalog bez definicji: model dostałby „nie ma takiej
    funkcji" i uznał, że kod jej nie zawiera, choć pomylił ścieżkę."""
    with pytest.raises(UnknownSymbolPathError) as caught:
        await _tool(tmp_path).read(ReadCodeSymbolQuery(name="nastepny", path=path))

    assert isinstance(caught.value, ToolCallError)
    assert path in str(caught.value)


async def test_a_file_the_parser_refused_sends_the_model_to_the_file_read(tmp_path: Path) -> None:
    """Sprawdza, czy pytanie o definicję w pliku, który stoi w mapie na liście plików z błędem
    składni, kończy się błędem mówiącym, żeby przeczytać plik narzędziem `read_code_file`.

    Wyłapuje odpowiedź „nie ma takiej funkcji" dla pliku, którego mapa nie obejmuje: funkcja
    w pliku jest, tylko nie w mapie, więc model ma po nią sięgnąć inną drogą."""
    query = ReadCodeSymbolQuery(name="cokolwiek", path="src/lib/Zepsuty.php")

    with pytest.raises(NoSuchSymbolError, match="read_code_file"):
        await _tool(tmp_path).read(query)


async def test_a_missing_package_or_map_stops_the_call_instead_of_answering_the_model(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy odczyt symbolu na paczce bez mapy symboli i na paczce, której nie ma wcale,
    kończy się wyjątkiem `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje brak mapy oddawany modelowi jako „nie ma takiej funkcji": paczka zbudowana przed
    wprowadzeniem mapy odpowiadałaby tak na każde pytanie, a błąd wdrożenia zostałby
    niezauważony."""
    without_map = _tool(tmp_path, with_map=False)
    nowhere     = ReadCodeSymbolTool(
        package = CodePackage(tmp_path / "nie-ma"),
        symbols = CodeSymbols(tmp_path / "nie-ma"),
    )

    for tool in (without_map, nowhere):
        with pytest.raises(CodePackageConfigError) as caught:
            await tool.read(ReadCodeSymbolQuery(name="nastepny"))

        assert not isinstance(caught.value, ToolCallError)


async def test_a_file_changed_after_the_map_was_built_stops_the_call(tmp_path: Path) -> None:
    """Sprawdza, czy po skróceniu pliku w paczce, bez przebudowy mapy, odczyt definicji z tego
    pliku kończy się wyjątkiem `CodePackageConfigError`.

    Wyłapuje odczyt według nieaktualnej mapy: narzędzie oddałoby linie, które już nie są tą
    funkcją, a model zacytowałby je jako jej treść."""
    tool = _tool(tmp_path)
    (tmp_path / "paczka" / "repo" / NUMER).write_text("<?php\nclass Numer {}\n", encoding="utf-8")

    with pytest.raises(CodePackageConfigError):
        await tool.read(ReadCodeSymbolQuery(name="nastepny"))
