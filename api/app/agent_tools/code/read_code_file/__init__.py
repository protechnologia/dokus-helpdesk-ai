"""
Description:
Narzędzie pomocnicze: plik z kodu aplikacji albo zakres jego linii, każda z numerem. Drugi krok
po szukaniu (`find_code_text`): linia znaleziona szukaniem mówi, gdzie tekst stoi, a odczyt
pokazuje, w jakiej funkcji leży i przy jakim warunku kod do niej dochodzi. Niczego nie cytuje —
źródłem odpowiedzi jest dopiero fragment wskazany jako przyczyna narzędziem `quote_code`.

| plik             | co zawiera                                                                |
|------------------|---------------------------------------------------------------------------|
| `models.py`      | zapytanie (ścieżka, zakres linii), wynik z dwoma zakresami i limit linii  |
| `errors.py`      | `NoSuchCodeFileError`, `StartOutOfFileError` — wracają do modelu          |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                        |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, wybranie linii, tekst dla modelu |
| `tool.py`        | `ReadCodeFileTool` — czyta plik z paczki kodu na dysku                    |
| `fake.py`        | `FakeReadCodeFileTool` — zmyślone pliki, bez dysku                        |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model, i znaczenie
flag `cut_by_limit` i `end_of_file` — w opisie `base.py`.

Jedno wywołanie oddaje najwyżej `MAX_LINES_PER_READ` linii. Wynik niesie obok siebie zakres, o
który agent prosił, i zakres, który dostał, bo to jedyne narzędzie, które może oddać mniej, niż
żądano: gdy odczyt urwie limit albo skończy się plik.
"""

from app.agent_tools.code.read_code_file.base import (
    ReadCodeFileToolBase,
    select_lines_and_build_result,
)
from app.agent_tools.code.read_code_file.errors import NoSuchCodeFileError, StartOutOfFileError
from app.agent_tools.code.read_code_file.fake import FakeReadCodeFileTool
from app.agent_tools.code.read_code_file.models import (
    MAX_LINES_PER_READ,
    CodeFileInfo,
    CodeLine,
    ReadCodeFileQuery,
    ReadCodeFileResult,
    RequestedLines,
    ReturnedLines,
)
from app.agent_tools.code.read_code_file.tool import ReadCodeFileTool

__all__ = [
    "MAX_LINES_PER_READ",
    "CodeFileInfo",
    "CodeLine",
    "FakeReadCodeFileTool",
    "NoSuchCodeFileError",
    "ReadCodeFileQuery",
    "ReadCodeFileResult",
    "ReadCodeFileTool",
    "ReadCodeFileToolBase",
    "RequestedLines",
    "ReturnedLines",
    "StartOutOfFileError",
    "select_lines_and_build_result",
]
