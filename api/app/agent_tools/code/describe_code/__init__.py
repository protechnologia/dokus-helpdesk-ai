"""
Description:
Narzędzie pomocnicze: opis projektu, czyli ogólny tekst o aplikacji, której kod czyta agent — z
jakich części się składa, w którym katalogu leży kod której z nich i czego w paczce nie ma. Od
niego agent zaczyna, gdy zgłoszenie nie niesie komunikatu ani kodu błędu, i do niego wraca, gdy
nie wie, w której części kodu szukać dalej. Niczego nie cytuje — opis mówi, gdzie co leży, nie
jak aplikacja się zachowuje.

| plik             | co zawiera                                                    |
|------------------|---------------------------------------------------------------|
| `models.py`      | zapytanie (bez argumentów) i wynik: metryczka paczki i opis   |
| `description.md` | opis NARZĘDZIA dla modelu, ten sam w każdym grafie            |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa i tekst dla modelu    |
| `tool.py`        | `DescribeCodeTool` — czyta opis i metryczkę z paczki na dysku |
| `fake.py`        | `FakeDescribeCodeTool` — ustalony opis, bez dysku             |

Przykład wyniku — w opisie `tool.py`; przykład tekstu, który czyta model — w opisie `base.py`.

Opis PROJEKTU to nie `description.md` z tego katalogu, tylko plik `project.md` w paczce kodu,
obok `manifest.json`: pisze go człowiek, osobno dla każdej paczki. Narzędzie oddaje go w całości
i dokłada gałąź oraz dzień budowy paczki, bo kod pochodzi z jednej gałęzi, a instalacja klienta
może stać na innej.
"""

from app.agent_tools.code.describe_code.base import DescribeCodeToolBase
from app.agent_tools.code.describe_code.fake import FakeDescribeCodeTool
from app.agent_tools.code.describe_code.models import DescribeCodeQuery, DescribeCodeResult
from app.agent_tools.code.describe_code.tool import DescribeCodeTool

__all__ = [
    "DescribeCodeQuery",
    "DescribeCodeResult",
    "DescribeCodeTool",
    "DescribeCodeToolBase",
    "FakeDescribeCodeTool",
]
