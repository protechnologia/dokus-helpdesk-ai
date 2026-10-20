import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.read_code_symbol import (
    MAX_CANDIDATES,
    MAX_LINES_PER_SYMBOL,
    NoSuchSymbolError,
    ReadCodeSymbolQuery,
    find_symbol_and_build_result,
)
from app.agent_tools.code.read_code_symbol.base import (
    bare_name_of,
    definitions_named,
    is_named,
    without_namespace,
)
from app.core_model.code.code_symbol import CodeSymbol
from app.core_model.code.code_symbol_map import CodeSymbolMap
from app.core_service.loader_code_package import CodePackageConfigError
from tests._helpers.numbered_lines import line_numbers, numbered_pairs

# Zmyślona mapa symboli: ta sama akcja w dwóch modułach, funkcje JS pod wspólnym obiektem
# i dwie funkcje o tej samej nazwie w jednym pliku. Liczy się wyłącznie mapa — plików nie ma,
# a „linie pliku" dostarcza `_lines()`.

SPRAWY = "src/apps/sprawy/actions/actions.class.php"
PISMA  = "src/apps/pisma/actions/actions.class.php"
JS     = "src/web/js/pisma.js"
GRID   = "src/web/js/siatka.js"
BROKEN = "src/lib/Zepsuty.php"


def _symbol(
    name:      str,         # np. "executeZapisz"
    scope:     str | None,  # np. "sprawyActions"
    kind:      str,         # np. "method"
    from_line: int,         # np. 5
    to_line:   int,         # np. 12
) -> CodeSymbol:
    """
    Description:
    Składa wpis mapy symboli z pozycyjnych wartości, żeby mapa testu mieściła się na ekranie.

    Example args:
        name="executeZapisz"
        scope="sprawyActions"
        kind="method"
        from_line=5
        to_line=12

    Example result:
        CodeSymbol(name="executeZapisz", scope="sprawyActions", kind="method", from_line=5, …)
    """
    return CodeSymbol(name=name, scope=scope, kind=kind, from_line=from_line, to_line=to_line)


SYMBOL_MAP = CodeSymbolMap(
    built_on      = "2026-10-13",
    syntax_errors = [BROKEN],
    files         = {
        SPRAWY: [
            _symbol("sprawyActions", None,            "class",  3, 40),
            _symbol("executeZapisz", "sprawyActions", "method", 5, 12),
            _symbol("executeLista",  "sprawyActions", "method", 14, 20),
        ],
        PISMA: [
            _symbol("pismaActions",  None,           "class",  3, 30),
            _symbol("executeZapisz", "pismaActions", "method", 5, 15),
        ],
        JS: [
            _symbol("wyslij",   "APP.pisma", "function", 2, 6),
            _symbol("zapisz",   "APP.pisma", "function", 8, 9),
            _symbol("pomocnik", None,        "function", 11, 12),
        ],
        GRID: [
            _symbol("dataInit", None, "function", 3, 4),
            _symbol("dataInit", None, "function", 6, 7),
        ],
    },
)

METHOD   = SYMBOL_MAP.files[SPRAWY][1]
FUNCTION = SYMBOL_MAP.files[JS][0]
CLASS    = SYMBOL_MAP.files[SPRAWY][0]


def _lines(
    path: str,  # np. "src/web/js/pisma.js"
) -> list[str]:
    """
    Description:
    Udaje plik na 60 linii: linia numer N ma treść „<ścieżka> linia N", więc po treści widać,
    z którego pliku i z której linii pochodzi.

    Example args:
        path="src/web/js/pisma.js"

    Example result:
        ["src/web/js/pisma.js linia 1", "src/web/js/pisma.js linia 2", …]
    """
    return [f"{path} linia {number}" for number in range(1, 61)]


def _result(
    name: str,                # np. "executeZapisz"
    path: str | None = None,  # np. "src/apps/sprawy"; None: cały kod
):
    """
    Description:
    Wykonuje odczyt symbolu na zmyślonej mapie i oddaje wynik narzędzia.

    Example args:
        name="executeZapisz"
        path="src/apps/sprawy"

    Example result:
        ReadCodeSymbolResult(symbol=SymbolDefinition(path="src/apps/sprawy/…", …), …)
    """
    return find_symbol_and_build_result(
        query      = ReadCodeSymbolQuery(name=name, path=path),
        inside     = path,
        symbol_map = SYMBOL_MAP,
        read_lines = _lines,
    )


@pytest.mark.parametrize(
    ("symbol", "name", "named"),
    [
        (METHOD,   "executeZapisz",                 True),
        (METHOD,   "sprawyActions::executeZapisz",  True),
        (METHOD,   "sprawyActions->executeZapisz",  True),
        (METHOD,   "sprawyActions.executeZapisz",   True),
        (METHOD,   "pismaActions::executeZapisz",   False),
        (METHOD,   "executezapisz",                 False),
        (METHOD,   "Zapisz",                        False),
        (METHOD,   "sprawyActions::",               False),
        (FUNCTION, "wyslij",                        True),
        (FUNCTION, "APP.pisma.wyslij",              True),
        (FUNCTION, "pisma.wyslij",                  False),
        (FUNCTION, "APP.sprawy.wyslij",             False),
        (CLASS,    "sprawyActions",                 True),
        (CLASS,    "Urzad::sprawyActions",          False),
    ],
)
def test_a_name_points_at_a_definition_alone_or_with_its_place(
    symbol: CodeSymbol,
    name:   str,
    named:  bool,
) -> None:
    """Sprawdza, które zapisy nazwy wskazują definicję: sama nazwa i nazwa poprzedzona klasą
    albo obiektem (z `::`, `->` albo kropką) tak, a nazwa z inną klasą, innym obiektem, częścią
    ścieżki obiektu, inną wielkością liter albo sam fragment nazwy nie.

    Wyłapuje dopasowanie po końcówce albo bez względu na wielkość liter: metoda jednej klasy
    wracałaby na pytanie o metodę innej, a model nie miałby jak tego zauważyć."""
    assert is_named(symbol, name) is named


@pytest.mark.parametrize(
    ("name", "bare"),
    [
        ("sprawyActions::executeZapisz", "executeZapisz"),
        ("APP.pisma.wyslij",             "wyslij"),
        ("$this->zapisz",                "zapisz"),
        ("Klasa::obiekt.pole",           "pole"),
        ("executeZapisz",                None),
        ("sprawyActions::",              None),
    ],
)
def test_the_bare_name_is_what_stands_after_the_last_separator(
    name: str,
    bare: str | None,
) -> None:
    """Sprawdza, czy z nazwy podanej razem z miejscem zostaje to, co stoi po ostatnim
    separatorze, a nazwa bez separatora i nazwa urwana na separatorze nie dają niczego.

    Wyłapuje odcinanie po pierwszym separatorze albo po niewłaściwym: komunikat błędu liczyłby
    definicje nie tej nazwy, o którą model pytał."""
    assert bare_name_of(name) == bare


@pytest.mark.parametrize(
    ("name", "without"),
    [
        ("Urzad\\Sprawy\\sprawyActions",                "sprawyActions"),
        ("\\sprawyActions",                              "sprawyActions"),
        ("Urzad\\Sprawy\\sprawyActions::executeLista",  "sprawyActions::executeLista"),
        ("sprawyActions::executeLista",                  "sprawyActions::executeLista"),
        ("APP.pisma.wyslij",                             "APP.pisma.wyslij"),
    ],
)
def test_the_namespace_before_a_name_is_dropped(
    name:    str,
    without: str,
) -> None:
    """Sprawdza, czy z nazwy znika przestrzeń nazw PHP — wszystko do ostatniego ukośnika
    wstecznego włącznie — a nazwa bez przestrzeni nazw, także z klasą albo z obiektem JS, wraca
    bez zmian.

    Wyłapuje zdejmowanie za dużo albo za mało: nazwa klasy razem z metodą ma zostać w całości,
    bo to klasa wskazuje, o którą metodę chodzi."""
    assert without_namespace(name) == without


@pytest.mark.parametrize(
    ("with_namespace", "plain"),
    [
        ("Urzad\\Sprawy\\sprawyActions",               "sprawyActions"),
        ("\\sprawyActions",                             "sprawyActions"),
        ("Urzad\\Sprawy\\sprawyActions::executeLista", "sprawyActions::executeLista"),
    ],
)
def test_a_class_given_with_its_namespace_reads_like_the_class_alone(
    with_namespace: str,
    plain:          str,
) -> None:
    """Sprawdza, czy klasa i metoda klasy podane z przestrzenią nazw oddają tę samą definicję
    i te same linie, co podane bez niej, a w wyniku wraca nazwa w brzmieniu od modelu.

    Wyłapuje błąd „nie ma takiej definicji" dla nazwy przepisanej z linii `use` albo z pełnej
    nazwy klasy w kodzie: w sondzie na żywym modelu kosztowało to jedną turę."""
    by_namespace = _result(with_namespace)
    by_plain     = _result(plain)

    assert by_namespace.symbol is not None
    assert by_namespace.symbol         == by_plain.symbol
    assert by_namespace.numbered_lines == by_plain.numbered_lines
    assert by_namespace.requested.name == with_namespace


def test_one_definition_comes_back_with_exactly_its_lines() -> None:
    """Sprawdza, czy nazwa wskazująca jedną definicję daje jej opis, zakres równy jej liniom
    i linie pliku od pierwszej do ostatniej, każdą z jej numerem, bez listy kandydatów.

    Wyłapuje zakres przesunięty o linię albo linie innego pliku: model cytowałby potem fragment
    pod numerami, pod którymi w pliku stoi co innego."""
    result = _result("executeLista")

    assert result.symbol.model_dump() == {
        "path": SPRAWY, "name": "executeLista", "scope": "sprawyActions", "kind": "method",
        "from_line": 14, "to_line": 20,
    }
    assert result.returned.model_dump() == {"from_line": 14, "to_line": 20, "cut_by_limit": False}
    assert numbered_pairs(result.numbered_lines) == [
        (number, f"{SPRAWY} linia {number}") for number in range(14, 21)
    ]
    assert (result.candidates, result.omitted_over_limit) == ([], 0)


@pytest.mark.parametrize(
    ("with_place", "name", "path"),
    [
        ("sprawyActions::executeZapisz", "executeZapisz", SPRAWY),
        ("sprawyActions->executeZapisz", "executeZapisz", SPRAWY),
        ("sprawyActions.executeZapisz",  "executeZapisz", SPRAWY),
        ("pismaActions::executeZapisz",  "executeZapisz", PISMA),
        ("APP.pisma.wyslij",             "wyslij",        JS),
        ("APP.pisma.zapisz",             "zapisz",        JS),
    ],
)
def test_a_name_with_its_place_reads_the_same_definition_as_the_name_with_the_file(
    with_place: str,
    name:       str,
    path:       str,
) -> None:
    """Sprawdza, czy nazwa podana razem z klasą albo obiektem, bez ścieżki, oddaje tę samą
    definicję, ten sam zakres i te same linie, co sama nazwa zawężona do pliku tej definicji.

    Wyłapuje zapis z miejscem, który działa inaczej niż zapis z plikiem: opis narzędzia obiecuje
    modelowi oba, więc `sprawyActions::executeZapisz` nie może oddać akcji innego modułu ani
    listy kandydatów, skoro klasa wskazuje jedną."""
    by_place = _result(with_place)
    by_file  = _result(name, path)

    assert by_place.symbol is not None
    assert by_place.symbol         == by_file.symbol
    assert by_place.returned       == by_file.returned
    assert by_place.numbered_lines == by_file.numbered_lines


def test_a_name_defined_in_two_files_gives_candidates_without_any_line() -> None:
    """Sprawdza, czy nazwa zdefiniowana w dwóch plikach, bez ścieżki, daje dwóch kandydatów
    w kolejności ścieżek, każdego z plikiem, klasą i liniami, a nie daje definicji, zakresu ani
    ani jednej linii treści.

    Wyłapuje narzędzie, które przy kilku definicjach oddaje pierwszą: model dostałby akcję
    innego modułu niż ten, o który chodzi, i nie wiedziałby, że były inne."""
    result = _result("executeZapisz")

    assert (result.symbol, result.returned, result.numbered_lines) == (None, None, None)
    assert [(c.path, c.scope, c.from_line, c.to_line) for c in result.candidates] == [
        (PISMA,  "pismaActions",  5, 15),
        (SPRAWY, "sprawyActions", 5, 12),
    ]
    assert result.omitted_over_limit == 0


@pytest.mark.parametrize("path", [SPRAWY, "src/apps/sprawy", "src/apps/sprawy/actions"])
def test_a_path_narrows_the_candidates_to_one_definition(path: str) -> None:
    """Sprawdza, czy ta sama nazwa zawężona do pliku albo do katalogu jednego modułu daje już
    jedną definicję z treścią, a zawężenie wraca w wyniku.

    Wyłapuje zawężenie, które nie działa dla katalogu: metodę z klasy bazowej, która leży obok
    pliku klasy, model ma znaleźć właśnie po katalogu."""
    result = _result("executeZapisz", path)

    assert (result.symbol.path, result.symbol.scope) == (SPRAWY, "sprawyActions")
    assert result.requested.model_dump() == {"name": "executeZapisz", "path": path}
    assert result.numbered_lines and not result.candidates


def test_two_definitions_of_one_file_stay_candidates_with_their_own_lines() -> None:
    """Sprawdza, czy dwie funkcje o tej samej nazwie w jednym pliku, także po zawężeniu do tego
    pliku, wracają jako dwóch kandydatów o różnych liniach.

    Wyłapuje narzędzie, które w takim pliku oddaje pierwszą funkcję: kandydat niesie linie po
    to, żeby model mógł przeczytać wybraną odczytem pliku."""
    result = _result("dataInit", GRID)

    assert result.symbol is None
    assert [(c.from_line, c.to_line) for c in result.candidates] == [(3, 4), (6, 7)]


def test_candidates_over_the_limit_are_counted_not_shown() -> None:
    """Sprawdza, czy przy liczbie definicji większej niż limit listy wynik pokazuje dokładnie
    tylu kandydatów, ile wynosi limit, a resztę podaje jako liczbę pominiętych.

    Wyłapuje listę bez limitu: nazwa konstruktora ma w prawdziwym kodzie ponad tysiąc
    definicji, a każda zajęłaby w wyniku kilka linii."""
    classes = [f"Klasa{number:02}" for number in range(MAX_CANDIDATES + 5)]
    crowded = SYMBOL_MAP.model_copy(update={"files": {
        f"src/lib/{name}.php": [_symbol("__construct", name, "method", 5, 9)] for name in classes
    }})

    result = find_symbol_and_build_result(
        query      = ReadCodeSymbolQuery(name="__construct"),
        inside     = None,
        symbol_map = crowded,
        read_lines = _lines,
    )

    assert len(result.candidates)    == MAX_CANDIDATES
    assert result.omitted_over_limit == 5
    assert result.candidates[0].path == "src/lib/Klasa00.php"


@pytest.mark.parametrize(
    ("length", "returned_to", "cut"),
    [
        (MAX_LINES_PER_SYMBOL - 1, MAX_LINES_PER_SYMBOL - 1, False),
        (MAX_LINES_PER_SYMBOL,     MAX_LINES_PER_SYMBOL,     False),
        (MAX_LINES_PER_SYMBOL + 1, MAX_LINES_PER_SYMBOL,     True),
        (2 * MAX_LINES_PER_SYMBOL, MAX_LINES_PER_SYMBOL,     True),
    ],
    ids=["o linię krótsza", "równo limit", "o linię dłuższa", "dwa razy dłuższa"],
)
def test_a_definition_longer_than_the_limit_is_cut_and_says_so(
    length:      int,
    returned_to: int,
    cut:         bool,
) -> None:
    """Sprawdza, czy definicja nie dłuższa niż limit linii wraca cała i bez flagi urwania,
    a dłuższa wraca urwana na limicie, z flagą — przy czym opis definicji zawsze podaje jej
    prawdziwą ostatnią linię.

    Wyłapuje granicę przesuniętą o jedną linię i urwanie bez flagi: model wziąłby początek
    długiej klasy za całą klasę."""
    long_map = SYMBOL_MAP.model_copy(update={"files": {
        "src/lib/Dluga.php": [_symbol("Dluga", None, "class", 1, length)],
    }})

    result = find_symbol_and_build_result(
        query      = ReadCodeSymbolQuery(name="Dluga"),
        inside     = None,
        symbol_map = long_map,
        read_lines = lambda path: [f"linia {number}" for number in range(1, length + 1)],
    )

    assert result.symbol.to_line == length
    assert (result.returned.to_line, result.returned.cut_by_limit) == (returned_to, cut)
    assert len(line_numbers(result.numbered_lines)) == returned_to


@pytest.mark.parametrize(
    ("name", "path", "says"),
    [
        ("executeLista",                 PISMA,  ["poza tą ścieżką: 1", "poszerz `path`"]),
        ("Urzad\\Sprawy\\sprawyActions", PISMA,  ["poza tą ścieżką: 1", "poszerz `path`"]),
        ("pismaActions::executeLista",   None,   ["samej nazwie executeLista", ": 1 —"]),
        ("anuluj",                       JS,     ["`find_code_text`"]),
        ("nieMaTakiej",                  None,   ["`find_code_text`"]),
        ("cokolwiek",                    BROKEN, ["błąd składni", "`read_code_file`"]),
    ],
    ids=["jest poza ścieżką", "z przestrzenią nazw, poza ścieżką", "klasa nie ma tej metody",
         "nie ma w pliku ani nigdzie", "nie ma nigdzie", "plik odrzucony przez parser"],
)
def test_a_name_without_a_definition_is_an_error_that_says_what_to_do(
    name: str,
    path: str | None,
    says: list[str],
) -> None:
    """Sprawdza, czy brak definicji kończy się wyjątkiem `NoSuchSymbolError`, który jest odmianą
    `ToolCallError` i mówi, co mapa wie o nazwie: że definicje są poza ścieżką, że klasa nie ma
    takiej metody, ale sama nazwa jest, że nazwy nie ma wcale, albo że plik odrzucił parser.

    Wyłapuje pusty wynik zamiast błędu oraz jeden komunikat na wszystkie przypadki: po
    „nie znaleziono" model nie wiedziałby, czy poszerzyć ścieżkę, czy szukać nazwy tekstem,
    a metoda z klasy bazowej w tym samym katalogu wyglądałaby jak metoda, której nie ma."""
    with pytest.raises(NoSuchSymbolError) as caught:
        _result(name, path)

    assert isinstance(caught.value, ToolCallError)
    for fragment in says:
        assert fragment in str(caught.value)


def test_a_method_of_another_class_is_not_returned_for_a_wrong_class() -> None:
    """Sprawdza, czy pytanie o metodę klasy, która takiej metody nie ma, kończy się błędem,
    choć inna klasa ma metodę o tej nazwie i jest ona w kodzie jedyna.

    Wyłapuje ciche dopasowanie po samej nazwie metody: model prosił o `pismaActions::
    executeLista`, a dostałby kod `sprawyActions::executeLista`, bez sygnału, że to inna klasa."""
    assert len(definitions_named(SYMBOL_MAP, "executeLista", None)) == 1

    with pytest.raises(NoSuchSymbolError):
        _result("pismaActions::executeLista")


def test_a_map_of_another_code_stops_the_call_instead_of_answering_the_model() -> None:
    """Sprawdza, czy definicja, której ostatnia linia według mapy leży za końcem pliku, kończy
    się wyjątkiem `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje odczyt z mapy zbudowanej dla innej wersji kodu: narzędzie oddawałoby uciętą funkcję
    albo linie innej funkcji, a model nie miałby jak zauważyć, że mapa jest nieaktualna."""
    with pytest.raises(CodePackageConfigError) as caught:
        find_symbol_and_build_result(
            query      = ReadCodeSymbolQuery(name="executeLista"),
            inside     = None,
            symbol_map = SYMBOL_MAP,
            read_lines = lambda path: ["<?php"] * 15,
        )

    assert not isinstance(caught.value, ToolCallError)
    assert "zbuduj mapę od nowa" in str(caught.value)
