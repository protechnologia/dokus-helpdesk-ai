"""
Description:
Programy, które `api` uruchamia jako osobny proces. Na górze pakietu leży to, co wspólne dla
każdego programu; każdy program ma własny podfolder z klientem i jego modelami.

| co          | co zawiera                                                                 |
|-------------|----------------------------------------------------------------------------|
| `base.py`   | `run_program()` — uruchomienie programu bez powłoki, z limitem czasu       |
| `models.py` | `ProgramOutput` — kod wyjścia i wyjście programu                           |
| `errors.py` | `ProcessError` i jego odmiana `ProcessConfigError`                         |
| `ripgrep/`  | `RipgrepClient` — szukanie tekstu w katalogu; stoi na nim `find_code_text` |

To, co wspólne, importuje się stąd (`from app.engine_process import ProcessError`), a klienta
programu z jego podfolderu (`from app.engine_process.ripgrep import RipgrepClient`).

Do czego:
Uruchomienie programu to przekroczenie granicy procesu, więc dostaje własny pakiet, jak rozmowa
z embedderem albo z modelem (CLAUDE.md -> „Warstwy kodu"). Kod spoza pakietu woła klienta
programu i dostaje nasze modele; procesy uruchamia tylko `base.py`.

Pakiet nazywa się od mechanizmu, nie od roli, inaczej niż `engine_llm` czy `engine_embedding`:
ma przyjąć każdy program uruchamiany procesem. Nowy program to nowy podfolder obok `ripgrep/`;
wspólne dla wszystkich jest uruchomienie (`base.py`) i błędy.

Fabryki tu nie ma: program jest jeden na zadanie, a jego nazwa to stała w pliku klienta.

Co wraca po awarii:

| co się stało                                   | wyjątek              | co robi trasa |
|------------------------------------------------|----------------------|---------------|
| programu nie ma albo nie ma katalogu roboczego | `ProcessConfigError` | 500           |
| program nie skończył w czasie albo oddał błąd  | `ProcessError`       | 503           |
"""

from app.engine_process.base import run_program
from app.engine_process.errors import ProcessConfigError, ProcessError
from app.engine_process.models import ProgramOutput

__all__ = [
    "ProcessConfigError",
    "ProcessError",
    "ProgramOutput",
    "run_program",
]
