"""
Description:
Czyta mapę symboli paczki kodu aplikacji: plik `symbols.json`, w którym stoi, gdzie zaczyna się
i kończy każda funkcja, metoda i klasa. Mapę zapisuje skrypt `scripts/build_code_symbols.py`;
tu jest tylko jej odczyt i sprawdzenie kształtu. Kodu z `repo/` ten plik nie dotyka.

Przed — fragment `symbols.json` paczki z aplikacji syntetycznej:

    "src/web/js/pisma/pisma.js": [
     {"name": "zapiszHandler", "scope": "APP.pisma", "kind": "function",
      "from_line": 3, "to_line": 7}, …]

Po:

    symbols.read().files["src/web/js/pisma/pisma.js"][0]
      →  CodeSymbol(name="zapiszHandler", scope="APP.pisma", kind="function",
                    from_line=3, to_line=7)

Co jest sprawdzane:

| co                                                        | wynik                    |
|-----------------------------------------------------------|--------------------------|
| mapy nie ma albo nie da się jej otworzyć                  | `CodePackageConfigError` |
| plik nie jest JSON-em albo ma inny kształt niż model mapy | `CodePackageConfigError` |

O czym pamiętać przy zmianach:

- Mapa leży OBOK `repo/`, jak metryczka: skrypt paczki kasuje `repo/` przy każdej budowie.
- Mapę czyta się z dysku przy każdym wywołaniu, bez pamiętania: przebudowa paczki podmienia ją
  bez restartu usługi. Odczyt mapy paczki Dokusa (7 MB, 55 tys. symboli) trwa 0,18 s.
- Brak mapy to błąd wdrożenia, jak brak paczki: do modelu nie wraca.
- Czytnik nie sprawdza, czy mapa pasuje do kodu w `repo/`. Obie rzeczy buduje jedno polecenie
  (`scripts/build_code_package.py build`), a po ręcznej zmianie `repo/` mapę buduje się
  od nowa.
- Mapa niesie definicje, nie użycia: kto woła daną funkcję, mówi szukanie w kodzie.
- Na razie nikt w aplikacji mapy nie czyta: narzędzie `read_code_symbol` i pole w wyniku
  `find_code_text` dojdą osobno (CLAUDE.md -> p. 73), razem z wyszukiwaniem po mapie.
"""

from pathlib import Path

from pydantic import ValidationError

from app.core_model.code.code_symbol_map import CodeSymbolMap
from app.core_service.loader_code_package import CodePackageConfigError

# Mapa symboli: zapisuje ją skrypt `scripts/build_code_symbols.py`, także na końcu budowy paczki.
SYMBOLS_FILE = "symbols.json"


class CodeSymbols:
    """
    Description:
    Mapa symboli paczki kodu aplikacji na dysku: oddaje ją w całości, sprawdzoną co do kształtu.

    Do czego:
    Z niej narzędzia agenta wezmą granice funkcji (CLAUDE.md -> p. 73). Osobno od `CodePackage`
    i `CodeDescription`, bo czyta inny plik paczki i nie przyjmuje ścieżki od modelu. Tylko do
    odczytu.

    Flow:
        1. Konstruktor zapamiętuje katalog paczki; dysku nie dotyka.
        2. `read()` czyta `symbols.json` i oddaje mapę jako `CodeSymbolMap`.
    """

    def __init__(
        self,
        root: Path,  # np. Path("/code/data/unsafe/code")
    ):
        """
        Description:
        Zapamiętuje katalog paczki. Nie sprawdza, czy mapa istnieje: budowa narzędzi nie dotyka
        dysku, a brak mapy wychodzi przy pierwszym użyciu.

        Example args:
            root=Path("/code/data/unsafe/code")

        Example result:
            CodeSymbols czytająca /code/data/unsafe/code/symbols.json
        """
        self._symbols = root / SYMBOLS_FILE

    def read(self) -> CodeSymbolMap:
        """
        Description:
        Czyta mapę symboli z pliku `symbols.json` i oddaje ją w całości: dzień budowy, pliki
        odrzucone przez parser i definicje każdego pliku z ich liniami.

        Example args:
            (brak)

        Example result:
            CodeSymbolMap(built_on=date(2026, 10, 13), syntax_errors=[],
                          files={"src/web/js/pisma/pisma.js": [CodeSymbol(…), CodeSymbol(…)]})

        Raises:
            CodePackageConfigError: mapy nie ma albo nie jest mapą symboli
        """
        try:
            symbol_map = CodeSymbolMap.model_validate_json(self._symbols.read_bytes())
        except (
            OSError,          # pliku nie ma albo nie da się go otworzyć
            ValidationError,  # nie JSON, nie UTF-8 albo inny kształt niż model mapy
        ) as exc:
            raise CodePackageConfigError(
                f"mapa symboli paczki kodu aplikacji jest nie do odczytania: {self._symbols} — "
                f"zbuduj ją (scripts/build_code_symbols.py build <katalog paczki>)"
            ) from exc

        return symbol_map
