"""
Description:
To, co wspólne dla prawdziwego `read_code_symbol` i jego atrapy: nazwa, klasa argumentów,
znalezienie definicji w mapie symboli i tekst dla modelu. Narzędzie i atrapa różnią się
wyłącznie tym, skąd biorą mapę symboli i linie pliku (`read()`).

Przed — zapytanie agenta:

    ReadCodeSymbolQuery(name="nastepnyNumer", path="src/lib/Urzad/Numeracja")

Po — tekst dla modelu, gdy pasuje jedna definicja (linie skrócone do dwóch):

    {
      "requested": {
        "name": "nastepnyNumer",
        "path": "src/lib/Urzad/Numeracja"
      },
      "symbol": {
        "path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
        "name": "nastepnyNumer",
        "scope": "GeneratorNumeru",
        "kind": "method",
        "from_line": 5,
        "to_line": 13
      },
      "returned": {
        "from_line": 5,
        "to_line": 13,
        "cut_by_limit": false
      },
      "numbered_lines": "5\t    public function nastepnyNumer($rok)\n6\t    {\n…",
      "candidates": [],
      "omitted_over_limit": 0
    }

Gdy pasuje kilka definicji, `symbol`, `returned` i `numbered_lines` to `null`, a pasujące
definicje stoją w `candidates`, bez treści.

Jak nazwa z zapytania pasuje do definicji z mapy:

| zapytanie                        | pasuje do                                             |
|----------------------------------|-------------------------------------------------------|
| `nastepnyNumer`                  | każdej definicji o tej nazwie                         |
| `GeneratorNumeru::nastepnyNumer` | metody `nastepnyNumer` klasy `GeneratorNumeru`        |
| `APP.pisma.wyslijHandler`        | funkcji `wyslijHandler` pod `APP.pisma`               |
| `GeneratorNumeru`                | klasy o tej nazwie                                    |
| `Urzad\\Numeracja\\GeneratorNumeru` | tej samej klasy: przestrzeń nazw jest pomijana       |

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: niczego nie cytuje i nie ma `cite()`, jak odczyt pliku.
- Treść wraca tylko przy jednej pasującej definicji. Przy kilku model dostaje kandydatów
  i wybiera: zawęża `path` do pliku kandydata albo czyta jego linie odczytem pliku. Bez tego
  narzędzie zgadywałoby, o którą z trzech akcji `executeZapisz` chodzi.
- Nazwa z miejscem, która nie pasuje, nie jest po cichu zamieniana na samą nazwę: model
  dostałby metodę innej klasy niż ta, o którą prosił. Błąd mówi, ile definicji ma sama nazwa.
- Wielkość liter ma znaczenie: nazwy pochodzą z kodu i model przepisuje je z wyniku szukania.
- Przestrzeń nazw PHP przed nazwą klasy jest zdejmowana (`without_namespace()`), bo mapa jej
  nie trzyma. To nie to samo co zamiana nazwy z klasą na samą nazwę: klasa zostaje ta, o którą
  model prosił, a dwie klasy o tej nazwie w różnych przestrzeniach wracają jako kandydaci.
- Wynik liczy jedna funkcja, `find_symbol_and_build_result()`, wspólna dla narzędzia i atrapy.
- Definicja, której linie wychodzą poza plik, znaczy, że mapa powstała z innego kodu niż ten
  w paczce: to błąd konfiguracji, nie błąd dla modelu.
- Ścieżka i numery linii są te same, które przyjmują `read_code_file` i `quote_code`.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod
from collections.abc import Callable, Sequence

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.code.read_code_symbol.errors import NoSuchSymbolError
from app.agent_tools.code.read_code_symbol.models import (
    MAX_CANDIDATES,
    MAX_LINES_PER_SYMBOL,
    ReadCodeSymbolQuery,
    ReadCodeSymbolResult,
    RequestedSymbol,
    ReturnedSymbolLines,
    SymbolDefinition,
)
from app.core_model.code.code_symbol import CodeSymbol
from app.core_model.code.code_symbol_map import CodeSymbolMap
from app.core_service.loader_code_package import CodePackageConfigError
from app.core_util.path import is_path_under
from app.core_util.text import number_lines

# Czym w zapytaniu bywa oddzielone miejsce od nazwy: `Klasa::metoda`, `$obiekt->metoda`,
# `APP.pisma.wyslij`.
SEPARATORS = ("::", "->", ".")

# Separator przestrzeni nazw PHP: `Urzad\\Numeracja\\GeneratorNumeru`.
NAMESPACE_SEPARATOR = "\\"


def without_namespace(
    name: str,  # np. "Urzad\\Numeracja\\GeneratorNumeru::nastepnyNumer"
) -> str:
    """
    Description:
    Zdejmuje z nazwy przestrzeń nazw PHP: zostaje to, co stoi po ostatnim ukośniku wstecznym.
    Mapa symboli przestrzeni nazw nie trzyma, więc klasa podana z nią i bez niej to ta sama
    klasa. Nazwa bez ukośnika wraca bez zmian.

    Example args:
        name="Urzad\\Numeracja\\GeneratorNumeru::nastepnyNumer"

    Example result:
        "GeneratorNumeru::nastepnyNumer"
    """
    return name.rsplit(NAMESPACE_SEPARATOR, 1)[-1]


def is_named(
    symbol: CodeSymbol,  # np. CodeSymbol(name="nastepnyNumer", scope="GeneratorNumeru", …)
    name:   str,         # np. "GeneratorNumeru::nastepnyNumer"
) -> bool:
    """
    Description:
    Mówi, czy nazwa z zapytania wskazuje tę definicję: jest jej nazwą albo nazwą poprzedzoną
    miejscem, w którym definicja leży, z dowolnym ze znanych separatorów.

    Example args:
        symbol=CodeSymbol(name="nastepnyNumer", scope="GeneratorNumeru", kind="method", …)
        name="GeneratorNumeru::nastepnyNumer"

    Example result:
        True
    """
    # --- sama nazwa ---
    if symbol.name == name:
        return True

    # --- nazwa z miejscem: tylko gdy definicja w czymś leży ---
    if symbol.scope is None:
        return False

    return any(name == f"{symbol.scope}{separator}{symbol.name}" for separator in SEPARATORS)


def bare_name_of(
    name: str,  # np. "sprawyActions::executeResetuj"
) -> str | None:
    """
    Description:
    Oddaje samą nazwę z nazwy podanej razem z miejscem: to, co stoi po ostatnim separatorze.
    Nazwa bez separatora nie ma czego odcinać.

    Example args:
        name="sprawyActions::executeResetuj"

    Example result:
        "executeResetuj"
    """
    # Gdzie stoi każdy separator, który w nazwie wystąpił; liczy się ten najdalej w prawo.
    places = [(name.rfind(separator), separator) for separator in SEPARATORS if separator in name]
    if not places:
        return None

    place, separator = max(places)
    bare             = name[place + len(separator):]

    return bare or None


def definitions_named(
    symbol_map: CodeSymbolMap,
    name:       str,         # np. "executeZapisz"
    inside:     str | None,  # np. "src/apps/frontend/modules"; None: cały kod
) -> list[SymbolDefinition]:
    """
    Description:
    Wybiera z mapy symboli definicje, do których pasuje nazwa, spod ścieżki zawężenia. Oddaje
    je po ścieżce pliku i po linii, z plikiem przy każdej.

    Example args:
        symbol_map=CodeSymbolMap(files={"src/…/kontrahenci/actions/actions.class.php": […], …})
        name="executeZapisz"
        inside="src/apps/frontend/modules"

    Example result:
        [SymbolDefinition(path="src/apps/frontend/modules/kontrahenci/actions/actions.class.php",
                          name="executeZapisz", scope="kontrahenciActions", kind="method",
                          from_line=13, to_line=27), …]
    """
    found = [
        SymbolDefinition(
            path      = path,
            name      = symbol.name,
            scope     = symbol.scope,
            kind      = symbol.kind,
            from_line = symbol.from_line,
            to_line   = symbol.to_line,
        )
        for path, symbols in symbol_map.files.items()
        # Bez zawężenia pasuje każdy plik; z zawężeniem ten plik albo pliki tego katalogu.
        if inside is None or is_path_under(path, inside)
        for symbol in symbols
        if is_named(symbol, name)
    ]

    return sorted(found, key=lambda definition: (definition.path, definition.from_line))


def find_symbol_and_build_result(
    query:      ReadCodeSymbolQuery,             # np. ReadCodeSymbolQuery(name="nastepnyNumer")
    inside:     str | None,                      # ścieżka zawężenia z paczki; None: cały kod
    symbol_map: CodeSymbolMap,                   # mapa symboli paczki
    read_lines: Callable[[str], Sequence[str]],  # oddaje linie pliku o podanej ścieżce
) -> ReadCodeSymbolResult:
    """
    Description:
    Znajduje w mapie symboli definicje, do których pasuje nazwa z zapytania, i składa wynik
    narzędzia. Jedna definicja wraca z liniami, najwyżej `MAX_LINES_PER_SYMBOL`; kilka wraca
    jako lista kandydatów bez treści, najwyżej `MAX_CANDIDATES`. Wspólne dla atrapy i narzędzia
    właściwego: oba najpierw ustalają ścieżkę zawężenia i biorą mapę.

    Example args:
        query=ReadCodeSymbolQuery(name="nastepnyNumer", path="src/lib/Urzad/Numeracja")
        inside="src/lib/Urzad/Numeracja"
        symbol_map=CodeSymbolMap(files={"src/lib/Urzad/Numeracja/GeneratorNumeru.php": […]})
        read_lines=package.read_lines

    Example result:
        ReadCodeSymbolResult(requested=RequestedSymbol(name="nastepnyNumer", path="src/lib/…"),
                             symbol=SymbolDefinition(path="src/lib/…/GeneratorNumeru.php", …),
                             returned=ReturnedSymbolLines(from_line=5, to_line=13,
                                                          cut_by_limit=False),
                             numbered_lines="5\t    public function …\n6\t    {\n…",
                             candidates=[], omitted_over_limit=0)

    Raises:
        NoSuchSymbolError: pod ścieżką nie ma definicji o tej nazwie
        CodePackageConfigError: linie definicji wychodzą poza plik, czyli mapa nie pasuje do kodu
    """
    requested = RequestedSymbol(name=query.name, path=inside)
    # Przestrzeni nazw mapa nie trzyma: szukamy klasy albo metody pod samą nazwą klasy.
    name      = without_namespace(query.name)
    found     = definitions_named(symbol_map, name, inside)

    # --- żadna definicja: błąd, który mówi, co mapa wie o tej nazwie ---
    if not found:
        bare_name = bare_name_of(name)
        raise NoSuchSymbolError(
            name         = query.name,
            path         = inside,
            outside      = len(definitions_named(symbol_map, name, None)),
            bare_name    = bare_name,
            bare_count   = len(definitions_named(symbol_map, bare_name, None)) if bare_name else 0,
            syntax_error = inside in symbol_map.syntax_errors,
        )

    # --- kilka definicji: lista kandydatów bez treści, wybiera model ---
    if len(found) > 1:
        several = ReadCodeSymbolResult(
            requested          = requested,
            symbol             = None,
            returned           = None,
            candidates         = found[:MAX_CANDIDATES],
            omitted_over_limit = max(0, len(found) - MAX_CANDIDATES),
        )

        return several

    # --- jedna definicja: jej linie, najwyżej limit ---
    symbol = found[0]
    lines  = read_lines(symbol.path)
    if symbol.to_line > len(lines):
        raise CodePackageConfigError(
            f"mapa symboli nie pasuje do kodu w paczce: {symbol.path} ma {len(lines)} linii, "
            f"a mapa mówi o linii {symbol.to_line} — zbuduj mapę od nowa "
            f"(scripts/build_code_symbols.py build <katalog paczki>)"
        )

    last   = min(symbol.to_line, symbol.from_line + MAX_LINES_PER_SYMBOL - 1)
    result = ReadCodeSymbolResult(
        requested      = requested,
        symbol         = symbol,
        returned       = ReturnedSymbolLines(
            from_line    = symbol.from_line,
            to_line      = last,
            cut_by_limit = last < symbol.to_line,  # definicja jest dłuższa niż limit linii
        ),
        numbered_lines = number_lines(lines[symbol.from_line - 1:last], first=symbol.from_line),
    )

    return result


class ReadCodeSymbolToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `read_code_symbol`: wszystko poza pobraniem mapy symboli i linii pliku.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeReadCodeSymbolTool`) i narzędzie właściwe na paczce
    kodu (`ReadCodeSymbolTool`). Każda dokłada wyłącznie `read()`, więc tekst dla modelu jest
    ten sam w testach i na produkcji.

    Flow:
        1. `run()` woła `read()` podklasy i dostaje `ReadCodeSymbolResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "read_code_symbol"
    description = read_description(__file__)
    args_model  = ReadCodeSymbolQuery

    @abstractmethod
    async def read(
        self,
        query: ReadCodeSymbolQuery,  # np. ReadCodeSymbolQuery(name="nastepnyNumer")
    ) -> ReadCodeSymbolResult:
        """
        Description:
        Odczytuje z kodu aplikacji definicję o podanej nazwie: jedną z liniami albo kilka jako
        listę kandydatów bez treści.

        Example args:
            query=ReadCodeSymbolQuery(name="nastepnyNumer", path="src/lib/Urzad/Numeracja")

        Example result:
            ReadCodeSymbolResult(requested=RequestedSymbol(name="nastepnyNumer", path="src/…"),
                                 symbol=SymbolDefinition(path="src/…/GeneratorNumeru.php", …),
                                 returned=ReturnedSymbolLines(from_line=5, to_line=13, …),
                                 numbered_lines="5\t    public function …\n…")
        """

    async def run(
        self,
        args: ReadCodeSymbolQuery,  # np. ReadCodeSymbolQuery(name="nastepnyNumer")
    ) -> str:
        """
        Description:
        Odczytuje definicję i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=ReadCodeSymbolQuery(name="nastepnyNumer")

        Example result:
            {"requested": {"name": "nastepnyNumer", "path": null},
             "symbol": {"path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php", …},
             "returned": {"from_line": 5, "to_line": 13, "cut_by_limit": false},
             "numbered_lines": "5\t    public function nastepnyNumer($rok)\n6\t    {\n…",
             "candidates": [], "omitted_over_limit": 0}
        """
        result = await self.read(args)
        text   = result_as_json(result)

        return text
