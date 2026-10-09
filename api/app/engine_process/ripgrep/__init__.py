"""
Description:
Program ripgrep: szukanie tekstu w katalogu. Importuje się stąd
(`from app.engine_process.ripgrep import RipgrepClient`), nie z modułów.

| plik        | co zawiera                                                                   |
|-------------|------------------------------------------------------------------------------|
| `client.py` | `RipgrepClient`, argumenty programu i rozbiór jego wyjścia                   |
| `models.py` | `FoundLine` — znaleziona linia: ścieżka, numer i treść                       |

Do czego:
Na kliencie stoi narzędzie agenta `find_code_text`, które szuka w paczce kodu aplikacji. Klient
o paczce nie wie nic: dostaje katalog i oddaje linie. Program uruchamia wspólne `run_program()`
z pakietu wyżej, a błędy to wspólne `ProcessError` i `ProcessConfigError`.

Przykład szukania i wyniku — w opisie `client.py`.
"""

from app.engine_process.ripgrep.client import WHOLE_DIRECTORY, RipgrepClient
from app.engine_process.ripgrep.models import FoundLine

__all__ = [
    "WHOLE_DIRECTORY",
    "FoundLine",
    "RipgrepClient",
]
