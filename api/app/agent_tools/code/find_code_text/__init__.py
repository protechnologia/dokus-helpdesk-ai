"""
Description:
Narzędzie pomocnicze: linie kodu aplikacji, w których stoi podany tekst — stały fragment
komunikatu z ekranu, wpis z logu, kod błędu albo nazwa z kodu. Od niego zaczyna się sprawa,
o której zgłoszenia i instrukcje nic nie mówią. Zwraca ścieżkę, numer linii, treść tej linii
i to, czym ją znaleziono, a z mapy symboli paczki nazwę funkcji, w której linia leży; niczego
nie cytuje.

| plik             | co zawiera                                                             |
|------------------|------------------------------------------------------------------------|
| `models.py`      | zapytanie (`exact`, `words`, `path`), znaleziona linia, wynik, limity  |
| `errors.py`      | `UnknownCodePathError` — wraca do modelu                               |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                     |
| `base.py`        | część wspólna: nazwa, tekst dla modelu, przycinanie, nazwa funkcji     |
| `tool.py`        | `FindCodeTextTool` — szukanie ripgrepem w paczce kodu na dysku         |
| `fake.py`        | `FakeFindCodeTextTool` — ustalone linie ze zmyślonych plików           |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie
`base.py`.

Wynik niesie treść trafionej linii, inaczej niż wyszukiwania zgłoszeń i dokumentacji: bez niej
model nie odróżni definicji od setek użyć tej samej nazwy. Otoczenie trafionej linii model
czyta narzędziem `read_code_file`, a całą funkcję, w której linia leży, narzędziem
`read_code_symbol`.
"""

from app.agent_tools.code.find_code_text.base import (
    FindCodeTextToolBase,
    shorten_line,
    symbol_name_at,
)
from app.agent_tools.code.find_code_text.errors import UnknownCodePathError
from app.agent_tools.code.find_code_text.fake import (
    FakeFindCodeTextTool,
    default_matched,
    matched_line_of_fake_file,
)
from app.agent_tools.code.find_code_text.models import (
    MAX_LINES_PER_SEARCH,
    MAX_TEXT_CHARS,
    MIN_LONGEST_WORD_CHARS,
    FindCodeTextQuery,
    FindCodeTextResult,
    MatchedLine,
)
from app.agent_tools.code.find_code_text.tool import FindCodeTextTool

__all__ = [
    "MAX_LINES_PER_SEARCH",
    "MAX_TEXT_CHARS",
    "MIN_LONGEST_WORD_CHARS",
    "FakeFindCodeTextTool",
    "FindCodeTextQuery",
    "FindCodeTextResult",
    "FindCodeTextTool",
    "FindCodeTextToolBase",
    "MatchedLine",
    "UnknownCodePathError",
    "default_matched",
    "matched_line_of_fake_file",
    "shorten_line",
    "symbol_name_at",
]
