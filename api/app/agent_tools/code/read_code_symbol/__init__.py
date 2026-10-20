"""
Description:
Narzędzie pomocnicze: jedna funkcja, metoda albo klasa z kodu aplikacji w całości, po nazwie.
Granice definicji bierze z mapy symboli paczki (`symbols.json`), więc model nie zgaduje zakresu
linii. Nazwę model zna z pola `symbol` w wyniku szukania (`find_code_text`) albo z wywołania
w przeczytanym kodzie. Niczego nie cytuje — źródłem odpowiedzi jest dopiero fragment wskazany
jako przyczyna narzędziem `quote_code`.

| plik             | co zawiera                                                                 |
|------------------|----------------------------------------------------------------------------|
| `models.py`      | zapytanie (nazwa, ścieżka), wynik w dwóch postaciach i oba limity          |
| `errors.py`      | `UnknownSymbolPathError`, `NoSuchSymbolError` — wracają do modelu          |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                         |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, szukanie w mapie, tekst dla modelu |
| `tool.py`        | `ReadCodeSymbolTool` — mapa symboli i pliki z paczki kodu na dysku         |
| `fake.py`        | `FakeReadCodeSymbolTool` — zmyślone pliki i ich mapa, bez dysku            |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model, i to, jak
nazwa z zapytania pasuje do definicji — w opisie `base.py`.

Do nazwy może pasować kilka definicji: akcję o tej samej nazwie mają różne moduły. Treść wraca
tylko przy jednej; przy kilku wynik wymienia kandydatów bez treści, a model zawęża ścieżkę.
"""

from app.agent_tools.code.read_code_symbol.base import (
    ReadCodeSymbolToolBase,
    find_symbol_and_build_result,
)
from app.agent_tools.code.read_code_symbol.errors import NoSuchSymbolError, UnknownSymbolPathError
from app.agent_tools.code.read_code_symbol.fake import FakeReadCodeSymbolTool
from app.agent_tools.code.read_code_symbol.models import (
    MAX_CANDIDATES,
    MAX_LINES_PER_SYMBOL,
    ReadCodeSymbolQuery,
    ReadCodeSymbolResult,
    RequestedSymbol,
    ReturnedSymbolLines,
    SymbolDefinition,
)
from app.agent_tools.code.read_code_symbol.tool import ReadCodeSymbolTool

__all__ = [
    "MAX_CANDIDATES",
    "MAX_LINES_PER_SYMBOL",
    "FakeReadCodeSymbolTool",
    "NoSuchSymbolError",
    "ReadCodeSymbolQuery",
    "ReadCodeSymbolResult",
    "ReadCodeSymbolTool",
    "ReadCodeSymbolToolBase",
    "RequestedSymbol",
    "ReturnedSymbolLines",
    "SymbolDefinition",
    "UnknownSymbolPathError",
    "find_symbol_and_build_result",
]
