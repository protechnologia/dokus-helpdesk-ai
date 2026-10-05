"""
Description:
Wspólne węzły grafów. Importuj stąd (`from app.agent_nodes import Node`).

Do czego:
Kontrakt węzła (`base.py`) i wpis logu, który dopisuje każdy węzeł (`LogEntry` w `models.py`).
Stanu tu nie ma — pola wspólne to `GraphState` w `app/agent_graphs/base.py`, a każdy graf ma własny
`state.py`. W katalogu każdego węzła: implementacja (`node.py`) i atrapa (`fake.py`), a gdy mają
część wspólną — także `base.py`. Węzeł używany przez jeden graf mieszka w katalogu tego grafu, nie
tutaj.

Węzły (CLAUDE.md -> „Plan"; `anonymize` i `agent` właściwe, `run_tools` i `respond` to atrapy —
właściwe w p. 10–11):

| węzeł       | co robi                                                                  |
|-------------|--------------------------------------------------------------------------|
| `anonymize` | wejście → `AnonymizedText`, fail-closed; bez atrapy węzła (p. 4)         |
| `agent`     | tura modelu z narzędziami: prompt grafu i rozmowa → tura w `messages`    |
| `run_tools` | wywołania z listy dozwolonych; tekst do `messages`, źródła do `sources`  |
| `respond`   | walidacja do modelu wyjścia, jeden retry, `requires_hits`                |
"""

from app.agent_nodes.base import Node
from app.agent_nodes.models import LogEntry

__all__ = [
    "LogEntry",
    "Node",
]
