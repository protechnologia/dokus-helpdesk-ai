"""
Description:
Testy jednostkowe tego, co w `scripts/build_code_symbols.py` stoi wokół rozbioru pliku:
rozpoznanie języka po rozszerzeniu (`language_of`) i zapis mapy jako JSON (`symbols_as_json`).
Sam rozbiór PHP i JS ma osobne pliki testów, a budowę mapy z paczki sprawdzają testy
integracyjne.
"""

import dataclasses
import json

import pytest
from build_code_symbols import Symbol, SymbolMap, language_of, symbols_as_json, symbols_of_file

# Mapa dwóch plików: jeden z klasą i metodą, drugi z funkcją pod polskim kluczem.
SYMBOL_MAP = SymbolMap(
    built_on      = "2026-10-13",
    files         = {
        "src/lib/Generator.php": [
            Symbol(name="Generator", scope=None,        kind="class",  from_line=3, to_line=20),
            Symbol(name="nastepny",  scope="Generator", kind="method", from_line=7, to_line=12),
        ],
        "src/web/js/okna.js": [
            Symbol(name="Zamknij okno „pismo”", scope="APP.okna", kind="function",
                   from_line=4, to_line=6),
        ],
    },
    syntax_errors = ["src/lib/zepsuty.php"],
)


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("src/lib/Generator.php",         "php"),
        ("src/web/js/okna.js",            "js"),
        ("src/web/js/STARE.JS",           "js"),
        ("src/lib/Wzor.PHP",              "php"),
        ("src/lib/Poczta/tresc.twig",     None),
        ("src/config/routing.yml",        None),
        ("src/web/js/okna.js.bak",        None),
        ("src/lib/Makefile",              None),
    ],
)
def test_the_language_is_told_by_the_extension_whatever_its_case(
    path:     str,
    language: str | None,
) -> None:
    """Sprawdza, czy plik PHP i JS jest rozpoznawany po rozszerzeniu także wtedy, gdy jest ono
    zapisane wielkimi literami, a szablon, konfiguracja i plik bez rozszerzenia nie mają języka.

    Wyłapuje porównanie rozszerzenia z rozróżnianiem wielkości liter: kod leży na dysku
    Windows, więc plik `STARE.JS` zostałby bez symboli, choć jest w paczce jak każdy inny."""
    assert language_of(path) == language


def test_a_file_the_map_does_not_cover_is_refused() -> None:
    """Sprawdza, czy prośba o symbole pliku, którego język nie jest obsługiwany, kończy się
    błędem z jego ścieżką.

    Wyłapuje rozbiór szablonu Twig parserem PHP: dałby błąd składni i wpis na liście plików
    odrzuconych, choć plik jest poprawny."""
    with pytest.raises(ValueError, match="src/lib/Poczta/tresc.twig"):
        symbols_of_file("src/lib/Poczta/tresc.twig", b"{{ pismo.numer }}")


def test_the_written_map_reads_back_as_the_same_map() -> None:
    """Sprawdza, czy zapisana mapa jest poprawnym JSON-em, który po wczytaniu niesie dokładnie
    te same pliki, symbole, dzień budowy i listę plików odrzuconych, z polskimi literami
    w nazwie bez zmian.

    Wyłapuje błąd w ręcznie składanym zapisie: zgubiony przecinek między plikami albo
    nazwę zapisaną sekwencjami `\\u…`, której czytający mapę człowiek nie znajdzie."""
    written = symbols_as_json(SYMBOL_MAP)

    assert json.loads(written) == dataclasses.asdict(SYMBOL_MAP)
    assert "Zamknij okno „pismo”" in written


def test_each_file_of_the_map_takes_one_line() -> None:
    """Sprawdza, czy w zapisanej mapie każdy plik kodu zajmuje jedną linię, w której stoi jego
    ścieżka i wszystkie jego symbole.

    Wyłapuje zapis całej mapy w jednej linii albo z symbolem rozbitym na kilka: szukanie nazwy
    w pliku mapy nie pokazywałoby wtedy, w którym pliku kodu ją zdefiniowano."""
    lines = symbols_as_json(SYMBOL_MAP).splitlines()

    with_generator = [line for line in lines if "nastepny" in line]

    assert len(with_generator) == 1
    assert with_generator[0].startswith('"src/lib/Generator.php": ')
    assert '"Generator"' in with_generator[0]


def test_a_map_without_any_symbol_is_still_valid_json() -> None:
    """Sprawdza, czy mapa paczki, w której nie ma ani jednej definicji, zapisuje się jako
    poprawny JSON z pustą listą plików.

    Wyłapuje zapis, który przy pustej liście plików zostawia niedomknięty obiekt: czytnik
    w aplikacji odrzuciłby taką mapę jako uszkodzoną."""
    empty = SymbolMap(built_on="2026-10-13")

    assert json.loads(symbols_as_json(empty)) == {
        "built_on":      "2026-10-13",
        "syntax_errors": [],
        "files":         {},
    }
