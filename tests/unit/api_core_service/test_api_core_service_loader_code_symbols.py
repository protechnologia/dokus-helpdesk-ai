import json
from datetime import date
from pathlib import Path

import pytest

from app.core_service.loader_code_package import CodePackageConfigError
from app.core_service.loader_code_symbols import CodeSymbols

# Mapa symboli stoi w katalogu paczki obok `repo/`. Testy zakładają ją w katalogu tymczasowym,
# więc nie potrzebują paczki zbudowanej skryptem ani parsera.

MAP = {
    "built_on":      "2026-10-13",
    "syntax_errors": ["src/lib/zepsuty.php"],
    "files":         {
        "src/lib/Numer.php": [
            {"name": "Numer", "scope": None, "kind": "class", "from_line": 2, "to_line": 7},
            {"name": "nastepny", "scope": "Numer", "kind": "method", "from_line": 4, "to_line": 6},
        ],
    },
}


def _symbols(
    tmp_path: Path,                 # katalog tymczasowy testu
    content:  object | None = MAP,  # treść `symbols.json`; None: pliku nie ma
) -> CodeSymbols:
    """
    Description:
    Zakłada katalog paczki z mapą symboli o podanej treści i oddaje jej czytnik. Napis i bajty
    trafiają do pliku bez zmian, wszystko inne jako JSON.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        content={"built_on": "2026-10-13", "syntax_errors": [], "files": {}}

    Example result:
        CodeSymbols czytająca <tmp_path>/paczka/symbols.json
    """
    root = tmp_path / "paczka"
    root.mkdir()

    if isinstance(content, bytes):
        (root / "symbols.json").write_bytes(content)
    elif isinstance(content, str):
        (root / "symbols.json").write_text(content, encoding="utf-8")
    elif content is not None:
        (root / "symbols.json").write_text(json.dumps(content), encoding="utf-8")

    return CodeSymbols(root)


def test_the_map_comes_back_with_its_files_and_symbols(tmp_path: Path) -> None:
    """Sprawdza, czy z pliku mapy wracają dzień budowy, lista plików odrzuconych i symbole
    pliku w kolejności z mapy, z nazwą, miejscem, rodzajem i liniami.

    Wyłapuje czytnik, który gubi część mapy albo zmienia kolejność symboli: klasa ma stać
    przed swoimi metodami, tak jak zapisał ją skrypt."""
    symbol_map = _symbols(tmp_path).read()

    assert symbol_map.built_on == date(2026, 10, 13)
    assert symbol_map.syntax_errors == ["src/lib/zepsuty.php"]
    assert [
        (symbol.name, symbol.scope, symbol.kind, symbol.from_line, symbol.to_line)
        for symbol in symbol_map.files["src/lib/Numer.php"]
    ] == [("Numer", None, "class", 2, 7), ("nastepny", "Numer", "method", 4, 6)]


def test_a_map_changed_on_disk_is_read_again(tmp_path: Path) -> None:
    """Sprawdza, czy po podmianie pliku mapy ten sam czytnik oddaje już nową mapę.

    Wyłapuje czytnik, który pamięta mapę od pierwszego odczytu: przebudowa paczki podmienia
    kod i mapę bez restartu usługi, więc narzędzia czytałyby granice funkcji starego kodu."""
    symbols = _symbols(tmp_path)

    before  = sorted(symbols.read().files)
    rebuilt = {"built_on": "2026-10-14", "syntax_errors": [], "files": {}}
    (tmp_path / "paczka" / "symbols.json").write_text(json.dumps(rebuilt), encoding="utf-8")

    assert (before, sorted(symbols.read().files)) == (["src/lib/Numer.php"], [])


@pytest.mark.parametrize(
    "content",
    [
        None,
        "to nie jest JSON",
        b"\xff\xfe mapa w innym kodowaniu",
        {"built_on": "2026-10-13", "files": {}},
        {**MAP, "files": {"src/lib/Numer.php": [{"name": "Numer", "kind": "class"}]}},
        {**MAP, "files": {"src/lib/Numer.php": [
            {"name": "Numer", "scope": None, "kind": "class", "from_line": -257, "to_line": 7},
        ]}},
        [MAP],
    ],
    ids=["brak pliku", "nie JSON", "nie UTF-8", "bez listy odrzuconych", "niepełny symbol",
         "linia ujemna", "lista"],
)
def test_a_missing_or_broken_map_is_a_configuration_error(
    tmp_path: Path,
    content:  object | None,
) -> None:
    """Sprawdza, czy brak mapy, plik, który nie jest JSON-em albo nie jest w UTF-8, mapa bez
    listy plików odrzuconych, z niepełnym wpisem symbolu, z ujemnym numerem linii albo zapisana
    jako lista kończy się wyjątkiem `CodePackageConfigError`.

    Wyłapuje czytnik, który w takim przypadku oddaje pustą mapę albo błąd wracający do modelu:
    model uznałby, że w kodzie nie ma takiej funkcji, i nikt nie dowiedziałby się, że paczka
    jest niekompletna."""
    with pytest.raises(CodePackageConfigError):
        _symbols(tmp_path, content).read()


def test_the_error_says_how_to_build_the_map(tmp_path: Path) -> None:
    """Sprawdza, czy komunikat o braku mapy podaje ścieżkę pliku, którego brakuje, i polecenie,
    które go buduje.

    Wyłapuje komunikat, z którego nie wynika, co zrobić: mapa jest osobnym plikiem paczki
    i paczka zbudowana przed jej wprowadzeniem wymaga jednego polecenia, nie przebudowy."""
    with pytest.raises(CodePackageConfigError) as raised:
        _symbols(tmp_path, None).read()

    assert str(tmp_path / "paczka" / "symbols.json") in str(raised.value)
    assert "build_code_symbols.py build" in str(raised.value)
