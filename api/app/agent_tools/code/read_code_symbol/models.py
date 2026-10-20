from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core_model.code.code_symbol import SymbolKind

# Najwyżej tyle linii definicji oddaje jeden odczyt; resztę czyta się narzędziem `read_code_file`.
# Ta sama liczba co limit odczytu pliku. W paczce kodu Dokusa dłuższych jest 8 funkcji i metod
# z 46 694 oraz 477 klas z 8392.
MAX_LINES_PER_SYMBOL = 300

# Najwyżej tyle definicji pokazuje lista kandydatów; pozostałe są tylko policzone. Ta sama nazwa
# bywa w kodzie zdefiniowana setki razy (`__construct`), a kandydat to jedna pozycja bez treści.
MAX_CANDIDATES = 20

# Nazwa definicji; spacje z brzegów są obcinane, a same spacje to brak nazwy.
SymbolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReadCodeSymbolQuery(BaseModel):
    """
    Description:
    O co agent prosi `read_code_symbol`: jedną funkcję, metodę albo klasę z kodu aplikacji, po
    nazwie. Nazwę można podać samą albo razem z tym, w czym definicja leży
    (`GeneratorNumeru::nastepnyNumer`, `APP.pisma.wyslijHandler`).

    `path` jest opcjonalne i znaczy to samo co w `find_code_text`: plik albo katalog, do którego
    zawęzić szukanie definicji. Bez niego narzędzie szuka w całym kodzie.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    name: SymbolName = Field(examples=["nastepnyNumer"])
    # Plik albo katalog w kodzie aplikacji; bez niego szukanie obejmuje cały kod.
    path: str | None = Field(default=None, min_length=1, examples=["src/lib/Urzad/Numeracja"])


class RequestedSymbol(BaseModel):
    """
    Description:
    O co agent prosił `read_code_symbol` — powtórzone w wyniku, żeby stało obok tego, co
    narzędzie znalazło. Ścieżka wraca w jednej postaci, względnej wobec kodu aplikacji.
    """

    model_config = ConfigDict(extra="forbid")

    name: str        = Field(min_length=1, examples=["nastepnyNumer"])
    # `None` znaczy, że agent szukał w całym kodzie.
    path: str | None = Field(min_length=1, examples=["src/lib/Urzad/Numeracja"])


class SymbolDefinition(BaseModel):
    """
    Description:
    Jedna definicja znaleziona przez `read_code_symbol`: plik, nazwa, to, w czym leży, rodzaj
    oraz pierwsza i ostatnia linia. W tym kształcie wraca i jedyna pasująca definicja, i każdy
    kandydat z listy, gdy pasuje ich kilka.

    Ścieżka i numery linii są te same, które przyjmują `read_code_file` i `quote_code`, więc
    kandydata da się przeczytać odczytem pliku bez przeliczania.
    """

    model_config = ConfigDict(extra="forbid")

    path:      str        = Field(min_length=1, examples=["src/web/js/pisma/pisma.js"])
    name:      str        = Field(min_length=1, examples=["nastepnyNumer"])
    # Klasa metody albo obiekt, pod którym leży funkcja JS; `None`, gdy nie leży w niczym.
    scope:     str | None = Field(examples=["GeneratorNumeru"])
    kind:      SymbolKind = Field(examples=["method"])
    from_line: int        = Field(ge=1, examples=[13])
    to_line:   int        = Field(ge=1, examples=[26])


class ReturnedSymbolLines(BaseModel):
    """
    Description:
    Zakres linii, który `read_code_symbol` naprawdę oddało, i powód, dla którego bywa krótszy od
    definicji: limit linii na wywołanie. Cała definicja stoi w `symbol.from_line`
    i `symbol.to_line`, więc różnicę widać w samym wyniku.
    """

    model_config = ConfigDict(extra="forbid")

    from_line:    int  = Field(ge=1, examples=[13])
    to_line:      int  = Field(ge=1, examples=[26])
    # Limit urwał definicję: dalsze linie czyta się `read_code_file` od `to_line` + 1.
    cut_by_limit: bool = Field(examples=[False])


class ReadCodeSymbolResult(BaseModel):
    """
    Description:
    Co daje jeden odczyt `read_code_symbol`. Wynik ma dwie postaci, zależnie od tego, ile
    definicji pasuje do nazwy:

    | pasuje | `symbol` | `returned` | `numbered_lines` | `candidates`         |
    |--------|----------|------------|------------------|----------------------|
    | jedna  | ona      | jej zakres | jej linie        | pusta                |
    | kilka  | `None`   | `None`     | `None`           | pasujące, bez treści |

    Gdy nie pasuje żadna, wyniku nie ma: narzędzie zgłasza błąd, który wraca do modelu.

    Linie definicji stoją w jednym tekście, każda z numerem i tabulatorem przed treścią, jak
    w wyniku `read_code_file`: model czyta funkcję w całości, jak kod.
    """

    model_config = ConfigDict(extra="forbid")

    requested:          RequestedSymbol
    # Jedyna pasująca definicja; `None`, gdy pasuje ich kilka.
    symbol:             SymbolDefinition | None
    returned:           ReturnedSymbolLines | None
    # Numer, tabulator i treść znak w znak, jak w `read_code_file`; `None` przy kandydatach.
    numbered_lines:     str | None             = Field(default=None, examples=["5\tfunction a()"])
    # Pasujące definicje, gdy jest ich kilka: po ścieżce i linii, najwyżej `MAX_CANDIDATES`.
    candidates:         list[SymbolDefinition] = Field(default_factory=list)
    # Ilu kandydatów nie zmieściło się na liście.
    omitted_over_limit: int                    = Field(default=0, ge=0, examples=[52])
