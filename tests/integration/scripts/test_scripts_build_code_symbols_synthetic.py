"""
Description:
Test integracyjny mapy symboli (`scripts/build_code_symbols.py`) na aplikacji syntetycznej:
paczka i jej mapa powstają raz, w katalogu tymczasowym, ze źródła `data/safe/code/source/`.
Bez stacku i bez modelu.

| co sprawdzają testy                         | z czym porównują mapę                          |
|---------------------------------------------|------------------------------------------------|
| czy każdy symbol stoi tam, gdzie mówi mapa  | z liniami pliku z paczki, czytanymi jak w `api` |
| czy mapa nie gubi definicji                 | z liczbą słów `function` i `class` w pliku     |
| czy znane miejsca aplikacji są w mapie      | z listą `KNOWN` spisaną ręcznie ze źródła      |
| czy `api` czyta to, co skrypt zapisał       | z czytnikiem `CodeSymbols`                     |

O czym pamiętać przy zmianach:

- Porównanie z liczbą słów `function` działa, bo źródło syntetyczne nie ma tego słowa
  w napisach ani w komentarzach, a jedyne funkcje bez własnego wpisu to funkcje bez nazwy,
  policzone ręcznie w `NAMELESS_FUNCTIONS`. Po zmianie pliku JS źródła liczbę trzeba poprawić.
- Test nie czyta ani nie zmienia paczki zbudowanej obok źródła (`data/safe/code/`).
"""

import dataclasses
import json
import re
from pathlib import Path
from typing import NamedTuple

import pytest
from build_code_package import build_package, load_rules
from build_code_symbols import SYMBOLS_NAME, Symbol, SymbolMap, build_symbols, language_of

from app.core_service.loader_code_package import CodePackage
from app.core_service.loader_code_symbols import CodeSymbols
from tests._helpers.synthetic_code import SYNTHETIC_RULES_FILE, SYNTHETIC_SOURCE_DIR

# Słowo `function` w kodzie PHP i JS oraz deklaracja klasy w PHP.
FUNCTION_WORD = re.compile(r"\bfunction\b")
CLASS_WORD    = re.compile(r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+\w+", re.M)

# Funkcje bez nazwy, podane jako argument wywołania (`.done(function (wynik) {…})`): w mapie nie
# mają własnego wpisu. Liczby spisane ręcznie z plików źródła.
NAMELESS_FUNCTIONS = {
    "src/web/js/_global/bledy.js":     1,
    "src/web/js/_global/zdarzenia.js": 1,
    "src/web/js/archiwum/archiwum.js": 2,
    "src/web/js/pisma/pisma.js":       2,
    "src/web/js/sprawy/sprawy.js":     3,
}


class Known(NamedTuple):
    """Miejsce w aplikacji syntetycznej, które mapa ma znać, spisane ręcznie ze źródła."""

    path:     str               # plik, w którym leży definicja
    name:     str               # nazwa definicji
    scope:    str | None        # w czym leży
    kind:     str               # czym jest
    contains: str               # fragment, który stoi w liniach definicji
    lacks:    str | None = None # fragment z sąsiedniej definicji, którego ma tam nie być


KNOWN = [
    Known(
        path     = "src/apps/frontend/modules/kontrahenci/actions/actions.class.php",
        name     = "executeZapisz",
        scope    = "kontrahenciActions",
        kind     = "method",
        contains = "Nazwa kontrahenta może mieć najwyżej ",
    ),
    Known(
        path     = "src/apps/frontend/modules/sprawy/actions/actions.class.php",
        name     = "executeZamknij",
        scope    = "sprawyActions",
        kind     = "method",
        contains = "Sprawa jest już zamknięta",
        lacks    = "public function executeLista(",
    ),
    Known(
        path     = "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
        name     = "nastepnyNumer",
        scope    = "GeneratorNumeru",
        kind     = "method",
        contains = "Brak sekwencji numeracji dla roku ",
    ),
    Known(
        path     = "src/web/js/pisma/pisma.js",
        name     = "wyslijHandler",
        scope    = "APP.pisma",
        kind     = "function",
        contains = "$.post('/pisma/wyslij'",
        lacks    = "$.post('/pisma/zapisz'",
    ),
]


class Built(NamedTuple):
    """Paczka z mapą symboli zbudowana na potrzeby tego pliku testów."""

    package_dir: Path         # np. Path("/tmp/pytest-of-root/pytest-0/paczka0")
    symbol_map:  SymbolMap    # mapa oddana przez skrypt
    package:     CodePackage  # czytnik kodu tej paczki, ten sam co w `api`


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> Built:
    """
    Description:
    Buduje paczkę z aplikacji syntetycznej i jej mapę symboli do katalogu tymczasowego, raz na
    cały plik testów: każdy test ogląda tę samą mapę z innej strony.

    Example args:
        tmp_path_factory=<fabryka katalogów tymczasowych pytesta>

    Example result:
        Built(package_dir=Path("/tmp/…/paczka0"), symbol_map=SymbolMap(…), package=CodePackage(…))
    """
    package_dir = tmp_path_factory.mktemp("paczka")
    build_package(SYNTHETIC_SOURCE_DIR, package_dir, load_rules(SYNTHETIC_RULES_FILE))
    symbol_map  = build_symbols(package_dir)

    return Built(package_dir=package_dir, symbol_map=symbol_map, package=CodePackage(package_dir))


def _all_symbols(
    symbol_map: SymbolMap,
) -> list[tuple[str, Symbol]]:
    """
    Description:
    Rozkłada mapę na pary: ścieżka pliku i jeden jego symbol.

    Example args:
        symbol_map=SymbolMap(files={"src/a.php": [Symbol("A", None, "class", 3, 9)]})

    Example result:
        [("src/a.php", Symbol("A", None, "class", 3, 9))]
    """
    return [(path, symbol) for path, symbols in symbol_map.files.items() for symbol in symbols]


def test_the_map_is_written_next_to_the_manifest_as_the_script_returned_it(built: Built) -> None:
    """Sprawdza, czy mapa leży w katalogu paczki obok metryczki, poza `repo/`, i czy plik
    niesie dokładnie to, co skrypt oddał jako wynik budowy.

    Wyłapuje mapę zapisaną do `repo/`, gdzie wychodziłaby w szukaniu i w spisie katalogu jak
    kod, oraz plik różny od wyniku, na którym stoją pozostałe testy."""
    on_disk = json.loads((built.package_dir / SYMBOLS_NAME).read_text(encoding="utf-8"))

    assert on_disk == dataclasses.asdict(built.symbol_map)
    assert not (built.package_dir / "repo" / SYMBOLS_NAME).exists()
    assert (built.package_dir / "manifest.json").is_file()


def test_every_symbol_starts_at_the_line_that_names_it_and_ends_at_a_closing_brace(
    built: Built,
) -> None:
    """Sprawdza każdy symbol mapy wobec pliku z paczki: pierwsza linia zawiera jego nazwę,
    ostatnia nawias zamykający albo średnik, a zakres mieści się w pliku. Linie czyta ten sam
    czytnik, którego używają narzędzia agenta.

    Wyłapuje numery linii przesunięte o jedną albo liczone inaczej niż w narzędziach:
    odczyt symbolu oddawałby funkcję bez nagłówka albo bez ostatniej linii."""
    wrong = []
    for path, symbol in _all_symbols(built.symbol_map):
        lines = built.package.read_lines(path)
        first = lines[symbol.from_line - 1]
        last  = lines[symbol.to_line - 1] if symbol.to_line <= len(lines) else ""
        if symbol.name not in first or not ("}" in last or last.rstrip().endswith(";")):
            wrong.append((path, symbol))

    assert built.symbol_map.files and not wrong


def test_symbols_of_one_file_are_nested_or_apart_never_overlapping(built: Built) -> None:
    """Sprawdza, czy dwa symbole jednego pliku albo leżą osobno, albo jeden w całości w drugim
    (metoda w klasie); żaden nie zaczyna się w środku innego i nie kończy poza nim.

    Wyłapuje źle wyznaczony koniec definicji: funkcja, która wchodzi na następną, oddawałaby
    przy odczycie początek cudzego kodu."""
    overlapping = []
    for path, symbols in built.symbol_map.files.items():
        for outer in symbols:
            for inner in symbols:
                starts_inside = outer.from_line < inner.from_line <= outer.to_line
                if starts_inside and inner.to_line > outer.to_line:
                    overlapping.append((path, outer.name, inner.name))

    assert not overlapping


def test_the_map_has_as_many_definitions_as_the_code_has(built: Built) -> None:
    """Sprawdza każdy plik PHP i JS paczki: liczba funkcji i metod w mapie równa się liczbie
    słów `function` w pliku, pomniejszonej o funkcje bez nazwy, a liczba klas
    liczbie deklaracji klas. Plik bez definicji nie ma wpisu w mapie.

    Wyłapuje definicje zgubione przez rozbiór albo policzone podwójnie: liczba z mapy jest
    tu sprawdzana rachunkiem, który parsera nie używa."""
    different = []
    for path in built.package.list_files("."):
        if language_of(path) is None:
            continue

        text      = "\n".join(built.package.read_lines(path))
        symbols   = built.symbol_map.files.get(path, [])
        functions = sum(symbol.kind in ("function", "method") for symbol in symbols)
        classes   = len(symbols) - functions
        expected  = (
            len(FUNCTION_WORD.findall(text)) - NAMELESS_FUNCTIONS.get(path, 0),
            len(CLASS_WORD.findall(text)) if path.endswith(".php") else 0,
        )
        if (functions, classes) != expected or (path in built.symbol_map.files) != bool(symbols):
            different.append((path, (functions, classes), expected))

    assert not different
    assert built.symbol_map.syntax_errors == []


@pytest.mark.parametrize("known", KNOWN, ids=[known.name for known in KNOWN])
def test_a_known_place_of_the_application_is_in_the_map_with_its_own_lines(
    built: Built,
    known: Known,
) -> None:
    """Sprawdza miejsce spisane ręcznie ze źródła aplikacji: mapa ma w tym pliku dokładnie
    jedną definicję o tej nazwie, z właściwym miejscem i rodzajem, a jej linie zawierają
    fragment tej definicji i nie zawierają fragmentu sąsiedniej.

    Wyłapuje zakres, który obejmuje za dużo albo nie to: akcję z końca długiego kontrolera
    oddaną razem z poprzednią albo handler JS oddany razem z handlerem obok."""
    found = [symbol for symbol in built.symbol_map.files[known.path] if symbol.name == known.name]

    assert len(found) == 1

    symbol = found[0]
    text   = "\n".join(built.package.read_lines(known.path)[symbol.from_line - 1:symbol.to_line])

    assert (symbol.scope, symbol.kind) == (known.scope, known.kind)
    assert known.contains in text
    assert known.lacks is None or known.lacks not in text


def test_an_action_name_shared_by_three_modules_is_defined_in_three_files(built: Built) -> None:
    """Sprawdza, czy akcja `executeZapisz`, którą mają trzy moduły aplikacji, jest w mapie
    trzy razy: raz w pliku każdego modułu, z nazwą klasy tego modułu.

    Wyłapuje mapę, która przy powtórzonej nazwie zostawia jedną definicję: odczyt po nazwie
    oddawałby akcję innego modułu niż ten, o który chodzi."""
    places = {
        (path, symbol.scope)
        for path, symbol in _all_symbols(built.symbol_map)
        if symbol.name == "executeZapisz"
    }

    assert places == {
        ("src/apps/frontend/modules/kontrahenci/actions/actions.class.php", "kontrahenciActions"),
        ("src/apps/frontend/modules/pisma/actions/actions.class.php",       "pismaActions"),
        ("src/apps/frontend/modules/sprawy/actions/actions.class.php",      "sprawyActions"),
    }


def test_the_map_written_by_the_script_is_read_by_the_application(built: Built) -> None:
    """Sprawdza, czy mapę zapisaną przez skrypt czyta czytnik z aplikacji (`CodeSymbols`)
    i czy oddaje te same pliki i symbole, co skrypt.

    Wyłapuje rozjazd między zapisem w skrypcie a modelem w aplikacji: nowe pole albo nowy
    rodzaj symbolu po jednej stronie zatrzymywałby każdą sprawę błędem konfiguracji."""
    read = CodeSymbols(built.package_dir).read()

    assert read.model_dump(mode="json") == dataclasses.asdict(built.symbol_map)
