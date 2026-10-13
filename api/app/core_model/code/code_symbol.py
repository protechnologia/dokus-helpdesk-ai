from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Czym jest definicja. Te same słowa zapisuje w mapie skrypt `scripts/build_code_symbols.py`.
SymbolKind = Literal["class", "interface", "trait", "method", "function"]


class CodeSymbol(BaseModel):
    """
    Description:
    Jedna definicja w pliku kodu aplikacji: funkcja, metoda albo klasa, z pierwszą i ostatnią
    linią. Wpis mapy symboli paczki (`symbols.json`), którą buduje skrypt
    `scripts/build_code_symbols.py`, a czyta `CodeSymbols` z
    `core_service/loader_code_symbols.py`.

    Do czego:
    Z tych granic narzędzia agenta wezmą funkcję w całości, żeby model nie zgadywał zakresu
    linii (CLAUDE.md -> p. 73). To definicja, nie użycie: wywołań funkcji mapa nie zna.

    `scope` mówi, w czym definicja leży: metoda w klasie (`GeneratorNumeru`), funkcja JS pod
    ścieżką nazw (`APP.pisma`). Pole jest wymagane, żeby brak był zapisany wprost.

    Numery linii liczą się od 1 i obie granice należą do definicji, jak w `read_code_file`
    i `quote_code`. Tego, że `to_line` nie jest mniejsze od `from_line`, model nie sprawdza:
    walidator w Pythonie wydłużał wczytanie mapy paczki Dokusa z 0,18 s do 0,34 s, a pilnują
    tego testy skryptu, który mapę zapisuje.
    """

    model_config = ConfigDict(extra="forbid")

    name:      str        = Field(min_length=1, examples=["nastepnyNumer"])
    # `None`: definicja nie leży w niczym nazwanym (klasa, funkcja poza klasą).
    scope:     str | None = Field(min_length=1, examples=["GeneratorNumeru"])
    kind:      SymbolKind = Field(examples=["method"])
    from_line: int        = Field(ge=1, examples=[13])
    to_line:   int        = Field(ge=1, examples=[26])
