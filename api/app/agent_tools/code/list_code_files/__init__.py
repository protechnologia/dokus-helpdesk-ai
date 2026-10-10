"""
Description:
Narzędzie pomocnicze: spis katalogu z kodu aplikacji, do wskazanej głębokości. Służy do
rozejrzenia się, gdy szukanie (`find_code_text`) daje za dużo trafień albo gdy model chce
zobaczyć, co leży obok znalezionego pliku. Niczego nie cytuje — spis mówi, co gdzie leży, nie
co w plikach stoi.

| plik             | co zawiera                                                                 |
|------------------|----------------------------------------------------------------------------|
| `models.py`      | zapytanie (katalog, głębokość), wynik z dwiema głębokościami i limity      |
| `errors.py`      | `NoSuchCodeDirError` — wraca do modelu                                     |
| `description.md` | opis narzędzia dla modelu, ten sam w każdym grafie                         |
| `base.py`        | część wspólna narzędzia i atrapy: nazwa, wybranie pozycji, tekst dla modelu |
| `tool.py`        | `ListCodeFilesTool` — wylicza pliki katalogu z paczki kodu na dysku        |
| `fake.py`        | `FakeListCodeFilesTool` — ścieżki zmyślonych plików, bez dysku             |

Przykład zapytania i wyniku — w opisie `tool.py`; przykład tekstu, który czyta model, i znaczenie
sygnałów `depth_cut_by_limit`, `has_more_depth` i `omitted_over_limit` — w opisie `base.py`.

Jedno wywołanie oddaje najwyżej `MAX_ENTRIES_PER_LISTING` pozycji. Wynik niesie obok siebie
głębokość, o którą agent prosił, i głębokość, którą dostał: gdy żądana nie mieści się w limicie,
narzędzie oddaje tyle pełnych poziomów, ile się mieści. Ścieżki pozycji przyjmują bez przeróbki
`read_code_file`, `find_code_text` i kolejny spis.
"""

from app.agent_tools.code.list_code_files.base import (
    ROOT_DIR,
    ListCodeFilesToolBase,
    select_entries_and_build_result,
)
from app.agent_tools.code.list_code_files.errors import NoSuchCodeDirError
from app.agent_tools.code.list_code_files.fake import FakeListCodeFilesTool
from app.agent_tools.code.list_code_files.models import (
    DEFAULT_DEPTH,
    MAX_ENTRIES_PER_LISTING,
    CodeDirEntry,
    CodeDirInfo,
    EntryKind,
    ListCodeFilesQuery,
    ListCodeFilesResult,
    RequestedDepth,
    ReturnedDepth,
)
from app.agent_tools.code.list_code_files.tool import ListCodeFilesTool

__all__ = [
    "DEFAULT_DEPTH",
    "MAX_ENTRIES_PER_LISTING",
    "ROOT_DIR",
    "CodeDirEntry",
    "CodeDirInfo",
    "EntryKind",
    "FakeListCodeFilesTool",
    "ListCodeFilesQuery",
    "ListCodeFilesResult",
    "ListCodeFilesTool",
    "ListCodeFilesToolBase",
    "NoSuchCodeDirError",
    "RequestedDepth",
    "ReturnedDepth",
    "select_entries_and_build_result",
]
