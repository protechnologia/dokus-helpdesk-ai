"""
Description:
Źródło wiedzy: fragment kodu aplikacji, który agent wskazał jako przyczynę opisanego zachowania.
Jedyne narzędzie kodu, które dokłada do listy źródeł odpowiedzi — odczyt pliku jej nie tworzy,
bo model przechodzi przez wiele więcej plików, niż potrzebuje do odpowiedzi. Każde cytowanie
niesie rolę: `cause` trafia na listę źródeł, `excluded` (miejsce sprawdzone i wykluczone) nie.
Jedno wywołanie to jeden fragment, więc limit wywołań jest limitem cytowań w sprawie.

| plik             | co zawiera                                                              |
|------------------|-------------------------------------------------------------------------|
| `models.py`      | zapytanie (ścieżka, zakres linii, rola), potwierdzenie i limit długości |
| `errors.py`      | `UnknownCodeFileError`, `LinesOutOfFileError` — wracają do modelu       |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                      |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, potwierdzenie, źródło          |
| `tool.py`        | `QuoteCodeTool` — sprawdza fragment w paczce kodu na dysku              |
| `fake.py`        | `FakeQuoteCodeTool` — zmyślone pliki, bez dysku                         |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model, i źródła —
w opisie `base.py`.

Narzędzie nie oddaje treści linii i nie sprawdza, czy model je wcześniej przeczytał. Narzędzi,
którymi model czyta kod, jeszcze nie ma (CLAUDE.md -> p. 62–66).
"""

from app.agent_tools.code.quote_code.base import QuoteCodeToolBase, check_lines_and_build_result
from app.agent_tools.code.quote_code.errors import LinesOutOfFileError, UnknownCodeFileError
from app.agent_tools.code.quote_code.fake import FakeQuoteCodeTool
from app.agent_tools.code.quote_code.models import (
    MAX_LINES_PER_QUOTE,
    QuoteCodeQuery,
    QuoteCodeResult,
    QuoteRole,
)
from app.agent_tools.code.quote_code.tool import QuoteCodeTool

__all__ = [
    "MAX_LINES_PER_QUOTE",
    "FakeQuoteCodeTool",
    "LinesOutOfFileError",
    "QuoteCodeQuery",
    "QuoteCodeResult",
    "QuoteCodeTool",
    "QuoteCodeToolBase",
    "QuoteRole",
    "UnknownCodeFileError",
    "check_lines_and_build_result",
]
