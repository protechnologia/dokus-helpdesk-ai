"""
Description:
Prawdziwe narzędzie `read_code_symbol`: oddaje z paczki kodu aplikacji jedną funkcję, metodę
albo klasę w całości, po nazwie. Granice bierze z mapy symboli paczki, linie z pliku. Nie woła
embeddera, bazy ani LLM-a — tylko folder paczki.

    nazwa i ścieżka → mapa symboli → jedna definicja  → jej linie z pliku, najwyżej limit
                                   → kilka definicji → lista kandydatów, bez treści

Przed — zapytanie agenta:

    ReadCodeSymbolQuery(name="executeZapisz", path="src/apps/frontend/modules/kontrahenci")

Po — wynik `read()`:

    ReadCodeSymbolResult(
        requested = RequestedSymbol(name="executeZapisz",
                                    path="src/apps/frontend/modules/kontrahenci"),
        symbol    = SymbolDefinition(
            path="src/apps/frontend/modules/kontrahenci/actions/actions.class.php",
            name="executeZapisz", scope="kontrahenciActions", kind="method",
            from_line=13, to_line=27,
        ),
        returned  = ReturnedSymbolLines(from_line=13, to_line=27, cut_by_limit=False),
        lines     = [SymbolLine(line=13, text="    public function executeZapisz(…"), …],
    )

To samo zapytanie bez `path` oddaje trzech kandydatów: akcję `executeZapisz` mają trzy moduły.

Co się dzieje po drodze:

1. Czytnik paczki sprawdza ścieżkę zawężenia i oddaje ją w jednej postaci; ścieżka spoza
   paczki albo donikąd kończy się `UnknownSymbolPathError`.
2. Czytnik mapy oddaje mapę symboli paczki.
3. Z mapy wybierane są definicje, do których pasuje nazwa, spod ścieżki zawężenia.
4. Jedna definicja wraca z liniami pliku, najwyżej `MAX_LINES_PER_SYMBOL`; kilka jako lista
   kandydatów, najwyżej `MAX_CANDIDATES`; brak kończy się `NoSuchSymbolError`.

O czym pamiętać przy zmianach:

- Odczyt symbolu źródeł nie tworzy, jak odczyt pliku: źródłem jest dopiero fragment zacytowany
  jako przyczyna narzędziem `quote_code`.
- Mapa jest czytana z dysku przy każdym wywołaniu: przebudowa paczki podmienia ją bez restartu
  usługi.
- Brak paczki albo mapy to `CodePackageConfigError`: nie wraca do modelu, zatrzymuje przebieg.
  Inaczej model dostawałby „nie ma takiej definicji" na każde pytanie.
- Mapa zna definicje z plików PHP i JS. Plik, którego parser nie rozebrał, symboli nie ma:
  błąd mówi wtedy modelowi, żeby czytał plik odczytem pliku.
"""

import logging

from app.agent_tools.code.read_code_symbol.base import (
    ReadCodeSymbolToolBase,
    find_symbol_and_build_result,
)
from app.agent_tools.code.read_code_symbol.errors import UnknownSymbolPathError
from app.agent_tools.code.read_code_symbol.models import ReadCodeSymbolQuery, ReadCodeSymbolResult
from app.core_service.loader_code_package import CodePackage, CodePathError
from app.core_service.loader_code_symbols import CodeSymbols

logger = logging.getLogger(__name__)

# Tak czytnik paczki oddaje katalog główny kodu; zawężenie do niego to brak zawężenia.
WHOLE_CODE = "."


class ReadCodeSymbolTool(ReadCodeSymbolToolBase):
    """
    Description:
    `read_code_symbol` na prawdziwej paczce kodu: znajduje definicję w mapie symboli i oddaje
    jej linie z pliku.

    Do czego:
    Odczyt jednej funkcji w grafach `search`, `suggest_questions` i `suggest_solution`. Model
    zna nazwę z pola `symbol` w wyniku szukania albo z wywołania w przeczytanym kodzie i dostaje
    całą funkcję, zamiast zgadywać zakres linii. Tylko do odczytu.

    Flow:
        1. `read()` ustala ścieżkę zawężenia w paczce i bierze mapę symboli.
        2. `find_symbol_and_build_result()` wybiera definicje i składa wynik.
        3. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        package: CodePackage,  # np. CodePackage(Path("/code/data/unsafe/code"))
        symbols: CodeSymbols,  # np. CodeSymbols(Path("/code/data/unsafe/code"))
    ):
        """
        Description:
        Spina narzędzie z paczką kodu i z jej mapą symboli. Oba czytniki są wstrzykiwane, nie
        budowane tutaj: paczka pilnuje ścieżek i oddaje linie, mapa granice definicji.

        Example args:
            package=CodePackage(Path("/code/data/unsafe/code"))
            symbols=CodeSymbols(Path("/code/data/unsafe/code"))

        Example result:
            ReadCodeSymbolTool gotowe do czytania definicji z paczki
        """
        self._package = package
        self._symbols = symbols

    async def read(
        self,
        query: ReadCodeSymbolQuery,  # np. ReadCodeSymbolQuery(name="nastepnyNumer")
    ) -> ReadCodeSymbolResult:
        """
        Description:
        Odczytuje z paczki definicję o podanej nazwie: jedną z liniami albo kilka jako listę
        kandydatów bez treści.

        Example args:
            query=ReadCodeSymbolQuery(name="nastepnyNumer", path="src/lib/Urzad/Numeracja")

        Example result:
            ReadCodeSymbolResult(requested=RequestedSymbol(name="nastepnyNumer", path="src/…"),
                                 symbol=SymbolDefinition(path="src/…/GeneratorNumeru.php", …),
                                 returned=ReturnedSymbolLines(from_line=13, to_line=26, …),
                                 lines=[SymbolLine(line=13, text="    public function …"), …])

        Raises:
            UnknownSymbolPathError: `path` nie wskazuje pliku ani katalogu w paczce
            NoSuchSymbolError: pod ścieżką nie ma definicji o tej nazwie
            CodePackageConfigError: nie ma paczki albo mapy symboli, albo mapa nie pasuje do kodu
        """
        # --- gdzie szukać definicji: cały kod albo sprawdzona ścieżka zawężenia ---
        inside = None

        if query.path:
            try:
                located = self._package.locate(query.path, allow_dir=True)
            except CodePathError as exc:
                # `from None`: wyjątek czytnika niczego tu nie dodaje, a komunikat idzie do modelu.
                raise UnknownSymbolPathError(str(exc)) from None
            inside = None if located == WHOLE_CODE else located

        symbol_map = self._symbols.read()
        result     = find_symbol_and_build_result(
            query      = query,
            inside     = inside,
            symbol_map = symbol_map,
            read_lines = self._package.read_lines,
        )

        # Same liczby: nazwę i ścieżkę podaje model, a wskazują one miejsce w kodzie klienta.
        logger.info(
            "read_code_symbol narrowed=%s found=%s candidates=%d omitted=%d lines=%d",
            inside is not None,
            result.symbol is not None,
            len(result.candidates),
            result.omitted_over_limit,
            len(result.lines),
        )

        return result
